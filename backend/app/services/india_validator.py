"""
India-specific vendor validation.

Layer 1: Deterministic format checks (regex, code logic — no LLM)
Layer 3: Cross-document consistency checks (deterministic)
"""

import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from rapidfuzz import fuzz

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
    "TMBL": "Tamilnad Mercantile Bank",
    "KVBL": "Karur Vysya Bank",
    "CIUB": "City Union Bank",
    "NKGS": "NKGSB Bank",
    "RATN": "RBL Bank",
    "SCBL": "Standard Chartered",
    "HSBC": "HSBC Bank",
    "CITI": "Citibank",
    "DBSS": "DBS Bank",
    "BNPA": "BNP Paribas",
    "DEUT": "Deutsche Bank",
    "JANA": "Jana Small Finance Bank",
    "UJVN": "Ujjivan Small Finance Bank",
    "ESAF": "ESAF Small Finance Bank",
    "PMCB": "Punjab and Maharashtra Co-operative Bank",
    "MAHB": "Bank of Maharashtra",
    "ALLA": "Allahabad Bank",
    "ANDB": "Andhra Bank",
    "CORP": "Corporation Bank",
    "DENA": "Dena Bank",
    "ORBC": "Oriental Bank of Commerce",
    "VIJB": "Vijaya Bank",
    "SYNB": "Syndicate Bank",
    "PYTM": "Paytm Payments Bank",
    "AIRP": "Airtel Payments Bank",
    "FINO": "Fino Payments Bank",
}

# ─── Regex Patterns ─────────────────────────────────────────────────────────────
CIN_PATTERN = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

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

COMPANY_ENTITY_TYPES = {"C", "F", "H"}

NAME_FUZZY_THRESHOLD = 85  # token_sort_ratio threshold for company name matching


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return s.upper().strip().replace(" ", "")


def _extract_pan_from_gstin(gstin: str) -> str:
    return gstin[2:12].upper() if len(gstin) >= 12 else ""


def _extract_state_code_from_gstin(gstin: str) -> str:
    return gstin[:2] if len(gstin) >= 2 else ""


def _names_match(name1: str, name2: str) -> tuple[bool, float]:
    """
    Fuzzy match company names using rapidfuzz token_sort_ratio.
    Returns (matched: bool, score: float).
    token_sort_ratio sorts tokens alphabetically before comparing, so
    "NEXOVA TECHNOLOGIES PRIVATE LIMITED" vs "TECHNOLOGIES NEXOVA LIMITED" both score ~100.
    Threshold 85 catches OCR artifacts (NEXDVA vs NEXOVA) while rejecting
    clear mismatches (NEXOVA vs NEXORA).
    """
    score = fuzz.token_sort_ratio(name1.upper(), name2.upper())
    return score >= NAME_FUZZY_THRESHOLD, score


def _extract_cin_year(cin: str) -> Optional[int]:
    """Extract the 4-digit incorporation year from CIN.

    CIN format: [LU][5-digit NIC][2-letter state][4-digit year][3-letter type][6-digit seq]
    Positions:   0    1-5          6-7             8-11          12-14          15-20
    Year lives at index 8:12, not 6:10.
    """
    try:
        if len(cin) >= 12:
            year_str = cin[8:12]
            year = int(year_str)
            if 1900 <= year <= 2100:
                return year
    except (ValueError, IndexError):
        pass
    return None


def _parse_year_from_date_str(date_str: str) -> Optional[int]:
    """Try to extract year from various date string formats."""
    if not date_str:
        return None
    # ISO format YYYY-MM-DD
    m = re.match(r"(\d{4})-\d{2}-\d{2}", date_str.strip())
    if m:
        return int(m.group(1))
    # DD/MM/YYYY
    m = re.match(r"\d{2}/\d{2}/(\d{4})", date_str.strip())
    if m:
        return int(m.group(1))
    # DD-MM-YYYY
    m = re.match(r"\d{2}-\d{2}-(\d{4})", date_str.strip())
    if m:
        return int(m.group(1))
    # YYYY alone
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return int(m.group(1))
    return None


def _parse_date(date_str: str) -> Optional[date]:
    """Parse a date string into a date object, trying multiple formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _validate_pan_checksum(pan: str) -> bool:
    """
    Validate PAN checksum using the standard algorithm.
    Weights: [2,4,6,8,10,3,5,7,9] for positions 0-8; position 9 is the check char.
    Letter value: A=0...Z=25; digit value: face value.
    Check char = chr(ord('A') + (sum % 26))
    """
    if not PAN_PATTERN.match(pan):
        return False
    weights = [2, 4, 6, 8, 10, 3, 5, 7, 9]

    def char_val(c: str) -> int:
        return ord(c) - ord('A') if c.isalpha() else int(c)

    total = sum(char_val(pan[i]) * weights[i] for i in range(9))
    expected = chr(ord('A') + (total % 26))
    return pan[9].upper() == expected


def _validate_account_number(account: str) -> tuple[bool, str]:
    """
    Indian bank accounts: 9–18 digits, digits only.
    Returns (valid: bool, reason: str).
    """
    digits_only = re.sub(r"\s", "", account)
    if not digits_only.isdigit():
        return False, f"Account number contains non-digit characters: '{account}'"
    if len(digits_only) < 9:
        return False, f"Account number too short ({len(digits_only)} digits) — Indian accounts are 9–18 digits"
    if len(digits_only) > 18:
        return False, f"Account number too long ({len(digits_only)} digits) — Indian accounts are 9–18 digits"
    return True, "OK"


# ─── Layer 1: Deterministic Format Checks ──────────────────────────────────────

def run_india_format_checks(form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Layer 1 — All India-specific deterministic format checks on form data.
    Returns list of check result dicts.
    """
    results = []

    cin = _normalize(form_data.get("cin_number", "") or "")
    pan = _normalize(form_data.get("pan_number", "") or "")
    gstin = _normalize(form_data.get("gstin_number", "") or "")
    ifsc = _normalize(form_data.get("ifsc_code", "") or "")
    account_type = (form_data.get("account_type", "") or "").strip().lower()
    registered_state = (form_data.get("registered_state", "") or "").strip()
    incorporation_date_str = (form_data.get("incorporation_date", "") or "").strip()
    account_number = (form_data.get("account_number", "") or "").strip()

    # ── CIN ──────────────────────────────────────────────────────────────────────
    if cin:
        if CIN_PATTERN.match(cin):
            results.append({
                "check": "cin_format",
                "status": "pass",
                "detail": f"CIN '{cin}' matches the required format",
                "confidence": 1.0,
                "layer": 1,
            })

            # CIN age check: chars 7-10 encode incorporation year
            cin_year = _extract_cin_year(cin)
            form_year = _parse_year_from_date_str(incorporation_date_str)

            if cin_year and form_year:
                if cin_year == form_year:
                    results.append({
                        "check": "cin_year_vs_incorporation_date",
                        "status": "pass",
                        "detail": f"CIN incorporation year ({cin_year}) matches the submitted incorporation date",
                        "confidence": 1.0,
                        "layer": 1,
                    })
                else:
                    results.append({
                        "check": "cin_year_vs_incorporation_date",
                        "status": "fail",
                        "detail": (
                            f"CIN encodes incorporation year {cin_year} but submitted incorporation date "
                            f"shows year {form_year}. These must match — this is a data integrity failure."
                        ),
                        "confidence": 1.0,
                        "layer": 1,
                    })
        else:
            results.append({
                "check": "cin_format",
                "status": "fail",
                "detail": f"CIN '{cin}' does not match expected format [L/U][5-digit NIC][2-letter state][4-digit year][PLC/OPC/etc][6-digit number]",
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
                "detail": f"PAN '{pan}' does not match expected format [5 letters][4 digits][1 letter]",
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

            # PAN checksum validation
            if _validate_pan_checksum(pan):
                results.append({
                    "check": "pan_checksum",
                    "status": "pass",
                    "detail": f"PAN checksum is valid",
                    "confidence": 1.0,
                    "layer": 1,
                })
            else:
                results.append({
                    "check": "pan_checksum",
                    "status": "warning",
                    "detail": (
                        f"PAN '{pan}' fails checksum validation. The PAN may contain a typo. "
                        "Cross-check with the physical PAN card."
                    ),
                    "confidence": 0.9,
                    "layer": 1,
                })

            # Entity type check
            pan_4th = pan[3]
            entity_type_name = PAN_ENTITY_TYPES.get(pan_4th, "Unknown")
            if pan_4th in COMPANY_ENTITY_TYPES:
                results.append({
                    "check": "pan_entity_type",
                    "status": "pass",
                    "detail": f"PAN entity type '{pan_4th}' = {entity_type_name} — valid for a business vendor",
                    "confidence": 1.0,
                    "layer": 1,
                })
            elif pan_4th == "P":
                results.append({
                    "check": "pan_entity_type",
                    "status": "fail",
                    "detail": (
                        "PAN 4th character 'P' indicates an Individual PAN. "
                        "Company vendors must submit a Company (C), Firm (F), or HUF (H) PAN."
                    ),
                    "confidence": 1.0,
                    "layer": 1,
                })
            else:
                results.append({
                    "check": "pan_entity_type",
                    "status": "warning",
                    "detail": f"PAN entity type '{pan_4th}' = {entity_type_name}. Verify this is appropriate for this vendor.",
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
                "detail": f"GSTIN '{gstin}' does not match expected 15-character format [2-digit state][PAN][entity][Z][checksum]",
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

            # GSTIN ↔ PAN cross-check
            if pan:
                embedded_pan = _extract_pan_from_gstin(gstin)
                if embedded_pan == pan:
                    results.append({
                        "check": "gstin_pan_match",
                        "status": "pass",
                        "detail": f"PAN embedded in GSTIN ('{embedded_pan}') matches the submitted PAN",
                        "confidence": 1.0,
                        "layer": 1,
                    })
                else:
                    results.append({
                        "check": "gstin_pan_match",
                        "status": "fail",
                        "detail": (
                            f"PAN embedded in GSTIN ('{embedded_pan}') does NOT match submitted PAN ('{pan}'). "
                            "The GSTIN may belong to a different entity."
                        ),
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
                    "detail": f"GSTIN state code '{state_code}' = '{state_name}'",
                    "confidence": 1.0,
                    "layer": 1,
                })
                if registered_state:
                    _, score = _names_match(registered_state, state_name)
                    if score >= NAME_FUZZY_THRESHOLD:
                        results.append({
                            "check": "gstin_state_vs_registered_state",
                            "status": "pass",
                            "detail": f"GSTIN state code '{state_code}' ({state_name}) is consistent with registered state '{registered_state}'",
                            "confidence": 1.0,
                            "layer": 1,
                        })
                    else:
                        results.append({
                            "check": "gstin_state_vs_registered_state",
                            "status": "fail",
                            "detail": (
                                f"GSTIN state code '{state_code}' implies '{state_name}' "
                                f"but registered state is '{registered_state}'. These must match."
                            ),
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
                "detail": f"IFSC '{ifsc}' does not match expected format [4-letter bank code][0][6-digit branch]",
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
            bank_prefix = ifsc[:4]
            known_bank = IFSC_BANK_CODES.get(bank_prefix)
            stated_bank = form_data.get("bank_name", "") or ""

            if known_bank:
                matched, score = _names_match(known_bank, stated_bank)
                if matched:
                    results.append({
                        "check": "ifsc_bank_name_match",
                        "status": "pass",
                        "detail": f"IFSC prefix '{bank_prefix}' = '{known_bank}' matches stated bank '{stated_bank}'",
                        "confidence": 1.0,
                        "layer": 1,
                    })
                else:
                    results.append({
                        "check": "ifsc_bank_name_match",
                        "status": "fail",
                        "detail": f"IFSC prefix '{bank_prefix}' = '{known_bank}' but stated bank is '{stated_bank}'. These must match.",
                        "confidence": 1.0,
                        "layer": 1,
                    })
            else:
                # Unknown prefix → warning, not fail
                results.append({
                    "check": "ifsc_bank_name_match",
                    "status": "warning",
                    "detail": (
                        f"IFSC prefix '{bank_prefix}' is not in our known bank code list "
                        "(may be a cooperative bank, NBFC, or new bank) — manual verification required"
                    ),
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

    # ── Bank Account Number ───────────────────────────────────────────────────────
    if account_number:
        valid, reason = _validate_account_number(account_number)
        if valid:
            results.append({
                "check": "account_number_format",
                "status": "pass",
                "detail": f"Account number length ({len(account_number.replace(' ', ''))} digits) is within the valid 9–18 digit range",
                "confidence": 1.0,
                "layer": 1,
            })
        else:
            results.append({
                "check": "account_number_format",
                "status": "fail",
                "detail": reason,
                "confidence": 1.0,
                "layer": 1,
            })
    else:
        results.append({
            "check": "account_number_format",
            "status": "missing",
            "detail": "Bank account number is required",
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
                "detail": "Account type is 'Savings Account'. Indian regulations require businesses to use a Current Account for commercial transactions. This is a red flag.",
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
    Includes form vs doc, and direct doc-to-doc comparisons.
    """
    results = []

    coi = extracted_docs.get("coi") or extracted_docs.get("registration") or {}
    pan_gstin = extracted_docs.get("pan_gstin") or extracted_docs.get("tax_cert") or {}
    bank = extracted_docs.get("bank_letter") or extracted_docs.get("bank") or {}

    pan_form = _normalize(form_data.get("pan_number", "") or "")
    gstin_form = _normalize(form_data.get("gstin_number", "") or "")
    cin_form = _normalize(form_data.get("cin_number", "") or "")
    company_name_form = form_data.get("company_name", "") or ""
    incorporation_date_str = (form_data.get("incorporation_date", "") or "").strip()

    coi_name = coi.get("entity_name") or coi.get("company_name")
    pan_name = pan_gstin.get("entity_name") or pan_gstin.get("company_name")
    bank_name_doc = bank.get("account_holder_name") or bank.get("account_name")

    # ── Company Name: form vs each document ──────────────────────────────────────
    name_sources = {
        "COI": coi_name,
        "PAN_GSTIN_doc": pan_name,
        "bank_doc": bank_name_doc,
    }
    for source, doc_name in name_sources.items():
        if not doc_name:
            continue
        matched, score = _names_match(company_name_form, doc_name)
        label = source.replace("_", " ")
        if matched:
            results.append({
                "check": f"company_name_vs_{source.lower()}",
                "status": "pass",
                "detail": f"Company name on {label} ('{doc_name}') matches submitted name ('{company_name_form}') — similarity {score:.0f}%",
                "confidence": round(score / 100, 2),
                "layer": 3,
            })
        else:
            results.append({
                "check": f"company_name_vs_{source.lower()}",
                "status": "fail",
                "detail": f"Name mismatch on {label}: document shows '{doc_name}' vs submitted '{company_name_form}' (similarity {score:.0f}%)",
                "confidence": round(score / 100, 2),
                "layer": 3,
            })

    # ── Direct doc-to-doc: COI name vs PAN doc name ───────────────────────────────
    if coi_name and pan_name:
        matched, score = _names_match(coi_name, pan_name)
        if matched:
            results.append({
                "check": "coi_vs_pan_doc_name",
                "status": "pass",
                "detail": f"Company name on COI ('{coi_name}') matches company name on PAN document ('{pan_name}')",
                "confidence": round(score / 100, 2),
                "layer": 3,
            })
        else:
            results.append({
                "check": "coi_vs_pan_doc_name",
                "status": "fail",
                "detail": (
                    f"Cross-document name mismatch: COI shows '{coi_name}' but PAN document shows '{pan_name}'. "
                    "These documents may belong to different entities."
                ),
                "confidence": round(score / 100, 2),
                "layer": 3,
            })

    # ── Direct doc-to-doc: COI name vs bank account name ─────────────────────────
    if coi_name and bank_name_doc:
        matched, score = _names_match(coi_name, bank_name_doc)
        if matched:
            results.append({
                "check": "coi_vs_bank_name",
                "status": "pass",
                "detail": f"Company name on COI ('{coi_name}') matches bank account holder name ('{bank_name_doc}')",
                "confidence": round(score / 100, 2),
                "layer": 3,
            })
        else:
            results.append({
                "check": "coi_vs_bank_name",
                "status": "fail",
                "detail": (
                    f"COI name ('{coi_name}') does not match bank account holder name ('{bank_name_doc}'). "
                    "The bank account may belong to a different entity."
                ),
                "confidence": round(score / 100, 2),
                "layer": 3,
            })

    # ── Direct doc-to-doc: PAN entity name vs bank account name ──────────────────
    if pan_name and bank_name_doc:
        matched, score = _names_match(pan_name, bank_name_doc)
        if matched:
            results.append({
                "check": "pan_vs_bank_name",
                "status": "pass",
                "detail": f"PAN entity name ('{pan_name}') matches bank account holder name ('{bank_name_doc}')",
                "confidence": round(score / 100, 2),
                "layer": 3,
            })
        else:
            results.append({
                "check": "pan_vs_bank_name",
                "status": "fail",
                "detail": (
                    f"PAN entity name ('{pan_name}') does not match bank account holder name ('{bank_name_doc}'). "
                    "These should be the same entity."
                ),
                "confidence": round(score / 100, 2),
                "layer": 3,
            })

    # ── CIN from COI vs form ─────────────────────────────────────────────────────
    coi_cin = _normalize(coi.get("cin_number") or coi.get("registration_number") or "")
    if coi_cin and cin_form:
        if coi_cin == cin_form:
            results.append({
                "check": "cin_coi_vs_form",
                "status": "pass",
                "detail": f"CIN on COI document ('{coi_cin}') matches submitted CIN",
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
                "detail": f"PAN embedded in GSTIN document ('{embedded}') matches the PAN document",
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "gstin_embedded_pan_vs_pan_doc",
                "status": "fail",
                "detail": (
                    f"Critical: PAN embedded in GSTIN ('{embedded}') does NOT match PAN document ('{doc_pan}'). "
                    "These documents belong to different entities."
                ),
                "confidence": 1.0,
                "layer": 3,
            })

    # ── GSTIN registration date vs incorporation date ─────────────────────────────
    gstin_reg_date_str = (pan_gstin.get("gstin_registration_date") or "").strip()
    coi_incorp_date_str = (coi.get("incorporation_date") or incorporation_date_str or "").strip()

    gstin_reg_date = _parse_date(gstin_reg_date_str)
    incorp_date = _parse_date(coi_incorp_date_str)

    if gstin_reg_date and incorp_date:
        if gstin_reg_date >= incorp_date:
            results.append({
                "check": "gstin_date_vs_incorporation_date",
                "status": "pass",
                "detail": (
                    f"GST registration date ({gstin_reg_date}) is on or after the incorporation date ({incorp_date}) — valid"
                ),
                "confidence": 1.0,
                "layer": 3,
            })
        else:
            results.append({
                "check": "gstin_date_vs_incorporation_date",
                "status": "fail",
                "detail": (
                    f"GST registration date ({gstin_reg_date}) is BEFORE the incorporation date ({incorp_date}). "
                    "A company cannot register for GST before it is incorporated. This is a fraud signal."
                ),
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

    # ── MICR vs IFSC city code consistency ────────────────────────────────────────
    micr = _normalize(bank.get("micr_code") or "")
    if micr and len(micr) >= 3 and doc_ifsc and len(doc_ifsc) >= 4:
        micr_city = micr[:3]   # first 3 digits of MICR = city code
        ifsc_branch = doc_ifsc[4:]  # last 6 chars encode branch
        # The MICR city code and IFSC branch city are linked but no simple 1:1 mapping.
        # Flag as warning if MICR prefix is all-zeros or obviously wrong (basic sanity).
        if micr_city == "000":
            results.append({
                "check": "micr_ifsc_consistency",
                "status": "warning",
                "detail": f"MICR city code is '000' which is unusual — verify bank document authenticity",
                "confidence": 0.7,
                "layer": 3,
            })
        else:
            results.append({
                "check": "micr_ifsc_consistency",
                "status": "pass",
                "detail": f"MICR code '{micr}' has city prefix '{micr_city}' — present and non-zero",
                "confidence": 0.8,
                "layer": 3,
            })

    # ── Account Type from bank doc ───────────────────────────────────────────────
    doc_account_type = (bank.get("account_type") or "").strip().lower()
    if doc_account_type:
        if "current" in doc_account_type:
            results.append({
                "check": "account_type_doc_check",
                "status": "pass",
                "detail": "Bank document confirms account type as Current Account",
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
