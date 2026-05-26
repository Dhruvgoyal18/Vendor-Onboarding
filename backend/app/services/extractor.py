import logging
from typing import Optional
from app.prompts.templates import (
    DOCUMENT_EXTRACTION_PROMPT,
    INDIA_COI_EXTRACTION_PROMPT,
    INDIA_PAN_GSTIN_EXTRACTION_PROMPT,
    INDIA_BANK_EXTRACTION_PROMPT,
    DOC_TYPE_CLASSIFICATION_PROMPT,
)
from app.services.llm_service import call_llm_json
from app.services.ocr_service import extract_text

logger = logging.getLogger(__name__)

# LLM now returns {"field": {"value": ..., "confidence": ...}} — critical fields per doc type
CRITICAL_FIELDS: dict[str, list[str]] = {
    "coi": ["entity_name", "cin_number", "incorporation_date"],
    "registration": ["entity_name", "cin_number", "incorporation_date"],
    "pan_gstin": ["entity_name", "pan_number"],
    "tax_cert": ["entity_name", "pan_number"],
    "bank_letter": ["account_number", "ifsc_code", "account_holder_name"],
    "bank": ["account_number", "ifsc_code", "account_holder_name"],
}

LOW_CONFIDENCE_THRESHOLD = 0.75  # below this on critical fields → partial extraction

# Maps (country, doc_type) → extraction system prompt
COUNTRY_DOC_PROMPTS = {
    ("IN", "coi"):          INDIA_COI_EXTRACTION_PROMPT,
    ("IN", "registration"): INDIA_COI_EXTRACTION_PROMPT,
    ("IN", "pan_gstin"):    INDIA_PAN_GSTIN_EXTRACTION_PROMPT,
    ("IN", "tax_cert"):     INDIA_PAN_GSTIN_EXTRACTION_PROMPT,
    ("IN", "bank_letter"):  INDIA_BANK_EXTRACTION_PROMPT,
    ("IN", "bank"):         INDIA_BANK_EXTRACTION_PROMPT,
}

GENERIC_TYPE_HINTS = {
    "registration": "This is a company registration certificate.",
    "bank_letter":  "This is a bank letter or voided cheque showing banking details.",
    "tax_cert":     "This is a tax certificate or tax registration document.",
    "coi":          "This is a Certificate of Incorporation.",
    "pan_gstin":    "This is a PAN card and/or GSTIN registration certificate.",
    "bank":         "This is a bank letter or voided cheque showing banking details.",
}

# Expected document types per doc_type key
EXPECTED_DOC_TYPES: dict[str, list[str]] = {
    "coi":          ["certificate_of_incorporation", "company_registration"],
    "registration": ["certificate_of_incorporation", "company_registration"],
    "pan_gstin":    ["pan_card", "gstin_certificate", "pan_gstin_combined"],
    "tax_cert":     ["pan_card", "gstin_certificate", "pan_gstin_combined", "vat_certificate"],
    "bank_letter":  ["bank_letter", "cancelled_cheque"],
    "bank":         ["bank_letter", "cancelled_cheque"],
}


def _classify_document(text: str) -> tuple[str, float]:
    """
    Run a fast LLM classification to verify the document type before full extraction.
    Returns (doc_type: str, confidence: float).
    """
    try:
        result = call_llm_json(
            DOC_TYPE_CLASSIFICATION_PROMPT,
            f"Classify this document:\n\n<document>\n{text[:3000]}\n</document>",
        )
        if isinstance(result, dict):
            return result.get("document_type", "other"), float(result.get("confidence", 0.0))
    except Exception as e:
        logger.warning(f"Document classification failed: {e}")
    return "other", 0.0


def _flatten_confident_fields(raw: dict, doc_type: str) -> dict:
    """
    Flatten the per-field confidence format into simple field→value pairs.
    Fields with confidence below LOW_CONFIDENCE_THRESHOLD on critical fields
    are set to None so downstream checks correctly flag them as missing.
    Also computes a quality_score (0–1) based on critical field presence.
    """
    flat = {}
    critical = CRITICAL_FIELDS.get(doc_type, [])
    low_confidence_critical: list[str] = []

    for field, val in raw.items():
        if val is None:
            flat[field] = None
            continue
        if isinstance(val, dict) and "value" in val:
            v = val["value"]
            conf = float(val.get("confidence", 1.0))
            # Drop critical fields below confidence threshold
            if field in critical and conf < LOW_CONFIDENCE_THRESHOLD:
                flat[field] = None
                low_confidence_critical.append(field)
                logger.info(f"Low-confidence critical field '{field}': {v!r} ({conf:.2f}) — treated as missing")
            else:
                flat[field] = v
        else:
            flat[field] = val  # legacy format (no confidence wrapper) — accept as-is

    # Compute quality score: fraction of critical fields successfully extracted
    if critical:
        present = sum(1 for f in critical if flat.get(f))
        flat["_quality_score"] = round(present / len(critical), 2)
        flat["_low_confidence_fields"] = low_confidence_critical
    else:
        flat["_quality_score"] = 1.0
        flat["_low_confidence_fields"] = []

    return flat


def extract_document(
    file_bytes: bytes,
    filename: str,
    document_type: str,
    country: Optional[str] = None,
) -> dict:
    """
    Extract structured data from a document using OCR + LLM.

    Steps:
    1. OCR — native PDF or Tesseract fallback (with preprocessing)
    2. Document type verification — classify before full extraction
    3. LLM extraction with per-field confidence
    4. Flatten per-field confidence; critical fields below 0.75 → None
    """
    text = extract_text(file_bytes, filename)

    if not text.strip():
        logger.warning(f"No text could be extracted from {filename}")
        return {"_quality_score": 0.0, "_low_confidence_fields": []}

    country_upper = (country or "").upper()

    # ── Step 2: Document type verification ────────────────────────────────────────
    expected_types = EXPECTED_DOC_TYPES.get(document_type, [])
    if expected_types:
        detected_type, type_conf = _classify_document(text)
        if type_conf >= 0.80 and detected_type not in expected_types:
            logger.warning(
                f"Document type mismatch: expected one of {expected_types} "
                f"but detected '{detected_type}' (conf={type_conf:.2f}) for '{filename}'"
            )
            return {
                "_doc_type_mismatch": True,
                "_detected_type": detected_type,
                "_expected_types": expected_types,
                "_type_confidence": type_conf,
                "_quality_score": 0.0,
                "_low_confidence_fields": [],
            }
        logger.info(f"Document classification: '{detected_type}' (conf={type_conf:.2f}) for {filename}")

    # ── Step 3: LLM extraction ────────────────────────────────────────────────────
    system_prompt = COUNTRY_DOC_PROMPTS.get(
        (country_upper, document_type),
        DOCUMENT_EXTRACTION_PROMPT,
    )

    if system_prompt != DOCUMENT_EXTRACTION_PROMPT:
        user_message = (
            f"Extract the required fields from the following document text:\n\n"
            f"<document>\n{text[:10000]}\n</document>"
        )
    else:
        type_hint = GENERIC_TYPE_HINTS.get(document_type, "This is a business document.")
        user_message = (
            f"{type_hint}\n\nExtract the required information into JSON:\n\n"
            f"<document>\n{text[:10000]}\n</document>"
        )

    try:
        raw = call_llm_json(system_prompt, user_message)
        if not isinstance(raw, dict):
            return {"_quality_score": 0.0, "_low_confidence_fields": []}
        return _flatten_confident_fields(raw, document_type)
    except Exception as e:
        logger.error(f"LLM extraction failed for {filename}: {e}")
        return {"_quality_score": 0.0, "_low_confidence_fields": []}
