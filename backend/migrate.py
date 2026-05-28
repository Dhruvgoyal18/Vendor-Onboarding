"""
Idempotent migration — safe to run multiple times.
Each statement runs in its own autocommit connection so a "column already exists"
error on one ALTER TABLE does NOT abort subsequent statements.
"""
import sys
from sqlalchemy import text
from app.database import engine
from app.models import (  # noqa — registers metadata
    Vendor, Document, ValidationResult, PipelineStageLog,
    RefreshToken, EmailLog, AuditEvent, LlmCache, CountryConfig,
)

_STATEMENTS = [
    # ── Vendor table: Phase-2 columns ──────────────────────────────────────
    ("vendors.sla_due_at",              "ALTER TABLE vendors ADD COLUMN sla_due_at TIMESTAMP"),
    ("vendors.deleted_at",              "ALTER TABLE vendors ADD COLUMN deleted_at TIMESTAMP"),
    ("vendors.archived_at",             "ALTER TABLE vendors ADD COLUMN archived_at TIMESTAMP"),
    ("vendors.override_by",             "ALTER TABLE vendors ADD COLUMN override_by VARCHAR"),
    ("vendors.override_at",             "ALTER TABLE vendors ADD COLUMN override_at TIMESTAMP"),
    ("vendors.override_reason",         "ALTER TABLE vendors ADD COLUMN override_reason TEXT"),
    ("vendors.pipeline_duration_ms",    "ALTER TABLE vendors ADD COLUMN pipeline_duration_ms BIGINT"),

    # ── Document table: Phase-2 columns ────────────────────────────────────
    ("documents.storage_key",           "ALTER TABLE documents ADD COLUMN storage_key VARCHAR"),
    ("documents.file_hash",             "ALTER TABLE documents ADD COLUMN file_hash VARCHAR"),
    ("documents.document_verified_type","ALTER TABLE documents ADD COLUMN document_verified_type VARCHAR"),
    ("documents.quality_score",         "ALTER TABLE documents ADD COLUMN quality_score FLOAT"),

    # ── New tables ──────────────────────────────────────────────────────────
    ("audit_events table", """
        CREATE TABLE IF NOT EXISTS audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            event_type VARCHAR NOT NULL,
            actor VARCHAR,
            actor_role VARCHAR,
            payload JSONB,
            created_at TIMESTAMP DEFAULT now()
        )
    """),
    ("llm_cache table", """
        CREATE TABLE IF NOT EXISTS llm_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            prompt_hash VARCHAR UNIQUE NOT NULL,
            provider VARCHAR,
            model VARCHAR,
            response_json JSONB,
            created_at TIMESTAMP DEFAULT now(),
            expires_at TIMESTAMP
        )
    """),
    ("country_configs table", """
        CREATE TABLE IF NOT EXISTS country_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            country_code VARCHAR(2) UNIQUE NOT NULL,
            required_documents JSONB,
            required_fields JSONB,
            validation_rules JSONB,
            sla_hours INTEGER DEFAULT 48,
            active BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT now()
        )
    """),

    # ── Schema V2: vendor versioning ────────────────────────────────────────
    ("vendors.version_number",          "ALTER TABLE vendors ADD COLUMN version_number INTEGER DEFAULT 1"),
    ("vendors.original_run_id",         "ALTER TABLE vendors ADD COLUMN original_run_id VARCHAR"),
    ("vendors.resubmission_notes",      "ALTER TABLE vendors ADD COLUMN resubmission_notes TEXT"),

    # ── Schema V2: document OCR tracking ───────────────────────────────────
    ("documents.ocr_status",            "ALTER TABLE documents ADD COLUMN ocr_status VARCHAR DEFAULT 'unknown'"),
    ("documents.ocr_issues",            "ALTER TABLE documents ADD COLUMN ocr_issues JSONB"),

    # ── Indexes ─────────────────────────────────────────────────────────────
    ("idx vendors.status",              "CREATE INDEX IF NOT EXISTS ix_vendors_status ON vendors(status)"),
    ("idx vendors.country+status",      "CREATE INDEX IF NOT EXISTS ix_vendors_country_status ON vendors(country, status)"),
    ("idx vendors.contact_email",       "CREATE INDEX IF NOT EXISTS ix_vendors_contact_email ON vendors(contact_email)"),
    ("idx vendors.created_at",          "CREATE INDEX IF NOT EXISTS ix_vendors_created_at ON vendors(created_at)"),
    ("idx vendors.original_run_id",     "CREATE INDEX IF NOT EXISTS ix_vendors_original_run_id ON vendors(original_run_id)"),
    ("idx vendors.version",             "CREATE INDEX IF NOT EXISTS ix_vendors_version ON vendors(original_run_id, version_number)"),
    ("idx audit_events.vendor_id",      "CREATE INDEX IF NOT EXISTS ix_audit_events_vendor_id ON audit_events(vendor_id)"),
    ("idx audit_events.event_type",     "CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events(event_type)"),
    ("idx llm_cache.prompt_hash",       "CREATE INDEX IF NOT EXISTS ix_llm_cache_prompt_hash ON llm_cache(prompt_hash)"),
    ("idx country_configs.code",        "CREATE INDEX IF NOT EXISTS ix_country_configs_code ON country_configs(country_code)"),
]


def migrate():
    ok = skipped = failed = 0

    for description, sql in _STATEMENTS:
        # Each statement gets its own autocommit connection so a failure on one
        # does not abort subsequent statements (PostgreSQL tx semantics).
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            try:
                conn.execute(text(sql.strip()))
                print(f"  OK      {description}")
                ok += 1
            except Exception as e:
                msg = str(e)
                if "already exists" in msg or "duplicate column" in msg.lower():
                    print(f"  SKIP    {description}")
                    skipped += 1
                else:
                    print(f"  FAIL    {description}: {msg}", file=sys.stderr)
                    failed += 1

    print(f"\n=== Migration done — {ok} applied, {skipped} skipped, {failed} failed ===\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    migrate()
