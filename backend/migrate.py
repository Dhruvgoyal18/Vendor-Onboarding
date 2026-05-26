"""
One-shot migration: adds columns/tables introduced in the Phase-2 rewrite.
Safe to run multiple times — every ALTER TABLE is wrapped in a try/except
that silently ignores "column already exists" errors.
"""
import sys
from sqlalchemy import text
from app.database import engine, Base
from app.models import (  # noqa — import all models so metadata is populated
    Vendor, Document, ValidationResult, PipelineStageLog,
    RefreshToken, EmailLog, AuditEvent, LlmCache, CountryConfig,
)


def run_sql(conn, sql: str, description: str):
    try:
        conn.execute(text(sql))
        print(f"  OK  {description}")
    except Exception as e:
        msg = str(e)
        if "already exists" in msg or "duplicate column" in msg.lower():
            print(f"  --  {description} (already exists, skipped)")
        else:
            print(f"  !!  {description} FAILED: {msg}", file=sys.stderr)
            raise


def migrate():
    with engine.begin() as conn:
        print("\n=== Vendor table — new columns ===")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN sla_due_at TIMESTAMP", "sla_due_at")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN deleted_at TIMESTAMP", "deleted_at")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN archived_at TIMESTAMP", "archived_at")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN override_by VARCHAR", "override_by")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN override_at TIMESTAMP", "override_at")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN override_reason TEXT", "override_reason")
        run_sql(conn, "ALTER TABLE vendors ADD COLUMN pipeline_duration_ms BIGINT", "pipeline_duration_ms")

        print("\n=== Document table — new columns ===")
        run_sql(conn, "ALTER TABLE documents ADD COLUMN storage_key VARCHAR", "storage_key")
        run_sql(conn, "ALTER TABLE documents ADD COLUMN file_hash VARCHAR", "file_hash")
        run_sql(conn, "ALTER TABLE documents ADD COLUMN document_verified_type VARCHAR", "document_verified_type")
        run_sql(conn, "ALTER TABLE documents ADD COLUMN quality_score FLOAT", "quality_score")

        print("\n=== New tables ===")
        # AuditEvent
        run_sql(conn, """
            CREATE TABLE IF NOT EXISTS audit_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                event_type VARCHAR NOT NULL,
                actor VARCHAR,
                actor_role VARCHAR,
                payload JSONB,
                created_at TIMESTAMP DEFAULT now()
            )
        """, "audit_events table")

        # LlmCache
        run_sql(conn, """
            CREATE TABLE IF NOT EXISTS llm_cache (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                prompt_hash VARCHAR UNIQUE NOT NULL,
                provider VARCHAR,
                model VARCHAR,
                response_json JSONB,
                created_at TIMESTAMP DEFAULT now(),
                expires_at TIMESTAMP
            )
        """, "llm_cache table")

        # CountryConfig
        run_sql(conn, """
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
        """, "country_configs table")

        print("\n=== Indexes ===")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_vendors_status ON vendors(status)", "ix_vendors_status")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_vendors_country_status ON vendors(country, status)", "ix_vendors_country_status")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_vendors_contact_email ON vendors(contact_email)", "ix_vendors_contact_email")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_vendors_created_at ON vendors(created_at)", "ix_vendors_created_at")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_vendors_original_run_id ON vendors(original_run_id)", "ix_vendors_original_run_id")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_audit_events_vendor_id ON audit_events(vendor_id)", "ix_audit_events_vendor_id")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events(event_type)", "ix_audit_events_event_type")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_llm_cache_prompt_hash ON llm_cache(prompt_hash)", "ix_llm_cache_prompt_hash")
        run_sql(conn, "CREATE INDEX IF NOT EXISTS ix_country_configs_code ON country_configs(country_code)", "ix_country_configs_code")

    print("\n=== Migration complete ===\n")


if __name__ == "__main__":
    migrate()
