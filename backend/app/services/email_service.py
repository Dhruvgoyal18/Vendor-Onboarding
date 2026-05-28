import logging
import resend
from typing import List, Dict
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(
    to: str,
    subject: str,
    body: str,
    email_type: str = "generic"
) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured — skipping email send")
        logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}\n{body}")
        return True  # Mock success in dev

    try:
        resend.api_key = settings.resend_api_key
        params = {
            "from": settings.from_email,
            "to": [to],
            "subject": subject,
            "text": body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent: {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_pending_email(
    to: str,
    vendor_name: str,
    email_body: str,
) -> bool:
    """Send pending/clarification request email to vendor."""
    return send_email(
        to=to,
        subject=f"Action Required: Vendor Onboarding for {vendor_name}",
        body=email_body,
        email_type="pending_request",
    )


def send_rejection_email(
    to: str,
    vendor_name: str,
    email_body: str,
) -> bool:
    """Send neutral rejection email to vendor."""
    return send_email(
        to=to,
        subject=f"Vendor Application Update — {vendor_name}",
        body=email_body,
        email_type="rejection_neutral",
    )


def _approval_email_body(vendor_name: str) -> str:
    return f"""Dear {vendor_name},

We are pleased to inform you that your vendor onboarding application has been reviewed and approved.

Your company is now registered as an approved vendor in our system.

What happens next:
  1. Our procurement team will reach out to you within 2–3 business days to discuss next steps.
  2. You will receive your vendor code and portal access credentials.
  3. Please keep your submitted documents on file for future reference.

If you have any questions, please contact our procurement team.

Congratulations and welcome aboard!

Best regards,
Vendor Onboarding Team"""


def send_approval_email(to: str, vendor_name: str) -> bool:
    """Send approval confirmation email to vendor."""
    return send_email(
        to=to,
        subject=f"Vendor Application Approved — {vendor_name}",
        body=_approval_email_body(vendor_name),
        email_type="approval",
    )


def send_ocr_failure_email(
    to: str,
    vendor_name: str,
    failed_docs: List[Dict],
) -> bool:
    """Send email when OCR fails for one or more uploaded documents."""
    doc_labels = {
        "coi": "Certificate of Incorporation (COI)",
        "registration": "Registration Certificate",
        "pan_gstin": "PAN Card & GSTIN Certificate",
        "tax_cert": "Tax Certificate",
        "bank_letter": "Bank Letter / Cancelled Cheque",
        "bank": "Bank Letter / Cancelled Cheque",
    }

    lines = []
    for doc in failed_docs:
        label = doc_labels.get(doc.get("type", ""), doc.get("type", "document").replace("_", " ").title())
        issues = doc.get("issues", ["Unable to extract text from this document"])
        issues_str = "; ".join(issues)
        lines.append(f"  • {label}: {issues_str}")

    doc_block = "\n".join(lines)

    body = f"""Dear {vendor_name},

Thank you for submitting your vendor onboarding application.

Our system encountered issues extracting information from the following uploaded document(s):

{doc_block}

This usually happens when:
  • The document is blurry, too dark, or low resolution (minimum 300 DPI recommended)
  • The document is password-protected or encrypted
  • The file is corrupt or partially uploaded
  • Text in the document is overlapping or obscured

To resolve this, please:
  1. Re-scan the document at a higher resolution (300 DPI or higher)
  2. Ensure the document is not password-protected
  3. Make sure all key fields (name, number, date) are clearly legible
  4. Upload the corrected document by resubmitting your application

You can resubmit using the "Resubmit" button on your application status page.

If you continue to experience issues, please contact our procurement team.

Best regards,
Vendor Onboarding Team"""

    return send_email(
        to=to,
        subject=f"Action Required: Document Processing Issue — {vendor_name}",
        body=body,
        email_type="ocr_failure",
    )
