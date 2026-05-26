# Step 1 — Submission Form

## What to Collect — Form Fields

### Company Information

* Company name

  * Text input
  * Required
  * Will be cross-checked against uploaded documents

* Registration number

  * Text input
  * Required
  * Format validation handled later in validation engine

* Country of incorporation

  * Dropdown using ISO country codes
  * Required
  * Used for tax validation logic

* Incorporation date

  * Date picker
  * Required
  * Used for fraud/credibility analysis

---

### Contact Information

* Contact name
* Contact email

  * Email validated client-side

---

### Tax Information

* Tax ID
* Tax ID type

  * VAT
  * EIN
  * GST
  * PAN
  * Other

Auto-fill based on country selection.

---

### Banking Information

* Bank account name
* Account number / IBAN
* Bank name
* Bank country

Important:

* Account name should match company name
* Bank country mismatch can become a fraud signal

---

### Document Uploads

Required documents:

1. Company registration certificate
2. Bank letter / voided cheque
3. Tax certificate

Accepted formats:

* PDF
* JPG
* PNG

Max size:

* 10MB each

---

## React Implementation Notes

### Suggested Form State

```javascript
const [form, setForm] = useState({
  company_name: '',
  reg_number: '',
  country: '',
  incorporation_date: '',
  contact_name: '',
  contact_email: '',
  tax_id: '',
  tax_id_type: '',
  bank_account_name: '',
  account_number: '',
  bank_name: '',
  bank_country: '',
  docs: {
    registration: null,
    bank_letter: null,
    tax_cert: null
  }
});
```

---

### Form Submission Flow

```javascript
const handleSubmit = async () => {
  const fd = new FormData();

  fd.append('data', JSON.stringify(form));
  fd.append('reg_doc', form.docs.registration);
  fd.append('bank_doc', form.docs.bank_letter);
  fd.append('tax_doc', form.docs.tax_cert);

  const res = await fetch('/api/submissions', {
    method: 'POST',
    body: fd
  });

  const { run_id } = await res.json();

  navigate(`/runs/${run_id}`);
};
```

---

### Product Thinking Enhancement

Auto-fill:

* UK → VAT
* US → EIN
* India → GSTIN

This reduces user errors.

---

# Step 2 — Extraction Pipeline

## Three Extraction Sub-Steps

---

## Step 2A — Normalize Form JSON

Tasks:

* Trim whitespace
* Uppercase country codes
* Normalize tax IDs
* Clean account numbers

Example Output:

```json
{
  "company_name": "ACME LTD",
  "country": "GB",
  "tax_id": "GB123456789"
}
```

---

## Step 2B — Document Extraction

### Strategy

#### Text PDFs

```text
PDF → pdfplumber → extracted text → Claude
```

#### Scanned/Image PDFs

```text
PDF/Image → Claude Vision
```

---

## Claude Extraction Prompt

```text
You are a document data extractor.

Extract the following fields:
- entity_name
- registration_number
- document_date
- issuing_authority
- account_name
- account_number
- tax_id
- country

Return ONLY JSON.
Do not invent values.
```

---

## Python Extraction Code

```python
import pdfplumber, base64, json
from anthropic import Anthropic

client = Anthropic()

def extract_document(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().split('.')[-1]

    if ext == 'pdf':
        import io

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ' '.join(
                p.extract_text() or '' for p in pdf.pages
            )

        if len(text.strip()) > 100:
            content = [{
                "type": "text",
                "text": f"Document text:\n{text}"
            }]
        else:
            b64 = base64.b64encode(file_bytes).decode()

            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64
                    }
                }
            ]

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": content
        }]
    )

    return json.loads(resp.content[0].text)
```

---

## Step 2C — Merge Into Vendor Object

Combine:

* Form data
* Registration document extraction
* Tax document extraction
* Bank document extraction

Example:

```json
{
  "run_id": "vnd_20260523_abc123",
  "form": {},
  "docs": {},
  "provenance": {}
}
```

Track provenance for every field.

---

# Step 3 — Validation Engine

The validation engine has three categories of checks.

---

# Check 1 — Completeness Checks

## Rule-Based Validation

### Checks

* Required fields present
* Tax ID format valid
* IBAN/account valid
* Email format valid
* Required documents uploaded

---

## Tax ID Regex Examples

### UK VAT

```regex
^GB[0-9]{9}$
```

### US EIN

```regex
^\d{2}-\d{7}$
```

### Indian GSTIN

```regex
^[0-9A-Z]{15}$
```

---

## IBAN Validation

Use:

```python
schwifty
```

---

## Important Optimization

If critical documents are missing:

* Stop pipeline early
* Avoid expensive AI calls

---

# Check 2 — Consistency Checks

## Claude-Powered Semantic Validation

### Compare:

* Company names
* Account names
* Tax IDs
* Countries
* Registration numbers

---

## Consistency Prompt

```text
Compare these data fields.

Return:
- match
- mismatch
- partial_match
- unverifiable

Also include:
- confidence
- detail
```

---

## Example Claude Output

```json
[
  {
    "check": "company_name",
    "status": "partial_match",
    "confidence": 0.85,
    "detail": "Ltd vs Limited"
  }
]
```

---

# Check 3 — Credibility Checks

## Fraud Signal Analysis

### Signals

* Bank country mismatch
* Very recent company
* Suspicious documents
* Generic templates
* Email domain mismatch
* Implausible business logic

---

## Fraud Prompt

```text
Analyze this vendor submission for fraud signals.

Return:
- risk_level
- flags
- reasoning
```

---

## Example Output

```json
{
  "risk_level": "medium",
  "flags": [
    {
      "signal": "country_mismatch",
      "severity": "medium"
    }
  ]
}
```

---

# Step 4 — Decision Engine

## Important Principle

AI performs analysis.

Your backend code makes the final deterministic decision.

This is critical for explainability.

---

## Decision Rules

### Pending

Conditions:

* Missing documents
* Missing critical fields
* Data inconsistencies

---

### Rejected

Conditions:

* High fraud risk
* Multiple medium fraud flags

---

### Approved

Conditions:

* All validations pass
* No serious inconsistencies

---

## Decision Logic Example

```python
def make_decision(completeness, consistency, credibility):

    missing_docs = [
        f for f in completeness
        if f['status'] == 'missing'
    ]

    if missing_docs:
        return {
            "status": "pending"
        }

    if credibility['risk_level'] == 'high':
        return {
            "status": "rejected"
        }

    return {
        "status": "approved"
    }
```

---

## Decision Summary Prompt

```text
Write a clear 2-paragraph summary.

Explain:
- what passed
- what failed
- why the decision was made
```

---

# Step 5 — Output Layer

## Approved Flow

Actions:

* Save VendorRecord
* Save validation results
* Store timestamps
* Optional internal notification

No vendor email required.

---

## Pending Flow

Actions:

* Save pending status
* Generate vendor-facing email
* Send via Resend or SendGrid
* Log communication

---

## Pending Email Prompt

```text
Write a professional onboarding follow-up email.

Clearly explain:
- what is missing
- what needs correction
- how to resubmit

Keep under 200 words.
```

---

## Email Sending Example

```python
import resend

def send_pending_email(email, body):

    resend.Emails.send({
        "from": "onboarding@company.com",
        "to": email,
        "subject": "Vendor onboarding action required",
        "text": body
    })
```

---

## Rejected Flow

Actions:

* Save fraud reasoning internally
* Store audit trail
* Send neutral decline email
* Never expose fraud reasoning externally

---

# Step 6 — Dashboard

## Dashboard View 1 — Run History Table

Columns:

* Vendor name
* Submitted time
* Status badge
* Decision reason
* Actions

---

## Dashboard View 2 — Live Run View

## Pipeline Stages

```text
Intake
↓
Extract Fields
↓
Extract Documents
↓
Merge
↓
Completeness Validation
↓
Consistency Check
↓
Credibility Check
↓
Decision
↓
Output
```

---

## Real-Time Updates

### Option 1 — Polling

Frontend polls every 2 seconds.

### Option 2 — SSE (Recommended)

Use Server-Sent Events.

Benefits:

* Real-time UX
* More production-like
* Better demo impact

---

## Backend Stage Tracking

```python
PIPELINE_STAGES = [
    "intake",
    "extract_fields",
    "extract_docs",
    "merge",
    "check_completeness",
    "check_consistency",
    "check_credibility",
    "decide",
    "output"
]
```

Store each stage completion in DB.

---

## React Polling Example

```javascript
useEffect(() => {

  const poll = setInterval(async () => {

    const res = await fetch(`/api/runs/${runId}/stages`);
    const data = await res.json();

    setStages(data.stages);

  }, 2000);

  return () => clearInterval(poll);

}, []);
```

---

# Edge Cases

---

## EC-1 — Name Typo

### Example

```text
Apex Solutions Ltd
vs
Apex Solution Ltd
```

### Expected

* Pending
* Clarification request
* Not fraud

---

## EC-2 — Country/Bank Mismatch

### Example

```text
Company Country: UK
Bank Country: Nigeria
```

### Expected

* Credibility flag
* Pending or rejected

---

## EC-3 — Missing Bank Letter

### Expected

* Immediate pending
* Pipeline short-circuit
* Avoid unnecessary AI calls

---

## EC-4 — Duplicate Submission

### Detection

Check:

* Same company name
* Same tax ID

### Expected

* Duplicate warning
* Ask if banking details changed
