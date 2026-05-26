import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Text, JSON, Enum, ForeignKey, Boolean, Float, Integer
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
    format_check = "format_check"       # Layer 1: deterministic format checks
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

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    decided_at = Column(DateTime)

    # Relationships
    documents = relationship("Document", back_populates="vendor", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="vendor", cascade="all, delete-orphan")
    pipeline_stages = relationship("PipelineStageLog", back_populates="vendor", cascade="all, delete-orphan")
    email_logs = relationship("EmailLog", back_populates="vendor", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    document_type = Column(String, nullable=False)  # registration, bank_letter, tax_cert
    file_path = Column(String)  # Supabase storage path
    original_filename = Column(String)
    extracted_json = Column(JSON)
    extraction_confidence = Column(Float)
    ocr_status = Column(String, default='unknown')  # unknown, success, partial, failed
    ocr_issues = Column(JSON)                        # list of issue strings
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
