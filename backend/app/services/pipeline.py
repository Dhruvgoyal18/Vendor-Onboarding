"""
Main pipeline orchestrator.
Runs the full vendor onboarding validation pipeline:
  intake → extract_fields → format_check (Layer 1) → extract_docs →
  cross_doc_check (Layer 3) → merge →
  check_completeness → check_consistency → check_credibility →
  decide → output
"""

import asyncio
import logging
import uuid
import os
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from sqlalchemy.orm import Session

from app.models import (
    Vendor, Document, ValidationResult, PipelineStageLog, EmailLog, AuditEvent,
    SubmissionStatus, PipelineStage, StageStatus
)
from app.schemas import SubmissionFormData
from app.services.extractor import extract_document
from app.services.validator import check_completeness, check_consistency, check_credibility
from app.services.india_validator import run_india_format_checks, run_india_cross_doc_checks
from app.services.external_api_service import run_external_verifications
from app.services.decision import (
    make_decision,
    generate_decision_summary,
    generate_pending_email,
    generate_rejection_email,
)
from app.services.email_service import (
    send_pending_email, send_rejection_email, send_approval_email, send_ocr_failure_email,
    _approval_email_body,
)
from app.config import get_settings
from app.services.storage_service import download_document

logger = logging.getLogger(__name__)
settings = get_settings()

PIPELINE_STAGES = [
    PipelineStage.intake,
    PipelineStage.extract_fields,
    PipelineStage.format_check,
    PipelineStage.external_verification,
    PipelineStage.extract_docs,
    PipelineStage.cross_doc_check,
    PipelineStage.merge,
    PipelineStage.check_completeness,
    PipelineStage.check_consistency,
    PipelineStage.check_credibility,
    PipelineStage.decide,
    PipelineStage.output,
    PipelineStage.done,
]


def _generate_run_id() -> str:
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    return f"vnd_{now.strftime('%Y%m%d')}_{suffix}"


def _update_stage(
    db: Session,
    vendor: Vendor,
    stage: PipelineStage,
    status: StageStatus,
    message: str = "",
    metadata: Dict = None,
):
    """Update a pipeline stage log and vendor current_stage."""
    stage_log = (
        db.query(PipelineStageLog)
        .filter(PipelineStageLog.vendor_id == vendor.id, PipelineStageLog.stage == stage)
        .first()
    )
    if not stage_log:
        stage_log = PipelineStageLog(vendor_id=vendor.id, stage=stage)
        db.add(stage_log)

    stage_log.status = status
    stage_log.message = message
    if metadata:
        stage_log.stage_metadata = metadata
    if status == StageStatus.running:
        stage_log.started_at = datetime.utcnow()
    elif status in (StageStatus.completed, StageStatus.failed, StageStatus.skipped):
        stage_log.completed_at = datetime.utcnow()

    vendor.current_stage = stage
    vendor.updated_at = datetime.utcnow()
    db.commit()


def _save_validation_results(
    db: Session,
    vendor: Vendor,
    category: str,
    results: List[Dict],
):
    """Persist validation check results to DB."""
    for r in results:
        vr = ValidationResult(
            vendor_id=vendor.id,
            category=category,
            check_name=r.get("check", "unknown"),
            status=r.get("status", "unknown"),
            detail=r.get("detail"),
            confidence=r.get("confidence"),
        )
        db.add(vr)
    db.commit()


async def run_pipeline(
    db: Session,
    vendor: Vendor,
    documents_data: Dict[str, tuple],  # {doc_type: (bytes, filename)}
):
    """
    Full async pipeline runner.
    documents_data: {"coi": (bytes, "coi.pdf"), "pan_gstin": (bytes, "pan.pdf"), "bank_letter": (bytes, "bank.pdf"), ...}
    """
    run_id = vendor.run_id
    country = (vendor.country or "").upper()
    pipeline_start = datetime.utcnow()
    logger.info(f"[{run_id}] Starting pipeline (country={country})")

    # Set SLA due date (48 hours from creation) and write audit event
    from datetime import timedelta
    if not vendor.sla_due_at:
        vendor.sla_due_at = (vendor.created_at or pipeline_start) + timedelta(hours=48)
    db.add(AuditEvent(
        vendor_id=vendor.id,
        event_type="pipeline_started",
        actor="system",
        actor_role="system",
        payload={"run_id": run_id, "country": country},
    ))
    db.commit()

    form_data = {
        "company_name": vendor.company_name,
        "registration_number": vendor.registration_number,
        "country": vendor.country,
        "incorporation_date": vendor.incorporation_date,
        "contact_name": vendor.contact_name,
        "contact_email": vendor.contact_email,
        "tax_id": vendor.tax_id,
        "tax_id_type": vendor.tax_id_type,
        "bank_account_name": vendor.bank_account_name,
        "account_number": vendor.account_number,
        "bank_name": vendor.bank_name,
        "bank_country": vendor.bank_country,
        # India-specific
        "cin_number": vendor.cin_number,
        "pan_number": vendor.pan_number,
        "gstin_number": vendor.gstin_number,
        "ifsc_code": vendor.ifsc_code,
        "account_type": vendor.account_type,
        "registered_state": vendor.registered_state,
    }

    format_check_results = []
    cross_doc_results = []

    try:
        # ── STAGE: intake ────────────────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.intake, StageStatus.running, "Receiving submission")
        await asyncio.sleep(0.5)

        # Duplicate detection — company name, PAN, GSTIN, account+IFSC
        dup_filters = [Vendor.company_name == vendor.company_name]
        if vendor.pan_number:
            dup_filters.append(Vendor.pan_number == vendor.pan_number)
        if vendor.gstin_number:
            dup_filters.append(Vendor.gstin_number == vendor.gstin_number)
        if vendor.account_number and vendor.ifsc_code:
            from sqlalchemy import and_
            dup_filters.append(
                and_(Vendor.account_number == vendor.account_number,
                     Vendor.ifsc_code == vendor.ifsc_code)
            )

        from sqlalchemy import or_
        existing = (
            db.query(Vendor)
            .filter(
                or_(*dup_filters),
                Vendor.id != vendor.id,
                Vendor.status.in_([SubmissionStatus.approved, SubmissionStatus.pending]),
            )
            .first()
        )
        if existing:
            vendor.is_duplicate = True
            vendor.duplicate_of_run_id = existing.run_id
            db.commit()

        _update_stage(db, vendor, PipelineStage.intake, StageStatus.completed,
                      "Submission received" + (" (duplicate detected)" if vendor.is_duplicate else ""))

        # ── STAGE: extract_fields ────────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.extract_fields, StageStatus.running, "Normalizing form data")
        await asyncio.sleep(0.3)
        _update_stage(db, vendor, PipelineStage.extract_fields, StageStatus.completed, "Form data normalized")

        # ── STAGE: format_check (Layer 1) ────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.format_check, StageStatus.running,
                      "Running deterministic format checks")

        if country == "IN":
            format_check_results = await asyncio.get_event_loop().run_in_executor(
                None, run_india_format_checks, form_data
            )
            _save_validation_results(db, vendor, "format_check", format_check_results)

            failed_format = [r for r in format_check_results if r.get("status") == "fail"]
            missing_format = [r for r in format_check_results if r.get("status") == "missing"]
            _update_stage(db, vendor, PipelineStage.format_check, StageStatus.completed,
                          f"India format checks: {len(format_check_results)} checks, "
                          f"{len(failed_format)} failed, {len(missing_format)} missing")
        else:
            _update_stage(db, vendor, PipelineStage.format_check, StageStatus.skipped,
                          f"Format checks skipped (country={country}, only India-specific rules implemented)")

        # ── STAGE: external_verification ────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.external_verification, StageStatus.running,
                      "Verifying with external registries (MCA21, GST portal, RBI IFSC)")

        external_check_results = []
        if country == "IN":
            ext_response = await asyncio.get_event_loop().run_in_executor(
                None, run_external_verifications, form_data
            )
            if not ext_response.get("skipped"):
                external_check_results = ext_response.get("checks", [])
                format_check_results = format_check_results + external_check_results
                _save_validation_results(db, vendor, "external_verification", external_check_results)

            ext_fails = [r for r in external_check_results if r.get("status") == "fail"]
            _update_stage(db, vendor, PipelineStage.external_verification, StageStatus.completed,
                          f"External checks: {len(external_check_results)} checks, {len(ext_fails)} failed"
                          if external_check_results else "External checks passed")
        else:
            _update_stage(db, vendor, PipelineStage.external_verification, StageStatus.skipped,
                          f"External verification skipped (country={country})")

        # ── STAGE: extract_docs ──────────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.extract_docs, StageStatus.running, "Extracting data from documents")

        extracted_docs = {}
        db_docs = db.query(Document).filter(Document.vendor_id == vendor.id).all()
        uploaded_doc_types = [doc.document_type for doc in db_docs]

        for doc in db_docs:
            doc_type = doc.document_type
            filename = doc.original_filename

            # Check if we already have successfully extracted JSON in the DB
            if doc.extracted_json and isinstance(doc.extracted_json, dict) and doc.extracted_json:
                logger.info(f"[{run_id}] Using existing extraction for: {doc_type}")
                extracted_docs[doc_type] = doc.extracted_json
                continue

            # Load file bytes — prefer Supabase Storage, fall back to local disk
            file_bytes = None
            if doc_type in documents_data:
                file_bytes, _ = documents_data[doc_type]
            elif doc.storage_key:
                file_bytes = await asyncio.get_event_loop().run_in_executor(
                    None, download_document, doc.storage_key
                )
                if file_bytes:
                    logger.info(f"[{run_id}] Loaded from Supabase Storage: {doc.storage_key}")
                else:
                    logger.warning(f"[{run_id}] Supabase Storage download failed for: {doc.storage_key}")
            if file_bytes is None and doc.file_path and os.path.exists(doc.file_path):
                try:
                    with open(doc.file_path, "rb") as f:
                        file_bytes = f.read()
                    logger.info(f"[{run_id}] Loaded document from local disk (fallback): {doc.file_path}")
                except Exception as e:
                    logger.error(f"[{run_id}] Failed to read local file ({doc.file_path}): {e}")

            if file_bytes is None:
                logger.warning(f"[{run_id}] No file bytes available for: {doc_type}")
                extracted_docs[doc_type] = {}
                continue

            logger.info(f"[{run_id}] Extracting: {doc_type} ({filename})")
            try:
                extracted = await asyncio.get_event_loop().run_in_executor(
                    None, extract_document, file_bytes, filename, doc_type, country
                )
                extracted_docs[doc_type] = extracted

                # Update document record
                doc.extracted_json = extracted
                doc.extraction_confidence = extracted.get("_extraction_confidence")
                doc.updated_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                logger.error(f"[{run_id}] Failed to extract {doc_type}: {e}")
                extracted_docs[doc_type] = {}

        _update_stage(db, vendor, PipelineStage.extract_docs, StageStatus.completed,
                      f"Extracted data from {len(extracted_docs)} documents")

        # ── OCR / Field-Weighted Quality Check ──────────────────────────────────────
        failed_docs = []
        for doc in db_docs:
            extracted = extracted_docs.get(doc.document_type, {})
            quality_score = extracted.get("_quality_score", None)
            low_conf_fields = extracted.get("_low_confidence_fields", [])
            doc_type_mismatch = extracted.get("_doc_type_mismatch", False)
            detected_type = extracted.get("_detected_type", "")

            # Filter out internal metadata keys for counting
            public = {k: v for k, v in extracted.items() if not k.startswith("_")}
            non_empty_fields = len([v for v in public.values() if v is not None and str(v).strip() != ""])

            if doc_type_mismatch:
                doc.ocr_status = "failed"
                doc.ocr_issues = [
                    f"Wrong document type: expected {doc.document_type.replace('_', ' ')} "
                    f"but this appears to be a '{detected_type}'. Please upload the correct document."
                ]
                failed_docs.append({"type": doc.document_type, "issues": doc.ocr_issues})
            elif not public or non_empty_fields == 0:
                doc.ocr_status = "failed"
                doc.ocr_issues = ["No text could be extracted — document may be unreadable, blurry, or password-protected"]
                failed_docs.append({"type": doc.document_type, "issues": doc.ocr_issues})
            elif quality_score is not None and quality_score < 0.5:
                # Critical fields missing even though some fields extracted
                doc.ocr_status = "partial"
                issues = ["Critical fields could not be extracted from this document"]
                if low_conf_fields:
                    issues.append(f"Low-confidence fields: {', '.join(low_conf_fields)} — document may be blurry or partially obscured")
                doc.ocr_issues = issues
                failed_docs.append({"type": doc.document_type, "issues": doc.ocr_issues})
            elif non_empty_fields < 2:
                doc.ocr_status = "partial"
                doc.ocr_issues = ["Only partial information could be extracted — document quality may be poor"]
                failed_docs.append({"type": doc.document_type, "issues": doc.ocr_issues})
            else:
                doc.ocr_status = "success"
                doc.ocr_issues = []
                if low_conf_fields:
                    doc.ocr_issues = [f"Low-confidence extraction on: {', '.join(low_conf_fields)}"]
            # Persist quality score
            if quality_score is not None:
                doc.quality_score = quality_score
            doc.updated_at = datetime.utcnow()
        db.commit()

        # Send OCR failure email if any docs failed
        if failed_docs and vendor.contact_email:
            logger.info(f"[{run_id}] Sending OCR failure email for {len(failed_docs)} documents")
            ocr_success = send_ocr_failure_email(vendor.contact_email, vendor.company_name, failed_docs)
            ocr_email_log = EmailLog(
                vendor_id=vendor.id,
                recipient=vendor.contact_email,
                subject=f"Action Required: Document Processing Issue — {vendor.company_name}",
                body=f"OCR failed for {len(failed_docs)} document(s): " + ", ".join(d['type'] for d in failed_docs),
                email_type="ocr_failure",
                success=ocr_success,
            )
            db.add(ocr_email_log)
            db.commit()

        # ── STAGE: cross_doc_check (Layer 3) ────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.cross_doc_check, StageStatus.running,
                      "Running cross-document consistency checks")

        if country == "IN" and extracted_docs:
            cross_doc_results = await asyncio.get_event_loop().run_in_executor(
                None, run_india_cross_doc_checks, form_data, extracted_docs
            )
            _save_validation_results(db, vendor, "cross_doc_check", cross_doc_results)

            cross_doc_fails = [r for r in cross_doc_results if r.get("status") == "fail"]
            _update_stage(db, vendor, PipelineStage.cross_doc_check, StageStatus.completed,
                          f"Cross-document checks: {len(cross_doc_results)} checks, {len(cross_doc_fails)} failed")
        else:
            _update_stage(db, vendor, PipelineStage.cross_doc_check, StageStatus.skipped,
                          "Cross-document checks skipped (no India docs or non-India country)")

        # ── STAGE: merge ─────────────────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.merge, StageStatus.running, "Merging vendor data")
        await asyncio.sleep(0.2)

        merged_data = {
            "form": form_data,
            "docs": extracted_docs,
            "format_checks": format_check_results,
            "cross_doc_checks": cross_doc_results,
            "provenance": {
                "form_fields": list(form_data.keys()),
                "extracted_docs": list(extracted_docs.keys()),
                "country": country,
            }
        }
        vendor.merged_data = merged_data
        db.commit()
        _update_stage(db, vendor, PipelineStage.merge, StageStatus.completed, "Vendor data merged")

        # ── STAGE: check_completeness ────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.check_completeness, StageStatus.running,
                      "Running completeness checks")

        completeness_results = await asyncio.get_event_loop().run_in_executor(
            None, check_completeness, form_data, uploaded_doc_types, country
        )
        _save_validation_results(db, vendor, "completeness", completeness_results)

        missing_critical = [
            r for r in completeness_results
            if r.get("status") == "missing" and r.get("check", "").startswith("doc_")
        ]
        _update_stage(db, vendor, PipelineStage.check_completeness, StageStatus.completed,
                      f"{len(completeness_results)} checks completed")

        # Short-circuit if critical docs missing
        if missing_critical:
            logger.info(f"[{run_id}] Short-circuiting: missing critical documents")
            decision = make_decision(
                completeness_results + format_check_results,
                [],
                {"risk_level": "low", "flags": []}
            )
            await _finalize(db, vendor, decision, completeness_results, [], {"risk_level": "low", "flags": []}, pipeline_start)
            return

        # ── STAGE: check_consistency ─────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.check_consistency, StageStatus.running,
                      "Analyzing data consistency")

        consistency_results = await asyncio.get_event_loop().run_in_executor(
            None, check_consistency, form_data, extracted_docs
        )
        _save_validation_results(db, vendor, "consistency", consistency_results)
        _update_stage(db, vendor, PipelineStage.check_consistency, StageStatus.completed,
                      f"{len(consistency_results)} consistency checks completed")

        # ── STAGE: check_credibility ─────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.check_credibility, StageStatus.running,
                      "Analyzing fraud signals")

        # Accumulate all deterministic check results for context
        prior_checks = completeness_results + format_check_results + cross_doc_results
        credibility_result = await asyncio.get_event_loop().run_in_executor(
            None, check_credibility, merged_data, prior_checks
        )
        vendor.risk_level = credibility_result.get("risk_level", "low")
        db.commit()

        flags = credibility_result.get("flags", [])
        cred_results = []
        for flag in flags:
            cred_results.append({
                "check": flag.get("signal", "fraud_flag"),
                "status": "fail" if flag.get("severity") in ("high", "medium") else "warning",
                "detail": flag.get("description", ""),
                "confidence": 0.8,
            })
        if not cred_results:
            cred_results = [{"check": "fraud_analysis", "status": "pass",
                             "detail": "No fraud signals detected", "confidence": 0.9}]
        _save_validation_results(db, vendor, "credibility", cred_results)
        _update_stage(db, vendor, PipelineStage.check_credibility, StageStatus.completed,
                      f"Risk level: {credibility_result.get('risk_level', 'unknown')}")

        # ── STAGE: decide ────────────────────────────────────────────────────────
        _update_stage(db, vendor, PipelineStage.decide, StageStatus.running, "Generating decision")

        # Combine all checks for decision making
        all_checks = completeness_results + format_check_results + cross_doc_results
        decision = make_decision(all_checks, consistency_results, credibility_result)
        _update_stage(db, vendor, PipelineStage.decide, StageStatus.completed,
                      f"Decision: {decision['status'].upper()}")

        # ── STAGE: output ────────────────────────────────────────────────────────
        await _finalize(db, vendor, decision, all_checks, consistency_results, credibility_result, pipeline_start)

    except Exception as e:
        logger.error(f"[{run_id}] Pipeline error: {e}", exc_info=True)
        vendor.status = SubmissionStatus.error
        vendor.updated_at = datetime.utcnow()
        db.commit()
        _update_stage(db, vendor, vendor.current_stage or PipelineStage.intake,
                      StageStatus.failed, f"Pipeline error: {str(e)}")


async def _finalize(
    db: Session,
    vendor: Vendor,
    decision: Dict,
    completeness_results: List[Dict],
    consistency_results: List[Dict],
    credibility_result: Dict,
    pipeline_start: datetime = None,
):
    """Finalize the pipeline: save decision, generate summary, send emails."""
    _update_stage(db, vendor, PipelineStage.output, StageStatus.running, "Generating output")

    # Generate decision summary
    summary = await asyncio.get_event_loop().run_in_executor(
        None,
        generate_decision_summary,
        decision,
        completeness_results,
        consistency_results,
        credibility_result,
        vendor.company_name,
    )

    vendor.status = SubmissionStatus(decision["status"])
    vendor.decision_summary = summary
    vendor.decided_at = datetime.utcnow()
    vendor.updated_at = datetime.utcnow()
    if pipeline_start:
        duration_ms = int((datetime.utcnow() - pipeline_start).total_seconds() * 1000)
        vendor.pipeline_duration_ms = duration_ms
    db.commit()

    # Email handling
    contact_email = vendor.contact_email
    vendor_name = vendor.company_name

    if decision["status"] == "pending" and contact_email:
        reasons = decision.get("reasons", {})
        issues = []
        if reasons.get("missing_documents"):
            issues.extend([f"Missing document: {d.replace('_', ' ')}" for d in reasons["missing_documents"]])
        if reasons.get("missing_fields"):
            issues.extend([f"Missing field: {f.replace('_', ' ')}" for f in reasons["missing_fields"]])
        if reasons.get("format_failures"):
            issues.extend([f"Invalid format: {f}" for f in reasons["format_failures"]])
        if reasons.get("consistency_failures"):
            issues.extend([f"Data inconsistency: {f}" for f in reasons["consistency_failures"]])
        if not issues:
            issues = [reasons.get("message", "Additional information required")]

        reason_codes = decision.get("reasons", {}).get("reason_codes", [])
        email_body = await asyncio.get_event_loop().run_in_executor(
            None, generate_pending_email, vendor_name, contact_email, issues,
            reason_codes, completeness_results, consistency_results
        )
        success = send_pending_email(contact_email, vendor_name, email_body)

        email_log = EmailLog(
            vendor_id=vendor.id,
            recipient=contact_email,
            subject=f"Action Required: Vendor Onboarding for {vendor_name}",
            body=email_body,
            email_type="pending_request",
            success=success,
        )
        db.add(email_log)
        db.commit()

    elif decision["status"] == "approved" and contact_email:
        success = send_approval_email(contact_email, vendor_name)
        email_log = EmailLog(
            vendor_id=vendor.id,
            recipient=contact_email,
            subject=f"Vendor Application Approved — {vendor_name}",
            body=_approval_email_body(vendor_name),
            email_type="approval",
            success=success,
        )
        db.add(email_log)
        db.commit()

    elif decision["status"] == "rejected" and contact_email:
        email_body = await asyncio.get_event_loop().run_in_executor(
            None, generate_rejection_email, vendor_name
        )
        success = send_rejection_email(contact_email, vendor_name, email_body)

        email_log = EmailLog(
            vendor_id=vendor.id,
            recipient=contact_email,
            subject=f"Vendor Application Update — {vendor_name}",
            body=email_body,
            email_type="rejection_neutral",
            success=success,
        )
        db.add(email_log)
        db.commit()

    _update_stage(db, vendor, PipelineStage.output, StageStatus.completed,
                  f"Output generated for status: {decision['status']}")
    _update_stage(db, vendor, PipelineStage.done, StageStatus.completed, "Pipeline complete")

    logger.info(f"[{vendor.run_id}] Pipeline complete: {decision['status'].upper()}")
