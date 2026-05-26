-- Vendor Onboarding System - Supabase Schema Migration
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Enums ──────────────────────────────────────────────────────────────────────

CREATE TYPE submission_status AS ENUM (
    'processing', 'pending', 'approved', 'rejected', 'error'
);

CREATE TYPE pipeline_stage AS ENUM (
    'intake', 'extract_fields', 'extract_docs', 'merge',
    'check_completeness', 'check_consistency', 'check_credibility',
    'decide', 'output', 'done'
);

CREATE TYPE stage_status AS ENUM (
    'pending', 'running', 'completed', 'failed', 'skipped'
);

-- ─── Vendors Table ───────────────────────────────────────────────────────────────

CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR NOT NULL UNIQUE,

    -- Company Info
    company_name VARCHAR NOT NULL,
    registration_number VARCHAR,
    country CHAR(2),
    incorporation_date VARCHAR,

    -- Contact Info
    contact_name VARCHAR,
    contact_email VARCHAR,

    -- Tax Info
    tax_id VARCHAR,
    tax_id_type VARCHAR,

    -- Banking Info
    bank_account_name VARCHAR,
    account_number VARCHAR,
    bank_name VARCHAR,
    bank_country CHAR(2),

    -- Status & Decision
    status submission_status NOT NULL DEFAULT 'processing',
    current_stage pipeline_stage DEFAULT 'intake',
    decision_summary TEXT,
    risk_level VARCHAR,

    -- Merged data (all extracted information)
    merged_data JSONB,

    -- Duplicate detection
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_run_id VARCHAR,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

CREATE INDEX idx_vendors_run_id ON vendors (run_id);
CREATE INDEX idx_vendors_status ON vendors (status);
CREATE INDEX idx_vendors_company_name ON vendors (company_name);
CREATE INDEX idx_vendors_created_at ON vendors (created_at DESC);

-- ─── Documents Table ──────────────────────────────────────────────────────────────

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    document_type VARCHAR NOT NULL,   -- registration, bank_letter, tax_cert
    file_path VARCHAR,                -- Supabase storage path
    original_filename VARCHAR,
    extracted_json JSONB,
    extraction_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_vendor_id ON documents (vendor_id);

-- ─── Validation Results Table ─────────────────────────────────────────────────────

CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    category VARCHAR NOT NULL,        -- completeness, consistency, credibility
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,          -- pass, fail, warning, missing, match, mismatch
    detail TEXT,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_validation_results_vendor_id ON validation_results (vendor_id);

-- ─── Pipeline Stage Logs Table ────────────────────────────────────────────────────

CREATE TABLE pipeline_stage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    stage pipeline_stage NOT NULL,
    status stage_status DEFAULT 'pending',
    message TEXT,
    metadata JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_pipeline_stage_logs_vendor_id ON pipeline_stage_logs (vendor_id);
CREATE UNIQUE INDEX idx_pipeline_stage_unique ON pipeline_stage_logs (vendor_id, stage);

-- ─── Email Logs Table ─────────────────────────────────────────────────────────────

CREATE TABLE email_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    recipient VARCHAR NOT NULL,
    subject VARCHAR NOT NULL,
    body TEXT,
    email_type VARCHAR,               -- pending_request, rejection_neutral, approval
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error TEXT
);

CREATE INDEX idx_email_logs_vendor_id ON email_logs (vendor_id);

-- ─── Auto-update updated_at trigger ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_vendors_updated_at
    BEFORE UPDATE ON vendors
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

-- ─── Row Level Security (Optional - for multi-tenant) ────────────────────────────
-- Enable RLS on all tables (disable for service role access)
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE validation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_stage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_logs ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (backend uses service key)
CREATE POLICY "service_role_all" ON vendors FOR ALL USING (true);
CREATE POLICY "service_role_all" ON documents FOR ALL USING (true);
CREATE POLICY "service_role_all" ON validation_results FOR ALL USING (true);
CREATE POLICY "service_role_all" ON pipeline_stage_logs FOR ALL USING (true);
CREATE POLICY "service_role_all" ON email_logs FOR ALL USING (true);
