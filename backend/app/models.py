import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Text, JSON, Enum, ForeignKey, Boolean, Float, Integer,
    BigInteger, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class SubmissionStatus(str, enum.Enum):
    processing = "processing"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    error = "error"


class PipelineStage(str, enum.Enum):
    intake = "intake"
    extract_fields = "extract_fields"
    format_check = "format_check"           # Layer 1: deterministic format checks
    external_verification = "external_verification"  # MCA21 / GST portal / IFSC / penny drop
    extract_docs = "extract_docs"
    cross_doc_check = "cross_doc_check" # Layer 3: cross-document checks
    merge = "merge"
    check_completeness = "check_completeness"
    check_consistency = "check_consistency"
    check_credibility = "check_credibility"
    decide = "decide"
    output = "output"
    done = "done"


class StageStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, unique=True, nullable=False, index=True)

    # Company Info
    company_name = Column(String, nullable=False)
    registration_number = Column(String)
    country = Column(String(2))
    incorporation_date = Column(String)

    # Contact Info
    contact_name = Column(String)
    contact_email = Column(String)

    # Tax Info
    tax_id = Column(String)
    tax_id_type = Column(String)

    # India-specific fields
    cin_number = Column(String)          # Certificate of Incorporation Number
    pan_number = Column(String)          # PAN card number
    gstin_number = Column(String)        # GSTIN
    ifsc_code = Column(String)           # IFSC code
    account_type = Column(String)        # Current / Savings
    registered_state = Column(String)    # Registered state (India)

    # Banking Info
    bank_account_name = Column(String)
    account_number = Column(String)
    bank_name = Column(String)
    bank_country = Column(String(2))

    # Status & Decision
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.processing, nullable=False)
    current_stage = Column(String, default=PipelineStage.intake.value)  # String to avoid PG enum caching
    decision_summary = Column(Text)
    risk_level = Column(String)

    # Merged vendor object (all extracted data)
    merged_data = Column(JSON)

    # Duplicate detection
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_run_id = Column(String)

    # Version tracking (for resubmissions)
    version_number = Column(Integer, default=1)
    original_run_id = Column(String)         # run_id of the first submission (all versions share this)
    resubmission_notes = Column(Text)        # vendor's notes on what they fixed

    # SLA & lifecycle
    sla_due_at = Column(DateTime)                  # created_at + 48h
    deleted_at = Column(DateTime)
    archived_at = Column(DateTime)

    # Admin override
    override_by = Column(String)                   # admin username
    override_at = Column(DateTime)
    override_reason = Column(Text)

    # Pipeline telemetry
    pipeline_duration_ms = Column(BigInteger)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    decided_at = Column(DateTime)

    # Relationships
    documents = relationship("Document", back_populates="vendor", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="vendor", cascade="all, delete-orphan")
    pipeline_stages = relationship("PipelineStageLog", back_populates="vendor", cascade="all, delete-orphan")
    email_logs = relationship("EmailLog", back_populates="vendor", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="vendor", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    document_type = Column(String, nullable=False)  # registration, bank_letter, tax_cert
    file_path = Column(String)
    original_filename = Column(String)
    extracted_json = Column(JSON)
    extraction_confidence = Column(Float)
    ocr_status = Column(String, default='unknown')  # unknown, success, partial, failed
    ocr_issues = Column(JSON)
    # Extended document fields
    storage_key = Column(String)                    # Supabase storage object key
    file_hash = Column(String)                      # SHA-256 of raw bytes
    document_verified_type = Column(String)         # LLM-confirmed doc type
    quality_score = Column(Float)                   # 0-1 extraction quality score
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="documents")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    category = Column(String, nullable=False)  # completeness, consistency, credibility
    check_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # pass, fail, warning, missing, match, mismatch
    detail = Column(Text)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="validation_results")


class PipelineStageLog(Base):
    __tablename__ = "pipeline_stage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    stage = Column(String, nullable=False)   # String to avoid PG enum caching for new values
    status = Column(String, default=StageStatus.pending.value)
    message = Column(Text)
    stage_metadata = Column('metadata', JSON)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    vendor = relationship("Vendor", back_populates="pipeline_stages")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False)       # "admin" or "vendor"
    subject = Column(String, nullable=False)    # username or email
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text)
    email_type = Column(String)  # pending_request, rejection_neutral, approval
    sent_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)
    error = Column(Text)

    vendor = relationship("Vendor", back_populates="email_logs")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    event_type = Column(String, nullable=False)  # submission_created, override, status_change, retry
    actor = Column(String)                        # username or "system"
    actor_role = Column(String)                   # admin, vendor, system
    payload = Column(JSON)                        # arbitrary event data
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="audit_events")


class LlmCache(Base):
    """Cache LLM responses to avoid duplicate API calls for identical inputs."""
    __tablename__ = "llm_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_hash = Column(String, unique=True, nullable=False, index=True)  # SHA-256 of prompt+input
    provider = Column(String)
    model = Column(String)
    response_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


class CountryConfig(Base):
    """Per-country validation configuration."""
    __tablename__ = "country_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(String(2), unique=True, nullable=False, index=True)
    required_documents = Column(JSON)     # list of required doc types
    required_fields = Column(JSON)        # list of required form fields
    validation_rules = Column(JSON)       # country-specific rule overrides
    sla_hours = Column(Integer, default=48)
    active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Performance indexes ──────────────────────────────────────────────────────
Index("ix_vendors_status", Vendor.status)
Index("ix_vendors_country_status", Vendor.country, Vendor.status)
Index("ix_vendors_contact_email", Vendor.contact_email)
Index("ix_vendors_created_at", Vendor.created_at)
Index("ix_vendors_original_run_id", Vendor.original_run_id)
Index("ix_audit_events_vendor_id", AuditEvent.vendor_id)
Index("ix_audit_events_event_type", AuditEvent.event_type)
