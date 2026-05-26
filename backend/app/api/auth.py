import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.config import get_settings
from app.database import get_db
from app.models import RefreshToken, Vendor

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class VendorLoginRequest(BaseModel):
    email: str
    run_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _store_refresh_token(
    db: Session, token: str, role: str, subject: str
) -> None:
    # Rotate: revoke all active tokens for this subject+role
    db.query(RefreshToken).filter(
        RefreshToken.subject == subject,
        RefreshToken.role == role,
        RefreshToken.revoked == False,
    ).update({"revoked": True})

    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(
        token_hash=_hash(token),
        role=role,
        subject=subject,
        expires_at=expires_at,
    ))
    db.commit()


def _verify_refresh_token(db: Session, token: str, expected_role: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "refresh" or payload.get("role") != expected_role:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == _hash(token),
        RefreshToken.revoked == False,
    ).first()

    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Rotate: mark current token as used
    stored.revoked = True
    db.commit()

    return payload


# ─── Admin ────────────────────────────────────────────────────────────────────

@router.post("/admin/login", response_model=TokenResponse)
def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    if req.username != settings.admin_username or req.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(sub=req.username, role="admin")
    refresh_token = create_refresh_token(sub=req.username, role="admin")
    _store_refresh_token(db, refresh_token, "admin", req.username)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/admin/refresh", response_model=TokenResponse)
def admin_refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = _verify_refresh_token(db, req.refresh_token, "admin")

    new_access = create_access_token(sub=payload["sub"], role="admin")
    new_refresh = create_refresh_token(sub=payload["sub"], role="admin")
    _store_refresh_token(db, new_refresh, "admin", payload["sub"])

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/admin/logout")
def admin_logout(req: RefreshRequest, db: Session = Depends(get_db)):
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == _hash(req.refresh_token)
    ).update({"revoked": True})
    db.commit()
    return {"ok": True}


# ─── Vendor ───────────────────────────────────────────────────────────────────

@router.post("/vendor/login", response_model=TokenResponse)
def vendor_login(req: VendorLoginRequest, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(
        Vendor.run_id == req.run_id,
        Vendor.contact_email == req.email,
    ).first()

    if not vendor:
        raise HTTPException(
            status_code=401,
            detail="No submission found for this email and Application ID",
        )

    access_token = create_access_token(sub=req.email, role="vendor")
    refresh_token = create_refresh_token(sub=req.email, role="vendor")
    _store_refresh_token(db, refresh_token, "vendor", req.email)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/vendor/refresh", response_model=TokenResponse)
def vendor_refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = _verify_refresh_token(db, req.refresh_token, "vendor")

    new_access = create_access_token(sub=payload["sub"], role="vendor")
    new_refresh = create_refresh_token(sub=payload["sub"], role="vendor")
    _store_refresh_token(db, new_refresh, "vendor", payload["sub"])

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/vendor/logout")
def vendor_logout(req: RefreshRequest, db: Session = Depends(get_db)):
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == _hash(req.refresh_token)
    ).update({"revoked": True})
    db.commit()
    return {"ok": True}


@router.get("/vendor/me")
def vendor_me(db: Session = Depends(get_db), authorization: str = None):
    """Get all submissions for the authenticated vendor's email."""
    from app.auth import require_vendor
    from fastapi import Request
    # This is called via the require_vendor dependency in the route
    raise HTTPException(status_code=405, detail="Use GET /api/submissions/mine")
