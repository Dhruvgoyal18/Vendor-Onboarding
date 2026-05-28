"""
Supabase Storage service for vendor documents.
Uses the Supabase Storage REST API directly via httpx (no extra SDK dependency).
Bucket: vendor-documents (private)
Path format: {run_id}/{doc_type}/{original_filename}
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BUCKET = "vendor-documents"


def _auth_headers() -> dict:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.supabase_service_key}"}


def ensure_bucket_exists() -> None:
    """Create the storage bucket on first startup if it doesn't exist."""
    settings = get_settings()
    base = f"{settings.supabase_url}/storage/v1"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/bucket/{BUCKET}", headers=_auth_headers())
            if resp.status_code == 200:
                logger.info(f"Storage bucket '{BUCKET}' exists")
                return

            resp = client.post(
                f"{base}/bucket",
                json={"id": BUCKET, "name": BUCKET, "public": False},
                headers={**_auth_headers(), "Content-Type": "application/json"},
            )
            if resp.status_code in (200, 201):
                logger.info(f"Created storage bucket '{BUCKET}'")
            else:
                logger.warning(f"Could not create bucket '{BUCKET}': {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Bucket init failed (non-fatal): {e}")


def upload_document(run_id: str, doc_type: str, filename: str, file_bytes: bytes) -> Optional[str]:
    """
    Upload a document to Supabase Storage.
    Returns the storage_key (path within bucket) on success, None on failure.
    """
    settings = get_settings()
    storage_key = f"{run_id}/{doc_type}/{filename}"
    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{storage_key}"

    lower = filename.lower()
    if lower.endswith(".pdf"):
        content_type = "application/pdf"
    elif lower.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif lower.endswith(".png"):
        content_type = "image/png"
    else:
        content_type = "application/octet-stream"

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                url,
                content=file_bytes,
                headers={**_auth_headers(), "Content-Type": content_type},
            )
            if resp.status_code in (200, 201):
                logger.info(f"Uploaded to Supabase Storage: {storage_key}")
                return storage_key
            logger.error(f"Supabase Storage upload failed ({resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Supabase Storage upload error for {storage_key}: {e}")
        return None


def download_document(storage_key: str) -> Optional[bytes]:
    """
    Download a document from Supabase Storage.
    Returns raw bytes on success, None on failure.
    """
    settings = get_settings()
    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{storage_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url, headers=_auth_headers())
            if resp.status_code == 200:
                logger.info(f"Downloaded from Supabase Storage: {storage_key}")
                return resp.content
            logger.error(f"Supabase Storage download failed ({resp.status_code}): {storage_key}")
            return None
    except Exception as e:
        logger.error(f"Supabase Storage download error for {storage_key}: {e}")
        return None
