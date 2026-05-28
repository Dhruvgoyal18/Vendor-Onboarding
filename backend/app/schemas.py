from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum
import uuid


# ─── Enums ─────────────────────────────────────────────────────────────────────

class TaxIdType(str, Enum):
    VAT = "VAT"
    EIN = "EIN"
    GST = "GST"
    PAN = "PAN"
    GSTIN = "GSTIN"
    OTHER = "OTHER"


class SubmissionStatus(str, Enum):
    processing = "processing"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    error = "error"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


# ─── Override ───────────────────────────────────────────────────────────────────

class OverrideRequest(BaseModel):
    decision: str   # "approved" or "rejected"
    reason: str


# ─── Submission ─────────────────────────────────────────────────────────────────

class SubmissionFormData(BaseModel):
    # Core fields (all countries)
    company_name: str
    registration_number: str
    country: str
    incorporation_date: str
    contact_name: str
    contact_email: str
    tax_id: Optional[str] = None
    tax_id_type: Optional[str] = None
    bank_account_name: str
    account_number: str
    bank_name: str
    bank_country: str

    # India-specific fields (optional for other countries)
    cin_number: Optional[str] = None       # Certificate of Incorporation Number
    pan_number: Optional[str] = None       # PAN card
    gstin_number: Optional[str] = None     # GSTIN
    ifsc_code: Optional[str] = None        # IFSC
    account_type: Optional[str] = None     # Current / Savings
    registered_state: Optional[str] = None # Indian state

    @field_validator("country", "bank_country")
    @classmethod
    def uppercase_country(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("company_name", "bank_account_name", "bank_name", "contact_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("tax_id")
    @classmethod
    def normalize_tax_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().upper().replace(" ", "").replace("-", "")

    @field_validator("cin_number", "pan_number", "gstin_number", "ifsc_code")
    @classmethod
    def normalize_india_ids(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().upper().replace(" ", "")


# ─── Documents ──────────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    document_type: str
    storage_key: Optional[str]
    original_filename: Optional[str]
    extracted_json: Optional[Dict[str, Any]]
    extraction_confidence: Optional[float]
    ocr_status: Optional[str] = "unknown"
    ocr_issues: Optional[List[Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Validation Result ──────────────────────────────────────────────────────────

class ValidationResultOut(BaseModel):
    id: str
    category: str
    check_name: str
    status: str
    detail: Optional[str]
    confidence: Optional[float]

    class Config:
        from_attributes = True


# ─── Pipeline Stage ─────────────────────────────────────────────────────────────

class PipelineStageOut(BaseModel):
    stage: str
    status: str
    message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Vendor / Run ───────────────────────────────────────────────────────────────

class EmailLogOut(BaseModel):
    id: str
    recipient: str
    subject: str
    body: Optional[str]
    email_type: Optional[str]
    sent_at: datetime
    success: bool

    class Config:
        from_attributes = True


class AuditEventOut(BaseModel):
    id: str
    event_type: str
    actor: Optional[str]
    actor_role: Optional[str]
    payload: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class VendorVersionOut(BaseModel):
    run_id: str
    version_number: int
    created_at: datetime
    status: str
    decision_summary: Optional[str]
    resubmission_notes: Optional[str] = None

    class Config:
        from_attributes = True


class VendorOut(BaseModel):
    id: str
    run_id: str
    company_name: str
    registration_number: Optional[str]
    country: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    tax_id: Optional[str]
    bank_account_name: Optional[str]
    bank_country: Optional[str]
    status: str
    current_stage: Optional[str]
    decision_summary: Optional[str]
    risk_level: Optional[str]
    is_duplicate: bool
    duplicate_of_run_id: Optional[str]
    version_number: Optional[int] = 1
    original_run_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True


class VendorDetailOut(VendorOut):
    # Fields not surfaced in the list view
    incorporation_date: Optional[str] = None
    tax_id_type: Optional[str] = None
    bank_name: Optional[str] = None
    cin_number: Optional[str] = None
    pan_number: Optional[str] = None
    gstin_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_type: Optional[str] = None
    registered_state: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    override_by: Optional[str] = None
    override_at: Optional[datetime] = None
    override_reason: Optional[str] = None
    pipeline_duration_ms: Optional[int] = None
    # Related objects
    documents: List[DocumentOut] = []
    validation_results: List[ValidationResultOut] = []
    pipeline_stages: List[PipelineStageOut] = []
    merged_data: Optional[Dict[str, Any]] = None
    email_logs: List[EmailLogOut] = []
    audit_events: List[AuditEventOut] = []


# ─── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total: int
    approved: int
    pending: int
    rejected: int
    processing: int
    error: int


class PaginatedVendors(BaseModel):
    items: List[VendorOut]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Submission Response ────────────────────────────────────────────────────────

class SubmissionResponse(BaseModel):
    run_id: str
    message: str


# ─── SSE Event ─────────────────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]
