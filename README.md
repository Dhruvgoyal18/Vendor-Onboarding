# VendorAI — AI-Powered Vendor Onboarding System

An enterprise-grade vendor onboarding and procurement validation system powered by Claude AI.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js + TypeScript)     →    Vercel                │
│  Backend  (FastAPI + Python)         →    Vercel Serverless      │
│  Database (PostgreSQL)               →    Supabase               │
│  AI Layer (Claude Sonnet)            →    Anthropic API          │
│  Email    (Resend)                   →    Resend                 │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **9-Stage AI Pipeline** — intake → extraction → validation → decision → output
- **Document AI Extraction** — Claude Vision parses PDFs and images automatically
- **Fraud Detection** — geographic mismatches, suspicious patterns, credibility scores
- **Real-Time Updates** — Server-Sent Events for live pipeline visualization
- **Completeness Checks** — rule-based validation with tax ID regex per country
- **Consistency Analysis** — Claude semantic comparison across form data + documents
- **Decision Engine** — deterministic rules (AI provides analysis, code makes decision)
- **Email Automation** — Resend-powered pending/rejection emails via Claude
- **Duplicate Detection** — same company + tax ID flagged automatically
- **Full Audit Trail** — every check and reasoning step persisted

## Project Structure

```
Vendor Onboarding/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── submissions.py  # POST /api/submissions, GET /api/submissions/:id
│   │   │   └── dashboard.py    # GET /api/dashboard/stats, /api/dashboard/history
│   │   ├── services/
│   │   │   ├── pipeline.py     # Main 9-stage orchestrator
│   │   │   ├── extractor.py    # Claude document extraction
│   │   │   ├── validator.py    # Completeness + consistency + credibility
│   │   │   ├── decision.py     # Decision engine + summaries
│   │   │   └── email_service.py
│   │   ├── prompts/
│   │   │   └── templates.py    # All Claude prompts
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── database.py         # DB connection
│   │   ├── config.py           # Settings
│   │   └── main.py             # FastAPI app
│   ├── requirements.txt
│   ├── vercel.json
│   └── .env.example
│
├── frontend/                   # Next.js TypeScript frontend
│   ├── app/
│   │   ├── page.tsx            # Landing page
│   │   ├── submit/page.tsx     # Vendor submission form
│   │   ├── dashboard/page.tsx  # Admin dashboard
│   │   └── runs/[id]/page.tsx  # Live run view
│   ├── components/
│   │   ├── SubmissionForm.tsx  # Multi-section form with file uploads
│   │   ├── PipelineTracker.tsx # Animated stage tracker
│   │   └── StatusBadge.tsx     # Status pill badges
│   ├── lib/
│   │   ├── api.ts              # API client
│   │   └── types.ts            # TypeScript types
│   ├── vercel.json
│   └── .env.example
│
└── supabase/
    └── schema.sql              # Database migration
```

## Setup

### 1. Supabase Database

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run `supabase/schema.sql`
3. Copy your project URL, anon key, and service role key

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run locally
uvicorn app.main:app --reload --port 8000
```

**Backend `.env` values:**
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
ANTHROPIC_API_KEY=your-anthropic-key
RESEND_API_KEY=your-resend-key        # Optional in dev
FROM_EMAIL=onboarding@yourdomain.com
FRONTEND_URL=http://localhost:3000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Run locally
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Deployment

### Deploy Backend to Vercel

```bash
cd backend
npx vercel --prod
```

Set Vercel environment variables in the Vercel dashboard (see `backend/vercel.json`).

### Deploy Frontend to Vercel

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your backend Vercel URL.

> **Note:** For production, consider deploying the backend to **Railway** or **Render** instead of Vercel for better support of long-running async tasks and SSE streaming.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/submissions` | Create submission + start pipeline |
| `GET` | `/api/submissions/:run_id` | Get full submission detail |
| `GET` | `/api/submissions/:run_id/stages` | Get pipeline stages (polling) |
| `GET` | `/api/submissions/:run_id/events` | SSE stream for real-time updates |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |
| `GET` | `/api/dashboard/history` | Paginated submission history |
| `GET` | `/docs` | Auto-generated Swagger UI |

## Pipeline Stages

1. **Intake** — Duplicate detection, submission stored
2. **Extract Fields** — Form data normalized
3. **Extract Docs** — Claude Vision extracts data from PDF/images
4. **Merge** — All data merged into unified vendor object
5. **Check Completeness** — Rule-based: required fields, tax ID format, IBAN
6. **Check Consistency** — Claude semantic comparison across data sources
7. **Check Credibility** — Claude fraud signal analysis
8. **Decide** — Deterministic decision: approved / pending / rejected
9. **Output** — Summary generated, emails sent, audit trail saved

## Edge Cases Handled

- **EC-1 Name Typo** — "Ltd" vs "Limited" → partial_match → pending
- **EC-2 Geographic Mismatch** — UK company, Nigerian bank → fraud flag
- **EC-3 Missing Documents** — Short-circuit pipeline, immediate pending
- **EC-4 Duplicate Submission** — Same company + tax ID → warning
