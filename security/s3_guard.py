"""S3-specific security guards.

Key validation, ownership enforcement, per-user CV limits,
and presigned URL hardening.
"""

import hashlib
import logging
import re

logger = logging.getLogger("security.s3_guard")

# ── Key format ──────────────────────────────────────────────────────
# users/user_{id}/safe_filename_{hex-uuid}.pdf|docx
_SAFE_KEY_RE = re.compile(
    r"^users/user_[a-zA-Z0-9\-_]+/[a-zA-Z0-9._-]+\.(pdf|docx)$"
)

# Path traversal in key
_TRAVERSAL_RE = re.compile(r"\.\.|%2[eEfF]|%2[fF]|%5[cC]")

# Max CVs per user (original + optimized combined)
MAX_CVS_PER_USER = 20

# Presigned URL max expiry (seconds)
MAX_PRESIGNED_EXPIRY = 60


def validate_s3_key(key: str) -> None:
    """Validate an S3 key against the allowed pattern.

    Prevents:
    - Path traversal (../, encoded variants)
    - Arbitrary key injection
    - Keys outside the user folder structure
    """
    if not key or not isinstance(key, str):
        raise ValueError("S3 key is required")

    if _TRAVERSAL_RE.search(key):
        logger.warning("s3_guard:traversal_attempt key=%s", redact_s3_key(key))
        raise ValueError("Path traversal detected in key")

    if not _SAFE_KEY_RE.match(key):
        logger.warning("s3_guard:invalid_key key=%s", redact_s3_key(key))
        raise ValueError("Invalid S3 key format")


def enforce_ownership(key: str, user_id: str) -> None:
    """Ensure the key belongs to the given user.

    Prevents accessing other users' files via key manipulation.
    """
    validate_s3_key(key)

    safe_user_id = re.sub(r"[^a-zA-Z0-9\-_]", "_", str(user_id))
    expected_prefix = f"users/user_{safe_user_id}/"

    if not key.startswith(expected_prefix):
        logger.warning(
            "s3_guard:ownership_violation user=%s key=%s",
            safe_user_id,
            redact_s3_key(key),
        )
        raise PermissionError("Access denied: key does not belong to this user")


def redact_s3_key(key: str | None) -> str:
    """Return a stable non-reversible key fingerprint for logs/audits."""
    if not key:
        return ""
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:16]
    parts = str(key).split("/")
    owner = parts[0][:18] if parts else "unknown"
    folder = parts[1] if len(parts) > 1 else "unknown"
    return f"{owner}/{folder}/sha256:{digest}"


def enforce_user_cv_limit(db, user_id: int, limit: int = MAX_CVS_PER_USER) -> None:
    """Reject upload if user has too many stored CVs.

    Prevents storage abuse and cost explosion.
    """
    from models import CVVersion

    count = (
        db.query(CVVersion)
        .filter(CVVersion.user_id == user_id)
        .filter(
            (CVVersion.original_s3_key.isnot(None))
            | (CVVersion.optimized_s3_key.isnot(None))
        )
        .count()
    )
    if count >= limit:
        logger.warning("s3_guard:cv_limit_reached user=%d count=%d", user_id, count)
        raise ValueError(
            f"Storage limit reached ({limit} CVs). Delete old CVs to upload new ones."
        )


def clamp_presigned_expiry(requested: int) -> int:
    """Ensure presigned URL expiry never exceeds the maximum."""
    if requested <= 0:
        return MAX_PRESIGNED_EXPIRY
    return min(requested, MAX_PRESIGNED_EXPIRY)
