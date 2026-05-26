import re
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()


def _clean_db_url(url: str) -> str:
    """
    Fix Supabase pooler connection URLs for psycopg2:
    1. URL-encode special characters in the password (e.g. '@' → '%40')
    2. Strip ?pgbouncer=true which psycopg2 doesn't understand.
    """
    # Step 1: Strip pgbouncer param (simple string approach, avoids urlparse issues)
    url = re.sub(r'[?&]pgbouncer=true', '', url)

    # Step 2: Encode special chars in password.
    # Supabase URLs have the form: postgresql://user:password@host:port/db
    # If password contains '@', the last '@' before the host is the real delimiter.
    # We match: scheme://userinfo@host... where userinfo may contain '@' in password.
    m = re.match(
        r'^(postgresql(?:\+\w+)?://)([^@]+):(.+)@([^@]+)$',
        url
    )
    if m:
        scheme_user = m.group(1) + m.group(2)  # e.g. postgresql://postgres.xxx
        password = m.group(3)                   # e.g. Suppandi@16
        rest = m.group(4)                       # e.g. host:port/db
        encoded_password = password.replace('@', '%40').replace(':', '%3A')
        url = f"{scheme_user}:{encoded_password}@{rest}"

    return url


_db_url = _clean_db_url(settings.database_url)

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
