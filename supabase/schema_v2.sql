-- Schema V2 Migration: versioning, OCR tracking, enhanced email logs
-- Run this in Supabase SQL Editor after schema.sql

-- Add versioning columns to vendors table
ALTER TABLE vendors
  ADD COLUMN IF NOT EXISTS version_number INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS original_run_id VARCHAR,
  ADD COLUMN IF NOT EXISTS resubmission_notes TEXT;

-- Add OCR quality tracking to documents table
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS ocr_status VARCHAR DEFAULT 'unknown',  -- unknown, success, partial, failed
  ADD COLUMN IF NOT EXISTS ocr_issues JSONB;  -- list of issue strings

-- Index for version lookups (all versions of a vendor)
CREATE INDEX IF NOT EXISTS idx_vendors_original_run_id ON vendors (original_run_id);
CREATE INDEX IF NOT EXISTS idx_vendors_version ON vendors (original_run_id, version_number);
