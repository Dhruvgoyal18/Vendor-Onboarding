import json
import logging
from typing import List, Dict, Any, Optional
from app.services.llm_service import call_llm
from app.prompts.templates import (
    DECISION_SUMMARY_PROMPT,
    PENDING_EMAIL_PROMPT,
    REJECTION_EMAIL_PROMPT,
)

logger = logging.getLogger(__name__)


def make_decision(
    completeness_results: List[Dict],
    consistency_results: List[Dict],
    credibility_result: Dict,
) -> Dict[str, Any]:
    """
    Deterministic decision engine.
    AI performs analysis; this function makes the final decision.
    """
    # --- Check for missing critical documents ---
    missing_docs = [
        r for r in completeness_results
        if r.get("status") == "missing" and r.get("check", "").startswith("doc_")
    ]

    missing_fields = [
        r for r in completeness_results
        if r.get("status") == "missing" and r.get("check", "").startswith("field_")
    ]

    failed_fields = [
        r for r in completeness_results
        if r.get("status") in ("fail",) and not r.get("check", "").startswith("doc_")
    ]

    consistency_failures = [
        r for r in consistency_results
        if r.get("status") in ("mismatch",)
    ]

    consistency_warnings = [
        r for r in consistency_results
        if r.get("status") in ("partial_match",)
    ]

    risk_level = credibility_result.get("risk_level", "low")
    flags = credibility_result.get("flags", [])
    high_severity_flags = [f for f in flags if f.get("severity") == "high"]
    medium_severity_flags = [f for f in flags if f.get("severity") == "medium"]

    # --- Decision Logic ---
    # REJECTED: High fraud risk or multiple high severity flags
    if risk_level == "high" or len(high_severity_flags) >= 2:
        return {
            "status": "rejected",
            "reasons": {
                "risk_level": risk_level,
                "high_severity_flags": high_severity_flags,
            }
        }

    # PENDING: Missing docs (short-circuit - avoid unnecessary AI calls)
    if missing_docs:
        return {
            "status": "pending",
            "reasons": {
                "missing_documents": [r["check"].replace("doc_", "") for r in missing_docs],
                "message": "Required documents are missing"
            }
        }

    # PENDING: Missing required fields
    if missing_fields:
        return {
            "status": "pending",
            "reasons": {
                "missing_fields": [r["check"].replace("field_", "") for r in missing_fields],
                "message": "Required fields are missing"
            }
        }

    # PENDING: Failed format checks
    if failed_fields:
        return {
            "status": "pending",
            "reasons": {
                "format_failures": [r["check"] for r in failed_fields],
                "message": "Some fields have invalid formats"
            }
        }

    # PENDING: Consistency mismatches
    if consistency_failures:
        return {
            "status": "pending",
            "reasons": {
                "consistency_failures": [r.get("check") for r in consistency_failures],
                "message": "Data inconsistencies found between form and documents"
            }
        }

    # PENDING: Medium fraud risk with flags
    if risk_level == "medium" and len(medium_severity_flags) >= 2:
        return {
            "status": "pending",
            "reasons": {
                "risk_level": risk_level,
                "flags": medium_severity_flags,
                "message": "Multiple risk flags require review"
            }
        }

    # APPROVED: All checks pass
    return {
        "status": "approved",
        "reasons": {
            "message": "All validation checks passed"
        }
    }


def generate_decision_summary(
    decision: Dict,
    completeness_results: List[Dict],
    consistency_results: List[Dict],
    credibility_result: Dict,
    vendor_name: str,
) -> str:
    """Generate a human-readable decision summary using Claude."""
    user_message = f"""
Vendor: {vendor_name}
Decision: {decision['status'].upper()}
Reasons: {json.dumps(decision.get('reasons', {}), indent=2)}

Completeness Check Results:
{json.dumps(completeness_results, indent=2)}

Consistency Check Results:
{json.dumps(consistency_results, indent=2)}

Credibility/Risk Assessment:
{json.dumps(credibility_result, indent=2)}

Write the decision summary now."""

    try:
        return call_llm(DECISION_SUMMARY_PROMPT, user_message, max_tokens=500)
    except Exception as e:
        logger.error(f"Failed to generate decision summary: {e}")
        return f"Decision: {decision['status'].upper()}. Automated summary unavailable."


def generate_pending_email(
    vendor_name: str,
    contact_email: str,
    issues: List[str],
) -> str:
    """Generate a pending/clarification request email using Claude."""
    user_message = f"""
Vendor: {vendor_name}
Contact Email: {contact_email}
Issues requiring action:
{chr(10).join(f'- {issue}' for issue in issues)}

Write the email body now."""

    try:
        return call_llm(PENDING_EMAIL_PROMPT, user_message, max_tokens=400)
    except Exception as e:
        logger.error(f"Failed to generate pending email: {e}")
        return f"Dear {vendor_name},\n\nThank you for your vendor onboarding submission. We require additional information to complete your review. Please resubmit with the following:\n\n{chr(10).join(issues)}\n\nBest regards,\nProcurement Team"


def generate_rejection_email(vendor_name: str) -> str:
    """Generate a neutral rejection email using Claude."""
    user_message = f"Vendor: {vendor_name}\n\nWrite the decline email body now."

    try:
        return call_llm(REJECTION_EMAIL_PROMPT, user_message, max_tokens=300)
    except Exception as e:
        logger.error(f"Failed to generate rejection email: {e}")
        return f"Dear {vendor_name},\n\nThank you for your interest in becoming a vendor. After careful review, we are unable to proceed with your application at this time.\n\nWe appreciate your interest and wish you the best.\n\nBest regards,\nProcurement Team"
