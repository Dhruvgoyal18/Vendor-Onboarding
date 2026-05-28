# Project KPIs — VendorAI

> Last updated: May 2026

This document defines the key performance indicators for VendorAI across three dimensions: pipeline quality, operational efficiency, and system reliability. Use these to evaluate the health of the system and track improvement over time.

---

## 1. Pipeline Quality

These KPIs measure how well the validation pipeline is performing its core job.

### 1.1 Decision Distribution

| Metric | Description | Target |
|--------|-------------|--------|
| **Approval rate** | % of submissions that reach `approved` | 40–60% (healthy intake quality) |
| **Pending rate** | % that reach `pending` | < 40% |
| **Rejection rate** | % that reach `rejected` | < 10% |
| **Error rate** | % that end in `error` status | < 1% |

> High pending rate (> 50%) signals the submission form needs better guidance. High rejection rate (> 15%) may indicate fraud targeting or overly strict rules.

### 1.2 Resubmission Funnel

| Metric | Description | Target |
|--------|-------------|--------|
| **Resubmission rate** | % of `pending` cases that come back with a resubmission | > 60% |
| **Resubmission-to-approval rate** | % of resubmissions that ultimately get approved | > 75% |
| **Avg resubmission count per case** | Median number of attempts before final decision | ≤ 2 |

> Low resubmission rate suggests vendors are abandoning the process — a UX or email clarity issue.

### 1.3 Validation Layer Coverage

| Metric | Description | Target |
|--------|-------------|--------|
| **Format check pass rate (India)** | % of India submissions where all format checks pass | > 80% |
| **OCR success rate** | % of uploaded documents with `ocr_status = success` | > 90% |
| **OCR partial rate** | % of documents with `ocr_status = partial` | < 8% |
| **OCR failure rate** | % of documents with `ocr_status = failed` | < 2% |
| **Cross-doc check pass rate (India)** | % of India submissions where all 13 cross-doc checks pass | > 85% |
| **Consistency match rate** | % of consistency check fields returning `match` | > 80% |

### 1.4 Fraud Detection

| Metric | Description | Target |
|--------|-------------|--------|
| **High-risk flag rate** | % of submissions flagged `risk_level = high` | < 5% |
| **Medium-risk flag rate** | % flagged `risk_level = medium` | < 15% |
| **Duplicate detection rate** | % of submissions with `is_duplicate = true` | Track only |
| **Geographic mismatch rate** | % with bank country ≠ company country | Track only |

---

## 2. Operational Efficiency

These KPIs measure how fast and reliable the system is in practice.

### 2.1 Pipeline Speed

| Metric | Description | Target |
|--------|-------------|--------|
| **Median pipeline duration** | `pipeline_duration_ms` p50 across all runs | < 30 seconds |
| **p95 pipeline duration** | 95th percentile pipeline time | < 90 seconds |
| **SLA breach rate** | % of submissions not decided within 48 hours | < 2% |
| **Time to first stage update** | Seconds from submission to first SSE event | < 3 seconds |

> Pipeline slowdowns are almost always in the OCR stage (Tesseract on scanned PDFs) or LLM calls (Groq cold starts or rate limits).

### 2.2 Email Delivery

| Metric | Description | Target |
|--------|-------------|--------|
| **Email success rate** | % of `email_logs` with `success = true` | > 99% |
| **Pending email delivery rate** | % of `pending` decisions with email sent | 100% |
| **Rejection email delivery rate** | % of `rejected` decisions with email sent | 100% |

### 2.3 Reason Code Clarity

| Metric | Description | Target |
|--------|-------------|--------|
| **Avg reason codes per pending** | Mean number of issues per pending decision | 1–3 (specific, not overwhelming) |
| **Most common reason codes** | Which reason codes appear most frequently | Track to prioritize UX improvements |

Top reason codes to watch:
- `MISSING_COI`, `MISSING_PAN_GSTIN`, `MISSING_BANK_LETTER` — document upload friction
- `GSTIN_PAN_MISMATCH`, `GSTIN_STATE_MISMATCH` — form field errors, need inline validation
- `COMPANY_NAME_COI_MISMATCH` — OCR quality or genuine mismatch
- `SAVINGS_ACCOUNT` — vendor education needed

### 2.4 Admin Overrides

| Metric | Description | Target |
|--------|-------------|--------|
| **Override rate** | % of finalized decisions later overridden by admin | < 5% |
| **Override direction** | pending→approved vs rejected→approved | Track for calibration |

> High override rate suggests the decision engine thresholds need tuning.

---

## 3. System Reliability

### 3.1 Pipeline Success

| Metric | Description | Target |
|--------|-------------|--------|
| **Pipeline completion rate** | % of started pipelines that reach `done` | > 99% |
| **Pipeline error rate** | % that end in `error` status | < 1% |
| **LLM call success rate** | % of LLM calls that return valid JSON | > 99% |
| **LLM cache hit rate** | % of LLM calls served from `llm_cache` | Track only (aim for > 10%) |

### 3.2 API Reliability

| Metric | Description | Target |
|--------|-------------|--------|
| **Submission endpoint p99 latency** | Time to return `run_id` from `POST /api/submissions` | < 2 seconds |
| **SSE stream uptime** | % of SSE connections that stay open until `done` | > 95% |
| **Dashboard API p99 latency** | `GET /api/dashboard/history` response time | < 500 ms |

### 3.3 Data Quality

| Metric | Description | Target |
|--------|-------------|--------|
| **Null merged_data rate** | % of finalized vendors with `merged_data = null` | 0% |
| **Missing stage logs** | % of pipelines with fewer than 13 stage log entries | < 1% |
| **Orphaned documents** | Documents with no parent vendor row | 0% |

---

## 4. Business Impact (Post-Launch)

These require tracking against a baseline of manual review:

| Metric | Description | Baseline (manual) | Target (AI) |
|--------|-------------|-------------------|-------------|
| **Avg review time per vendor** | Time from submission to final decision | 2–3 business days | < 30 seconds automated |
| **Reviewer hours saved per week** | Admin time freed from manual checks | 40 hrs/week (estimate) | Measure after 1 month |
| **Vendor onboarding cycle time** | Total time from first submission to approved | 5–10 days | < 48 hours |
| **False rejection rate** | % of rejected vendors who were legitimate (requires manual audit sample) | Unknown | < 2% |
| **Fraud catch rate** | % of flagged-high submissions confirmed as fraudulent upon review | Unknown | > 80% precision |

---

## 5. Dashboard Queries (Reference SQL)

```sql
-- Approval / pending / rejection rates (last 30 days)
SELECT status, COUNT(*) AS cnt, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM vendors
WHERE created_at > NOW() - INTERVAL '30 days'
  AND status IN ('approved','pending','rejected')
GROUP BY status;

-- Median pipeline duration (ms)
SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pipeline_duration_ms) AS p50,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY pipeline_duration_ms) AS p95
FROM vendors
WHERE pipeline_duration_ms IS NOT NULL
  AND created_at > NOW() - INTERVAL '30 days';

-- OCR success rates
SELECT ocr_status, COUNT(*) AS cnt
FROM documents
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY ocr_status;

-- Top reason codes (from pending decisions)
SELECT v.run_id, vr.check_name, vr.detail
FROM validation_results vr
JOIN vendors v ON vr.vendor_id = v.id
WHERE v.status = 'pending'
  AND vr.status IN ('fail','missing')
  AND v.created_at > NOW() - INTERVAL '30 days'
ORDER BY vr.check_name;

-- SLA breaches
SELECT COUNT(*) AS breached
FROM vendors
WHERE sla_due_at < NOW()
  AND status IN ('processing','pending')
  AND deleted_at IS NULL;

-- LLM cache hit rate
SELECT 
  COUNT(*) FILTER (WHERE response_json IS NOT NULL) AS hits,
  COUNT(*) AS total
FROM llm_cache
WHERE created_at > NOW() - INTERVAL '7 days';
```
