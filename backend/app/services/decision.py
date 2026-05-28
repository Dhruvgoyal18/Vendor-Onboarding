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

# ─── Reason Codes ────────────────────────────────────────────────────────────────
# Each entry: (human_readable_message, severity_score)
REASON_CODES: Dict[str, tuple[str, int]] = {
    "MISSING_COI":             ("Please upload your Certificate of Incorporation (COI).", 10),
    "MISSING_PAN_GSTIN":       ("Please upload your PAN Card and GSTIN Certificate.", 10),
    "MISSING_BANK_LETTER":     ("Please upload a bank account verification letter or cancelled cheque.", 10),
    "SAVINGS_ACCOUNT":         ("A Current Account is required for vendor payments. Savings accounts are not accepted.", 8),
    "GSTIN_PAN_MISMATCH":      ("The PAN number embedded in your GSTIN does not match your submitted PAN number.", 8),
    "GSTIN_STATE_MISMATCH":    ("The state code in your GSTIN does not match your registered state.", 8),
    "CIN_YEAR_MISMATCH":       ("The incorporation year encoded in your CIN does not match the incorporation date you provided.", 8),
    "PAN_ENTITY_INDIVIDUAL":   ("Your PAN indicates an Individual (personal PAN). Business vendors must submit a Company (C), Firm (F), or HUF (H) PAN.", 8),
    "PAN_CHECKSUM_INVALID":    ("Your PAN number failed checksum validation — it may contain a typo. Please verify against your physical PAN card.", 5),
    "BANK_NAME_MISMATCH":      ("The bank name does not match the bank indicated by your IFSC code.", 8),
    "ACCOUNT_NUMBER_INVALID":  ("Bank account number must be 9–18 digits containing only numbers.", 8),
    "COMPANY_NAME_COI_MISMATCH": ("The company name on your Certificate of Incorporation does not match the name you submitted.", 10),
    "COMPANY_NAME_PAN_MISMATCH": ("The company name on your PAN document does not match the name you submitted.", 8),
    "COMPANY_NAME_BANK_MISMATCH": ("The bank account holder name does not match your company name.", 8),
    "GSTIN_DATE_BEFORE_INCORPORATION": ("Your GST registration date is earlier than your incorporation date, which is not possible. Please verify your documents.", 10),
    "COI_VS_PAN_NAME_MISMATCH":  ("The company name on your COI does not match the name on your PAN document.", 10),
    "COI_VS_BANK_NAME_MISMATCH": ("The company name on your COI does not match the bank account holder name.", 10),
    "PAN_VS_BANK_NAME_MISMATCH": ("The entity name on your PAN document does not match the bank account holder name.", 8),
    "IFSC_FORMAT_INVALID":     ("Your IFSC code format is invalid.", 8),
    "OCR_FAILURE":             ("One or more documents could not be read. Please resubmit clearer, unencrypted documents scanned at 300 DPI or higher.", 8),
    "PARTIAL_EXTRACTION":      ("Some required information could not be extracted from your documents. Ensure key fields are clearly visible.", 5),
    "DOC_TYPE_MISMATCH":       ("One or more uploaded documents appears to be the wrong type. Please upload the correct document in each slot.", 10),
    "DATA_CONSISTENCY_ISSUES": ("Multiple data inconsistencies were found between your form data and submitted documents.", 8),
    "ACCOUNT_TYPE_MISSING":    ("Account type is required. Please specify 'Current Account'.", 8),
    "CIN_FORMAT_INVALID":      ("Your CIN (Corporate Identification Number) has an invalid format.", 8),
    "GSTIN_FORMAT_INVALID":    ("Your GSTIN has an invalid format.", 8),
    "MISSING_REQUIRED_FIELDS": ("One or more required fields are missing from your submission.", 5),
    "FOREIGN_BANK_ACCOUNT":    ("Your company is registered in India but the bank account appears to be in a foreign country. An Indian bank account is required.", 8),
}

# Severity score → rejection threshold
REJECTION_THRESHOLD = 25

# Maps check names from validation results to reason codes
CHECK_TO_REASON: Dict[str, str] = {
    "doc_coi":              "MISSING_COI",
    "doc_registration":     "MISSING_COI",
    "doc_pan_gstin":        "MISSING_PAN_GSTIN",
    "doc_tax_cert":         "MISSING_PAN_GSTIN",
    "doc_bank_letter":      "MISSING_BANK_LETTER",
    "account_type":         "SAVINGS_ACCOUNT",
    "gstin_pan_match":      "GSTIN_PAN_MISMATCH",
    "gstin_state_vs_registered_state": "GSTIN_STATE_MISMATCH",
    "cin_year_vs_incorporation_date":  "CIN_YEAR_MISMATCH",
    "pan_entity_type":      "PAN_ENTITY_INDIVIDUAL",
    "pan_checksum":         "PAN_CHECKSUM_INVALID",
    "ifsc_bank_name_match": "BANK_NAME_MISMATCH",
    "account_number_format": "ACCOUNT_NUMBER_INVALID",
    "company_name_vs_coi":  "COMPANY_NAME_COI_MISMATCH",
    "company_name_vs_pan_gstin_doc": "COMPANY_NAME_PAN_MISMATCH",
    "company_name_vs_bank_doc": "COMPANY_NAME_BANK_MISMATCH",
    "gstin_date_vs_incorporation_date": "GSTIN_DATE_BEFORE_INCORPORATION",
    "coi_vs_pan_doc_name":  "COI_VS_PAN_NAME_MISMATCH",
    "coi_vs_bank_name":     "COI_VS_BANK_NAME_MISMATCH",
    "pan_vs_bank_name":     "PAN_VS_BANK_NAME_MISMATCH",
    "ifsc_format":          "IFSC_FORMAT_INVALID",
    "cin_format":           "CIN_FORMAT_INVALID",
    "gstin_format":         "GSTIN_FORMAT_INVALID",
}


def _collect_reason_codes(
    all_checks: List[Dict],
    consistency_results: List[Dict],
) -> List[str]:
    """Map failed check names to reason codes. Returns deduplicated ordered list."""
    codes_seen: set[str] = set()
    codes: List[str] = []

    def add(code: str):
        if code and code not in codes_seen:
            codes_seen.add(code)
            codes.append(code)

    for r in all_checks + consistency_results:
        check = r.get("check", "")
        status = r.get("status", "")
        if status in ("fail", "missing"):
            mapped = CHECK_TO_REASON.get(check)
            if mapped:
                add(mapped)
            elif status == "missing" and check.startswith("field_"):
                add("MISSING_REQUIRED_FIELDS")
            elif status == "missing" and check.startswith("doc_"):
                add("MISSING_COI")  # generic fallback
    return codes


def _severity_score(
    missing_docs: List[Dict],
    format_failures: List[Dict],
    all_checks: List[Dict],
    consistency_results: List[Dict],
    risk_level: str,
    flags: List[Dict],
) -> int:
    """
    Compute an integer severity score.
    Threshold >= REJECTION_THRESHOLD → too many problems, reject instead of pending.
    """
    score = 0
    score += 10 * len(missing_docs)                          # missing critical docs
    score += 8  * len(format_failures)                       # hard format failures

    # Cross-doc and layer-1 failures (from all_checks but not doc/field level)
    structural_fails = [
        r for r in all_checks
        if r.get("status") in ("fail",) and not r.get("check", "").startswith("doc_")
        and not r.get("check", "").startswith("field_")
    ]
    score += 6 * len(structural_fails)

    consistency_failures = [r for r in consistency_results if r.get("status") == "mismatch"]
    consistency_warnings = [r for r in consistency_results if r.get("status") == "partial_match"]
    score += 8 * len(consistency_failures)
    score += 3 * len(consistency_warnings)

    high_flags  = [f for f in flags if f.get("severity") == "high"]
    medium_flags = [f for f in flags if f.get("severity") == "medium"]
    score += 15 * (1 if risk_level == "medium" else 0)
    score += 25 * len(high_flags)
    score += 8  * len(medium_flags)

    return score


def make_decision(
    completeness_results: List[Dict],
    consistency_results: List[Dict],
    credibility_result: Dict,
) -> Dict[str, Any]:
    """
    Deterministic decision engine with severity accumulation.
    """
    missing_docs = [
        r for r in completeness_results
        if r.get("status") == "missing" and r.get("check", "").startswith("doc_")
    ]
    missing_fields = [
        r for r in completeness_results
        if r.get("status") == "missing" and r.get("check", "").startswith("field_")
    ]
    format_failures = [
        r for r in completeness_results
        if r.get("status") == "fail" and not r.get("check", "").startswith("doc_")
    ]
    consistency_failures = [r for r in consistency_results if r.get("status") == "mismatch"]

    risk_level = credibility_result.get("risk_level", "low")
    flags = credibility_result.get("flags", [])
    high_severity_flags = [f for f in flags if f.get("severity") == "high"]

    # Hard rejection: high risk or any single high-severity fraud flag
    if risk_level == "high" or len(high_severity_flags) >= 1:
        return {
            "status": "rejected",
            "reasons": {
                "risk_level": risk_level,
                "high_severity_flags": high_severity_flags,
            },
            "severity_score": _severity_score(
                missing_docs, format_failures, completeness_results,
                consistency_results, risk_level, flags
            ),
        }

    # Compute severity score for everything else
    severity = _severity_score(
        missing_docs, format_failures, completeness_results,
        consistency_results, risk_level, flags
    )

    reason_codes = _collect_reason_codes(completeness_results, consistency_results)

    if severity >= REJECTION_THRESHOLD:
        return {
            "status": "rejected",
            "reasons": {
                "severity_score": severity,
                "reason_codes": reason_codes,
                "message": f"Too many validation failures (score {severity} ≥ {REJECTION_THRESHOLD})",
            },
            "severity_score": severity,
        }

    if missing_docs or missing_fields or format_failures or consistency_failures or severity > 0:
        all_reasons: Dict[str, Any] = {"reason_codes": reason_codes, "severity_score": severity}
        if missing_docs:
            all_reasons["missing_documents"] = [r["check"].replace("doc_", "") for r in missing_docs]
        if missing_fields:
            all_reasons["missing_fields"] = [r["check"].replace("field_", "") for r in missing_fields]
        if format_failures:
            all_reasons["format_failures"] = [r["check"] for r in format_failures]
        if consistency_failures:
            all_reasons["consistency_failures"] = [r.get("check") for r in consistency_failures]
        return {
            "status": "pending",
            "reasons": all_reasons,
            "severity_score": severity,
        }

    return {
        "status": "approved",
        "reasons": {"message": "All validation checks passed"},
        "severity_score": 0,
    }


def generate_decision_summary(
    decision: Dict,
    completeness_results: List[Dict],
    consistency_results: List[Dict],
    credibility_result: Dict,
    vendor_name: str,
) -> str:
    """Generate a human-readable decision summary using the LLM."""
    user_message = f"""
Vendor: {vendor_name}
Decision: {decision['status'].upper()}
Severity Score: {decision.get('severity_score', 'N/A')}
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


_CHECK_LABELS: Dict[str, str] = {
    "cin_format":                       "CIN format",
    "cin_year_vs_incorporation_date":   "CIN year vs incorporation date",
    "pan_format":                       "PAN format",
    "pan_checksum":                     "PAN checksum",
    "pan_entity_type":                  "PAN entity type",
    "gstin_format":                     "GSTIN format",
    "gstin_pan_match":                  "GSTIN ↔ PAN match",
    "gstin_state_code":                 "GSTIN state code",
    "gstin_state_vs_registered_state":  "GSTIN state vs registered state",
    "ifsc_format":                      "IFSC format",
    "ifsc_bank_name_match":             "IFSC ↔ bank name",
    "account_number_format":            "Account number format",
    "account_type":                     "Account type",
    "email_format":                     "Email format",
    "iban_format":                      "IBAN format",
    "tax_id_format":                    "Tax ID format",
    "account_name_match":               "Account name vs company name",
    "company_name_vs_coi":              "Company name vs COI",
    "company_name_vs_pan_gstin_doc":    "Company name vs PAN/GSTIN doc",
    "company_name_vs_bank_doc":         "Company name vs bank document",
    "coi_vs_pan_doc_name":              "COI name vs PAN document",
    "coi_vs_bank_name":                 "COI name vs bank account",
    "pan_vs_bank_name":                 "PAN name vs bank account",
    "cin_coi_vs_form":                  "CIN on COI vs submitted CIN",
    "pan_doc_vs_form":                  "PAN on document vs submitted PAN",
    "gstin_doc_vs_form":                "GSTIN on document vs submitted GSTIN",
    "gstin_embedded_pan_vs_pan_doc":    "PAN embedded in GSTIN vs PAN document",
    "gstin_date_vs_incorporation_date": "GST registration date vs incorporation date",
    "ifsc_doc_vs_form":                 "IFSC on bank document vs submitted IFSC",
    "micr_ifsc_consistency":            "MICR code sanity check",
    "account_type_doc_check":           "Account type on bank document",
}

_DOC_LABELS: Dict[str, str] = {
    "coi":        "Certificate of Incorporation (COI)",
    "registration": "Registration Certificate",
    "pan_gstin":  "PAN Card & GSTIN Certificate",
    "tax_cert":   "Tax Certificate",
    "bank_letter": "Bank Letter / Cancelled Cheque",
    "bank":       "Bank Letter / Cancelled Cheque",
}

_FIELD_LABELS: Dict[str, str] = {
    "company_name":      "Company Name",
    "registration_number": "Registration Number",
    "country":           "Country",
    "incorporation_date": "Incorporation Date",
    "contact_name":      "Contact Name",
    "contact_email":     "Contact Email",
    "cin_number":        "CIN Number",
    "pan_number":        "PAN Number",
    "gstin_number":      "GSTIN Number",
    "ifsc_code":         "IFSC Code",
    "account_type":      "Account Type",
    "registered_state":  "Registered State",
    "bank_account_name": "Bank Account Name",
    "account_number":    "Account Number",
    "bank_name":         "Bank Name",
    "bank_country":      "Bank Country",
}


def _section(title: str, lines: List[str]) -> str:
    bar = "─" * 56
    return f"{bar}\n{title}\n{bar}\n" + "\n".join(lines)


def render_pending_email(
    vendor_name: str,
    reason_codes: List[str],
    all_checks: Optional[List[Dict]] = None,
    consistency_results: Optional[List[Dict]] = None,
) -> str:
    """
    Build a structured pending email that shows the vendor exactly what
    failed, what passed, and numbered action items to fix.
    """
    checks = all_checks or []
    consistency = consistency_results or []

    # ── Bucket every check into one of five groups ──────────────────────────
    missing_docs:   List[Dict] = []
    missing_fields: List[Dict] = []
    format_fails:   List[Dict] = []
    cross_doc_fails: List[Dict] = []
    warnings:       List[Dict] = []
    passed:         List[Dict] = []

    for r in checks:
        status = r.get("status", "")
        check  = r.get("check", "")
        if status == "missing" and check.startswith("doc_"):
            missing_docs.append(r)
        elif status == "missing" and check.startswith("field_"):
            missing_fields.append(r)
        elif status == "fail":
            if r.get("layer") == 3 or any(
                check.startswith(p) for p in (
                    "company_name_vs_", "coi_vs_", "pan_vs_",
                    "cin_coi_", "pan_doc_", "gstin_doc_",
                    "gstin_embedded_", "gstin_date_", "ifsc_doc_",
                    "micr_", "account_type_doc",
                )
            ):
                cross_doc_fails.append(r)
            else:
                format_fails.append(r)
        elif status == "warning":
            warnings.append(r)
        elif status == "pass":
            passed.append(r)

    # Consistency results — mismatches and partial matches
    consistency_issues = [
        r for r in consistency
        if r.get("status") in ("mismatch", "partial_match")
    ]

    sections: List[str] = []

    # ── Missing documents ────────────────────────────────────────────────────
    if missing_docs:
        lines = []
        for r in missing_docs:
            doc_key = r.get("check", "").replace("doc_", "")
            label = _DOC_LABELS.get(doc_key, doc_key.replace("_", " ").title())
            lines.append(f"  ✗ {label}")
        sections.append(_section("MISSING DOCUMENTS", lines))

    # ── Missing form fields ──────────────────────────────────────────────────
    if missing_fields:
        lines = []
        for r in missing_fields:
            field_key = r.get("check", "").replace("field_", "")
            label = _FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())
            lines.append(f"  ✗ {label}")
        sections.append(_section("MISSING REQUIRED FIELDS", lines))

    # ── Format / compliance failures ─────────────────────────────────────────
    if format_fails:
        lines = []
        for r in format_fails:
            check = r.get("check", "")
            label = _CHECK_LABELS.get(check, check.replace("_", " ").title())
            detail = r.get("detail", "")
            lines.append(f"  ✗ {label}")
            if detail:
                lines.append(f"    → {detail}")
        sections.append(_section("FORMAT & COMPLIANCE ISSUES", lines))

    # ── Cross-document failures ──────────────────────────────────────────────
    if cross_doc_fails:
        lines = []
        for r in cross_doc_fails:
            check = r.get("check", "")
            label = _CHECK_LABELS.get(check, check.replace("_", " ").title())
            detail = r.get("detail", "")
            lines.append(f"  ✗ {label}")
            if detail:
                lines.append(f"    → {detail}")
        sections.append(_section("CROSS-DOCUMENT INCONSISTENCIES", lines))

    # ── LLM consistency failures ─────────────────────────────────────────────
    if consistency_issues:
        lines = []
        for r in consistency_issues:
            check  = r.get("check", "").replace("_", " ").title()
            detail = r.get("detail", "")
            form_v = r.get("form_value")
            doc_v  = r.get("document_value")
            line = f"  ✗ {check}"
            if form_v and doc_v:
                line += f" (submitted: '{form_v}' / document: '{doc_v}')"
            lines.append(line)
            if detail:
                lines.append(f"    → {detail}")
        sections.append(_section("DATA INCONSISTENCIES (Form vs Documents)", lines))

    # ── Warnings ─────────────────────────────────────────────────────────────
    if warnings:
        lines = []
        for r in warnings:
            check = r.get("check", "")
            label = _CHECK_LABELS.get(check, check.replace("_", " ").title())
            detail = r.get("detail", "")
            lines.append(f"  ⚠ {label}")
            if detail:
                lines.append(f"    → {detail}")
        sections.append(_section("WARNINGS (review recommended)", lines))

    # ── What passed ──────────────────────────────────────────────────────────
    total   = len(checks) + len(consistency)
    n_pass  = len(passed) + len([r for r in consistency if r.get("status") in ("match",)])
    n_fail  = total - n_pass
    if passed:
        pass_lines = [f"  {n_pass} of {total} checks passed" if total else ""]
        key_pass = [
            r for r in passed
            if r.get("check", "") in _CHECK_LABELS
        ][:6]
        for r in key_pass:
            label = _CHECK_LABELS.get(r.get("check", ""), "")
            if label:
                pass_lines.append(f"  ✓ {label}")
        sections.append(_section("WHAT PASSED", pass_lines))

    # ── Required action items ─────────────────────────────────────────────────
    action_items = []
    for i, code in enumerate(reason_codes, 1):
        msg, _ = REASON_CODES.get(code, (f"Please address issue: {code}", 5))
        action_items.append(f"  {i}. {msg}")

    if not action_items:
        action_items = ["  1. Please review your submission and ensure all required information is complete."]

    sections.append(_section("REQUIRED ACTIONS", action_items))

    issues_block = "\n\n".join(sections)

    return f"""Dear {vendor_name},

Thank you for submitting your vendor onboarding application.

After our automated review, your application requires the following corrections before we can proceed:

{issues_block}

─────────────────────────────────────────────────────────
HOW TO RESUBMIT
─────────────────────────────────────────────────────────
Visit the vendor portal and click "Resubmit Application" on your status page.
Your previous details will be pre-filled — correct the issues above and resubmit.

If you have questions, please contact our procurement team.

Best regards,
Vendor Onboarding Team"""


def generate_pending_email(
    vendor_name: str,
    contact_email: str,
    issues: List[str],
    reason_codes: Optional[List[str]] = None,
    all_checks: Optional[List[Dict]] = None,
    consistency_results: Optional[List[Dict]] = None,
) -> str:
    """
    Generate pending email with full check breakdown.
    Uses deterministic renderer when reason_codes are available (preferred path).
    Falls back to LLM only when no structured data exists.
    """
    if reason_codes or all_checks:
        return render_pending_email(vendor_name, reason_codes or [], all_checks, consistency_results)

    # LLM fallback — no structured data available
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
        return render_pending_email(vendor_name, [], None, None)


def generate_rejection_email(vendor_name: str) -> str:
    """Generate a neutral rejection email using the LLM."""
    user_message = f"Vendor: {vendor_name}\n\nWrite the decline email body now."

    try:
        return call_llm(REJECTION_EMAIL_PROMPT, user_message, max_tokens=300)
    except Exception as e:
        logger.error(f"Failed to generate rejection email: {e}")
        return (
            f"Dear {vendor_name},\n\nThank you for your interest in becoming a vendor. "
            "After careful review, we are unable to proceed with your application at this time.\n\n"
            "We appreciate your interest and wish you the best.\n\nBest regards,\nProcurement Team"
        )
