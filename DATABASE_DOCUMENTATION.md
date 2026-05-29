# Database Documentation

## Overview

The Vendor Onboarding system uses a **PostgreSQL** database (hosted on Supabase) accessed via **SQLAlchemy ORM**. The database stores everything needed to run a fully automated, multi-stage AI-powered vendor validation pipeline — from the initial form submission through OCR extraction, format checks, fraud analysis, and the final decision.

**Connection**: Configured via `DATABASE_URL` in `.env`. The `database.py` module handles Supabase pooler quirks (URL-encoding passwords, stripping `?pgbouncer=true`). Connection pool is set to 5 workers + 10 overflow for production; SQLite is supported for tests.

**Schema creation**: `Base.metadata.create_all(bind=engine)` runs on every server startup, so the tables are always in sync with the models.

---

## Tables

### 1. `vendors`

The **central table**. One row per submission attempt. Every other table links back to this one.

```
vendors
├── id                  UUID (PK)
├── run_id              String, unique, indexed  -- human-readable ID like "vnd_20260529_a1b2c3d4"
│
├── company_name        String                   -- submitted company name
├── registration_number String                   -- company reg number (non-India)
├── country             String(2)                -- ISO 2-letter code ("IN", "GB", "US", …)
├── incorporation_date  String                   -- "YYYY-MM-DD" or free-text
│
├── contact_name        String
├── contact_email       String, indexed
│
├── tax_id              String                   -- generic tax ID (non-India)
├── tax_id_type         String                   -- "VAT", "EIN", "GST", etc.
│
│   ── India-specific ──────────────────────────────────────────
├── cin_number          String                   -- Corporate Identification Number
├── pan_number          String                   -- PAN card number
├── gstin_number        String                   -- GST Identification Number
├── ifsc_code           String                   -- bank branch IFSC
├── account_type        String                   -- "Current" or "Savings"
├── registered_state    String                   -- Indian state
│
│   ── Banking ─────────────────────────────────────────────────
├── bank_account_name   String
├── account_number      String
├── bank_name           String
├── bank_country        String(2)
│
│   ── Pipeline status ─────────────────────────────────────────
├── status              Enum(processing|pending|approved|rejected|error)
├── current_stage       String                   -- last pipeline stage that ran
├── decision_summary    Text                     -- LLM-generated human-readable summary
├── risk_level          String                   -- "low" | "medium" | "high"
│
│   ── Merged data ─────────────────────────────────────────────
├── merged_data         JSON                     -- full snapshot: form + extracted docs + check results
│
│   ── Duplicate detection ──────────────────────────────────────
├── is_duplicate        Boolean (default false)
├── duplicate_of_run_id String                   -- run_id of the original vendor if duplicate
│
│   ── Versioning / resubmissions ──────────────────────────────
├── version_number      Integer (default 1)
├── original_run_id     String                   -- all versions of the same vendor share this
├── resubmission_notes  Text                     -- vendor's notes on what they fixed
│
│   ── SLA & lifecycle ──────────────────────────────────────────
├── sla_due_at          DateTime                 -- created_at + 48 hours
│
│   ── Admin overrides ──────────────────────────────────────────
├── override_by         String                   -- admin username who overrode
├── override_at         DateTime
├── override_reason     Text
│
│   ── Performance telemetry ────────────────────────────────────
├── pipeline_duration_ms BigInteger              -- wall-clock time for the entire pipeline
│
│   ── Timestamps ───────────────────────────────────────────────
├── created_at          DateTime (auto)
├── updated_at          DateTime (auto-update)
└── decided_at          DateTime                 -- when status changed to approved/rejected/pending
```

**Why this shape?**

- `run_id` is the externally visible ID (format: `vnd_YYYYMMDD_xxxxxxxx`). The UUID `id` is used internally for all foreign keys — it is never shown to vendors.
- India-specific fields (`cin_number`, `pan_number`, `gstin_number`, `ifsc_code`, `account_type`, `registered_state`) are nullable so the table handles all countries without needing a separate schema.
- `merged_data` is a denormalized JSON snapshot of everything the pipeline produced (form data + extracted doc fields + check results). It is used by the credibility stage to give the LLM full context without re-querying every sub-table, and it is returned in the admin detail view.
- `version_number` + `original_run_id` implement a lightweight resubmission chain: v1 has `original_run_id = NULL`, v2 onwards set `original_run_id` to v1's `run_id`. Querying all versions of a vendor means filtering `WHERE original_run_id = X OR run_id = X`.
- `is_duplicate` / `duplicate_of_run_id` are set during the `intake` pipeline stage by matching on company name, PAN, GSTIN, and account+IFSC against existing approved/pending records.

**Indexes**

| Index | Columns | Purpose |
|---|---|---|
| `ix_vendors_run_id` | `run_id` | Primary lookup by submission ID |
| `ix_vendors_status` | `status` | Dashboard filter by status |
| `ix_vendors_country_status` | `country, status` | Country-scoped status filters |
| `ix_vendors_contact_email` | `contact_email` | Vendor "my submissions" lookup |
| `ix_vendors_created_at` | `created_at` | Chronological ordering |
| `ix_vendors_original_run_id` | `original_run_id` | Resubmission chain lookup |
| `ix_vendors_version` | `original_run_id, version_number` | Ordered version history |

---

### 2. `documents`

One row per uploaded file per submission.

```
documents
├── id                   UUID (PK)
├── vendor_id            UUID (FK → vendors.id)
├── document_type        String  -- "coi" | "pan_gstin" | "bank_letter" | "registration" | "tax_cert"
├── file_path            String  -- local disk path (fallback)
├── original_filename    String  -- the name the vendor uploaded
├── extracted_json       JSON    -- structured fields extracted by OCR + LLM
├── extraction_confidence Float  -- overall confidence score from the extractor
├── ocr_status           String  -- "unknown" | "success" | "partial" | "failed"
├── ocr_issues           JSON    -- list of human-readable issue strings
├── storage_key          String  -- Supabase Storage object key (primary source)
├── quality_score        Float   -- 0–1 field-weighted extraction quality score
├── created_at           DateTime
└── updated_at           DateTime
```

**Why this shape?**

- `document_type` determines what fields the extractor looks for and what cross-document checks apply. India uses `coi`, `pan_gstin`, `bank_letter`; non-India uses `registration`, `tax_cert`, `bank_letter`.
- `extracted_json` is the heart of the OCR pipeline result. It is a free-form dict of field names → values, plus private metadata keys prefixed with `_` (e.g. `_quality_score`, `_low_confidence_fields`, `_doc_type_mismatch`). The metadata is stripped before being sent to the LLM.
- `ocr_status` and `ocr_issues` are set after the extraction quality check: if no text could be extracted (`failed`), if critical fields are missing (`partial`), or if the document appears to be the wrong type (`failed` with a mismatch message). This drives the OCR failure email.
- `storage_key` points to Supabase Storage. The pipeline preferentially downloads from there; `file_path` is a local fallback for when the server has the file on disk. This means the pipeline is resilient to either path being unavailable.
- `quality_score` is a float computed by the extractor based on how many expected critical fields were found and with what confidence. A score below 0.5 triggers the `partial` OCR status.

---

### 3. `validation_results`

One row per individual check that ran during the pipeline. All stages that produce checks write here.

```
validation_results
├── id          UUID (PK)
├── vendor_id   UUID (FK → vendors.id)
├── category    String  -- "format_check" | "external_verification" | "cross_doc_check"
│                       -- | "completeness" | "consistency" | "credibility"
├── check_name  String  -- e.g. "pan_format", "doc_coi", "company_name_vs_coi"
├── status      String  -- "pass" | "fail" | "warning" | "missing" | "match" | "mismatch"
├── detail      Text    -- human-readable explanation of the result
├── confidence  Float   -- 0.0–1.0
└── created_at  DateTime
```

**Why this shape?**

- Every pipeline stage writes its results here so the admin dashboard can show a per-vendor audit trail of every check that ran. The decision engine reads these rows to compute its final verdict.
- `category` groups checks by which pipeline stage produced them. This lets the frontend separate "why was this rejected" into distinct sections (format issues vs. missing docs vs. cross-doc mismatches vs. credibility flags).
- `check_name` maps 1:1 to the `CHECK_TO_REASON` dict in `decision.py`, which translates technical check names into vendor-facing reason codes (e.g. `gstin_pan_match` → `GSTIN_PAN_MISMATCH`).
- `status` vocabulary differs slightly between stages: completeness checks use `"missing"` for absent documents/fields; consistency (LLM) checks use `"match"` / `"mismatch"` / `"partial_match"`; format checks use `"pass"` / `"fail"` / `"warning"`.

---

### 4. `pipeline_stage_logs`

One row per pipeline stage per submission. Created upfront (all stages, `status=pending`) when a submission is created, then updated as the pipeline progresses.

```
pipeline_stage_logs
├── id             UUID (PK)
├── vendor_id      UUID (FK → vendors.id)
├── stage          String  -- one of the 13 PipelineStage values
├── status         String  -- "pending" | "running" | "completed" | "failed" | "skipped"
├── message        Text    -- short status message (e.g. "India format checks: 8 checks, 2 failed")
├── metadata       JSON    -- arbitrary stage-specific payload
├── started_at     DateTime
└── completed_at   DateTime
```

**Pipeline stages (in order)**

| Stage | What it does |
|---|---|
| `intake` | Receives submission, runs duplicate detection |
| `extract_fields` | Normalises form field data |
| `format_check` | Deterministic regex/checksum checks on PAN, GSTIN, CIN, IFSC, account number (India only) |
| `external_verification` | Calls external registries: MCA21, GST portal, RBI IFSC API (India only) |
| `extract_docs` | Runs OCR + LLM extraction on each uploaded PDF |
| `cross_doc_check` | Compares extracted fields across documents (COI vs PAN vs bank letter) |
| `merge` | Consolidates form + doc extractions + check results into `vendors.merged_data` |
| `check_completeness` | Verifies all required fields and documents are present |
| `check_consistency` | LLM cross-checks form data vs. document data for semantic mismatches |
| `check_credibility` | LLM fraud/risk signal analysis across the full merged dataset |
| `decide` | Deterministic rules engine computes final status (approved / pending / rejected) |
| `output` | Generates LLM decision summary, sends email to vendor |
| `done` | Pipeline complete |

**Why this shape?**

- Pre-creating all stage rows at submission time (all `pending`) allows the SSE stream (`/events`) and polling endpoint (`/stages`) to immediately return a full ordered list of stages without waiting for them to run.
- `started_at` / `completed_at` allow computing per-stage durations for performance monitoring.
- Non-India submissions skip `format_check`, `external_verification`, and `cross_doc_check` — their stage rows are set to `"skipped"`.
- On server restart, the startup recovery code looks for vendors stuck in `processing` with no `running` or `completed` stage rows, and marks them `error`. This prevents zombie submissions.

---

### 5. `refresh_tokens`

Stores hashed refresh tokens for the JWT auth system.

```
refresh_tokens
├── id          UUID (PK)
├── token_hash  String, unique, indexed  -- SHA hash of the refresh token
├── role        String                   -- "admin" | "vendor"
├── subject     String                   -- username (admin) or email (vendor)
├── expires_at  DateTime
├── revoked     Boolean (default false)
└── created_at  DateTime
```

**Why this shape?**

- Refresh tokens are rotated: each use issues a new token and revokes the old one. Storing only the hash (not the raw token) means a database breach cannot be used to impersonate users.
- `role` is stored so the token can reconstruct the full JWT payload on refresh without re-authenticating.
- Access tokens are short-lived (15 min), signed JWTs — they are **not** stored in the database. Only refresh tokens (7-day lifetime) are persisted.

---

### 6. `email_logs`

Records every outbound email, whether it succeeded or failed.

```
email_logs
├── id          UUID (PK)
├── vendor_id   UUID (FK → vendors.id)
├── recipient   String    -- email address
├── subject     String
├── body        Text      -- full email body
├── email_type  String    -- "pending_request" | "rejection_neutral" | "approval" | "ocr_failure"
├── sent_at     DateTime
├── success     Boolean
└── error       Text      -- error message if sending failed
```

**Why this shape?**

- The full body is stored so admins can see exactly what was communicated to a vendor, which matters for audit and dispute resolution.
- `email_type` lets you filter by stage: `ocr_failure` emails are sent mid-pipeline (if OCR fails), while `pending_request`, `approval`, `rejection_neutral` are sent at the end.
- `success` / `error` let you identify and retry failed sends without re-running the full pipeline.

---

### 7. `audit_events`

Append-only log of significant lifecycle events for each submission.

```
audit_events
├── id          UUID (PK)
├── vendor_id   UUID (FK → vendors.id)
├── event_type  String  -- "pipeline_started" | "override" | "status_change" | "retry"
├── actor       String  -- username or "system"
├── actor_role  String  -- "admin" | "vendor" | "system"
├── payload     JSON    -- arbitrary event-specific data
└── created_at  DateTime
```

**Why this shape?**

- Supports compliance and audit requirements: who did what and when on each submission.
- `payload` is flexible JSON — an override event stores `{prev_status, new_status, reason}`, a pipeline start stores `{run_id, country}`.
- Events are always appended, never updated. This gives a tamper-evident history.

**Indexes**

| Index | Columns | Purpose |
|---|---|---|
| `ix_audit_events_vendor_id` | `vendor_id` | Fast lookup of all events for a vendor |
| `ix_audit_events_event_type` | `event_type` | Filter by event type across all vendors |

---

## Entity Relationships

```
vendors (1) ──< documents         (many)
vendors (1) ──< validation_results (many)
vendors (1) ──< pipeline_stage_logs (many)
vendors (1) ──< email_logs         (many)
vendors (1) ──< audit_events       (many)

refresh_tokens — standalone (no FK to vendors)
```

All child tables use `cascade="all, delete-orphan"` on the ORM relationship, so deleting a vendor row cascades to all its documents, checks, stage logs, emails, and audit events.

---

## Status Lifecycle

```
              ┌─────────────┐
  submission  │  processing │  pipeline is actively running
  created ──► │             │
              └──────┬──────┘
                     │
          ┌──────────┼───────────┐
          ▼          ▼           ▼
      pending     approved    rejected
  (needs fixes) (all passed) (too many failures
                              or high fraud risk)
                     
        error  ←── pipeline threw an unhandled exception
```

- `processing` is the only transient status; all others are terminal (pipeline complete).
- Admins can override any non-`processing` status to `approved` or `rejected` via `POST /api/submissions/{run_id}/override`. This writes an `audit_event` and sends the appropriate email.
- A `pending` vendor can resubmit, creating a new `vendors` row (v2) linked via `original_run_id`.

---

## Decision Engine Logic

The `decide` stage in `decision.py` is fully deterministic — no LLM involved. It works as follows:

1. **Hard reject** if `risk_level == "high"` or any single high-severity fraud flag exists.
2. **Compute severity score** by accumulating weighted points:
   - Missing critical document: +10 each
   - Hard format failure: +8 each
   - Structural check failure: +6 each
   - Consistency mismatch: +8 each
   - Consistency partial match: +3 each
   - Medium fraud flag: +8 each; high fraud flag: +25 each
   - Medium risk level overall: +15
3. **Reject** if total score ≥ 25 (the `REJECTION_THRESHOLD`).
4. **Pending** if any missing docs/fields, format failures, or consistency failures exist.
5. **Approved** if the score is 0 and no failures exist.

Each failed check maps to a `reason_code` (e.g. `GSTIN_PAN_MISMATCH`, `MISSING_COI`) which drives the email body sent to the vendor.

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| UUID primary keys | Avoids sequential ID leakage, safe for external exposure |
| String (not PG Enum) for `stage` and `status` columns | Prevents SQLAlchemy/PostgreSQL enum caching bugs when adding new stages |
| JSON for `merged_data` and `extracted_json` | Schema-free storage for LLM output that varies by country and document type |
| Pre-create all stage rows at submission time | Allows SSE and polling to return a complete ordered stage list immediately |
| Denormalized `merged_data` on `vendors` | One-shot context for the LLM credibility check without N+1 queries |
| Store email body in `email_logs` | Full auditability of exactly what was communicated to each vendor |
| Append-only `audit_events` | Tamper-evident record for admin override disputes |
| `original_run_id` pattern for versioning | Simple, no separate version table; all versions queryable with a single OR filter |
