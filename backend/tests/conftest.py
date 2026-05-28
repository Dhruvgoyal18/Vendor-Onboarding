"""
Shared pytest fixtures.

Uses an in-memory SQLite DB so tests never touch the real Supabase Postgres.
The FastAPI app is imported after env vars are patched so Settings validation passes.
"""
import os
import pytest
from unittest.mock import patch

# Patch required env vars before importing anything that calls get_settings()
ENV_OVERRIDES = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-anon-key",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "DATABASE_URL": "sqlite:///./test.db",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "GROQ_API_KEY": "",
    "RESEND_API_KEY": "",
}

@pytest.fixture(scope="session", autouse=True)
def patch_env():
    with patch.dict(os.environ, ENV_OVERRIDES):
        yield


@pytest.fixture(scope="session")
def admin_token(patch_env):
    """Valid admin JWT for use in protected endpoint tests."""
    from app.auth import create_access_token
    return create_access_token("admin", "admin")


@pytest.fixture(scope="session")
def test_client(patch_env):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.database import Base
    from app.main import app
    from app.database import get_db

    engine = create_engine(
        "sqlite:///./test_vendorai.db",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    Base.metadata.drop_all(bind=engine)
    import pathlib
    pathlib.Path("./test_vendorai.db").unlink(missing_ok=True)
