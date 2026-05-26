import re
import logging
import json
from typing import List, Dict, Any, Optional
from app.services.llm_service import call_llm_json
from app.prompts.templates import CONSISTENCY_CHECK_PROMPT, CREDIBILITY_CHECK_PROMPT

logger = logging.getLogger(__name__)

# ─── Tax ID Regex Patterns ──────────────────────────────────────────────────────
TAX_ID_PATTERNS = {
    "GB": {
        "type": "VAT",
        "pattern": r"^GB[0-9]{9}$",
        "description": "UK VAT number (GB + 9 digits)"
    },
    "US": {
        "type": "EIN",
        "pattern": r"^\d{2}-?\d{7}$",
        "description": "US EIN (XX-XXXXXXX)"
    },
    "IN": {
        "type": "GSTIN",
        "pattern": r"^[0-9A-Z]{15}$",
        "description": "Indian GSTIN (15 alphanumeric characters)"
    },
    "AU": {
        "type": "ABN",
        "pattern": r"^\d{11}$",
        "description": "Australian ABN (11 digits)"
    },
    "DE": {
        "type": "VAT",
        "pattern": r"^DE[0-9]{9}$",
        "description": "German VAT number"
    },
    "FR": {
        "type": "VAT",
        "pattern": r"^FR[A-Z0-9]{2}[0-9]{9}$",
        "description": "French VAT number"
    },
}

REQUIRED_FIELDS = [
    "company_name",
    "registration_number",
    "country",
    "incorporation_date",
    "contact_name",
    "contact_email",
    "bank_account_name",
    "account_number",
    "bank_name",
    "bank_country",
]

INDIA_REQUIRED_FIELDS = [
    "company_name",
    "country",
    "incorporation_date",
    "contact_name",
    "contact_email",
    "cin_number",
    "pan_number",
    "gstin_number",
    "ifsc_code",
    "account_type",
    "registered_state",
    "bank_account_name",
    "account_number",
    "bank_name",
    "bank_country",
]

REQUIRED_DOCS = ["registration", "bank_letter", "tax_cert"]
INDIA_REQUIRED_DOCS = ["coi", "pan_gstin", "bank_letter"]
# Aliases: accept either naming convention
INDIA_DOC_ALIASES = {
    "coi": ["coi", "registration"],
    "pan_gstin": ["pan_gstin", "tax_cert"],
    "bank_letter": ["bank_letter", "bank"],
}


def check_completeness(
    form_data: Dict[str, Any],
    uploaded_docs: List[str],
    country: str = ""
) -> List[Dict[str, Any]]:
    """
    Rule-based completeness validation.
    Routes to India-specific or generic checks based on country.
    Returns list of check results.
    """
    country_upper = (country or form_data.get("country", "") or "").upper()

    if country_upper == "IN":
        return _check_completeness_india(form_data, uploaded_docs)
    else:
        return _check_completeness_generic(form_data, uploaded_docs)


def _check_completeness_india(
    form_data: Dict[str, Any],
    uploaded_docs: List[str]
) -> List[Dict[str, Any]]:
    """India-specific completeness checks."""
    results = []

    for field in INDIA_REQUIRED_FIELDS:
        value = form_data.get(field)
        if not value or str(value).strip() == "":
            results.append({
                "check": f"field_{field}",
                "status": "missing",
                "detail": f"Required field '{field.replace('_', ' ')}' is missing",
                "confidence": 1.0,
            })
        else:
            results.append({
                "check": f"field_{field}",
                "status": "pass",
                "detail": f"Field '{field.replace('_', ' ')}' is present",
                "confidence": 1.0,
            })

    # Email format check
    email = form_data.get("contact_email", "")
    email_pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if email and not re.match(email_pattern, email):
        results.append({"check": "email_format", "status": "fail",
                        "detail": f"Email '{email}' is not a valid format", "confidence": 1.0})
    elif email:
        results.append({"check": "email_format", "status": "pass",
                        "detail": "Email format is valid", "confidence": 1.0})

    # Document completeness — accept either naming convention
    for doc_label, aliases in INDIA_DOC_ALIASES.items():
        found = any(alias in uploaded_docs for alias in aliases)
        human_label = {"coi": "Certificate of Incorporation",
                       "pan_gstin": "PAN Card & GSTIN Certificate",
                       "bank_letter": "Bank Letter / Cancelled Cheque"}[doc_label]
        if found:
            results.append({
                "check": f"doc_{doc_label}",
                "status": "pass",
                "detail": f"Required document '{human_label}' was uploaded",
                "confidence": 1.0,
            })
        else:
            results.append({
                "check": f"doc_{doc_label}",
                "status": "missing",
                "detail": f"Required document '{human_label}' is missing. Please upload it.",
                "confidence": 1.0,
            })

    return results


def _check_completeness_generic(
    form_data: Dict[str, Any],
    uploaded_docs: List[str]
) -> List[Dict[str, Any]]:
    """Generic completeness checks for non-India countries."""
    results = []

    for field in REQUIRED_FIELDS:
        value = form_data.get(field)
        if not value or str(value).strip() == "":
            results.append({
                "check": f"field_{field}",
                "status": "missing",
                "detail": f"Required field '{field.replace('_', ' ')}' is missing",
                "confidence": 1.0,
            })
        else:
            results.append({
                "check": f"field_{field}",
                "status": "pass",
                "detail": f"Field '{field.replace('_', ' ')}' is present",
                "confidence": 1.0,
            })

    # Email format validation
    email = form_data.get("contact_email", "")
    email_pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if email and not re.match(email_pattern, email):
        results.append({
            "check": "email_format",
            "status": "fail",
            "detail": f"Email '{email}' is not a valid format",
            "confidence": 1.0,
        })
    elif email:
        results.append({
            "check": "email_format",
            "status": "pass",
            "detail": "Email format is valid",
            "confidence": 1.0,
        })

    # Tax ID format validation
    country = form_data.get("country", "").upper()
    tax_id = form_data.get("tax_id", "").strip().upper().replace(" ", "").replace("-", "")
    if country in TAX_ID_PATTERNS and tax_id:
        pattern_info = TAX_ID_PATTERNS[country]
        # Normalize EIN for comparison
        normalized_tax_id = tax_id.replace("-", "")
        normalized_pattern = pattern_info["pattern"].replace("-?", "")
        if re.match(pattern_info["pattern"], tax_id) or re.match(normalized_pattern, normalized_tax_id):
            results.append({
                "check": "tax_id_format",
                "status": "pass",
                "detail": f"Tax ID matches expected {pattern_info['type']} format for {country}",
                "confidence": 1.0,
            })
        else:
            results.append({
                "check": "tax_id_format",
                "status": "fail",
                "detail": f"Tax ID does not match expected format for {country}: {pattern_info['description']}",
                "confidence": 1.0,
            })
    elif tax_id:
        results.append({
            "check": "tax_id_format",
            "status": "pass",
            "detail": "Tax ID present (no format validation for this country)",
            "confidence": 0.5,
        })

    # IBAN validation using schwifty
    account_number = form_data.get("account_number", "").strip().replace(" ", "")
    if account_number and account_number.upper()[:2].isalpha():
        try:
            from schwifty import IBAN
            iban = IBAN(account_number)
            results.append({
                "check": "iban_format",
                "status": "pass",
                "detail": f"IBAN is valid: {iban.formatted}",
                "confidence": 1.0,
            })
        except Exception as e:
            results.append({
                "check": "iban_format",
                "status": "fail",
                "detail": f"IBAN validation failed: {str(e)}",
                "confidence": 1.0,
            })

    # Document completeness
    for doc_type in REQUIRED_DOCS:
        if doc_type in uploaded_docs:
            results.append({
                "check": f"doc_{doc_type}",
                "status": "pass",
                "detail": f"Required document '{doc_type.replace('_', ' ')}' was uploaded",
                "confidence": 1.0,
            })
        else:
            results.append({
                "check": f"doc_{doc_type}",
                "status": "missing",
                "detail": f"Required document '{doc_type.replace('_', ' ')}' is missing",
                "confidence": 1.0,
            })

    # Account name vs company name match check
    company_name = form_data.get("company_name", "").upper().strip()
    bank_account_name = form_data.get("bank_account_name", "").upper().strip()
    if company_name and bank_account_name:
        # Simple normalization for comparison
        cn_clean = re.sub(r"\b(LTD|LIMITED|INC|LLC|CORP|CO)\b", "", company_name).strip()
        ban_clean = re.sub(r"\b(LTD|LIMITED|INC|LLC|CORP|CO)\b", "", bank_account_name).strip()
        if cn_clean == ban_clean or company_name == bank_account_name:
            results.append({
                "check": "account_name_match",
                "status": "pass",
                "detail": "Bank account name matches company name",
                "confidence": 0.95,
            })
        elif cn_clean in ban_clean or ban_clean in cn_clean:
            results.append({
                "check": "account_name_match",
                "status": "warning",
                "detail": f"Bank account name partially matches company name: '{bank_account_name}' vs '{company_name}'",
                "confidence": 0.7,
            })
        else:
            results.append({
                "check": "account_name_match",
                "status": "fail",
                "detail": f"Bank account name does not match company name: '{bank_account_name}' vs '{company_name}'",
                "confidence": 0.9,
            })

    return results


def check_consistency(form_data: Dict[str, Any], extracted_docs: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """
    LLM-powered semantic consistency check between form data and extracted documents.
    Includes incorporation date, address/state, and email domain checks.
    """
    if not extracted_docs:
        return [{
            "check": "consistency_check",
            "status": "skipped",
            "detail": "No extracted document data available for comparison",
            "confidence": 0.0,
        }]

    # Strip internal metadata fields from docs before sending to LLM
    clean_docs = {
        k: {fk: fv for fk, fv in v.items() if not fk.startswith("_")}
        for k, v in extracted_docs.items()
        if isinstance(v, dict)
    }

    user_message = f"""Compare these vendor data objects for consistency:

FORM DATA (submitted by vendor):
{json.dumps(form_data, indent=2)}

EXTRACTED DOCUMENT DATA:
{json.dumps(clean_docs, indent=2)}

Compare these fields if data is available from both sources:
1. Company/entity name (form: company_name vs documents: entity_name)
2. Registration number / CIN
3. Tax ID / GSTIN / PAN
4. Bank account name (form: bank_account_name vs bank doc: account_name/account_holder_name)
5. Country / registered state
6. Incorporation date (form: incorporation_date vs COI: incorporation_date)
7. Address/state consistency (if any document shows an address, does the state match form registered_state?)
8. Email domain plausibility (form: contact_email domain vs company name)

Return a JSON array of comparison results."""

    try:
        result = call_llm_json(CONSISTENCY_CHECK_PROMPT, user_message)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        return []
    except Exception as e:
        logger.error(f"Consistency check failed: {e}")
        return [{
            "check": "consistency_check",
            "status": "error",
            "detail": f"Consistency analysis failed: {str(e)}",
            "confidence": 0.0,
        }]


def check_credibility(vendor_data: Dict[str, Any], all_checks: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    LLM fraud/risk signal analysis. Receives pipeline_checks from previous stages
    so it can factor in how many deterministic checks already failed.
    """
    # Summarise previous check failures for the LLM context
    check_summary: Dict[str, Any] = {}
    if all_checks:
        fails = [r for r in all_checks if r.get("status") in ("fail", "missing")]
        warnings = [r for r in all_checks if r.get("status") == "warning"]
        check_summary = {
            "total_checks": len(all_checks),
            "failed_checks": len(fails),
            "warning_checks": len(warnings),
            "failed_check_names": [r.get("check") for r in fails[:10]],  # top 10
        }

    # Strip internal metadata from vendor_data docs
    clean_vendor = {}
    for k, v in vendor_data.items():
        if k == "docs" and isinstance(v, dict):
            clean_vendor[k] = {
                dk: {fk: fv for fk, fv in dv.items() if not fk.startswith("_")}
                for dk, dv in v.items()
                if isinstance(dv, dict)
            }
        else:
            clean_vendor[k] = v

    user_message = f"""Analyze this vendor submission for fraud signals and risk:

VENDOR DATA:
{json.dumps(clean_vendor, indent=2)}

PIPELINE CHECK SUMMARY (from earlier deterministic stages):
{json.dumps(check_summary, indent=2)}

Provide a comprehensive risk assessment."""

    try:
        result = call_llm_json(CREDIBILITY_CHECK_PROMPT, user_message)
        if isinstance(result, dict):
            return result
        return {"risk_level": "low", "flags": [], "reasoning": "Unable to parse risk assessment"}
    except Exception as e:
        logger.error(f"Credibility check failed: {e}")
        return {
            "risk_level": "low",
            "flags": [],
            "reasoning": f"Credibility analysis failed: {str(e)}"
        }
