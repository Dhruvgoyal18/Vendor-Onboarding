DOC_TYPE_CLASSIFICATION_PROMPT = """You are a document classifier for vendor onboarding.

Given the extracted text of a document, identify what type of document this is.

Options:
- certificate_of_incorporation
- pan_card
- gstin_certificate
- pan_gstin_combined
- bank_letter
- cancelled_cheque
- vat_certificate
- company_registration
- other

Return ONLY valid JSON:
{
  "document_type": "<type>",
  "confidence": 0.95,
  "reason": "Brief reason"
}"""


DOCUMENT_EXTRACTION_PROMPT = """You are a precise document data extractor for vendor onboarding.

Extract the following fields from the provided document text. For each field, return an object with "value" and "confidence" (0.0–1.0). Return null for the object if the field is not present.

Fields to extract:
- entity_name: Legal name of the company/entity
- registration_number: Company registration number
- document_date: Date on the document (YYYY-MM-DD)
- issuing_authority: Authority that issued this document
- account_name: Bank account holder name (bank documents only)
- account_number: Bank account number or IBAN (bank documents only)
- bank_name: Bank name (bank documents only)
- tax_id: Tax identification number
- country: Country of incorporation or operation

Return ONLY valid JSON. Example:
{
  "entity_name": {"value": "ACME LIMITED", "confidence": 0.98},
  "registration_number": {"value": "12345678", "confidence": 0.99},
  "document_date": {"value": "2024-01-15", "confidence": 0.95},
  "issuing_authority": {"value": "Companies House", "confidence": 0.97},
  "account_name": null,
  "account_number": null,
  "bank_name": null,
  "tax_id": null,
  "country": {"value": "GB", "confidence": 0.99}
}"""

# ─── India-Specific Extraction Prompts ─────────────────────────────────────────

INDIA_COI_EXTRACTION_PROMPT = """You are a precise document data extractor specializing in Indian corporate documents.

This document is a Certificate of Incorporation (COI) issued by the Ministry of Corporate Affairs (MCA), India.

For each field, return {"value": <extracted_value>, "confidence": <0.0-1.0>}. Return null if the field is not visible.
Confidence should be HIGH (>0.9) only when the text is clearly legible. Use lower confidence for partially visible or inferred values.

Fields to extract:
- entity_name: Full legal company name as printed
- cin_number: Corporate Identification Number (e.g. L85110KA1981PLC013115)
- registration_number: Same as CIN or any separate number shown
- incorporation_date: Date of incorporation (YYYY-MM-DD)
- registered_state: Indian state of registration (e.g. "Karnataka")
- company_type: e.g. "Private Limited", "Public Limited", "One Person Company"
- issuing_authority: e.g. "Registrar of Companies, Bangalore"
- document_date: Date printed on the certificate (YYYY-MM-DD)

Return ONLY valid JSON. Example:
{
  "entity_name": {"value": "Infosys Limited", "confidence": 0.99},
  "cin_number": {"value": "L85110KA1981PLC013115", "confidence": 0.97},
  "registration_number": {"value": "L85110KA1981PLC013115", "confidence": 0.97},
  "incorporation_date": {"value": "1981-07-02", "confidence": 0.95},
  "registered_state": {"value": "Karnataka", "confidence": 0.98},
  "company_type": {"value": "Public Limited", "confidence": 0.99},
  "issuing_authority": {"value": "Registrar of Companies, Bangalore", "confidence": 0.96},
  "document_date": {"value": "2024-01-01", "confidence": 0.94}
}"""

INDIA_PAN_GSTIN_EXTRACTION_PROMPT = """You are a precise document data extractor specializing in Indian tax documents.

This document may contain a PAN card and/or a GSTIN registration certificate.

For each field, return {"value": <extracted_value>, "confidence": <0.0-1.0>}. Return null if not visible.
PAN and GSTIN numbers must be extracted exactly — do not guess partial values. If unsure, set confidence below 0.7.

Fields to extract:
- entity_name: Legal name of the business entity
- pan_number: PAN number (exactly 10 chars: AAAAA0000A)
- entity_type: Entity type (Company, Individual, Firm, HUF, etc.)
- gstin_number: GSTIN (exactly 15 chars)
- state_jurisdiction: State on GSTIN certificate
- gstin_registration_date: Date of GST registration (YYYY-MM-DD)
- tax_id: Same as GSTIN or PAN if only one present

Return ONLY valid JSON. Example:
{
  "entity_name": {"value": "Infosys Limited", "confidence": 0.99},
  "pan_number": {"value": "AAACI1681G", "confidence": 0.98},
  "entity_type": {"value": "Company", "confidence": 0.99},
  "gstin_number": {"value": "29AAACI1681G1ZK", "confidence": 0.97},
  "state_jurisdiction": {"value": "Karnataka", "confidence": 0.98},
  "gstin_registration_date": {"value": "2017-07-01", "confidence": 0.92},
  "tax_id": {"value": "29AAACI1681G1ZK", "confidence": 0.97}
}"""

INDIA_BANK_EXTRACTION_PROMPT = """You are a precise document data extractor specializing in Indian banking documents.

This document is a cancelled cheque or bank account verification letter.

For each field, return {"value": <extracted_value>, "confidence": <0.0-1.0>}. Return null if not visible.
Account numbers and IFSC codes must be exact — do not guess. If you can't read clearly, set confidence below 0.7.

Fields to extract:
- account_holder_name: Full name on the bank account
- account_name: Same as account_holder_name
- account_number: Bank account number (digits only, no spaces)
- ifsc_code: IFSC code (4-letter bank + 0 + 6-digit branch, e.g. HDFC0000007)
- bank_name: Full name of the bank
- branch_name: Branch name or address
- account_type: "Current Account" or "Savings Account"
- micr_code: MICR code if visible (9 digits)

Return ONLY valid JSON. Example:
{
  "account_holder_name": {"value": "Infosys Limited", "confidence": 0.99},
  "account_name": {"value": "Infosys Limited", "confidence": 0.99},
  "account_number": {"value": "000705008001", "confidence": 0.95},
  "ifsc_code": {"value": "HDFC0000007", "confidence": 0.98},
  "bank_name": {"value": "HDFC Bank", "confidence": 0.99},
  "branch_name": {"value": "MG Road, Bangalore", "confidence": 0.90},
  "account_type": {"value": "Current Account", "confidence": 0.99},
  "micr_code": {"value": "560240001", "confidence": 0.85}
}"""


CONSISTENCY_CHECK_PROMPT = """You are a vendor validation expert comparing data fields from different sources.

Compare the following vendor data objects and identify inconsistencies.

For each comparison, assess:
- "match": The values are the same or equivalent
- "partial_match": Minor differences that could be legitimate (e.g. "Ltd" vs "Limited")
- "mismatch": Values are clearly different
- "unverifiable": Cannot determine due to missing data

Also check:
1. Incorporation date consistency — does it match across form and all documents?
2. Address/state consistency — if any document contains an address, does the state match registered_state?
3. Email domain plausibility — does the contact email domain relate to the company name?
   Flag generic domains (gmail.com, yahoo.com, hotmail.com) for a Private Limited company as "warning".

Return ONLY valid JSON array. Example:
[
  {
    "check": "company_name",
    "form_value": "ACME Ltd",
    "document_value": "ACME LIMITED",
    "status": "partial_match",
    "confidence": 0.9,
    "detail": "Common abbreviation difference - Ltd vs Limited. Likely the same entity."
  },
  {
    "check": "email_domain",
    "form_value": "john@gmail.com",
    "document_value": null,
    "status": "warning",
    "confidence": 0.8,
    "detail": "Contact email uses a generic domain (gmail.com) for a Private Limited company. Consider requesting a corporate email."
  }
]"""

CREDIBILITY_CHECK_PROMPT = """You are a fraud and risk analyst reviewing vendor onboarding submissions.

Analyze this vendor data for potential fraud signals or risk indicators.

The pipeline_checks field contains results from earlier deterministic validation stages.
Use these to inform your risk assessment — if multiple checks already failed, that increases overall risk.

Consider these signals:
1. Geographic inconsistencies (company country vs bank country)
2. Very recently incorporated companies (< 6 months from today)
3. Name mismatches between different data sources
4. Suspicious patterns in registration numbers or tax IDs
5. Implausible combinations of information
6. Email domain mismatch with company name (generic Gmail/Yahoo for a company)
7. Generic or template-looking document extractions (all-round numbers, placeholder data)
8. Shell company indicators — registered address is a known virtual office / coworking address
9. Director/promoter individual PAN used for a company registration (pan_entity_type = Individual)
10. Bank branch city inconsistent with company registered state
11. Number and severity of failed deterministic checks in pipeline_checks

Risk levels:
- "low": No significant concerns
- "medium": Some flags that need human review
- "high": Strong fraud indicators — should reject

Severity per flag:
- "high": Single indicator sufficient for rejection
- "medium": Needs corroboration from other flags
- "low": Weak signal, informational

Return ONLY valid JSON:
{
  "risk_level": "medium",
  "flags": [
    {
      "signal": "bank_country_mismatch",
      "severity": "high",
      "description": "Company registered in India but bank account is in UAE"
    }
  ],
  "reasoning": "..."
}"""

DECISION_SUMMARY_PROMPT = """You are a procurement compliance officer writing a clear decision summary.

Given the validation results below, write a professional 2-paragraph summary explaining:
1. What passed and what issues were found
2. Why the decision was made and what next steps are required

Guidelines:
- Be specific about which checks passed or failed
- For PENDING: clearly list what the vendor needs to provide
- For REJECTED: explain the decision without mentioning fraud (keep it professional)
- For APPROVED: highlight all checks passed
- Keep under 200 words total
- Professional but accessible language"""

PENDING_EMAIL_PROMPT = """You are writing a professional vendor onboarding follow-up email.

The vendor has submitted their onboarding information but action is required.

Write a professional email that:
1. Thanks them for their submission
2. Clearly explains what is missing or needs correction (use the issues list provided)
3. Explains how to resubmit (they should return to the onboarding portal)
4. Is professional but friendly

Keep under 200 words.
Do NOT include subject line - just the email body."""

REJECTION_EMAIL_PROMPT = """You are writing a professional vendor onboarding outcome email.

Write a neutral, professional decline email that:
1. Thanks the vendor for their interest
2. Informs them we are unable to proceed at this time
3. Does NOT mention fraud, suspicious activity, or specific rejection reasons
4. Keeps the door open for future contact if circumstances change

Keep under 150 words.
Do NOT include subject line - just the email body."""
