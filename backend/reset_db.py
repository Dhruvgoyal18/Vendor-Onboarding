"""
Hard reset — drops every app table, recreates schema from models, then runs migrate.
Safe to run multiple times. Only touches app-owned tables.
"""
import sys
from sqlalchemy import text
from app.database import engine
from app.models import Base  # noqa — ensures all models are registered


APP_TABLES = [
    # Drop in reverse FK dependency order; CASCADE handles any leftovers
    "audit_events",
    "email_logs",
    "pipeline_stage_logs",
    "validation_results",
    "documents",
    "vendors",
    "refresh_tokens",
    # Legacy zombie tables (may or may not exist)
    "llm_cache",
    "country_configs",
]


def reset():
    print("=== Dropping all app tables ===")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table in APP_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            print(f"  Dropped  {table}")

    print("\n=== Recreating schema from models ===")
    Base.metadata.create_all(engine)
    print("  Tables created via SQLAlchemy metadata")

    print("\n=== Running incremental migration ===")
    from migrate import migrate
    migrate()

    print("=== Reset complete — database is clean ===")


if __name__ == "__main__":
    reset()
