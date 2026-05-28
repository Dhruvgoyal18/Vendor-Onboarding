# VendorAI — System Overview

> Last updated: May 2026

---

## Problem Statement

Procurement teams manually review vendor submissions across multiple documents, validate business registration and tax IDs, flag inconsistencies and fraud signals, and draft response emails. This is slow, error-prone, and doesn't scale.

VendorAI automates the entire workflow end-to-end:

1. Vendors submit a form + documents via a web portal
2. A 13-stage AI pipeline validates everything automatically
3. Every check result and reasoning step is persisted and visible
4. The system decides: **approved**, **pending** (with specific fix instructions), or **rejected**
5. Automated emails are sent to the vendor
6. An admin dashboard shows all submissions, filters, and overrides

---

## Actual Tech Stack (As Built)

### Frontend
- **Next.js 15** (App Router) + TypeScript
- **Tailwind CSS** for styling
- **react-hook-form + zod** for form validation
- **lucide-react** for icons
- **jose** for client-side JWT handling
- Deployed on **Vercel**

### Backend
- **FastAPI** (Python) — async, SSE support, auto-generated Swagger
- **SQLAlchemy 2.0** ORM with **psycopg2** driver
- **Pydantic v2** for request/response validation and settings
- **Alembic** for database migrations
- Deployed on **Vercel** (or Railway/Render for production SSE)

### Database
- **PostgreSQL** hosted on **Supabase**
- 9 tables: vendors, documents, validation_results, pipeline_stage_logs, refresh_tokens, email_logs, audit_events, llm_cache, country_configs

### AI / LLM
- **Groq** `llama-3.3-70b-versatile` — default LLM provider (fast, free tier available)
- **Anthropic Claude Sonnet** — optional via `LLM_PROVIDER=anthropic`
- Temperature: 0.1 for all extraction/analysis calls
- LLM cache table (PostgreSQL) keyed by SHA-256 prompt hash

### OCR
- **pdfplumber** — native text extraction from generated PDFs
- **pdf2image + Tesseract** — fallback OCR for scanned PDFs and images
- **PIL (Pillow)** — image preprocessing

### Validation Libraries
- **rapidfuzz** — fuzzy name matching with `token_sort_ratio` (threshold: 85)
- **schwifty** — IBAN validation for non-India countries
- **pycountry** — ISO country code lookups

### Auth
- **python-jose** for JWT signing (HS256)
- Separate admin and vendor JWT pairs
- 15-min access tokens, 7-day refresh tokens with rotation
- Refresh tokens stored as SHA-256 hashes in `refresh_tokens` table

### Email
- **Resend** SDK for transactional emails
- Email types: pending (deterministic reason codes), rejection, OCR failure, approval

---

## High-Level Architecture

```
Browser (Next.js)
      │
      │  POST /api/submissions (multipart/form-data)
      │  GET  /api/submissions/{id}/events  (SSE)
      ▼
FastAPI Backend
      │
      ├── Creates vendors + documents rows (status=processing)
      ├── Returns run_id immediately
      │
      └── BackgroundTask: run_pipeline(vendor_id)
           │
           ├─ [intake]                Duplicate detection, SLA clock, audit event
           ├─ [extract_fields]        Normalize form data
           ├─ [format_check]          India: CIN/PAN/GSTIN/IFSC regex + checksums
           ├─ [external_verification] India: MCA21, GST, RBI IFSC, Penny Drop
           ├─ [extract_docs]          OCR → LLM structured extraction per file
           ├─ [cross_doc_check]       India: 13 deterministic doc-vs-doc checks
           ├─ [merge]                 Build merged_data JSON blob
           ├─ [check_completeness]    Required fields + docs present
           ├─ [check_consistency]     LLM: form vs extracted doc fields
           ├─ [check_credibility]     LLM: fraud / risk signal analysis
           ├─ [decide]                Severity score → approved/pending/rejected
           └─ [output → done]         LLM summary, emails, final DB writes
```

---

## Data Flow

```
Form Submission
    └── vendors row (processing)
    └── documents rows (ocr_status=unknown)
         │
         ▼
Pipeline runs in background
    └── validation_results rows accumulate per check
    └── pipeline_stage_logs rows created per stage
    └── documents.extracted_json filled in
    └── vendors.merged_data assembled
    └── vendors.risk_level set
         │
         ▼
Decision
    └── vendors.status → approved | pending | rejected
    └── vendors.decision_summary (LLM text)
    └── email_logs rows (emails sent)
    └── audit_events rows (pipeline complete)
```

---

## India vs Generic Mode

The system has deep India-specific logic that activates when `country == "IN"`:

| Layer | India | Generic |
|-------|-------|---------|
| Format checks | CIN, PAN, GSTIN, IFSC regex + checksums | Tax ID regex + IBAN |
| External verification | MCA21, GST Portal, RBI IFSC, Penny Drop | Skipped |
| Document extraction | India-specific prompts per doc type | Generic extraction prompt |
| Cross-doc checks | 13-check matrix (names, IDs, dates) | Skipped |
| Required documents | COI, PAN+GSTIN doc, Bank letter | Registration, bank letter, tax cert |

---

## Key Design Decisions

**AI provides analysis; code makes decisions.** LLM calls produce risk flags and consistency notes. The final approved/pending/rejected decision is deterministic Python — no LLM. This makes the decision auditable and testable.

**Short-circuit on missing docs.** If any required document is absent, the pipeline skips consistency and credibility (expensive LLM calls) and jumps directly to `decide` with `pending`.

**Deterministic pending emails.** The primary email path generates numbered action items from `reason_codes` — no LLM needed, fully testable, pre-approved copy. LLM is only used as a fallback when no reason codes exist.

**Fuzzy name matching over exact match.** OCR artifacts and legal suffix variations ("Pvt Ltd" vs "Private Limited") require tolerance. `rapidfuzz.token_sort_ratio ≥ 85` catches OCR noise while still rejecting genuine mismatches.

**Provider-agnostic LLM calls.** One env var switch (`LLM_PROVIDER=groq|anthropic`) changes the provider across the entire pipeline. All prompts are written to work with both.
