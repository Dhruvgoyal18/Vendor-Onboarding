# Implementation Plan — As Built

> This document reflects what was actually implemented as of May 2026.
> It serves as a reference for what each layer does and the order it was built.

---

## Phase 1 — Core Submission Flow

### 1.1 Database Schema

Tables created in `supabase/schema.sql`:

- `vendors` — core submission record with all form fields, status, SLA, risk level, merged data
- `documents` — one row per uploaded file with OCR results and extracted JSON
- `validation_results` — per-check results (pass/fail/warning) across all pipeline stages
- `pipeline_stage_logs` — per-stage timing and status
- `refresh_tokens` — hashed JWT refresh tokens for rotation
- `email_logs` — audit log of every email attempted
- `audit_events` — immutable event log
- `llm_cache` — deduplication cache for LLM calls
- `country_configs` — per-country required fields, docs, SLA hours

### 1.2 Backend Submission Endpoint

`POST /api/submissions` (multipart/form-data):
- Accepts JSON `data` field + up to 4 file fields
- Creates `vendors` row with `status=processing`
- Creates `documents` rows (one per file) with `ocr_status=unknown`
- Kicks off `run_pipeline(vendor_id)` as a `BackgroundTask`
- Returns `{ run_id, message }` immediately

### 1.3 Pipeline Orchestrator

`services/pipeline.py` — `run_pipeline()`:
- Runs all 13 stages sequentially
- Each stage calls `_update_stage(stage_name, status, message)`
- SSE event pushed after each stage update
- `_finalize()` sets terminal status and timestamps
- On unhandled exception: `vendors.status = "error"`

---

## Phase 2 — Validation Engine

### 2.1 India Format Checks (`services/india_validator.py`)

All deterministic, no LLM. Runs at `format_check` stage:

- CIN format regex + year extraction check
- PAN format regex + checksum algorithm + entity type check
- GSTIN format regex + PAN embedding check + state code check + fuzzy state-vs-registered_state
- IFSC format regex + bank name fuzzy match via `IFSC_BANK_CODES` dict
- Account number (9–18 digits) + account type (must be Current)

Known defect: `_extract_cin_year()` uses wrong slice `cin[6:10]` instead of `cin[8:12]`, causing silent skip of `cin_year_vs_incorporation_date` for all valid CINs.

### 2.2 External API Verification (`services/external_api_service.py`)

India only. Currently mocked for demo; replace each function body with real HTTP calls for production:

- `verify_cin_mca21(cin)` — checks MCA21 registry
- `verify_gstin_gst_portal(gstin)` — checks GST portal
- `verify_ifsc_rbi(ifsc)` — RBI IFSC branch lookup + state check
- `verify_penny_drop(account_number, ifsc, account_name)` — bank account validation

### 2.3 OCR Service (`services/ocr_service.py`)

- PDF: `pdfplumber` native extraction first
- If `< 100 chars` extracted: fallback to `pdf2image` + Tesseract at 300 DPI
- Images (JPG/PNG): Tesseract directly
- Returns raw text string

### 2.4 Document Extractor (`services/extractor.py`)

- Takes OCR text + doc_type + country
- Routes to country+type specific system prompt from `prompts/templates.py`
- Calls LLM via `llm_service.call_llm_json()`
- Returns JSON with fields + metadata keys (`_quality_score`, `_doc_type_mismatch`, etc.)
- Quality assessment logic classifies `ocr_status` as `success | partial | failed`

### 2.5 India Cross-Document Checks (`services/india_validator.py`)

13-check matrix at `cross_doc_check` stage:
- Company name from form vs each document's entity name (fuzzy ≥ 85)
- Entity name cross-doc comparisons (COI vs PAN, COI vs Bank, PAN vs Bank)
- CIN, PAN, GSTIN exact match between form and respective document
- GSTIN embedded PAN chars vs PAN doc (catches mismatched entities)
- GSTIN registration date ≥ incorporation date
- IFSC exact match form vs bank doc
- MICR code sanity check

### 2.6 Completeness Check (`services/validator.py`)

Two paths:
- `_check_completeness_india()` — checks 15 required fields + 3 required doc groups
- `_check_completeness_generic()` — checks 10 required fields + 3 required doc groups + IBAN validation

Short-circuit: if any doc is missing → skip consistency + credibility → go straight to `decide`.

### 2.7 Consistency Check (`services/validator.py`)

LLM call with `CONSISTENCY_CHECK_PROMPT`. Compares form fields vs extracted doc data. Returns array of `{field, status, form_value, doc_value, detail}` with statuses `match | partial_match | mismatch | unverifiable`.

### 2.8 Credibility Check (`services/validator.py`)

LLM call with `CREDIBILITY_CHECK_PROMPT`. Analyzes all merged_data for fraud signals. Returns `{risk_level, flags, reasoning}`. Each high/medium flag is stored as a `fail` validation_result.

---

## Phase 3 — Decision Engine (`services/decision.py`)

Fully deterministic. No LLM.

### Severity Score

```
+10 per missing document
+8  per format failure
+6  per structural failure
+8  per consistency mismatch
+3  per partial match
+15 if risk_level = medium
+25 per high fraud flag
+8  per medium fraud flag
```

### Decision Tree

```
1. high risk or high fraud flag  →  REJECTED
2. score ≥ 25                    →  REJECTED
3. any missing/fail checks       →  PENDING + reason_codes
4. all clear                     →  APPROVED
```

### Reason Codes

27 named reason codes with human-readable fix instructions. Primary pending email is rendered deterministically from these codes — no LLM cost.

---

## Phase 4 — Output Stage

1. LLM generates `decision_summary` (≤200 words, human-readable)
2. `vendors.status`, `decided_at`, `pipeline_duration_ms` set
3. Email dispatch:
   - `pending` → `render_pending_email()` from reason codes (LLM fallback if none)
   - `rejected` → LLM-generated neutral decline email
   - `approved` → no email (configurable)
4. OCR failure emails sent earlier in pipeline if any doc was `partial` or `failed`

---

## Phase 5 — API Layer

### Submissions API (`api/submissions.py`)

- `POST /api/submissions` — form intake
- `GET /api/submissions/{run_id}` — full detail
- `GET /api/submissions/{run_id}/stages` — stage list for polling
- `GET /api/submissions/{run_id}/events` — SSE stream
- `GET /api/submissions/{run_id}/versions` — resubmission history
- `POST /api/submissions/{run_id}/resubmit` — submit corrected version
- `GET /api/submissions/mine` — vendor's own submissions (Vendor JWT)

### Dashboard API (`api/dashboard.py`)

- `GET /api/dashboard/stats` — counts by status, risk level, SLA breach
- `GET /api/dashboard/history` — paginated list with `status`, `search` filters

### Auth API (`api/auth.py`)

- Admin: login with username/password → JWT pair
- Vendor: login with email + run_id → JWT pair
- Refresh token rotation (revoke old, issue new)
- Logout (revoke refresh token)

---

## Phase 6 — Frontend

### Pages

| Route | Purpose |
|-------|---------|
| `/` | Landing page with feature overview |
| `/submit` | Vendor onboarding form (company, tax, bank, docs) |
| `/runs/[id]` | Live pipeline tracker with SSE, stage cards, result details |
| `/dashboard` | Admin dashboard (stats, history table, filters) |
| `/admin/login` | Admin credentials login |
| `/vendor/login` | Vendor login (email + run_id) |
| `/vendor/me` | List of all vendor's submissions |
| `/vendor/[runId]` | Vendor-facing status page |

### Key Components

- `SubmissionForm.tsx` — multi-section form with country-adaptive fields (India shows CIN/PAN/GSTIN)
- `PipelineTracker.tsx` — animated stage list, polls SSE, shows per-stage check results
- `StatusBadge.tsx` — colored pill for approved/pending/rejected/processing

### Auth Flow (Frontend)

Middleware at Next.js edge verifies `admin_access_token` cookie, attempts silent refresh via `/api/auth/admin/refresh` route, redirects to login on failure. Same pattern for vendor routes.

---

## Phase 7 — Security & Infrastructure

- **JWT**: HS256, secrets never stored — SHA-256 hash only
- **CORS**: Allow-origin regex matching Vercel preview URLs (`*.vercel.app`) + explicit production origins
- **File storage**: Supabase Storage (files uploaded via `storage_service.py`)
- **Swagger**: Bearer token scheme configured in `main.py`
- **Rate limiting**: Not implemented — recommended for production

---

## Known Defects & Tech Debt

| ID | Location | Description |
|----|----------|-------------|
| BUG-01 | `india_validator.py:_extract_cin_year` | Wrong slice `cin[6:10]` — CIN year check silently skips for all valid CINs |
| TD-01 | `external_api_service.py` | All external verifications are mocked — replace with real HTTP calls for production |
| TD-02 | `pipeline.py` | No retry logic for LLM calls — a transient Groq 429 aborts the pipeline |
| TD-03 | Auth | Admin password stored as plain string in env var — should be bcrypt hash |
| TD-04 | `output` stage | Approval emails not sent — only pending and rejection emails implemented |
