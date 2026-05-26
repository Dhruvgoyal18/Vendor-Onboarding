"""
India-specific vendor validation.

Layer 1: Deterministic format checks (regex, code logic — no LLM)
Layer 3: Cross-document consistency checks (deterministic + LLM for name matching)
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ─── India State Codes (GSTIN prefix) ──────────────────────────────────────────
INDIA_STATE_CODES: Dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh (new)",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# ─── IFSC Bank Code Map ─────────────────────────────────────────────────────────
IFSC_BANK_CODES: Dict[str, str] = {
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "SBIN": "State Bank of India",
    "KKBK": "Kotak Mahindra Bank",
    "UTIB": "Axis Bank",
    "PUNB": "Punjab National Bank",
    "CNRB": "Canara Bank",
    "UBIN": "Union Bank of India",
    "BARB": "Bank of Baroda",
    "IOBA": "Indian Overseas Bank",
    "BKID": "Bank of India",
    "INDB": "IndusInd Bank",
    "YESB": "Yes Bank",
    "IDFC": "IDFC First Bank",
    "AUBL": "AU Small Finance Bank",
    "FDRL": "Federal Bank",
    "SIBL": "South Indian Bank",
    "LAVB": "Lakshmi Vilas Bank",
    "CSBK": "CSB Bank",
    "DCBL": "DCB Bank",
}

# ─── Regex Patterns ─────────────────────────────────────────────────────────────
CIN_PATTERN = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

# PAN 4th character entity type mapping
PAN_ENTITY_TYPES = {
    "P": "Individual",
    "C": "Company",
    "H": "Hindu Undivided Family (HUF)",
    "F": "Firm / LLP",
    "A": "Association of Persons (AOP)",
    "B": "Body of Individuals (BOI)",
    "T": "Trust / AOP (Trust)",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
}

COMPANY_ENTITY_TYPES = {"C", "F", "H"}  # Valid for a business vendor


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Uppercase and strip whitespace for comparisons."""
    return s.upper().strip().replace(" ", "")


def _extract_pan_from_gstin(gstin: str) -> str:
    """Extract embedded PAN (chars 3–12, 0-indexed 2–11) from GSTIN."""
    return gstin[2:12].upper() if len(gstin) >= 12 else ""


def _extract_state_code_from_gstin(gstin: str) -> str:
    """Extract 2-digit state code from GSTIN."""
    return gstin[:2] if len(gstin) >= 2 else ""


def _names_match(name1: str, name2: str) -> bool:
    """Fuzzy match company names: ignore suffixes like Ltd / Limited / Pvt / Private."""
    STRIP_SUFFIXES = r"\b(LIMITED|LTD|PRIVATE|PVT|INCORPORATED|INC|COMPANY|CO|CORPORATION|CORP|LLP|SOLUTIONS|SERVICES|TECHNOLOGIES|TECH)\b"
    n1 = re.sub(STRIP_SUFFIXES, "", name1.upper()).strip()
    n2 = re.sub(STRIP_SUFFIXES, "", name2.upper()).strip()
    return n1 == n2 or n1 in n2 or n2 in n1


# ─── Layer 1: Deterministic Format Checks ──────────────────────────────────────

def run_india_format_checks(form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Layer 1 — Run all India-specific deterministic format checks on form data.
    Returns a list of check result dicts.
    """
    results = []

    cin = _normalize(form_data.get("cin_number", "") or "")
    pan = _normalize(form_data.get("pan_number", "") or "")
    gstin = _normalize(form_data.get("gstin_number", "") or "")
    ifsc = _normalize(form_data.get("ifsc_code", "") or "")
    account_type = (form_data.get("account_type", "") or "").strip().lower()
    registered_state = (form_data.get("registered_state", "") or "").strip()

    # ── CIN ──────────────────────────────────────────────────────────────────────
    if cin:
        if CIN_PATTERN.match(cin):
            results.append({
                "check": "cin_format",
                "status": "pass",
                "detail": f"CIN '{cin}' matches the required format [L/U][NIC5][State2][Year4][Company3][Num6]",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "cin_format",
                "status": "fail",
                "detail": f"CIN '{cin}' does not match expected format. Expected: [L/U][5-digit NIC][2-letter state][4-digit year][PLC/OPC/etc][6-digit number]. Example: L85110KA1981PLC013115",
                "confidence": 1.0,
                "layer": 1,
            })
    else:
        results.append({
            "check": "cin_format",
            "status": "missing",
            "detail": "CIN (Corporate Identification Number) is required for Indian companies",
            "confidence": 1.0,
            "layer": 1,
        })

    # ── PAN ──────────────────────────────────────────────────────────────────────
    if pan:
        if not PAN_PATTERN.match(pan):
            results.append({
                "check": "pan_format",
                "status": "fail",
                "detail": f"PAN '{pan}' does not match expected format [5 letters][4 digits][1 letter]. Example: AAACI1681G",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "pan_format",
                "status": "pass",
                "detail": f"PAN '{pan}' matches the required format",
                "confidence": 1.0,
                "layer": 1,
            })
            # Check 4th character for entity type
            pan_4th = pan[3]
            entity_type_name = PAN_ENTITY_TYPES.get(pan_4th, "Unknown")
            if pan_4th in COMPANY_ENTITY_TYPES:
                results.append({
                    "check": "pan_entity_type",
                    "status": "pass",
                    "detail": f"PAN 4th character '{pan_4th}' indicates entity type: {entity_type_name} — valid for a business vendor",
                    "confidence": 1.0,
                    "layer": 1,
                })
            elif pan_4th == "P":
                results.append({
                    "check": "pan_entity_type",
                    "status": "fail",
                    "detail": "PAN 4th character 'P' indicates an Individual PAN. Company vendors must submit a Company (C), Firm (F), or HUF (H) PAN — not a personal one. This is a HIGH-RISK flag.",
                    "confidence": 1.0,
                    "layer": 1,
                })
            else:
                results.append({
                    "check": "pan_entity_type",
                    "status": "warning",
                    "detail": f"PAN 4th character '{pan_4th}' indicates entity type: {entity_type_name}. Verify this is correct for this vendor.",
                    "confidence": 0.8,
                    "layer": 1,
                })
    else:
        results.append({
            "check": "pan_format",
            "status": "missing",
            "detail": "PAN (Permanent Account Number) is required for Indian companies",
            "confidence": 1.0,
            "layer": 1,
        })

    # ── GSTIN ─────────────────────────────────────────────────────────────────────
    if gstin:
        if not GSTIN_PATTERN.match(gstin):
            results.append({
                "check": "gstin_format",
                "status": "fail",
                "detail": f"GSTIN '{gstin}' does not match expected 15-character format [2-digit state][PAN][1-digit entity][Z][1 checksum]. Example: 29AAACI1681G1ZK",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "gstin_format",
                "status": "pass",
                "detail": f"GSTIN '{gstin}' matches the required format",
                "confidence": 1.0,
                "layer": 1,
            })

            # GSTIN ↔ PAN cross-check (entirely deterministic — no LLM)
            if pan:
                embedded_pan = _extract_pan_from_gstin(gstin)
                if embedded_pan == pan:
                    results.append({
                        "check": "gstin_pan_match",
                        "status": "pass",
                        "detail": f"PAN embedded in GSTIN ('{embedded_pan}') matches the provided PAN card number",
                        "confidence": 1.0,
                        "layer": 1,
                    })
                else:
                    results.append({
                        "check": "gstin_pan_match",
                        "status": "fail",
                        "detail": f"PAN embedded in GSTIN ('{embedded_pan}') does NOT match the provided PAN ('{pan}'). This is a critical mismatch indicating the GSTIN may belong to a different entity.",
                        "confidence": 1.0,
                        "layer": 1,
                    })

            # GSTIN state code vs registered state
            state_code = _extract_state_code_from_gstin(gstin)
            state_name = INDIA_STATE_CODES.get(state_code)
            if state_name:
                results.append({
                    "check": "gstin_state_code",
                    "status": "pass",
                    "detail": f"GSTIN state code '{state_code}' corresponds to '{state_name}'",
                    "confidence": 1.0,
                    "layer": 1,
                })
                # Compare with the registered state from form
                if registered_state:
                    registered_norm = registered_state.upper().strip()
                    state_norm = state_name.upper().strip()
                    if registered_norm in state_norm or state_norm in registered_norm:
                        results.append({
                            "check": "gstin_state_vs_registered_state",
                            "status": "pass",
                            "detail": f"GSTIN state code '{state_code}' ({state_name}) is consistent with the registered state '{registered_state}'",
                            "confidence": 1.0,
                            "layer": 1,
                        })
                    else:
                        results.append({
                            "check": "gstin_state_vs_registered_state",
                            "status": "fail",
                            "detail": f"GSTIN state code '{state_code}' implies '{state_name}' but registered state is '{registered_state}'. These must match for head-office GST registration.",
                            "confidence": 1.0,
                            "layer": 1,
                        })
            else:
                results.append({
                    "check": "gstin_state_code",
                    "status": "warning",
                    "detail": f"Unrecognized GSTIN state code '{state_code}'",
                    "confidence": 0.7,
                    "layer": 1,
                })
    else:
        results.append({
            "check": "gstin_format",
            "status": "missing",
            "detail": "GSTIN (Goods and Services Tax Identification Number) is required for Indian companies",
            "confidence": 1.0,
            "layer": 1,
        })

    # ── IFSC ─────────────────────────────────────────────────────────────────────
    if ifsc:
        if not IFSC_PATTERN.match(ifsc):
            results.append({
                "check": "ifsc_format",
                "status": "fail",
                "detail": f"IFSC '{ifsc}' does not match expected format [4-letter bank code][0][6-digit branch]. Example: HDFC0000007",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "ifsc_format",
                "status": "pass",
                "detail": f"IFSC '{ifsc}' matches the required format",
                "confidence": 1.0,
                "layer": 1,
            })
            # IFSC prefix ↔ bank name cross-check
            bank_prefix = ifsc[:4]
            known_bank = IFSC_BANK_CODES.get(bank_prefix)
            stated_bank = _normalize(form_data.get("bank_name", "") or "")
            if known_bank:
                known_bank_norm = _normalize(known_bank)
                if known_bank_norm in stated_bank or stated_bank in known_bank_norm:
                    results.append({
                        "check": "ifsc_bank_name_match",
                        "status": "pass",
                        "detail": f"IFSC prefix '{bank_prefix}' corresponds to '{known_bank}', which matches the stated bank name",
                        "confidence": 1.0,
                        "layer": 1,
                    })
                else:
                    results.append({
                        "check": "ifsc_bank_name_match",
                        "status": "fail",
                        "detail": f"IFSC prefix '{bank_prefix}' corresponds to '{known_bank}', but stated bank name is '{form_data.get('bank_name', '')}'. These must match.",
                        "confidence": 1.0,
                        "layer": 1,
                    })
            else:
                results.append({
                    "check": "ifsc_bank_name_match",
                    "status": "warning",
                    "detail": f"IFSC prefix '{bank_prefix}' is not in our known bank code list — manual verification required",
                    "confidence": 0.5,
                    "layer": 1,
                })
    else:
        results.append({
            "check": "ifsc_format",
            "status": "missing",
            "detail": "IFSC code is required for Indian bank accounts",
            "confidence": 1.0,
            "layer": 1,
        })

    # ── Account Type ─────────────────────────────────────────────────────────────
    if account_type:
        if "current" in account_type:
            results.append({
                "check": "account_type",
                "status": "pass",
                "detail": "Account type is 'Current Account' — required for business transactions in India",
                "confidence": 1.0,
                "layer": 1,
            })
        elif "savings" in account_type:
            results.append({
                "check": "account_type",
                "status": "fail",
                "detail": "Account type is 'Savings Account'. Indian regulations require businesses to use a Current Account for commercial transactions above certain thresholds. This is a red flag.",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "account_type",
                "status": "warning",
                "detail": f"Account type '{account_type}' is unrecognized. Expected 'Current Account' for a business.",
                "confidence": 0.6,
                "layer": 1,
            })
    else:
        results.append({
            "check": "account_type",
            "status": "missing",
            "detail": "Account type is required. Must be 'Current Account' for business vendors.",
            "confidence": 1.0,
            "layer": 1,
        })

    return results


# ─── Layer 3: Cross-Document Consistency Checks ─────────────────────────────────

def run_india_cross_doc_checks(
    form_data: Dict[str, Any],
    extracted_docs: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Layer 3 — Deterministic cross-document consistency checks for India.
    Compares extracted fields across COI, PAN+GSTIN, and Bank documents.
    """
    results = []

    coi = extracted_docs.get("coi") or extracted_docs.get("registration") or {}
    pan_gstin = extracted_docs.get("pan_gstin") or extracted_docs.get("tax_cert") or {}
    bank = extracted_docs.get("bank_letter") or extracted_docs.get("bank") or {}

    pan_form = _normalize(form_data.get("pan_number", "") or "")
    gstin_form = _normalize(form_data.get("gstin_number", "") or "")
    cin_form = _normalize(form_data.get("cin_number", "") or "")
    company_name_form = form_data.get("company_name", "") or ""

    # ── Company Name across COI, PAN, GSTIN, Bank ───────────────────────────────
    name_sources = {
        "COI": coi.get("entity_name") or coi.get("company_name"),
        "PAN/GSTIN doc": pan_gstin.get("entity_name") or pan_gstin.get("company_name"),
        "Bank": bank.get("account_holder_name") or bank.get("account_name"),
    }

    names_with_values = {k: v for k, v in name_sources.items() if v}
    if names_with_values:
        # Compare all extracted names to the form-submitted company name
        for source, doc_name in names_with_values.items():
            if _names_match(company_name_form, doc_name):
                results.append({
                    "check": f"company_name_vs_{source.lower().replace('/', '_').replace(' ', '_')}",
                    "status": "pass",
                    "detail": f"Company name on {source} ('{doc_name}') matches the submitted company name ('{company_name_form}')",
                    "confidence": 0.95,
                    "layer": 3,
                })
            else:
                results.append({
                    "check": f"company_name_vs_{source.lower().replace('/', '_').replace(' ', '_')}",
                    "status": "fail",
                    "detail": f"Company name mismatch: {source} shows '{doc_name}' but form submitted '{company_name_form}'",
                    "confidence": 0.9,
                    "layer": 3,
                })

    # ── CIN from COI vs form ─────────────────────────────────────────────────────
    coi_cin = _normalize(coi.get("cin_number") or coi.get("registration_number") or "")
    if coi_cin and cin_form:
        if coi_cin == cin_form:
            results.append({
                "check": "cin_coi_vs_form",
                "status": "pass",
                "detail": f"CIN on COI document ('{coi_cin}') matches the submitted CIN",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "cin_coi_vs_form",
                "status": "fail",
                "detail": f"CIN mismatch: COI shows '{coi_cin}' but form submitted '{cin_form}'",
                "confidence": 1.0,
                "layer": 3,
            })

    # ── PAN from PAN/GSTIN doc vs form ───────────────────────────────────────────
    doc_pan = _normalize(pan_gstin.get("pan_number") or pan_gstin.get("pan") or "")
    if doc_pan and pan_form:
        if doc_pan == pan_form:
            results.append({
                "check": "pan_doc_vs_form",
                "status": "pass",
                "detail": f"PAN on document ('{doc_pan}') matches submitted PAN",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "pan_doc_vs_form",
                "status": "fail",
                "detail": f"PAN mismatch: document shows '{doc_pan}' but form submitted '{pan_form}'",
                "confidence": 1.0,
                "layer": 3,
            })

    # ── GSTIN from PAN/GSTIN doc vs form ─────────────────────────────────────────
    doc_gstin = _normalize(pan_gstin.get("gstin_number") or pan_gstin.get("gstin") or "")
    if doc_gstin and gstin_form:
        if doc_gstin == gstin_form:
            results.append({
                "check": "gstin_doc_vs_form",
                "status": "pass",
                "detail": f"GSTIN on document ('{doc_gstin}') matches submitted GSTIN",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "gstin_doc_vs_form",
                "status": "fail",
                "detail": f"GSTIN mismatch: document shows '{doc_gstin}' but form submitted '{gstin_form}'",
                "confidence": 1.0,
                "layer": 3,
            })

    # ── PAN embedded in GSTIN doc vs PAN doc ────────────────────────────────────
    if doc_gstin and doc_pan:
        embedded = _extract_pan_from_gstin(doc_gstin)
        if embedded == doc_pan:
            results.append({
                "check": "gstin_embedded_pan_vs_pan_doc",
                "status": "pass",
                "detail": f"PAN embedded in GSTIN document ('{embedded}') matches the PAN on the PAN document",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "gstin_embedded_pan_vs_pan_doc",
                "status": "fail",
                "detail": f"Critical cross-document mismatch: PAN embedded in GSTIN ('{embedded}') does NOT match PAN document ('{doc_pan}'). These documents may belong to different entities.",
                "confidence": 1.0,
                "layer": 3,
            })

    # ── IFSC from bank doc vs form ───────────────────────────────────────────────
    doc_ifsc = _normalize(bank.get("ifsc_code") or bank.get("ifsc") or "")
    form_ifsc = _normalize(form_data.get("ifsc_code", "") or "")
    if doc_ifsc and form_ifsc:
        if doc_ifsc == form_ifsc:
            results.append({
                "check": "ifsc_doc_vs_form",
                "status": "pass",
                "detail": f"IFSC on bank document ('{doc_ifsc}') matches submitted IFSC",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "ifsc_doc_vs_form",
                "status": "fail",
                "detail": f"IFSC mismatch: bank document shows '{doc_ifsc}' but form submitted '{form_ifsc}'",
                "confidence": 1.0,
                "layer": 3,
            })

    # ── Account Type from bank doc ───────────────────────────────────────────────
    doc_account_type = (bank.get("account_type") or "").strip().lower()
    if doc_account_type:
        if "current" in doc_account_type:
            results.append({
                "check": "account_type_doc_check",
                "status": "pass",
                "detail": f"Bank document confirms account type as Current Account",
                "confidence": 1.0,
                "layer": 3,
            })
        elif "savings" in doc_account_type:
            results.append({
                "check": "account_type_doc_check",
                "status": "fail",
                "detail": "Bank document confirms account type as Savings Account. Indian business regulations require a Current Account.",
                "confidence": 1.0,
                "layer": 3,
            })

    if not results:
        results.append({
            "check": "cross_doc_check",
            "status": "skipped",
            "detail": "Not enough extracted document data available for cross-document checks",
            "confidence": 0.0,
            "layer": 3,
        })

    return results
