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
    RefreshToken, EmailLog, AuditEvent,
)

_STATEMENTS = [
    # ── Vendor table: Phase-2 columns ──────────────────────────────────────
    ("vendors.sla_due_at",              "ALTER TABLE vendors ADD COLUMN sla_due_at TIMESTAMP"),
    ("vendors.override_by",             "ALTER TABLE vendors ADD COLUMN override_by VARCHAR"),
    ("vendors.override_at",             "ALTER TABLE vendors ADD COLUMN override_at TIMESTAMP"),
    ("vendors.override_reason",         "ALTER TABLE vendors ADD COLUMN override_reason TEXT"),
    ("vendors.pipeline_duration_ms",    "ALTER TABLE vendors ADD COLUMN pipeline_duration_ms BIGINT"),

    # ── Document table: Phase-2 columns ────────────────────────────────────
    ("documents.storage_key",           "ALTER TABLE documents ADD COLUMN storage_key VARCHAR"),
    ("documents.quality_score",         "ALTER TABLE documents ADD COLUMN quality_score FLOAT"),

    # ── Core tables (idempotent) ────────────────────────────────────────────
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
    ("refresh_tokens table", """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            token_hash VARCHAR UNIQUE NOT NULL,
            role VARCHAR NOT NULL,
            subject VARCHAR NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT now()
        )
    """),

    # ── Schema V2: vendor versioning ────────────────────────────────────────
    ("vendors.version_number",          "ALTER TABLE vendors ADD COLUMN version_number INTEGER DEFAULT 1"),
    ("vendors.original_run_id",         "ALTER TABLE vendors ADD COLUMN original_run_id VARCHAR"),
    ("vendors.resubmission_notes",      "ALTER TABLE vendors ADD COLUMN resubmission_notes TEXT"),

    # ── Schema V2: document OCR tracking ───────────────────────────────────
    ("documents.ocr_status",            "ALTER TABLE documents ADD COLUMN ocr_status VARCHAR DEFAULT 'unknown'"),
    ("documents.ocr_issues",            "ALTER TABLE documents ADD COLUMN ocr_issues JSONB"),

    # ── Schema V3: document timestamps ─────────────────────────────────────
    ("documents.updated_at",            "ALTER TABLE documents ADD COLUMN updated_at TIMESTAMP"),
    ("documents.updated_at backfill",   "UPDATE documents SET updated_at = created_at WHERE updated_at IS NULL"),

    # ── Schema V3: drop dead document columns ──────────────────────────────
    ("documents.file_hash drop",             "ALTER TABLE documents DROP COLUMN IF EXISTS file_hash"),
    ("documents.document_verified_type drop","ALTER TABLE documents DROP COLUMN IF EXISTS document_verified_type"),

    # ── Schema V4: drop zombie vendor columns ──────────────────────────────
    ("vendors.deleted_at drop",         "ALTER TABLE vendors DROP COLUMN IF EXISTS deleted_at"),
    ("vendors.archived_at drop",        "ALTER TABLE vendors DROP COLUMN IF EXISTS archived_at"),

    # ── Schema V4: drop zombie tables ──────────────────────────────────────
    ("drop llm_cache",                  "DROP TABLE IF EXISTS llm_cache"),
    ("drop country_configs",            "DROP TABLE IF EXISTS country_configs"),

    # ── Indexes ─────────────────────────────────────────────────────────────
    ("idx vendors.status",              "CREATE INDEX IF NOT EXISTS ix_vendors_status ON vendors(status)"),
    ("idx vendors.country+status",      "CREATE INDEX IF NOT EXISTS ix_vendors_country_status ON vendors(country, status)"),
    ("idx vendors.contact_email",       "CREATE INDEX IF NOT EXISTS ix_vendors_contact_email ON vendors(contact_email)"),
    ("idx vendors.created_at",          "CREATE INDEX IF NOT EXISTS ix_vendors_created_at ON vendors(created_at)"),
    ("idx vendors.original_run_id",     "CREATE INDEX IF NOT EXISTS ix_vendors_original_run_id ON vendors(original_run_id)"),
    ("idx vendors.version",             "CREATE INDEX IF NOT EXISTS ix_vendors_version ON vendors(original_run_id, version_number)"),
    ("idx audit_events.vendor_id",      "CREATE INDEX IF NOT EXISTS ix_audit_events_vendor_id ON audit_events(vendor_id)"),
    ("idx audit_events.event_type",     "CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events(event_type)"),
    ("idx refresh_tokens.token_hash",   "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens(token_hash)"),
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
