import asyncio
import json
import logging
import uuid
import os
from datetime import datetime
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_vendor, require_admin
from app.database import get_db
from sqlalchemy import or_
from app.models import (
    Vendor, Document, PipelineStageLog, EmailLog, AuditEvent,
    SubmissionStatus, PipelineStage, StageStatus
)
from app.schemas import (
    SubmissionFormData, VendorDetailOut, SubmissionResponse,
    EmailLogOut, VendorVersionOut, OverrideRequest, AuditEventOut
)
from app.services.email_service import send_approval_email, send_rejection_email
from app.services.pipeline import run_pipeline, _generate_run_id, PIPELINE_STAGES
from app.services.storage_service import upload_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def _validate_file(file: UploadFile) -> bytes:
    """Validate and read uploaded file."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Invalid file type: {file.content_type}. Allowed: PDF, JPG, PNG")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large: {len(content)} bytes. Max: {MAX_FILE_SIZE} bytes")
    return content


@router.post("", response_model=SubmissionResponse)
async def create_submission(
    background_tasks: BackgroundTasks,
    data: str = Form(...),
    registration_doc: Optional[UploadFile] = File(None),
    bank_doc: Optional[UploadFile] = File(None),
    tax_doc: Optional[UploadFile] = File(None),
    pan_gstin_doc: Optional[UploadFile] = File(None),  # India: PAN + GSTIN doc
    db: Session = Depends(get_db),
):
    """
    Create a new vendor submission and kick off the validation pipeline.
    """
    # Parse and validate form data
    try:
        form_dict = json.loads(data)
        form_data = SubmissionFormData(**form_dict)
    except Exception as e:
        raise HTTPException(400, f"Invalid form data: {str(e)}")

    # Read uploaded documents
    documents_data = {}
    doc_records = {}

    # Generate run_id early so we can name files with it
    run_id = _generate_run_id()

    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
    os.makedirs(uploads_dir, exist_ok=True)

    if registration_doc and registration_doc.filename:
        file_bytes = await _validate_file(registration_doc)
        doc_key = "coi" if form_data.country == "IN" else "registration"
        documents_data[doc_key] = (file_bytes, registration_doc.filename)
        storage_key = upload_document(run_id, doc_key, registration_doc.filename, file_bytes)
        file_path = os.path.join(uploads_dir, f"{run_id}_{doc_key}_{registration_doc.filename}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        doc_records[doc_key] = (registration_doc.filename, file_path, storage_key)

    if bank_doc and bank_doc.filename:
        file_bytes = await _validate_file(bank_doc)
        documents_data["bank_letter"] = (file_bytes, bank_doc.filename)
        storage_key = upload_document(run_id, "bank_letter", bank_doc.filename, file_bytes)
        file_path = os.path.join(uploads_dir, f"{run_id}_bank_letter_{bank_doc.filename}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        doc_records["bank_letter"] = (bank_doc.filename, file_path, storage_key)

    if tax_doc and tax_doc.filename:
        file_bytes = await _validate_file(tax_doc)
        doc_key = "pan_gstin" if form_data.country == "IN" else "tax_cert"
        documents_data[doc_key] = (file_bytes, tax_doc.filename)
        storage_key = upload_document(run_id, doc_key, tax_doc.filename, file_bytes)
        file_path = os.path.join(uploads_dir, f"{run_id}_{doc_key}_{tax_doc.filename}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        doc_records[doc_key] = (tax_doc.filename, file_path, storage_key)

    if pan_gstin_doc and pan_gstin_doc.filename:
        file_bytes = await _validate_file(pan_gstin_doc)
        documents_data["pan_gstin"] = (file_bytes, pan_gstin_doc.filename)
        storage_key = upload_document(run_id, "pan_gstin", pan_gstin_doc.filename, file_bytes)
        file_path = os.path.join(uploads_dir, f"{run_id}_pan_gstin_{pan_gstin_doc.filename}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        doc_records["pan_gstin"] = (pan_gstin_doc.filename, file_path, storage_key)

    # Create vendor record
    vendor = Vendor(
        run_id=run_id,
        company_name=form_data.company_name,
        registration_number=form_data.registration_number,
        country=form_data.country,
        incorporation_date=form_data.incorporation_date,
        contact_name=form_data.contact_name,
        contact_email=form_data.contact_email,
        tax_id=form_data.tax_id,
        tax_id_type=form_data.tax_id_type,
        bank_account_name=form_data.bank_account_name,
        account_number=form_data.account_number,
        bank_name=form_data.bank_name,
        bank_country=form_data.bank_country,
        # India-specific fields
        cin_number=form_data.cin_number,
        pan_number=form_data.pan_number,
        gstin_number=form_data.gstin_number,
        ifsc_code=form_data.ifsc_code,
        account_type=form_data.account_type,
        registered_state=form_data.registered_state,
        status=SubmissionStatus.processing,
        current_stage=PipelineStage.intake,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    # Create document records
    for doc_type, (filename, file_path, storage_key) in doc_records.items():
        doc = Document(
            vendor_id=vendor.id,
            document_type=doc_type,
            original_filename=filename,
            file_path=file_path,
            storage_key=storage_key,
        )
        db.add(doc)

    # Initialize pipeline stage logs
    for stage in PIPELINE_STAGES:
        stage_log = PipelineStageLog(
            vendor_id=vendor.id,
            stage=stage,
            status=StageStatus.pending,
        )
        db.add(stage_log)

    db.commit()

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline_sync, vendor.id, documents_data
    )

    return SubmissionResponse(
        run_id=run_id,
        message="Submission received. Pipeline is running."
    )


def _run_pipeline_sync(vendor_id: uuid.UUID, documents_data: dict):
    """Wrapper to run async pipeline in background task. Uses a fresh DB session."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            return
        asyncio.run(run_pipeline(db, vendor, documents_data))
    finally:
        db.close()


@router.post("/{run_id}/retry")
def retry_submission(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Re-trigger the pipeline for a stuck or errored submission.
    Resets all stage logs to pending and re-runs the pipeline.
    Documents are not re-uploaded — extraction uses already-stored extracted_json.
    """
    from app.models import Document
    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    if vendor.status == SubmissionStatus.processing:
        raise HTTPException(409, "Submission is already processing")

    # Reset vendor status
    vendor.status = SubmissionStatus.processing
    vendor.current_stage = PipelineStage.intake
    vendor.updated_at = datetime.utcnow()

    # Reset all stage logs to pending
    from app.models import PipelineStageLog
    for stage_log in vendor.pipeline_stages:
        stage_log.status = StageStatus.pending
        stage_log.message = None
        stage_log.started_at = None
        stage_log.completed_at = None

    db.commit()

    # Re-trigger pipeline (no document bytes — pipeline will use already-extracted JSON or files on disk)
    background_tasks.add_task(_run_pipeline_sync, vendor.id, {})

    return {"run_id": run_id, "message": "Pipeline re-triggered successfully"}


@router.get("/mine")
def get_my_submissions(
    db: Session = Depends(get_db),
    vendor_payload: dict = Depends(require_vendor),
):
    """Get all submissions for the authenticated vendor's email."""
    email = vendor_payload["sub"]
    vendors = (
        db.query(Vendor)
        .filter(Vendor.contact_email == email)
        .order_by(Vendor.created_at.desc())
        .all()
    )
    return [
        {
            "run_id": v.run_id,
            "company_name": v.company_name,
            "country": v.country,
            "status": v.status,
            "risk_level": v.risk_level,
            "created_at": v.created_at,
            "decided_at": v.decided_at,
            "version_number": v.version_number,
        }
        for v in vendors
    ]


@router.post("/{run_id}/override", tags=["admin"])
def override_submission(
    run_id: str,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    admin_payload: dict = Depends(require_admin),
):
    """
    Admin override: force-set a submission to approved or rejected.
    Writes an audit event, flips vendor status, and sends the appropriate email.
    """
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")
    if not body.reason or not body.reason.strip():
        raise HTTPException(400, "reason is required")

    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")
    if vendor.status == SubmissionStatus.processing:
        raise HTTPException(409, "Cannot override a submission that is still processing")

    prev_status = vendor.status
    vendor.status = SubmissionStatus(body.decision)
    vendor.override_by = admin_payload["sub"]
    vendor.override_at = datetime.utcnow()
    vendor.override_reason = body.reason.strip()
    vendor.decided_at = datetime.utcnow()
    vendor.updated_at = datetime.utcnow()

    db.add(AuditEvent(
        vendor_id=vendor.id,
        event_type="override",
        actor=admin_payload["sub"],
        actor_role="admin",
        payload={
            "prev_status": str(prev_status),
            "new_status": body.decision,
            "reason": body.reason.strip(),
        },
    ))
    db.commit()

    # Send email
    if body.decision == "approved" and vendor.contact_email:
        success = send_approval_email(vendor.contact_email, vendor.company_name)
        db.add(EmailLog(
            vendor_id=vendor.id,
            recipient=vendor.contact_email,
            subject=f"Vendor Application Approved — {vendor.company_name}",
            body=f"Override approved by {admin_payload['sub']}. Reason: {body.reason}",
            email_type="approval",
            success=success,
        ))
        db.commit()
    elif body.decision == "rejected" and vendor.contact_email:
        from app.services.decision import generate_rejection_email
        email_body = generate_rejection_email(vendor.company_name)
        success = send_rejection_email(vendor.contact_email, vendor.company_name, email_body)
        db.add(EmailLog(
            vendor_id=vendor.id,
            recipient=vendor.contact_email,
            subject=f"Vendor Application Update — {vendor.company_name}",
            body=email_body,
            email_type="rejection_neutral",
            success=success,
        ))
        db.commit()

    return {
        "run_id": run_id,
        "status": body.decision,
        "override_by": admin_payload["sub"],
        "override_at": vendor.override_at.isoformat(),
    }


@router.get("/{run_id}", response_model=VendorDetailOut)
def get_submission(run_id: str, db: Session = Depends(get_db)):
    """Get full submission details by run_id."""
    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    return VendorDetailOut(
        id=str(vendor.id),
        run_id=vendor.run_id,
        company_name=vendor.company_name,
        registration_number=vendor.registration_number,
        country=vendor.country,
        contact_name=vendor.contact_name,
        contact_email=vendor.contact_email,
        tax_id=vendor.tax_id,
        bank_account_name=vendor.bank_account_name,
        bank_country=vendor.bank_country,
        status=vendor.status,
        current_stage=vendor.current_stage if vendor.current_stage else None,
        decision_summary=vendor.decision_summary,
        risk_level=vendor.risk_level,
        is_duplicate=vendor.is_duplicate,
        duplicate_of_run_id=vendor.duplicate_of_run_id,
        version_number=vendor.version_number or 1,
        original_run_id=vendor.original_run_id,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
        decided_at=vendor.decided_at,
        # Detail-only fields
        incorporation_date=vendor.incorporation_date,
        tax_id_type=vendor.tax_id_type,
        bank_name=vendor.bank_name,
        cin_number=vendor.cin_number,
        pan_number=vendor.pan_number,
        gstin_number=vendor.gstin_number,
        ifsc_code=vendor.ifsc_code,
        account_type=vendor.account_type,
        registered_state=vendor.registered_state,
        sla_due_at=vendor.sla_due_at,
        override_by=vendor.override_by,
        override_at=vendor.override_at,
        override_reason=vendor.override_reason,
        pipeline_duration_ms=vendor.pipeline_duration_ms,
        merged_data=vendor.merged_data,
        documents=[
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "storage_key": d.storage_key,
                "original_filename": d.original_filename,
                "extracted_json": d.extracted_json,
                "extraction_confidence": d.extraction_confidence,
                "ocr_status": d.ocr_status or "unknown",
                "ocr_issues": d.ocr_issues or [],
                "created_at": d.created_at,
            }
            for d in vendor.documents
        ],
        validation_results=[
            {
                "id": str(vr.id),
                "category": vr.category,
                "check_name": vr.check_name,
                "status": vr.status,
                "detail": vr.detail,
                "confidence": vr.confidence,
            }
            for vr in vendor.validation_results
        ],
        pipeline_stages=[
            {
                "stage": ps.stage,
                "status": ps.status,
                "message": ps.message,
                "started_at": ps.started_at,
                "completed_at": ps.completed_at,
            }
            for ps in sorted(vendor.pipeline_stages, key=lambda x: PIPELINE_STAGES.index(x.stage))
        ],
        email_logs=[
            {
                "id": str(el.id),
                "recipient": el.recipient,
                "subject": el.subject,
                "body": el.body,
                "email_type": el.email_type,
                "sent_at": el.sent_at,
                "success": el.success,
            }
            for el in sorted(vendor.email_logs, key=lambda x: x.sent_at)
        ],
        audit_events=[
            {
                "id": str(ae.id),
                "event_type": ae.event_type,
                "actor": ae.actor,
                "actor_role": ae.actor_role,
                "payload": ae.payload,
                "created_at": ae.created_at,
            }
            for ae in sorted(vendor.audit_events, key=lambda x: x.created_at)
        ],
    )


@router.get("/{run_id}/versions", response_model=list[VendorVersionOut])
def get_versions(run_id: str, db: Session = Depends(get_db)):
    """Get all versions of a vendor submission (same original_run_id)."""
    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    original = vendor.original_run_id or vendor.run_id
    versions = (
        db.query(Vendor)
        .filter(
            or_(
                Vendor.original_run_id == original,
                Vendor.run_id == original,
            )
        )
        .order_by(Vendor.version_number)
        .all()
    )
    return versions


@router.post("/{run_id}/resubmit", response_model=SubmissionResponse)
async def resubmit_vendor(
    run_id: str,
    background_tasks: BackgroundTasks,
    data: str = Form(...),
    registration_doc: Optional[UploadFile] = File(None),
    bank_doc: Optional[UploadFile] = File(None),
    tax_doc: Optional[UploadFile] = File(None),
    pan_gstin_doc: Optional[UploadFile] = File(None),
    resubmission_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Create a new version of an existing vendor submission.
    Computes improvements vs the previous version.
    """
    old_vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not old_vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    try:
        form_dict = json.loads(data)
        form_data = SubmissionFormData(**form_dict)
    except Exception as e:
        raise HTTPException(400, f"Invalid form data: {str(e)}")

    new_run_id = _generate_run_id()
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
    os.makedirs(uploads_dir, exist_ok=True)

    documents_data: dict = {}
    doc_records: dict = {}

    if registration_doc and registration_doc.filename:
        file_bytes = await _validate_file(registration_doc)
        doc_key = "coi" if form_data.country == "IN" else "registration"
        documents_data[doc_key] = (file_bytes, registration_doc.filename)
        storage_key = upload_document(new_run_id, doc_key, registration_doc.filename, file_bytes)
        fp = os.path.join(uploads_dir, f"{new_run_id}_{doc_key}_{registration_doc.filename}")
        with open(fp, "wb") as f:
            f.write(file_bytes)
        doc_records[doc_key] = (registration_doc.filename, fp, storage_key)

    if bank_doc and bank_doc.filename:
        file_bytes = await _validate_file(bank_doc)
        documents_data["bank_letter"] = (file_bytes, bank_doc.filename)
        storage_key = upload_document(new_run_id, "bank_letter", bank_doc.filename, file_bytes)
        fp = os.path.join(uploads_dir, f"{new_run_id}_bank_letter_{bank_doc.filename}")
        with open(fp, "wb") as f:
            f.write(file_bytes)
        doc_records["bank_letter"] = (bank_doc.filename, fp, storage_key)

    if tax_doc and tax_doc.filename:
        file_bytes = await _validate_file(tax_doc)
        doc_key = "pan_gstin" if form_data.country == "IN" else "tax_cert"
        documents_data[doc_key] = (file_bytes, tax_doc.filename)
        storage_key = upload_document(new_run_id, doc_key, tax_doc.filename, file_bytes)
        fp = os.path.join(uploads_dir, f"{new_run_id}_{doc_key}_{tax_doc.filename}")
        with open(fp, "wb") as f:
            f.write(file_bytes)
        doc_records[doc_key] = (tax_doc.filename, fp, storage_key)

    if pan_gstin_doc and pan_gstin_doc.filename:
        file_bytes = await _validate_file(pan_gstin_doc)
        documents_data["pan_gstin"] = (file_bytes, pan_gstin_doc.filename)
        storage_key = upload_document(new_run_id, "pan_gstin", pan_gstin_doc.filename, file_bytes)
        fp = os.path.join(uploads_dir, f"{new_run_id}_pan_gstin_{pan_gstin_doc.filename}")
        with open(fp, "wb") as f:
            f.write(file_bytes)
        doc_records["pan_gstin"] = (pan_gstin_doc.filename, fp, storage_key)

    original_run_id = old_vendor.original_run_id or old_vendor.run_id
    new_version = (old_vendor.version_number or 1) + 1

    new_vendor = Vendor(
        run_id=new_run_id,
        company_name=form_data.company_name,
        registration_number=form_data.registration_number,
        country=form_data.country,
        incorporation_date=form_data.incorporation_date,
        contact_name=form_data.contact_name,
        contact_email=form_data.contact_email,
        tax_id=form_data.tax_id,
        tax_id_type=form_data.tax_id_type,
        bank_account_name=form_data.bank_account_name,
        account_number=form_data.account_number,
        bank_name=form_data.bank_name,
        bank_country=form_data.bank_country,
        cin_number=form_data.cin_number,
        pan_number=form_data.pan_number,
        gstin_number=form_data.gstin_number,
        ifsc_code=form_data.ifsc_code,
        account_type=form_data.account_type,
        registered_state=form_data.registered_state,
        status=SubmissionStatus.processing,
        current_stage=PipelineStage.intake,
        version_number=new_version,
        original_run_id=original_run_id,
        resubmission_notes=resubmission_notes,
    )
    db.add(new_vendor)
    db.commit()
    db.refresh(new_vendor)

    for doc_type, (filename, file_path, storage_key) in doc_records.items():
        doc = Document(
            vendor_id=new_vendor.id,
            document_type=doc_type,
            original_filename=filename,
            file_path=file_path,
            storage_key=storage_key,
        )
        db.add(doc)

    for stage in PIPELINE_STAGES:
        stage_log = PipelineStageLog(
            vendor_id=new_vendor.id,
            stage=stage,
            status=StageStatus.pending,
        )
        db.add(stage_log)

    db.commit()

    background_tasks.add_task(_run_pipeline_sync, new_vendor.id, documents_data)

    return SubmissionResponse(
        run_id=new_run_id,
        message=f"Resubmission (v{new_version}) received. Pipeline is running."
    )


@router.get("/{run_id}/stages")
def get_stages(run_id: str, db: Session = Depends(get_db)):
    """Get pipeline stages for polling-based updates."""
    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    stages = (
        db.query(PipelineStageLog)
        .filter(PipelineStageLog.vendor_id == vendor.id)
        .all()
    )
    return {
        "run_id": run_id,
        "status": vendor.status,
        "current_stage": vendor.current_stage if vendor.current_stage else None,
        "stages": [
            {
                "stage": s.stage,
                "status": s.status,
                "message": s.message,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in sorted(stages, key=lambda x: PIPELINE_STAGES.index(x.stage))
        ]
    }


@router.get("/{run_id}/events")
async def sse_events(run_id: str, db: Session = Depends(get_db)):
    """Server-Sent Events stream for real-time pipeline updates."""
    vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
    if not vendor:
        raise HTTPException(404, f"Submission '{run_id}' not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        TERMINAL = {"approved", "rejected", "pending", "error"}
        max_polls = 180  # 3 minutes timeout

        def _build_event(current_vendor, stages) -> str:
            return json.dumps({
                "run_id": run_id,
                "status": current_vendor.status,
                "current_stage": current_vendor.current_stage,
                "stages": [
                    {
                        "stage": s.stage,
                        "status": s.status,
                        "message": s.message,
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    }
                    for s in sorted(stages, key=lambda x: PIPELINE_STAGES.index(x.stage))
                ],
                "decision_summary": current_vendor.decision_summary,
                "risk_level": current_vendor.risk_level,
            })

        # Send initial state immediately — no 1-second wait
        db.expire(vendor)
        current_vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
        if not current_vendor:
            return
        stages = (
            db.query(PipelineStageLog)
            .filter(PipelineStageLog.vendor_id == current_vendor.id)
            .all()
        )
        yield f"data: {_build_event(current_vendor, stages)}\n\n"
        if current_vendor.status in TERMINAL:
            return

        last_stage_data = {s.stage: {"status": s.status, "message": s.message} for s in stages}
        last_status = current_vendor.status

        for _ in range(max_polls):
            await asyncio.sleep(1)

            db.expire(current_vendor)
            current_vendor = db.query(Vendor).filter(Vendor.run_id == run_id).first()
            if not current_vendor:
                break

            stages = (
                db.query(PipelineStageLog)
                .filter(PipelineStageLog.vendor_id == current_vendor.id)
                .all()
            )
            stage_data = {s.stage: {"status": s.status, "message": s.message} for s in stages}
            current_status = current_vendor.status

            if stage_data != last_stage_data or current_status != last_status:
                last_stage_data = stage_data
                last_status = current_status
                yield f"data: {_build_event(current_vendor, stages)}\n\n"

            if current_status in TERMINAL:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
