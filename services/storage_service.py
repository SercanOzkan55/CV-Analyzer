"""High-level CV storage service.

Business logic for storing / retrieving original and optimized CVs.
Delegates all S3 I/O to s3_service.  This is the only module that
API routes should import for file-storage operations.
"""

import logging
import uuid
from typing import Literal

from config.aws import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, is_configured
from security.file_guard import validate_file_upload
from security.s3_guard import enforce_ownership
from security.validators import validate_user_id
from services import s3_service
from services import local_storage_service
import os

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "s3").lower()

logger = logging.getLogger(__name__)

Folder = Literal["original", "optimized"]


# ── Key builder ─────────────────────────────────────────────────────

def build_key(user_id: str, folder: Folder, extension: str = "pdf") -> str:
    """Build a safe, unique S3 key.

    Pattern: user_{user_id}/original|optimized/{uuid}.pdf
    """
    ext = extension.lower().strip(".")
    if ext not in ("pdf", "docx"):
        ext = "pdf"
    file_id = uuid.uuid4().hex
    return f"user_{user_id}/{folder}/{file_id}.{ext}"


# ── Uploads ─────────────────────────────────────────────────────────

def _validate_upload(
    file_bytes: bytes,
    content_type: str,
    filename: str | None = None,
) -> str:
    """Pre-flight checks before uploading.

    Uses security.file_guard for magic-byte / extension / size checks.
    Returns the validated content type.
    """
    if not is_configured():
        raise RuntimeError("S3 storage is not configured")
    # file_guard does size, extension, magic-byte, PDF complexity checks
    return validate_file_upload(file_bytes, filename, content_type)


def upload_original_cv(
    file_bytes: bytes,
    user_id: str,
    content_type: str = "application/pdf",
    filename: str | None = None,
) -> str:
    """Store the user's original uploaded CV.  Returns the S3 key."""
    safe_uid = validate_user_id(user_id)
    ct = _validate_upload(file_bytes, content_type, filename)
    ext = "docx" if "wordprocessingml" in ct else "pdf"
    key = build_key(safe_uid, "original", ext)
    
    if STORAGE_BACKEND == "local":
        local_storage_service.upload(file_bytes, key, ct)
    else:
        s3_service.upload(file_bytes, key, ct)
        
    logger.info("storage:original_uploaded backend=%s user=%s key=%s", STORAGE_BACKEND, safe_uid, key)
    return key


def upload_optimized_cv(
    file_bytes: bytes,
    user_id: str,
    content_type: str = "application/pdf",
    filename: str | None = None,
) -> str:
    """Store an optimized / generated CV.  Returns the S3 key."""
    safe_uid = validate_user_id(user_id)
    ct = _validate_upload(file_bytes, content_type, filename)
    ext = "docx" if "wordprocessingml" in ct else "pdf"
    key = build_key(safe_uid, "optimized", ext)
    
    if STORAGE_BACKEND == "local":
        local_storage_service.upload(file_bytes, key, ct)
    else:
        s3_service.upload(file_bytes, key, ct)
        
    logger.info("storage:optimized_uploaded backend=%s user=%s key=%s", STORAGE_BACKEND, safe_uid, key)
    return key


# ── Downloads ───────────────────────────────────────────────────────

def get_download_url(key: str, user_id: str, expires: int = 60) -> str:
    """Return a presigned download URL for a stored CV.

    Enforces ownership and clamps expiry.
    """
    enforce_ownership(key, user_id)
    
    if STORAGE_BACKEND == "local":
        # For local storage, we might return a local file path or a specialized internal route
        # For now, return the absolute path (used by internal processes)
        return local_storage_service.get_local_path(key)
    
    return s3_service.get_presigned_url(key, expires)


# ── Delete ──────────────────────────────────────────────────────────

def delete_cv(key: str, user_id: str) -> None:
    """Delete a CV from S3.  Enforces ownership."""
    enforce_ownership(key, user_id)
    
    if STORAGE_BACKEND == "local":
        local_storage_service.delete(key)
    else:
        s3_service.delete(key)
        
    logger.info("storage:deleted backend=%s user=%s key=%s", STORAGE_BACKEND, user_id, key)


# ── Existence check ─────────────────────────────────────────────────

def exists(key: str) -> bool:
    """Return True if the key exists in configured storage."""
    if STORAGE_BACKEND == "local":
        return local_storage_service.head(key) is not None
    return s3_service.head(key) is not None


# ── Health ──────────────────────────────────────────────────────────

def check_health() -> bool:
    """Verify storage backend is reachable."""
    if STORAGE_BACKEND == "local":
        return local_storage_service.validate_storage()
    return s3_service.validate_bucket()
