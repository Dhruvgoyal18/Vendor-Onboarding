# End-to-End AI Vendor Onboarding & Procurement Validation System

## 1. Problem Statement

The core problem being solved:

A procurement reviewer manually checks vendor submissions across multiple documents, validates details, identifies inconsistencies/fraud signals, and drafts response emails.

This system automates the entire workflow:

1. Intake vendor submissions
2. Extract structured information from forms and documents
3. Validate completeness and consistency
4. Detect fraud/risk signals
5. Make approval decisions
6. Generate vendor/internal communication
7. Track everything through a live dashboard

The system must also make the reasoning visible at every step.

---

# 2. High-Level Architecture

```text
Frontend (React + Tailwind)
        |
        v
FastAPI Backend
        |
        +--> Claude API
        |       - Document Extraction
        |       - Consistency Analysis
        |       - Fraud Detection
        |       - Decision Summaries
        |
        +--> SQLite/Postgres
        |
        +--> Email Provider
                - Resend / SendGrid
```

---

# 3. Recommended Tech Stack

## Frontend

### Framework

* React (Vite)

### Styling

* Tailwind CSS

### Why?

* Fast development
* Great demo experience
* Easy deployment
* Single-page dashboard + form app

---

## Backend

### Framework

* FastAPI

### Why?

* Async support
* Excellent API performance
* Auto-generated Swagger docs
* Easy SSE support
* Easy integration with AI APIs

---

## AI Layer

### Model

* Claude Sonnet (`claude-sonnet-4-20250514`)

### Responsibilities

* Document field extraction
* Cross-document consistency analysis
* Fraud signal detection
* Human-readable decision summaries
* Vendor email generation

---

## Document Parsing

### Libraries

* `pdfplumber`
* Claude Vision API

### Strategy

| Document Type      | Handling                       |
| ------------------ | ------------------------------ |
| Text PDFs          | Extract text with `pdfplumber` |
| Scanned/Image PDFs | Send directly to Claude Vision |

Avoid building a separate OCR pipeline unless necessary.

---

## Database

### Development

* SQLite

### Production

* PostgreSQL

### ORM

* SQLAlchemy

---

## Email Service

Choose one:

* Resend
* SendGrid

Used for:

* Pending request emails
* Missing document requests
* Clarification requests

---

## Deployment

### Frontend

* Vercel

### Backend

* Railway / Render

---

# 4. Core Features

---

# Feature 1 — Vendor Submission Form

## Objective

Allow vendors to submit onboarding information and upload supporting documents.

---

## Fields Required

### Company Information

* Company name
* Registration number
* Country
* Incorporated date

### Contact Information

* Primary contact name
* Email

### Banking Information

* Account name
* Account number / IBAN
* Bank name
* Bank country

### Tax Information

* Tax ID
* Tax type

  * VAT
  * EIN
  * GST
  * etc.

### Document Uploads

* Registration certificate
* Bank letter / voided check
* Tax certificate

---

## Frontend Requirements

### Validation

Implement:

* Required field validation
* Email validation
* IBAN validation
* GST/VAT/EIN format validation
* Date validation

### UX Requirements

* Clean UI
* Drag-and-drop uploads
* Progress indicators
* Toast notifications
* Mobile responsive

---

# Feature 2 — Extraction Pipeline

## Objective

Convert all incoming data into a normalized structured vendor object.

---

# Step 2A — Form Extraction

The frontend already provides structured JSON.

Normalize:

* Trim whitespace
* Standardize capitalization
* Uppercase country codes
* Normalize tax IDs

Example:

```json
{
  "company_name": "ACME LTD",
  "country": "GB",
  "tax_id": "GB123456789"
}
```

---

# Step 2B — Document Extraction

## Flow

### Text PDFs

```text
PDF --> pdfplumber --> extracted text --> Claude
```

### Image PDFs

```text
PDF/Image --> Claude Vision
```

---

## Claude Prompt Example

```text
Extract the following fields from this document:

- Entity name
- Registration number
- Date
- Issuing authority

Return JSON only.
```

---

## Expected Claude Output

```json
{
  "entity_name": "ACME LIMITED",
  "registration_number": "12345678",
  "issuing_authority": "Companies House"
}
```

---

# Step 2C — Merge & Cross-Reference

Merge:

* Form data
* Registration certificate extraction
* Tax certificate extraction
* Bank document extraction

Into one unified vendor object.

Example:

```json
{
  "company_name_form": "ACME LTD",
  "company_name_certificate": "ACME LIMITED",
  "bank_account_name": "ACME LIMITED",
  "country": "GB"
}
```

---

# Feature 3 — Validation Engine

This is the core intelligence layer.

---

# Validation Category 1 — Completeness Checks

## Type

Rule-based validation

## Checks

* Missing fields
* Missing documents
* Invalid tax ID formats
* Invalid IBAN/account formats

---

## Examples

### UK VAT

```regex
^GB[0-9]{9}$
```

### US EIN

```regex
^[0-9]{2}-[0-9]{7}$
```

### Indian GSTIN

```regex
^[0-9A-Z]{15}$
```

---

## Output Format

```json
{
  "check": "tax_id_format",
  "status": "pass",
  "detail": "Valid UK VAT format"
}
```

---

# Validation Category 2 — Consistency Checks

## Type

Claude-powered semantic comparison

---

## Checks

* Company name consistency
* Tax ID consistency
* Bank account name match
* Country consistency
* Registration number match

---

## Claude Prompt

```text
Compare these two data objects and identify inconsistencies.

For each field pair:
- match
- mismatch
- unable to verify

Return JSON only.
```

---

## Output Example

```json
{
  "check": "company_name_match",
  "status": "fail",
  "detail": "Form says 'Acme Ltd', certificate says 'ACME LIMITED'"
}
```

---

# Validation Category 3 — Credibility Checks

## Type

Claude-powered fraud/risk analysis

---

## Fraud Signals

### Geographic Risks

* Bank country differs from company country

### Suspicious Registration

* Company incorporated very recently

### Document Issues

* Generic templates
* Metadata inconsistencies
* Reused documents

### Business Logic Issues

* Business type inconsistent with activity
* Implausible combinations of information

---

## Claude Prompt

```text
Analyze this vendor submission for fraud signals.

Consider:
- Name mismatches
- Geographic inconsistencies
- Suspicious document patterns
- Implausible data combinations

Return:
- risk level (low/medium/high)
- specific flags
- reasoning
```

---

## Example Output

```json
{
  "risk_level": "medium",
  "flags": [
    "Bank account located in different country",
    "Registration date only 10 days old"
  ]
}
```

---

# Feature 4 — Decision Engine

## Objective

Convert validation outputs into a final business decision.

---

# Decision Rules

## Approved

Conditions:

* All completeness checks pass
* No consistency failures
* Risk level = low

---

## Pending

Conditions:

* Missing documents
* Minor inconsistencies
* Clarification required

---

## Rejected

Conditions:

* Medium/high fraud risk
* Multiple severe inconsistencies
* Suspected intentional misrepresentation

---

# Human-Readable Summary

Use Claude to generate explanations.

---

## Prompt

```text
Given these validation results, write a clear explanation of why this vendor submission was approved/pending/rejected.

Be specific about:
- what passed
- what failed
- next steps
```

---

# Feature 5 — Output Layer

---

# Approved Flow

## Actions

* Save vendor record
* Store extracted data
* Save validation history
* Timestamp approval

---

# Pending Flow

## Actions

* Generate vendor-facing email
* List missing/inconsistent information
* Send email via Resend/SendGrid
* Log communication

---

# Rejected Flow

## Actions

* Generate internal fraud/risk report
* Store reasoning and flags
* Do NOT email vendor automatically

---

# Feature 6 — Dashboard

---

# Dashboard View 1 — Run History

## Table Columns

* Vendor name
* Submission time
* Status
* Decision summary
* Actions

---

## UX Features

* Color-coded status badges
* Search/filter
* Pagination
* Expandable details

---

# Dashboard View 2 — Live Run View

## Purpose

Visualize the pipeline execution in real-time.

---

## Pipeline Stages

```text
Intake
↓
Extracting Fields
↓
Completeness Validation
↓
Consistency Analysis
↓
Credibility Analysis
↓
Decision
↓
Output Generation
```

---

## Real-Time Updates

### Option 1 — Polling

Frontend polls backend every 2 seconds.

### Option 2 — SSE (Recommended)

Use Server-Sent Events.

Why SSE?

* More impressive demo
* Real-time feel
* Lower overhead than polling

---

# 5. Suggested Backend Architecture

---

# Suggested FastAPI Structure

```text
backend/
│
├── app/
│   ├── api/
│   ├── services/
│   ├── validators/
│   ├── prompts/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── utils/
│   └── main.py
```

---

# Suggested React Structure

```text
frontend/
│
├── src/
│   ├── pages/
│   ├── components/
│   ├── services/
│   ├── hooks/
│   ├── store/
│   └── App.tsx
```

---

# 6. Suggested API Endpoints

---

# Submission APIs

## Create Submission

```http
POST /submissions
```

---

## Upload Documents

```http
POST /submissions/{id}/documents
```

---

## Get Submission Status

```http
GET /submissions/{id}
```

---

## Live Updates (SSE)

```http
GET /submissions/{id}/events
```

---

## Dashboard History

```http
GET /dashboard/history
```

---

# 7. Suggested Database Schema

---

# Vendors Table

```sql
vendors
- id
- company_name
- country
- tax_id
- status
- created_at
```

---

# Documents Table

```sql
documents
- id
- vendor_id
- document_type
- file_path
- extracted_json
```

---

# Validation Results Table

```sql
validation_results
- id
- vendor_id
- check_name
- status
- detail
```

---

# Email Logs Table

```sql
email_logs
- id
- vendor_id
- recipient
- subject
- sent_at
```

---

# 8. Edge Cases to Implement

---

# EC-1 — Minor Name Mismatch

## Scenario

```text
Form:
Apex Solutions Ltd

Bank Letter:
Apex Solution Ltd
```

---

## Expected Outcome

* Flag as inconsistency
* Status = Pending
* Ask vendor for clarification

---

# EC-2 — Geographic Mismatch

## Scenario

```text
Company Country: UK
Bank Country: Nigeria
```

---

## Expected Outcome

* Raise credibility flag
* Ask for explanation
* Potential rejection if combined with other risks

---

# EC-3 — Missing Bank Document

## Scenario

Everything valid except:

* Missing bank letter

---

## Expected Outcome

* Status = Pending
* Email vendor requesting missing document

---

# EC-4 — Duplicate Submission

## Scenario

Same:

* Company name
* Tax ID

Already approved previously.

---

## Expected Outcome

* Detect duplicate
* Ask whether banking details are being updated

---

# 9. Real-Time Processing Flow

```text
User submits form
        ↓
Store submission
        ↓
Extract fields
        ↓
Validate completeness
        ↓
Run consistency analysis
        ↓
Run fraud analysis
        ↓
Generate decision
        ↓
Generate communication
        ↓
Save results
        ↓
Update dashboard
```

---

# 10. AI Prompt Engineering Strategy

---

# Prompt Design Principles

## Rules

* Always request JSON-only output
* Use deterministic structure
* Keep prompts task-specific
* Separate extraction from reasoning

---

# Prompt Categories

| Prompt Type        | Purpose              |
| ------------------ | -------------------- |
| Extraction Prompt  | Extract fields       |
| Consistency Prompt | Compare objects      |
| Fraud Prompt       | Risk analysis        |
| Summary Prompt     | Human explanation    |
| Email Prompt       | Vendor communication |

---

# 11. Security Considerations

---

# File Upload Security

* Restrict file types
* Scan uploads
* Size limits
* Secure temp storage

---

# AI Safety

* Validate Claude JSON outputs
* Retry malformed responses
* Add schema enforcement

---

# Data Security

* Encrypt sensitive banking info
* Mask account numbers in logs
* Never expose fraud reasoning externally

---

# 12. Demo Strategy

---

# Demo Flow

## Happy Path

Show:

* Successful approval
* Real-time pipeline
* Database save

---

## Edge Case 1

Minor name mismatch.

---

## Edge Case 2

Geographic fraud signal.

---

# Most Important Demo Features

## 1. Live Pipeline View

Makes system feel production-grade.

---

## 2. Actual Email Sending

Shows end-to-end automation.

---

## 3. Explainable Reasoning

Important for trust and compliance.

---

# 13. Day-by-Day Development Plan

---

# Day 2

* React form
* FastAPI skeleton
* Upload endpoint

---

# Day 3

* Extraction pipeline
* Claude integration
* Document parsing

---

# Day 4

* Validation engine
* Consistency checks
* Fraud analysis

---

# Day 5

* Decision engine
* Email sending
* Database integration

---

# Day 6

* Dashboard
* Live run view
* SSE integration
* Edge case testing

---

# Day 7

* Polish UI
* Record Loom demo
* Final testing
* Deployment

---

# 14. What Makes This Project Stand Out

---

# Key Strengths

## End-to-End Automation

Not just validation — complete workflow automation.

---

## Human-Readable Decisions

AI explains reasoning clearly.

---

## Live Operational Visibility

Real-time status tracking.

---

## Real-World Business Logic

Handles ambiguity:

* typo vs fraud
* missing docs vs malicious intent

---

## Production Feel

* Dashboard
* Emails
* Live updates
* History tracking
* Explainability

---

# 15. Recommended Enhancements (Optional)

---

# Additional Ideas

## Confidence Scores

Assign confidence values to extraction and validation.

---

## Audit Trail

Store every AI reasoning step.

---

## Multi-Tenant Support

Support multiple procurement teams.

---

## RBAC

Reviewer/admin roles.

---

## Human Override

Allow manual approval/rejection.

---

## Batch Uploads

CSV + bulk document processing.

---

## Webhooks

Notify ERP/procurement systems.

---

# 16. Final Goal

Build a system that feels like a real enterprise procurement automation platform:

* Intelligent
* Explainable
* Automated
* Real-time
* Production-oriented
* Demo-friendly
