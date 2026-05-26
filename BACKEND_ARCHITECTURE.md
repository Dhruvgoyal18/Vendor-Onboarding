# Backend Architecture — Complete Technical Reference

> Last updated: May 2026  
> Stack: FastAPI · SQLAlchemy · PostgreSQL (Supabase) · Anthropic Claude / Groq Llama · Tesseract OCR · pdfplumber · rapidfuzz

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Database Schema & Row Lifecycle](#2-database-schema--row-lifecycle)
3. [API Endpoints Reference](#3-api-endpoints-reference)
4. [The Validation Pipeline — Stage by Stage](#4-the-validation-pipeline--stage-by-stage)
5. [OCR Layer — How Text Is Extracted from Documents](#5-ocr-layer--how-text-is-extracted-from-documents)
6. [India Validation Deep Dive](#6-india-validation-deep-dive)
7. [Decision Engine Logic](#7-decision-engine-logic)
8. [LLM Usage Map](#8-llm-usage-map)
9. [Auth System (JWT)](#9-auth-system-jwt)
10. [End-to-End Walkthrough — India Vendor Submission](#10-end-to-end-walkthrough--india-vendor-submission)
11. [Edge Cases & How They Are Handled](#11-edge-cases--how-they-are-handled)

---

## 1. System Overview

```
Frontend (Next.js :3000)
    │
    │  POST /api/submissions  (multipart/form-data)
    ▼
FastAPI Backend (:8000)
    │
    ├── Saves Vendor row (status=processing)
    ├── Saves Document rows (one per uploaded file)
    ├── Kicks off background task (BackgroundTasks)
    │
    └── run_pipeline() ─────────────────────────────────────────────────────►
         │
         ├─ [intake]                Duplicate detection (4 signals)
         ├─ [extract_fields]        Normalize form data
         ├─ [format_check]          Layer 1: Deterministic regex/logic (India only)
         ├─ [external_verification] MCA21, GST portal, RBI IFSC, penny drop (India only)
         ├─ [extract_docs]          Layer 2: OCR → LLM extraction per document
         ├─ [cross_doc_check]       Layer 3: Cross-document deterministic checks (India)
         ├─ [merge]                 Assemble merged_data JSON blob
         ├─ [check_completeness]    Rule-based field + doc presence checks
         ├─ [check_consistency]     LLM: form data vs extracted doc data
         ├─ [check_credibility]     LLM: fraud/risk signal analysis
         ├─ [decide]                Deterministic decision engine (severity scoring)
         └─ [output → done]         Generate summary, send emails, mark final status
```

The pipeline runs **asynchronously in a background task** — the HTTP response
(`run_id`, `message`) is returned immediately after the DB rows are created.
The frontend polls via SSE (`/api/submissions/{run_id}/events`) for live updates.

---

## 2. Database Schema & Row Lifecycle

### 2.1 Tables

```
vendors
  id                    UUID  PK
  run_id                STRING  UNIQUE  e.g. "vnd_20260526_a3f9b1c2"
  company_name          STRING
  country               STRING(2)         e.g. "IN", "GB"
  incorporation_date    STRING
  contact_name          STRING
  contact_email         STRING
  tax_id                STRING
  tax_id_type           STRING
  status                ENUM  processing | pending | approved | rejected | error
  current_stage         STRING            last pipeline stage that ran
  merged_data           JSON              full snapshot after merge stage
  risk_level            STRING            low | medium | high
  is_duplicate          BOOL
  duplicate_of_run_id   STRING
  version_number        INT               (1 for first submission, 2+ for resubmissions)
  original_run_id       STRING            shared across all resubmissions of same case
  resubmission_notes    TEXT              vendor's notes on what they fixed
  decision_summary      TEXT              LLM-generated human readable summary
  decided_at            TIMESTAMP
  pipeline_duration_ms  BIGINT            wall-clock time for the full pipeline run
  sla_due_at            TIMESTAMP         created_at + 48h (set at pipeline start)
  deleted_at            TIMESTAMP
  archived_at           TIMESTAMP
  override_by           STRING            admin username who overrode status
  override_at           TIMESTAMP
  override_reason       TEXT
  ...all form fields:
    bank_account_name, account_number, bank_name, bank_country
    cin_number, pan_number, gstin_number, ifsc_code,
    account_type, registered_state

documents
  id                    UUID  PK
  vendor_id             UUID  FK→vendors.id
  document_type         STRING  "coi" | "pan_gstin" | "bank_letter" | "registration" | "tax_cert"
  file_path             STRING  local disk path (backend/uploads/)
  original_filename     STRING
  extracted_json        JSON    structured data the LLM extracted (null until pipeline runs)
  ocr_status            STRING  unknown | success | partial | failed
  ocr_issues            JSON    list of issue strings
  storage_key           STRING  Supabase storage object key
  file_hash             STRING  SHA-256 of raw bytes
  document_verified_type STRING LLM-confirmed document type
  quality_score         FLOAT  0.0–1.0 extraction quality score

validation_results
  id                UUID  PK
  vendor_id         UUID  FK→vendors.id
  category          STRING  format_check | external_verification | cross_doc_check |
                            completeness | consistency | credibility
  check_name        STRING  e.g. "cin_format", "gstin_pan_match", "mca21_cin_active"
  status            STRING  pass | fail | warning | missing | match | mismatch | skipped | error
  detail            TEXT    human-readable explanation
  confidence        FLOAT   0.0–1.0

pipeline_stage_logs
  id                UUID  PK
  vendor_id         UUID  FK→vendors.id
  stage             STRING  one of the 13 pipeline stage names
  status            STRING  pending | running | completed | failed | skipped
  message           TEXT    progress description
  stage_metadata    JSON    optional extra data
  started_at        TIMESTAMP
  completed_at      TIMESTAMP

refresh_tokens
  id                UUID  PK
  token_hash        STRING  SHA-256 of the raw JWT (never store raw token)
  role              STRING  "admin" | "vendor"
  subject           STRING  username or email
  expires_at        TIMESTAMP
  revoked           BOOL

email_logs
  id                UUID  PK
  vendor_id         UUID  FK→vendors.id
  recipient         STRING
  subject           STRING
  body              TEXT
  email_type        STRING  pending_request | rejection_neutral | ocr_failure | approval
  success           BOOL
  error             TEXT

audit_events
  id                UUID  PK
  vendor_id         UUID  FK→vendors.id
  event_type        STRING  pipeline_started | override | status_change | retry
  actor             STRING  username or "system"
  actor_role        STRING  admin | vendor | system
  payload           JSONB   arbitrary event data
  created_at        TIMESTAMP

llm_cache
  id                UUID  PK
  prompt_hash       STRING  UNIQUE — SHA-256 of prompt+input
  provider          STRING
  model             STRING
  response_json     JSONB
  created_at        TIMESTAMP
  expires_at        TIMESTAMP

country_configs
  id                UUID  PK
  country_code      STRING(2)  UNIQUE
  required_documents  JSONB   list of required doc types
  required_fields     JSONB   list of required form fields
  validation_rules    JSONB   country-specific rule overrides
  sla_hours           INT     default 48
  active              BOOL
  updated_at          TIMESTAMP
```

**Indexes:**
`ix_vendors_status`, `ix_vendors_country_status`, `ix_vendors_contact_email`,
`ix_vendors_created_at`, `ix_vendors_original_run_id`,
`ix_audit_events_vendor_id`, `ix_audit_events_event_type`,
`ix_llm_cache_prompt_hash`, `ix_country_configs_code`

### 2.2 Row Creation Sequence

When a vendor submits the form, rows are created in this exact order:

```
1. vendors row  →  status=processing, current_stage="intake"
2. documents rows  →  one per uploaded file, ocr_status="unknown"
3. pipeline_stage_logs rows  →  created lazily by _update_stage() as each stage starts
4. audit_events row  →  event_type="pipeline_started" (written at pipeline start)
```

As the pipeline progresses:
- `vendors.current_stage` is updated to the running stage name
- `vendors.sla_due_at` is set to `created_at + 48 hours` at pipeline start
- `vendors.status` stays `processing` until `_finalize()` is called
- At `_finalize()`: `vendors.status` flips to `approved | pending | rejected`
- `vendors.decided_at` and `vendors.pipeline_duration_ms` are set
- `validation_results` rows accumulate throughout the pipeline

### 2.3 merged_data JSON Structure

After the `merge` stage, `vendors.merged_data` contains:

```json
{
  "form": {
    "company_name": "NEXOVA TECHNOLOGIES PRIVATE LIMITED",
    "cin_number": "U72200MH2015PTC267736",
    "pan_number": "AABCT3518Q",
    "gstin_number": "27AABCT3518Q1ZK",
    ...
  },
  "docs": {
    "coi": {
      "entity_name": "NEXOVA TECHNOLOGIES PRIVATE LIMITED",
      "cin_number": "U72200MH2015PTC267736",
      "incorporation_date": "2015-03-15",
      "registered_state": "Maharashtra"
    },
    "pan_gstin": {
      "entity_name": "NEXOVA TECHNOLOGIES PRIVATE LIMITED",
      "pan_number": "AABCT3518Q",
      "gstin_number": "27AABCT3518Q1ZK"
    },
    "bank_letter": {
      "account_holder_name": "NEXOVA TECHNOLOGIES PRIVATE LIMITED",
      "account_number": "50200045678901",
      "ifsc_code": "HDFC0000007",
      "bank_name": "HDFC Bank",
      "account_type": "Current Account"
    }
  },
  "format_checks": [...],
  "cross_doc_checks": [...],
  "provenance": {
    "form_fields": ["company_name", "cin_number", ...],
    "extracted_docs": ["coi", "pan_gstin", "bank_letter"],
    "country": "IN"
  }
}
```

Note: `format_checks` in `merged_data` includes both Layer 1 format check results AND
external verification results — they are appended together before the merge stage.

---

## 3. API Endpoints Reference

### 3.1 Submissions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/submissions` | None | Create new vendor submission |
| GET | `/api/submissions/{run_id}` | None | Get full vendor detail |
| GET | `/api/submissions/{run_id}/stages` | None | Get pipeline stage statuses |
| GET | `/api/submissions/{run_id}/events` | None | SSE stream for live updates |
| GET | `/api/submissions/{run_id}/versions` | None | All resubmissions of a case |
| POST | `/api/submissions/{run_id}/resubmit` | None | Resubmit with corrections |
| GET | `/api/submissions/mine` | Vendor JWT | All submissions for logged-in email |

**POST /api/submissions** accepts `multipart/form-data`:
- `data` (string): JSON-serialized form fields
- `registration_doc` (file, optional): Registration certificate / COI
- `bank_doc` (file, optional): Bank letter / cancelled cheque
- `tax_doc` (file, optional): Tax certificate
- `pan_gstin_doc` (file, optional): India: combined PAN+GSTIN doc

Returns: `{ "run_id": "vnd_20260526_a3f9b1c2", "message": "..." }`

### 3.2 Dashboard (Admin JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/stats` | Aggregate counts by status |
| GET | `/api/dashboard/history` | Paginated vendor list with filters |

Query params for `/history`: `page`, `page_size`, `status`, `search`

### 3.3 Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/auth/admin/login` | `{username, password}` | Issue admin JWT pair |
| POST | `/api/auth/admin/refresh` | `{refresh_token}` | Rotate tokens |
| POST | `/api/auth/admin/logout` | `{refresh_token}` | Revoke refresh token |
| POST | `/api/auth/vendor/login` | `{email, run_id}` | Issue vendor JWT pair |
| POST | `/api/auth/vendor/refresh` | `{refresh_token}` | Rotate tokens |
| POST | `/api/auth/vendor/logout` | `{refresh_token}` | Revoke refresh token |

---

## 4. The Validation Pipeline — Stage by Stage

### Stage 1: `intake`

**What it does:**
- Marks the submission as received
- Sets `vendors.sla_due_at = created_at + 48 hours`
- Writes an `audit_events` row (`event_type="pipeline_started"`)
- Runs a **duplicate check** using an OR query across 4 signals:
  1. Same `company_name`
  2. Same `pan_number` (India)
  3. Same `gstin_number` (India)
  4. Same `account_number` AND `ifsc_code` combination
- Matches only against vendors in `approved` or `pending` status
- If found: sets `vendor.is_duplicate = True` and records `duplicate_of_run_id`
- Duplicate is NOT a blocker — the pipeline continues, but it surfaces in the admin dashboard

**DB writes:**
- `pipeline_stage_logs.status = running → completed`
- `vendors.is_duplicate`, `vendors.duplicate_of_run_id` (if applicable)
- `vendors.sla_due_at`
- `audit_events` row

---

### Stage 2: `extract_fields`

**What it does:**
- Builds a normalized `form_data` dict from the vendor DB record
- All India identifiers (CIN, PAN, GSTIN, IFSC) are already normalized to uppercase by Pydantic validators at submission time
- No external calls — pure normalization

---

### Stage 3: `format_check` (Layer 1 — India only)

**What it does:** Runs `run_india_format_checks(form_data)` from `india_validator.py`.
Only runs when `country == "IN"`. For all other countries, this stage is **skipped**.

Checks performed (all deterministic, no LLM):

| Check | What it validates | Fail behavior |
|-------|------------------|---------------|
| `cin_format` | Regex `^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$` | fail |
| `cin_year_vs_incorporation_date` | Year in CIN chars 7–10 vs submitted incorporation date | fail |
| `pan_format` | Regex `^[A-Z]{5}[0-9]{4}[A-Z]{1}$` | fail |
| `pan_checksum` | Standard PAN checksum algorithm (weights [2,4,6,8,10,3,5,7,9]) | warning (not fail) |
| `pan_entity_type` | 4th char: `C`=Company, `F`=Firm, `H`=HUF (pass); `P`=Individual (fail); other = warning | fail / warning |
| `gstin_format` | Regex 15-char pattern `[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]` | fail |
| `gstin_pan_match` | Chars 3–12 of GSTIN must equal submitted PAN | fail |
| `gstin_state_code` | First 2 digits looked up in `INDIA_STATE_CODES` dict | warning if unknown |
| `gstin_state_vs_registered_state` | GSTIN state must fuzzy-match `registered_state` (≥85 score) | fail |
| `ifsc_format` | Regex `^[A-Z]{4}0[A-Z0-9]{6}$` | fail |
| `ifsc_bank_name_match` | First 4 chars of IFSC looked up in `IFSC_BANK_CODES` dict; fuzzy-matched vs `bank_name` | fail / warning if unknown prefix |
| `account_number_format` | Must be 9–18 digits, digits only | fail |
| `account_type` | Must contain "current" (case-insensitive); "savings" = fail | fail |

> **Known bug:** `_extract_cin_year()` uses `cin[6:10]` which returns the 2-letter state code plus the first 2 year digits (e.g., `"KA20"` for `U74140KA2018PTC123456`). `int("KA20")` raises `ValueError`, the function returns `None`, and the `cin_year_vs_incorporation_date` check is silently skipped for all valid CINs. The correct slice is `cin[8:12]`. This is a known defect — no test case currently exercises this check.

Results are written to `validation_results` with `category="format_check"`.

---

### Stage 4: `external_verification` (India only)

**What it does:** Calls `run_external_verifications(form_data)` from `external_api_service.py`.
Only runs substantively for `country == "IN"`. For other countries, stage is **skipped**.

Four external API calls are made (currently mocked for demo; production replaces with real HTTP calls):

| API | What it checks | Failure condition |
|-----|---------------|-------------------|
| **MCA21** (`verify_cin_mca21`) | CIN registered and active in MCA registry | CIN not found or `status != Active` |
| **GST Portal** (`verify_gstin_gst_portal`) | GSTIN active and not cancelled | `status != Active` |
| **RBI IFSC** (`verify_ifsc_rbi`) | IFSC code resolves to a real bank branch | `found == False` |
| **IFSC state cross-check** | Branch state from RBI matches `registered_state` | State mismatch → **warning** (not fail) |
| **Penny drop** (`verify_penny_drop`) | Account number + IFSC combination is valid | Account verification bounces |

Generated check names: `mca21_cin_active`, `gst_portal_gstin_active`, `rbi_ifsc_valid`,
`ifsc_state_vs_registered_state`, `penny_drop_verified`

Results are saved to `validation_results` with `category="external_verification"` AND are
appended to `format_check_results` in memory, so they feed directly into the severity score and
reason codes in the decision stage.

**Mock registry data:**

```python
_MOCK_MCA_ACTIVE_CINS = {
    "U74999DL2024PTC123456",
    "U74999KA2020PTC456789",
    "L85110KA1981PLC013115",
}
# CINs with year part (chars 8–11) ≥ 2020 are also treated as Active.

_MOCK_GST_ACTIVE_GSTINS = {
    "07AABCN1234Q1ZK", "29AABCN1234Q1ZK", "29AAACI1681G1ZK",
}
# Syntactically valid GSTINs not in this set are also treated as Active.

_MOCK_IFSC_REGISTRY = {
    "HDFC0001234": {"bank": "HDFC Bank",  "city": "New Delhi",  "state": "Delhi"},
    "ICIC0004567": {"bank": "ICICI Bank", "city": "Bengaluru",  "state": "Karnataka"},
    "SBIN0011567": {"bank": "SBI",        "city": "New Delhi",  "state": "Delhi"},
    "AXIS0001234": {"bank": "Axis Bank",  "city": "Mumbai",     "state": "Maharashtra"},
    "KKBK0001234": {"bank": "Kotak",      "city": "Mumbai",     "state": "Maharashtra"},
}
# IFSCs not in registry derive bank name from prefix; state/city returned as None.

_MOCK_PENNY_DROP_PASS = {
    ("1234567890", "HDFC0001234"),
    ("0987654321", "ICIC0004567"),
    ("1122334455", "SBIN0011567"),
}
# Unknown combos default to verified=True in mock.
```

---

### Stage 5: `extract_docs` (Layer 2 — OCR + LLM)

**What it does:** For each uploaded document, extracts structured JSON using OCR + LLM.

**Sub-process per document:**

```
file_bytes
    │
    ▼
ocr_service.extract_text(file_bytes, filename)
    ├── If image (jpg/png): Tesseract directly
    └── If PDF:
         ├── pdfplumber (native text extraction)
         └── If <100 chars extracted → fallback to pdf2image + Tesseract at 300 DPI
    │
    ▼  raw text string
    │
extractor.extract_document(file_bytes, filename, doc_type, country)
    │
    ├── Route to correct system prompt:
    │    ├── (IN, coi)        → INDIA_COI_EXTRACTION_PROMPT
    │    ├── (IN, pan_gstin)  → INDIA_PAN_GSTIN_EXTRACTION_PROMPT
    │    ├── (IN, bank_letter/bank) → INDIA_BANK_EXTRACTION_PROMPT
    │    └── anything else    → DOCUMENT_EXTRACTION_PROMPT (generic)
    │
    ▼
LLM call (Groq Llama-3.3-70b or Claude Sonnet)
    → returns structured JSON (may include internal metadata keys starting with "_")
    │
    ▼
document.extracted_json = {...}   (saved to DB)
```

**OCR Quality Assessment** (after all docs extracted):

The extractor may return internal metadata fields in the JSON:

| Metadata key | Meaning |
|--------------|---------|
| `_doc_type_mismatch` | `True` if LLM detected the wrong document type was uploaded |
| `_detected_type` | What the LLM thinks the document actually is |
| `_quality_score` | Float 0–1: fraction of critical fields successfully extracted |
| `_low_confidence_fields` | List of field names where extraction was uncertain |

OCR scoring logic (priority order):

| Condition | `ocr_status` | Action |
|-----------|--------------|--------|
| `_doc_type_mismatch == True` | `failed` | Email vendor: "wrong document type" |
| 0 non-metadata non-empty fields | `failed` | Email vendor: "document unreadable" |
| `_quality_score < 0.5` | `partial` | Email vendor: "critical fields missing" |
| fewer than 2 non-empty fields | `partial` | Email vendor: "poor quality" |
| otherwise | `success` | Continue |

`document.quality_score` is persisted to the DB from `_quality_score` if present.

If any doc is `failed` or `partial`, an OCR failure email is sent to `contact_email`, but the pipeline **continues** — it does not abort.

---

### Stage 6: `cross_doc_check` (Layer 3 — India only)

**What it does:** Runs `run_india_cross_doc_checks(form_data, extracted_docs)`. Only runs when
`country == "IN"` and at least one document was successfully extracted.

See [Section 6](#6-india-validation-deep-dive) for the full breakdown.

---

### Stage 7: `merge`

**What it does:** Assembles `merged_data` from form data + extracted docs + all check results and saves it to `vendors.merged_data`. This is the single source of truth passed to all downstream checks.

---

### Stage 8: `check_completeness`

**What it does:** Rule-based check that all required fields and documents are present.

**For India** (`_check_completeness_india`):

Required fields: `company_name`, `country`, `incorporation_date`, `contact_name`, `contact_email`, `cin_number`, `pan_number`, `gstin_number`, `ifsc_code`, `account_type`, `registered_state`, `bank_account_name`, `account_number`, `bank_name`, `bank_country`

Required documents: `coi` (or `registration`), `pan_gstin` (or `tax_cert`), `bank_letter` (or `bank`)

**For non-India** (`_check_completeness_generic`):

Required fields: `company_name`, `registration_number`, `country`, `incorporation_date`, `contact_name`, `contact_email`, `bank_account_name`, `account_number`, `bank_name`, `bank_country`

Extra checks: Tax ID format validation (country-specific regex), IBAN validation via `schwifty`, bank account name vs company name match.

Required documents: `registration`, `bank_letter`, `tax_cert`

**Short-circuit:** If any `doc_*` check has `status=missing`, the pipeline skips consistency + credibility stages and jumps directly to `decide` with a `pending` result. This avoids expensive LLM calls when documents are simply absent.

---

### Stage 9: `check_consistency`

**What it does:** Sends the form data and all extracted document JSON to the LLM to identify mismatches between what the vendor typed and what the documents actually contain.

**LLM prompt** (`CONSISTENCY_CHECK_PROMPT`): Compares `company_name`, `registration_number`, `tax_id`, `bank_account_name`, and `country` between form and docs.

**LLM returns** a JSON array of results with statuses: `match` | `partial_match` | `mismatch` | `unverifiable`.

Note: For India, deterministic cross-doc checks already caught hard mismatches in Layer 3. This stage adds semantic reasoning (e.g. "Nexova Technologies Pvt Ltd" vs "NEXOVA TECHNOLOGIES PRIVATE LIMITED" → `partial_match`).

---

### Stage 10: `check_credibility`

**What it does:** Sends the entire `merged_data` plus all prior deterministic check results to the LLM for fraud signal analysis.

**LLM prompt** (`CREDIBILITY_CHECK_PROMPT`) asks the model to evaluate:
1. Geographic inconsistencies (company country ≠ bank country)
2. Very recently incorporated companies (<6 months)
3. Name mismatches across sources
4. Suspicious patterns in registration/tax IDs
5. Implausible data combinations
6. Email domain mismatch with company name
7. Generic/template-looking documents

**LLM returns:**
```json
{
  "risk_level": "low | medium | high",
  "flags": [
    { "signal": "bank_country_mismatch", "severity": "high | medium | low", "description": "..." }
  ],
  "reasoning": "..."
}
```

`vendors.risk_level` is set from this result. Each flag with `severity == "high"` or `"medium"` is stored as a `fail` validation result (category `"credibility"`).

---

### Stage 11: `decide`

**What it does:** Pure deterministic logic in `make_decision()`. No LLM.

See [Section 7](#7-decision-engine-logic) for the full decision tree and severity scoring.

---

### Stage 12: `output`

**What it does:**
1. Calls LLM (Groq) to generate a human-readable `decision_summary` (≤200 words)
2. Sets `vendors.status` to the final value
3. Sets `vendors.decided_at` and `vendors.pipeline_duration_ms`
4. Sends email based on outcome:
   - `pending` → Pending email. **Primary path**: deterministic `render_pending_email()` from reason codes. Fallback: LLM-generated if no reason codes.
   - `rejected` → Neutral decline email (LLM-generated, no mention of fraud)
   - `approved` → No email currently

---

### Stage 13: `done`

Pipeline complete. `pipeline_stage_logs` row marked `completed`. Frontend SSE stream closes.

---

## 5. OCR Layer — How Text Is Extracted from Documents

```
extract_text(file_bytes, filename)
│
├── Extension = jpg / jpeg / png
│   └── extract_text_from_image()
│       └── PIL.Image.open() → pytesseract.image_to_string()
│
└── Extension = pdf
    ├── extract_text_from_pdf_native()
    │   └── pdfplumber.open() → page.extract_text() for each page
    │       → join all pages with spaces
    │
    └── If len(native_text) < 100 chars:
        └── extract_text_from_pdf_ocr()
            └── pdf2image.convert_from_bytes(dpi=300)
                → pytesseract.image_to_string() per page
                → join all pages
```

**Why the 100-char threshold?** A native PDF with embedded text (generated PDF like a bank statement) will yield thousands of characters. A scanned PDF (photo of a physical document wrapped in a PDF container) yields fewer than 100 chars from native extraction. This automatically distinguishes the two types.

**Metadata fields injected by extractor into `extracted_json`:**

```python
{
  # ... real extracted fields ...
  "_quality_score": 0.85,           # fraction of critical fields found
  "_low_confidence_fields": ["cin_number"],  # fields the LLM wasn't confident about
  "_doc_type_mismatch": False,       # True if wrong document type detected
  "_detected_type": "bank_letter",  # what the LLM thinks it actually is
}
```

Pipeline code strips `_`-prefixed keys before counting non-empty fields and before passing data downstream.

---

## 6. India Validation Deep Dive

India has three distinct validation layers that run sequentially.

### 6.1 Layer 1 — Format Checks (`format_check` stage)

Pure Python/regex + one checksum algorithm. No external calls. Runs before any document processing.

**GSTIN ↔ PAN cross-check (deterministic):**

```
GSTIN: 27AABCT3518Q1ZK
         ^^             → state code "27" = Maharashtra
           AABCT3518Q   → embedded PAN (chars index 2–11)
                     1  → entity number
                      Z → always Z (GST network constant)
                       K → checksum character

PAN submitted: AABCT3518Q
Embedded PAN:  AABCT3518Q  ✓ MATCH → check: gstin_pan_match = PASS
State code 27 = Maharashtra, registered_state = "Maharashtra" ✓ MATCH
```

**PAN checksum algorithm:**

```python
weights = [2, 4, 6, 8, 10, 3, 5, 7, 9]
char_val = lambda c: ord(c) - ord('A') if c.isalpha() else int(c)
total = sum(char_val(pan[i]) * weights[i] for i in range(9))
expected_checkchar = chr(ord('A') + (total % 26))
# pan[9] must equal expected_checkchar
```

A checksum failure produces a **warning**, not a fail (to avoid rejecting vendors who transposed a digit — a manual review signal, not an automatic block).

**Account number validation:** 9–18 digits, digits only. Spaces are stripped before checking.

**IFSC ↔ Bank name cross-check:**

```
IFSC: HDFC0000007
First 4 chars: HDFC → lookup in IFSC_BANK_CODES → "HDFC Bank"
bank_name submitted: "HDFC Bank"
Fuzzy match (rapidfuzz token_sort_ratio): score=100 ≥ 85 → PASS
```

`IFSC_BANK_CODES` contains 50+ entries including domestic banks, co-operative banks, and foreign bank branches (DBS, Citibank, HSBC, Deutsche Bank, etc.).

### 6.2 Layer 2 — OCR Extraction (`extract_docs` stage)

The LLM is given the OCR-extracted text and a highly specific system prompt for each document type.

**India COI extraction prompt** targets:
`entity_name`, `cin_number`, `registration_number`, `incorporation_date`, `registered_state`, `company_type`, `issuing_authority`, `document_date`

**India PAN+GSTIN extraction prompt** targets:
`entity_name`, `pan_number`, `entity_type`, `gstin_number`, `state_jurisdiction`, `gstin_registration_date`, `tax_id`

**India Bank extraction prompt** targets:
`account_holder_name`, `account_name`, `account_number`, `ifsc_code`, `bank_name`, `branch_name`, `account_type`, `micr_code`

### 6.3 Layer 3 — Cross-Document Checks (`cross_doc_check` stage)

Compares extracted document data against each other and against the submitted form. All deterministic. Uses **rapidfuzz `token_sort_ratio`** for name comparisons (threshold: 85).

**Full check matrix for India:**

| Check | Source A | Source B | Match logic |
|-------|----------|----------|-------------|
| `company_name_vs_coi` | form: `company_name` | COI: `entity_name` | `_names_match()` fuzzy ≥85 |
| `company_name_vs_pan_gstin_doc` | form: `company_name` | PAN doc: `entity_name` | same |
| `company_name_vs_bank_doc` | form: `company_name` | Bank: `account_holder_name` | same |
| `coi_vs_pan_doc_name` | COI: `entity_name` | PAN doc: `entity_name` | direct doc-to-doc fuzzy |
| `coi_vs_bank_name` | COI: `entity_name` | Bank: `account_holder_name` | direct doc-to-doc fuzzy |
| `pan_vs_bank_name` | PAN doc: `entity_name` | Bank: `account_holder_name` | direct doc-to-doc fuzzy |
| `cin_coi_vs_form` | COI: `cin_number` | form: `cin_number` | exact after normalize |
| `pan_doc_vs_form` | PAN doc: `pan_number` | form: `pan_number` | exact after normalize |
| `gstin_doc_vs_form` | PAN doc: `gstin_number` | form: `gstin_number` | exact after normalize |
| `gstin_embedded_pan_vs_pan_doc` | GSTIN doc: chars 3–12 | PAN doc: `pan_number` | exact — catches docs from different entities |
| `gstin_date_vs_incorporation_date` | PAN doc: `gstin_registration_date` | COI/form: `incorporation_date` | GST date must be ≥ incorporation date |
| `ifsc_doc_vs_form` | Bank doc: `ifsc_code` | form: `ifsc_code` | exact after normalize |
| `micr_ifsc_consistency` | Bank doc: `micr_code` | — | first 3 digits of MICR must not be "000" |
| `account_type_doc_check` | Bank doc: `account_type` | — | must contain "current" |

**The `_names_match()` function:**

```python
from rapidfuzz import fuzz

NAME_FUZZY_THRESHOLD = 85  # token_sort_ratio threshold

def _names_match(name1: str, name2: str) -> tuple[bool, float]:
    score = fuzz.token_sort_ratio(name1.upper(), name2.upper())
    return score >= NAME_FUZZY_THRESHOLD, score
```

`token_sort_ratio` sorts tokens alphabetically before comparing:
```
"NEXOVA TECHNOLOGIES PRIVATE LIMITED" → sorted: "LIMITED NEXOVA PRIVATE TECHNOLOGIES"
"NEXOVA TECH PVT LTD"                 → sorted: "LTD NEXOVA PVT TECH"
score ≈ 80 → below threshold → MISMATCH
```

Versus exact-match after stripping suffixes (old approach), fuzzy matching catches OCR artifacts
(`NEXDVA` vs `NEXOVA`, score ≈88 → PASS) while still rejecting clear name mismatches.

### 6.4 External API Verification (`external_verification` stage)

See [Stage 4](#stage-4-external_verification-india-only) for the full breakdown.

The `external_api_service.py` module provides four verifier functions:

```
verify_cin_mca21(cin)          → checks MCA21 registry
verify_gstin_gst_portal(gstin) → checks GST portal
verify_ifsc_rbi(ifsc)          → branch lookup + state cross-check
verify_penny_drop(account_number, ifsc, account_name)  → account validation

run_external_verifications(form_data)  → runs all four, returns {"api_results": {...}, "checks": [...]}
```

In production, each function replaces its mock HTTP call with the real API endpoint. The rest of the pipeline is unaffected — it only sees the normalized `checks` list.

---

## 7. Decision Engine Logic

`make_decision()` in `decision.py` — pure Python, no LLM.

### 7.1 Decision Tree

```
Inputs:
  completeness_results  (includes format_check + external_verification results)
  consistency_results   (LLM output)
  credibility_result    { risk_level, flags }

Decision tree (evaluated in order, first match wins):

1. risk_level == "high"  OR  ≥1 high-severity fraud flag
   → REJECTED  (hard rejection, no threshold needed)

2. severity_score ≥ REJECTION_THRESHOLD (25)
   → REJECTED  (too many accumulated problems)

3. Any missing docs, missing fields, format failures, or consistency failures
   → PENDING  (with reason_codes listing exactly what to fix)

4. All checks pass
   → APPROVED
```

### 7.2 Severity Score Formula

```python
REJECTION_THRESHOLD = 25

score = 0
score += 10 * len(missing_docs)           # doc_* checks with status=missing
score += 8  * len(format_failures)        # non-doc/field checks with status=fail
score += 6  * len(structural_fails)       # all_checks fail (not doc_ or field_ prefixed)
score += 8  * len(consistency_failures)   # consistency checks with status=mismatch
score += 3  * len(consistency_warnings)   # consistency checks with status=partial_match
score += 15 * (1 if risk_level == "medium" else 0)
score += 25 * len(high_flags)             # credibility flags severity=high
score += 8  * len(medium_flags)           # credibility flags severity=medium
```

Note: A failing format check (e.g. `gstin_pan_match`) contributes both to `format_failures`
(+8) and to `structural_fails` (+6), for **14 pts per format failure**. This means:
- 1 format failure = 14 pts → PENDING
- 2 format failures = 28 pts → REJECTED

### 7.3 Reason Codes

Every `pending` decision carries a `reason_codes` list mapping to the `REASON_CODES` dict:

```python
REASON_CODES: Dict[str, tuple[str, int]] = {
    "MISSING_COI":              ("Please upload your Certificate of Incorporation (COI).", 10),
    "MISSING_PAN_GSTIN":        ("Please upload your PAN Card and GSTIN Certificate.", 10),
    "MISSING_BANK_LETTER":      ("Please upload a bank account verification letter or cancelled cheque.", 10),
    "SAVINGS_ACCOUNT":          ("A Current Account is required for vendor payments.", 8),
    "GSTIN_PAN_MISMATCH":       ("The PAN embedded in your GSTIN does not match your submitted PAN.", 8),
    "GSTIN_STATE_MISMATCH":     ("The GSTIN state code does not match your registered state.", 8),
    "CIN_YEAR_MISMATCH":        ("The incorporation year in your CIN does not match your stated incorporation date.", 8),
    "PAN_ENTITY_INDIVIDUAL":    ("Business vendors must submit a Company (C), Firm (F), or HUF (H) PAN.", 8),
    "PAN_CHECKSUM_INVALID":     ("Your PAN may contain a typo — checksum validation failed.", 5),
    "BANK_NAME_MISMATCH":       ("The bank name does not match the bank indicated by your IFSC code.", 8),
    "ACCOUNT_NUMBER_INVALID":   ("Bank account number must be 9–18 digits.", 8),
    "COMPANY_NAME_COI_MISMATCH":("Company name on COI does not match your submitted name.", 10),
    "COMPANY_NAME_PAN_MISMATCH":("Company name on PAN document does not match your submitted name.", 8),
    "COMPANY_NAME_BANK_MISMATCH":("Bank account holder name does not match your company name.", 8),
    "GSTIN_DATE_BEFORE_INCORPORATION": ("GST registration date is earlier than incorporation — not possible.", 10),
    "COI_VS_PAN_NAME_MISMATCH": ("Name on COI does not match name on PAN document.", 10),
    "COI_VS_BANK_NAME_MISMATCH":("Name on COI does not match bank account holder name.", 10),
    "PAN_VS_BANK_NAME_MISMATCH":("PAN entity name does not match bank account holder name.", 8),
    "IFSC_FORMAT_INVALID":      ("Your IFSC code format is invalid.", 8),
    "OCR_FAILURE":              ("One or more documents could not be read.", 8),
    "PARTIAL_EXTRACTION":       ("Some required information could not be extracted from your documents.", 5),
    "DOC_TYPE_MISMATCH":        ("One or more documents appears to be the wrong type.", 10),
    "DATA_CONSISTENCY_ISSUES":  ("Multiple data inconsistencies between form and documents.", 8),
    "ACCOUNT_TYPE_MISSING":     ("Account type is required. Please specify 'Current Account'.", 8),
    "CIN_FORMAT_INVALID":       ("Your CIN has an invalid format.", 8),
    "GSTIN_FORMAT_INVALID":     ("Your GSTIN has an invalid format.", 8),
    "MISSING_REQUIRED_FIELDS":  ("One or more required fields are missing.", 5),
    "FOREIGN_BANK_ACCOUNT":     ("Indian company requires an Indian bank account.", 8),
}
```

`CHECK_TO_REASON` maps validation result check names → reason code strings. `_collect_reason_codes()` iterates all `fail` and `missing` results and builds a deduplicated ordered list.

### 7.4 Pending Email Generation

```python
def generate_pending_email(vendor_name, contact_email, issues, reason_codes=None):
    if reason_codes:
        return render_pending_email(vendor_name, reason_codes)  # deterministic, no LLM
    # LLM fallback when no reason codes
    return call_llm(PENDING_EMAIL_PROMPT, ...)
```

`render_pending_email()` builds a numbered action-item list from reason codes:
```
Dear NEXOVA TECHNOLOGIES PRIVATE LIMITED,

Thank you for submitting your vendor onboarding application.

After reviewing your submission, we require the following to be addressed:

1. The PAN number embedded in your GSTIN does not match your submitted PAN number.
2. The GSTIN state code does not match your registered state.

To resubmit, please visit the vendor onboarding portal and use the "Resubmit Application"
button on your status page. ...
```

**Why prefer reason_codes over LLM?** Deterministic output, no API cost, fully testable,
and the messages are pre-approved for the specific issue rather than improvised.

---

## 8. LLM Usage Map

| Stage | LLM Call | Provider | Model | Purpose |
|-------|----------|----------|-------|---------|
| `extract_docs` | `call_llm_json()` | Groq (default) | `llama-3.3-70b-versatile` | Extract fields from OCR text |
| `check_consistency` | `call_llm_json()` | Groq | Llama-3.3-70b | Compare form vs doc fields |
| `check_credibility` | `call_llm_json()` | Groq | Llama-3.3-70b | Fraud/risk analysis |
| `output` | `call_llm()` | Groq | Llama-3.3-70b | Generate decision summary |
| `output` | `call_llm()` | Groq | Llama-3.3-70b | Generate pending email (fallback only — primary path is deterministic) |
| `output` | `call_llm()` | Groq | Llama-3.3-70b | Generate rejection email |

**Provider switching:** Set `LLM_PROVIDER=anthropic` in `.env` to use Claude Sonnet instead of Groq. All prompts are provider-agnostic.

**Temperature:** Groq calls use `temperature=0.1` to keep extraction deterministic.

**JSON safety:** `_safe_json_parse()` strips markdown code fences (` ```json `) before parsing.

---

## 9. Auth System (JWT)

### Token Design

| Token | Cookie | httpOnly | Expiry | Purpose |
|-------|--------|----------|--------|---------|
| Admin access | `admin_access_token` | No (readable by JS) | 15 min | Bearer auth to backend API |
| Admin refresh | `admin_refresh_token` | Yes | 7 days | Token rotation |
| Vendor access | `vendor_access_token` | No | 15 min | Bearer auth to backend API |
| Vendor refresh | `vendor_refresh_token` | Yes | 7 days | Token rotation |

JWT payload:
```json
{ "sub": "admin", "role": "admin", "type": "access", "exp": 1779803723 }
```

### Refresh Token Rotation

Every time a refresh token is used, the old one is immediately revoked in `refresh_tokens` table and a new pair is issued. Re-using a revoked token returns `401 Refresh token revoked`. Tokens are stored as SHA-256 hashes — the raw JWT is never stored.

### Vendor Authentication

Vendors log in with `{ email, run_id }`. The backend verifies that a `vendors` row exists with both `contact_email = email` AND `run_id = run_id`. This proves the vendor owns the submission (they received the run_id by email). The resulting JWT's `sub` is the vendor's email, giving access to all submissions for that email via `GET /api/submissions/mine`.

### Middleware Flow (Next.js)

```
Request to /dashboard/* or /runs/*
    │
    ├── Read admin_access_token cookie
    ├── jwtVerify(token, JWT_SECRET)
    │   ├── Valid → NextResponse.next()
    │   └── Invalid/expired →
    │       ├── Read admin_refresh_token cookie
    │       ├── POST http://localhost:8000/api/auth/admin/refresh
    │       │   ├── Success → set new cookies → NextResponse.next()
    │       │   └── Fail → clear cookies → redirect /admin/login
    │       └── No refresh token → redirect /admin/login
```

The frontend `apiRequest()` helper reads `admin_access_token` or `vendor_access_token` from
cookies and sends it as `Authorization: Bearer <token>`. On 401, it calls
`/api/auth/{role}/refresh` via the Next.js API route (which proxies to the backend), then retries
once.

---

## 10. End-to-End Walkthrough — India Vendor Submission

**Scenario:** Nexova Technologies submits their vendor application.

### Step 1: Form Submission

```
POST /api/submissions  (multipart/form-data)

Form data:
  company_name: "NEXOVA TECHNOLOGIES PRIVATE LIMITED"
  country: "IN"
  cin_number: "U72200MH2015PTC267736"
  pan_number: "AABCT3518Q"
  gstin_number: "27AABCT3518Q1ZK"
  ifsc_code: "HDFC0000007"
  bank_name: "HDFC Bank"
  account_type: "Current Account"
  registered_state: "Maharashtra"
  bank_account_name: "NEXOVA TECHNOLOGIES PRIVATE LIMITED"
  account_number: "50200045678901"
  incorporation_date: "2015-03-15"
  contact_email: "priya@nexovatech.in"

Files:
  registration_doc: india_coi.pdf
  pan_gstin_doc:    india_pan_gstin.pdf
  bank_doc:         india_bank_letter.pdf

HTTP Response (immediate):
  { "run_id": "vnd_20260526_a3f9b1c2", "message": "Submission received." }
```

---

### Step 2: intake stage

```
sla_due_at = created_at + 48h
audit_events: pipeline_started

Duplicate check (OR query):
  company_name = 'NEXOVA TECHNOLOGIES PRIVATE LIMITED'
  OR pan_number = 'AABCT3518Q'
  OR gstin_number = '27AABCT3518Q1ZK'
  OR (account_number = '50200045678901' AND ifsc_code = 'HDFC0000007')
  AND status IN ('approved', 'pending') AND id != <this vendor>
→ No rows found → is_duplicate = False
```

---

### Step 3: extract_fields stage

Form data normalized. No external calls.

---

### Step 4: format_check stage

```
cin_format               pass  — "U72200MH2015PTC267736" matches pattern
pan_format               pass  — "AABCT3518Q" matches pattern
pan_checksum             pass  — checksum char 'Q' is valid
pan_entity_type          pass  — 4th char 'C' = Company
gstin_format             pass  — "27AABCT3518Q1ZK" matches 15-char pattern
gstin_pan_match          pass  — embedded "AABCT3518Q" = submitted PAN
gstin_state_code         pass  — "27" = Maharashtra
gstin_state_vs_registered_state  pass  — Maharashtra = Maharashtra
ifsc_format              pass  — "HDFC0000007" matches pattern
ifsc_bank_name_match     pass  — prefix "HDFC" = HDFC Bank, matches stated bank
account_number_format    pass  — 14 digits, within 9–18 range
account_type             pass  — "Current Account"
```

---

### Step 5: external_verification stage

```
MCA21:
  CIN "U72200MH2015PTC267736" — not in mock registry, year=2015 < 2020 → Not Found
  check: mca21_cin_active = fail
  (In production this would confirm active status)

GST Portal:
  GSTIN "27AABCT3518Q1ZK" — not in mock registry but syntactically valid → Active
  check: gst_portal_gstin_active = pass

RBI IFSC:
  IFSC "HDFC0000007" — not in mock IFSC_REGISTRY, derives bank from prefix "HDFC"
  check: rbi_ifsc_valid = pass  — "HDFC0000007 verified — HDFC Bank"
  ifsc_state_vs_registered_state: state=None (unknown branch) → not evaluated

Penny drop:
  ("50200045678901", "HDFC0000007") not in mock pass set → defaults to verified=True
  check: penny_drop_verified = pass
```

---

### Step 6: extract_docs stage

Each of the 3 PDFs is OCR'd then LLM-extracted:
- COI → `{entity_name, cin_number, incorporation_date, registered_state, ...}` → success (7 fields)
- PAN+GSTIN → `{entity_name, pan_number, gstin_number, gstin_registration_date, ...}` → success (6 fields)
- Bank letter → `{account_holder_name, account_number, ifsc_code, bank_name, account_type, ...}` → success (7 fields)

No OCR failure email sent.

---

### Step 7: cross_doc_check stage

```
company_name_vs_coi              pass  — "NEXOVA TECHNOLOGIES PVT LTD" score=92
company_name_vs_pan_gstin_doc    pass  — score=100
company_name_vs_bank_doc         pass  — score=100
coi_vs_pan_doc_name              pass  — score=100
coi_vs_bank_name                 pass  — score=100
pan_vs_bank_name                 pass  — score=100
cin_coi_vs_form                  pass  — "U72200MH2015PTC267736" exact match
pan_doc_vs_form                  pass  — "AABCT3518Q" exact match
gstin_doc_vs_form                pass  — "27AABCT3518Q1ZK" exact match
gstin_embedded_pan_vs_pan_doc    pass  — embedded "AABCT3518Q" = PAN doc
gstin_date_vs_incorporation_date pass  — GSTIN registered 2017-04-01 ≥ inc 2015-03-15
ifsc_doc_vs_form                 pass  — "HDFC0000007" exact match
account_type_doc_check           pass  — bank doc confirms Current Account
```

---

### Step 8–10: merge, completeness, consistency, credibility

All checks pass. `risk_level = "low"`. No flags.

---

### Step 11: decide stage

```
severity_score = 0
risk_level = "low"
high_severity_flags = []
→ Decision: APPROVED
```

---

### Step 12: output stage

LLM generates decision summary. `vendors.status = approved`. No email sent.

---

## 11. Edge Cases & How They Are Handled

### Individual PAN Submitted (4th char = 'P')

```
format_check: pan_entity_type = fail
reason_code: PAN_ENTITY_INDIVIDUAL
severity += 14 (8 format + 6 structural)
→ make_decision(): severity=14 < 25 → PENDING
→ pending email: "Business vendors must submit a Company (C), Firm (F), or HUF (H) PAN."
```

### GSTIN Belongs to a Different Entity

```
gstin: 27XXXXX0000Y1ZK  (belongs to Company X)
pan:   AABCT3518Q       (belongs to Nexova)

format_check: gstin_pan_match = fail → 14 pts
reason_code: GSTIN_PAN_MISMATCH
→ PENDING (score < 25)
```

### Two Format Failures (e.g. GSTIN/PAN mismatch + GSTIN state mismatch)

```
format_check: gstin_pan_match = fail       → 14 pts
format_check: gstin_state_vs_registered_state = fail  → 14 pts
total: 28 pts ≥ 25
→ REJECTED (severity threshold exceeded)
```

### Savings Account Submitted

```
format_check: account_type = fail          → 14 pts

If bank doc also extracted:
cross_doc_check: account_type_doc_check = fail  → additional structural fail

→ If both: at least 14 + 6 = 20 pts + possible format fail = likely REJECTED
→ If only form: 14 pts → PENDING with reason SAVINGS_ACCOUNT
```

### IFSC Code Doesn't Match the Bank Name

```
IFSC: ICIC0000041  (ICICI Bank)
bank_name: "HDFC Bank"

format_check: ifsc_bank_name_match = fail (fuzzy score < 85)
reason_code: BANK_NAME_MISMATCH
→ 14 pts → PENDING
```

### High Risk Score from LLM

```
Company country: IN
Bank country: AE (UAE)

credibility:
  risk_level: "high"
  flags: [{ signal: "bank_country_mismatch", severity: "high" }]

make_decision(): risk_level == "high" → immediate REJECTED
(no threshold needed, hard rejection)
```

### Single High-Severity Fraud Flag

```
credibility:
  risk_level: "medium"
  flags: [{ signal: "very_recently_incorporated", severity: "high" }]

make_decision(): len(high_severity_flags) >= 1 → REJECTED
(changed from ≥2 high flags in prior version — now a single high flag is enough)
```

### OCR Fails on a Document

The pipeline does **not abort**. The document gets `ocr_status="failed"`, an email goes to the vendor, and the pipeline continues with empty extracted data for that document. This means:
- Layer 3 cross-doc checks have less data → fewer results
- LLM consistency check sees empty doc data → marks checks as `unverifiable`
- Decision depends on other checks — likely `pending` due to effective missing doc data

### Wrong Document Uploaded in Wrong Slot

```
extract_docs: LLM detects _doc_type_mismatch=True, _detected_type="bank_letter"
  (vendor uploaded bank letter in the COI slot)

ocr_status = "failed"
ocr_issues = ["Wrong document type: expected coi but this appears to be a 'bank_letter'. 
               Please upload the correct document."]

Email sent to vendor. Pipeline continues. Completeness check will mark doc_coi as missing.
→ PENDING (missing_documents: [coi])
reason_code: DOC_TYPE_MISMATCH
```

### Duplicate Submission

```
Same PAN already exists with status=approved.

intake: is_duplicate = True, duplicate_of_run_id = "vnd_20260510_xyz"
Pipeline continues normally (does not short-circuit).
Admin dashboard shows the duplicate flag.
Decision is made on the new submission's own merits.
```

### Resubmission

```
POST /api/submissions/{original_run_id}/resubmit

New vendor row created:
  version_number = 2
  original_run_id = "vnd_20260510_xyz" (shared with v1)

Full pipeline runs again from scratch on the new data.
All documents must be re-uploaded.
```

### Pipeline Crash Mid-Run

On startup, `main.py` lifespan function queries for vendors with `status=processing`
where no stage has `status=running or completed`. These are fully orphaned and
marked `status=error`.

Partially-completed pipelines remain in `processing` state — not automatically recovered.
The vendor must resubmit.

### Missing Documents (Short-Circuit)

```
completeness: doc_coi = missing, doc_pan_gstin = missing

make_decision():
  missing_docs = [doc_coi, doc_pan_gstin]
  severity = 10 + 10 = 20 (< 25, so not score-rejected)
  → PENDING (missing_documents: [coi, pan_gstin])
  reason_codes: [MISSING_COI, MISSING_PAN_GSTIN]

_finalize() called directly — consistency and credibility stages SKIPPED.
Saves 3 LLM calls when the vendor simply forgot to upload files.
```

### Scanned PDF (No Embedded Text)

```
pdfplumber extraction: "   " (2 chars — just whitespace)
len < 100 → fallback to pdf2image + Tesseract at 300 DPI
→ OCR text extracted at pixel level → passed to LLM for field extraction
```

---

*This document reflects the codebase as of May 2026. All pipeline logic lives in `backend/app/services/`. India validation rules live in `backend/app/services/india_validator.py`. External API mocks live in `backend/app/services/external_api_service.py`. Decision engine (severity scoring, reason codes) lives in `backend/app/services/decision.py`.*
