from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

settings = get_settings()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(sub: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": sub, "role": role, "type": "access", "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def create_refresh_token(sub: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": sub, "role": role, "type": "refresh", "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return authorization.split(" ", 1)[1]


def require_admin(authorization: Optional[str] = Header(default=None)):
    token = _extract_bearer(authorization)
    payload = decode_token(token)
    if payload.get("role") != "admin" or payload.get("type") != "access":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def require_vendor(authorization: Optional[str] = Header(default=None)):
    token = _extract_bearer(authorization)
    payload = decode_token(token)
    if payload.get("role") != "vendor" or payload.get("type") != "access":
        raise HTTPException(status_code=403, detail="Vendor access required")
    return payload
