# VendorAI — AI-Powered Vendor Onboarding System

An enterprise-grade, fully automated vendor onboarding and procurement validation platform. Vendors submit a form and documents; a 13-stage AI pipeline extracts, validates, scores, and decides — all in real time.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend   Next.js 15 + TypeScript + Tailwind CSS  →  Vercel       │
│  Backend    FastAPI + Python                        →  Vercel        │
│  Database   PostgreSQL                              →  Supabase      │
│  AI Layer   Groq Llama-3.3-70b / Claude Sonnet      →  Groq / Anthropic │
│  OCR        Tesseract + pdfplumber + pdf2image      →  Self-hosted   │
│  Email      Resend                                  →  Resend        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Feature Overview

| Category | What it does |
|---|---|
| **13-Stage Pipeline** | Intake → Extract → Format Check → External Verify → OCR → Cross-Doc → Merge → Completeness → Consistency → Credibility → Decide → Output → Done |
| **India-Specific Validation** | CIN, PAN, GSTIN, IFSC regex + checksum + fuzzy cross-checks, MCA21 / GST Portal / RBI IFSC / Penny Drop verification (mock, prod-ready) |
| **OCR Layer** | pdfplumber (native PDFs) + Tesseract fallback (scanned PDFs, images) with quality scoring |
| **LLM Extraction** | Groq Llama-3.3-70b (Claude Sonnet optional) extracts structured JSON from raw OCR text per document type |
| **Consistency Check** | LLM semantic comparison of form data vs extracted document fields |
| **Credibility / Fraud** | LLM detects geographic mismatches, new-company risk, suspicious IDs, email domain anomalies |
| **Deterministic Decisions** | Rule-based severity scoring — AI provides analysis, code makes the final decision |
| **Real-Time Updates** | SSE stream for live pipeline stage visualization |
| **Email Automation** | Pending (deterministic reason codes), rejection (LLM), OCR failure — all via Resend |
| **Resubmission Flow** | Vendors can resubmit with corrections; full version history tracked |
| **Duplicate Detection** | 4-signal OR query across company name, PAN, GSTIN, account + IFSC |
| **SLA Tracking** | 48-hour SLA clock set at pipeline start |
| **Admin Override** | Admins can manually override status with an audit log entry |
| **JWT Auth** | Separate admin + vendor JWT with 15-min access / 7-day refresh + rotation |
| **LLM Cache** | SHA-256 keyed prompt cache in PostgreSQL to avoid redundant LLM calls |
| **Full Audit Trail** | Every pipeline event, override, and email logged |

---

## Project Structure

```
Vendor Onboarding/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── submissions.py        # POST /api/submissions, GET /api/submissions/:id, SSE, resubmit
│   │   │   ├── dashboard.py          # GET /api/dashboard/stats, /api/dashboard/history
│   │   │   └── auth.py               # Admin + vendor JWT login/refresh/logout
│   │   ├── services/
│   │   │   ├── pipeline.py           # 13-stage pipeline orchestrator
│   │   │   ├── extractor.py          # LLM-based document field extraction
│   │   │   ├── validator.py          # Completeness + consistency + credibility
│   │   │   ├── india_validator.py    # India format checks + cross-doc checks
│   │   │   ├── external_api_service.py # MCA21, GST Portal, RBI IFSC, Penny Drop
│   │   │   ├── ocr_service.py        # Tesseract + pdfplumber OCR
│   │   │   ├── decision.py           # Severity scoring + decision engine
│   │   │   ├── email_service.py      # Resend email dispatch
│   │   │   ├── llm_service.py        # Groq/Anthropic LLM client + cache
│   │   │   └── storage_service.py    # Supabase Storage uploads
│   │   ├── prompts/
│   │   │   └── templates.py          # All LLM system prompts
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── schemas.py                # Pydantic request/response schemas
│   │   ├── database.py               # DB session + engine
│   │   ├── config.py                 # Pydantic settings (env vars)
│   │   └── main.py                   # FastAPI app + CORS + router registration
│   ├── requirements.txt
│   ├── vercel.json
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                  # Landing page
│   │   ├── submit/page.tsx           # Vendor submission form
│   │   ├── dashboard/page.tsx        # Admin dashboard
│   │   ├── runs/[id]/page.tsx        # Live pipeline run view
│   │   ├── admin/login/page.tsx      # Admin login
│   │   ├── vendor/login/page.tsx     # Vendor login (email + run_id)
│   │   ├── vendor/me/page.tsx        # Vendor: all my submissions
│   │   └── vendor/[runId]/page.tsx   # Vendor: single submission status
│   ├── components/
│   │   ├── SubmissionForm.tsx        # Multi-section form with file uploads
│   │   ├── PipelineTracker.tsx       # Animated real-time stage tracker
│   │   └── StatusBadge.tsx           # Status pill (approved / pending / rejected)
│   ├── lib/
│   │   ├── api.ts                    # API client (fetch + JWT + auto-refresh)
│   │   └── types.ts                  # TypeScript types shared across app
│   ├── vercel.json
│   └── .env.example
│
└── supabase/
    └── schema.sql                    # Full PostgreSQL DDL + indexes
```

---

## Pipeline Stages

| # | Stage | What happens |
|---|---|---|
| 1 | `intake` | SLA clock set, duplicate 4-signal check, audit event written |
| 2 | `extract_fields` | Form data normalized to internal dict |
| 3 | `format_check` | India only — CIN, PAN, GSTIN, IFSC regex + checksums (deterministic) |
| 4 | `external_verification` | India only — MCA21, GST Portal, RBI IFSC, Penny Drop |
| 5 | `extract_docs` | OCR → LLM structured extraction per document, quality scoring |
| 6 | `cross_doc_check` | India only — 13 deterministic doc-vs-doc + doc-vs-form comparisons |
| 7 | `merge` | Assemble `merged_data` JSON from all sources |
| 8 | `check_completeness` | Rule-based: required fields + required documents present |
| 9 | `check_consistency` | LLM: form data vs extracted doc fields |
| 10 | `check_credibility` | LLM: fraud risk analysis (geo, age, name anomalies, email domain) |
| 11 | `decide` | Severity score → approved / pending / rejected (no LLM) |
| 12 | `output` | LLM summary, email dispatch, final DB writes |
| 13 | `done` | Pipeline complete, SSE stream closes |

---

## API Reference

### Submissions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/submissions` | None | Create submission + start pipeline |
| `GET` | `/api/submissions/{run_id}` | None | Full vendor detail + all check results |
| `GET` | `/api/submissions/{run_id}/stages` | None | Pipeline stage statuses (polling) |
| `GET` | `/api/submissions/{run_id}/events` | None | SSE live stream |
| `GET` | `/api/submissions/{run_id}/versions` | None | All resubmissions of a case |
| `POST` | `/api/submissions/{run_id}/resubmit` | None | Resubmit with corrections |
| `GET` | `/api/submissions/mine` | Vendor JWT | All submissions for logged-in vendor |

### Dashboard (Admin JWT required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dashboard/stats` | Aggregate counts by status + risk |
| `GET` | `/api/dashboard/history` | Paginated + filterable submission history |

### Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/admin/login` | `{username, password}` | Admin JWT pair |
| `POST` | `/api/auth/admin/refresh` | `{refresh_token}` | Rotate admin tokens |
| `POST` | `/api/auth/admin/logout` | `{refresh_token}` | Revoke admin refresh token |
| `POST` | `/api/auth/vendor/login` | `{email, run_id}` | Vendor JWT pair |
| `POST` | `/api/auth/vendor/refresh` | `{refresh_token}` | Rotate vendor tokens |
| `POST` | `/api/auth/vendor/logout` | `{refresh_token}` | Revoke vendor refresh token |

`GET /docs` — Auto-generated Swagger UI with Bearer auth.

---

## Database Schema (Key Tables)

| Table | Purpose |
|---|---|
| `vendors` | One row per submission: status, merged data, risk level, SLA, override info |
| `documents` | One row per uploaded file: OCR status, extracted JSON, quality score |
| `validation_results` | Every check result (pass/fail/warning) with category, detail, confidence |
| `pipeline_stage_logs` | Per-stage timing and status log |
| `refresh_tokens` | SHA-256 hashed tokens for rotation + revocation |
| `email_logs` | Every email sent: type, recipient, success/failure |
| `audit_events` | Immutable audit trail: pipeline events, overrides, retries |
| `llm_cache` | Prompt-hash-keyed LLM response cache with TTL |
| `country_configs` | Per-country required fields, docs, rules, SLA hours |

---

## Decision Engine

```
Severity score is calculated from all validation results:

  +10 per missing document
  +8  per format/field failure
  +6  per other structural failure
  +8  per consistency mismatch
  +3  per consistency partial match
  +15 if risk_level = medium
  +25 per high-severity fraud flag
  +8  per medium-severity fraud flag

Decision tree (first match wins):
  1. risk_level == "high" OR any high-severity fraud flag  →  REJECTED
  2. severity_score ≥ 25                                   →  REJECTED
  3. Any missing doc / field / format fail / consistency fail  →  PENDING
  4. All clear                                             →  APPROVED
```

---

## Setup

### 1. Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. SQL Editor → run `supabase/schema.sql`
3. Note: project URL, anon key, service role key, DB URL

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env (see below)
uvicorn app.main:app --reload --port 8000
```

**Required `.env` values:**

```env
DATABASE_URL=postgresql://postgres:password@db.YOUR_PROJECT.supabase.co:5432/postgres
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
ANTHROPIC_API_KEY=your-anthropic-key      # if LLM_PROVIDER=anthropic
GROQ_API_KEY=your-groq-key                # default LLM provider
LLM_PROVIDER=groq                         # or "anthropic"
RESEND_API_KEY=your-resend-key
FROM_EMAIL=onboarding@yourdomain.com
FRONTEND_URL=http://localhost:3000
JWT_SECRET=your-32-char-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Deployment

### Backend → Vercel

```bash
cd backend
npx vercel --prod
```

Set all backend env vars in the Vercel dashboard.

> For production workloads with long-running SSE streams, **Railway** or **Render** are better choices than Vercel (which has a 10s function timeout).

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your deployed backend URL.

---

## LLM Providers

| Provider | Model | Toggle |
|---|---|---|
| **Groq** (default) | `llama-3.3-70b-versatile` | `LLM_PROVIDER=groq` |
| Anthropic | `claude-sonnet-4-5` | `LLM_PROVIDER=anthropic` |

All prompts are provider-agnostic. Switch at any time via env var.

---

## Edge Cases

| ID | Scenario | Result |
|----|----------|--------|
| EC-1 | Name abbreviation — "Pvt Ltd" vs "Private Limited" | fuzzy score ≈ 80 → MISMATCH → pending |
| EC-2 | Indian company, Nigerian bank account | credibility high flag → rejected |
| EC-3 | Documents missing entirely | completeness short-circuits to pending |
| EC-4 | Same company + PAN resubmits | duplicate flag set, pipeline continues |
| EC-5 | Scanned PDF (no native text) | auto-fallback to Tesseract OCR at 300 DPI |
| EC-6 | Wrong document type uploaded | `_doc_type_mismatch=True` → OCR failure email, pending |
| EC-7 | GSTIN PAN chars don't match submitted PAN | format check fail → pending, reason code issued |
| EC-8 | Individual PAN (4th char = P) submitted | `pan_entity_type` fail → pending |
