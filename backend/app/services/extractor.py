import logging
from typing import Optional
from app.prompts.templates import (
    DOCUMENT_EXTRACTION_PROMPT,
    INDIA_COI_EXTRACTION_PROMPT,
    INDIA_PAN_GSTIN_EXTRACTION_PROMPT,
    INDIA_BANK_EXTRACTION_PROMPT,
)
from app.services.llm_service import call_llm_json
from app.services.ocr_service import extract_text

logger = logging.getLogger(__name__)

# ─── Prompt Routing ─────────────────────────────────────────────────────────────

# Maps (country, doc_type) → extraction system prompt
COUNTRY_DOC_PROMPTS = {
    # India-specific prompts
    ("IN", "coi"):         INDIA_COI_EXTRACTION_PROMPT,
    ("IN", "registration"): INDIA_COI_EXTRACTION_PROMPT,   # alias
    ("IN", "pan_gstin"):   INDIA_PAN_GSTIN_EXTRACTION_PROMPT,
    ("IN", "tax_cert"):    INDIA_PAN_GSTIN_EXTRACTION_PROMPT,  # alias
    ("IN", "bank_letter"): INDIA_BANK_EXTRACTION_PROMPT,
    ("IN", "bank"):        INDIA_BANK_EXTRACTION_PROMPT,   # alias
}

# Generic type hints for non-India (fallback)
GENERIC_TYPE_HINTS = {
    "registration": "This is a company registration certificate.",
    "bank_letter":  "This is a bank letter or voided cheque showing banking details.",
    "tax_cert":     "This is a tax certificate or tax registration document.",
    "coi":          "This is a Certificate of Incorporation.",
    "pan_gstin":    "This is a PAN card and/or GSTIN registration certificate.",
    "bank":         "This is a bank letter or voided cheque showing banking details.",
}


def extract_document(
    file_bytes: bytes,
    filename: str,
    document_type: str,
    country: Optional[str] = None,
) -> dict:
    """
    Extract structured data from a document using OCR + LLM.

    Strategy:
    - Layer 2: Run OCR service to extract all text (native PDF or Tesseract fallback).
    - Route to the correct extraction prompt based on country + doc_type.
    - Send extracted text to LLM for structured JSON extraction.
    """
    # 1. End-to-End OCR / Text Extraction
    text = extract_text(file_bytes, filename)

    if not text.strip():
        logger.warning(f"No text could be extracted from {filename}")
        return {}

    # 2. Select prompt: India-specific if country=IN, else generic
    country_upper = (country or "").upper()
    system_prompt = COUNTRY_DOC_PROMPTS.get(
        (country_upper, document_type),
        DOCUMENT_EXTRACTION_PROMPT  # fallback to generic
    )

    # Build user message
    if system_prompt != DOCUMENT_EXTRACTION_PROMPT:
        # India-specific: prompt is already very explicit, just provide document text
        user_message = (
            f"Extract the required fields from the following document text:\n\n"
            f"<document>\n{text[:10000]}\n</document>"
        )
    else:
        # Generic fallback: add document type hint
        type_hint = GENERIC_TYPE_HINTS.get(document_type, "This is a business document.")
        user_message = (
            f"{type_hint}\n\nPlease analyze the following document text and extract "
            f"the required information into JSON:\n\n<document>\n{text[:10000]}\n</document>"
        )

    # 3. LLM Extraction
    try:
        result = call_llm_json(system_prompt, user_message)
        return result
    except Exception as e:
        logger.error(f"LLM extraction failed for {filename}: {e}")
        return {}
