"""AWS configuration loader.

Reads credentials and bucket settings from environment variables.
Never hardcodes secrets; all values come from .env / environment.
Crashes on startup if required variables are missing in production.
"""

import logging
import os

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        logger.warning("Invalid integer for %s; using %d", name, default)
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION: str = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET: str = os.getenv("S3_BUCKET", "cv-analyzer-storage")
AWS_USE_IAM_ROLE: bool = _bool_env("AWS_USE_IAM_ROLE", False)

# Allowed content types for CV uploads.
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

# Max upload size: 5 MB by default. Keep request body slightly higher for
# multipart form overhead via MAX_REQUEST_BODY_BYTES in main.py.
MAX_UPLOAD_BYTES = _int_env("MAX_UPLOAD_BYTES", 5_000_000, minimum=128 * 1024)

# Presigned URL default expiry: 60 seconds; never long-lived.
PRESIGNED_URL_EXPIRY = _int_env("PRESIGNED_URL_EXPIRY", 60, minimum=5, maximum=60)

# PDF / DOCX parser safety knobs.
MAX_PDF_PAGES = _int_env("MAX_PDF_PAGES", 50, minimum=1, maximum=200)
MAX_PDF_OBJECTS = _int_env("MAX_PDF_OBJECTS", 5_000, minimum=100, maximum=50_000)
MAX_DOCX_FILES = _int_env("MAX_DOCX_FILES", 2_000, minimum=10, maximum=10_000)
MAX_DOCX_UNCOMPRESSED_BYTES = _int_env(
    "MAX_DOCX_UNCOMPRESSED_BYTES",
    20 * 1024 * 1024,
    minimum=256 * 1024,
    maximum=200 * 1024 * 1024,
)
MAX_DOCX_COMPRESSION_RATIO = _int_env(
    "MAX_DOCX_COMPRESSION_RATIO",
    100,
    minimum=10,
    maximum=1000,
)

# S3 server-side encryption. Set S3_KMS_KEY_ID to move uploads to aws:kms.
S3_KMS_KEY_ID: str = os.getenv("S3_KMS_KEY_ID", "").strip()
S3_SSE_ALGORITHM: str = os.getenv(
    "S3_SSE_ALGORITHM",
    "aws:kms" if S3_KMS_KEY_ID else "AES256",
).strip()


def has_static_credentials() -> bool:
    """Return True when both static AWS key env vars are present."""
    return bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)


def has_partial_static_credentials() -> bool:
    """Return True when exactly one static AWS key env var is present."""
    return bool(AWS_ACCESS_KEY_ID) ^ bool(AWS_SECRET_ACCESS_KEY)


def is_configured() -> bool:
    """Return True if storage has a bucket and a credential source."""
    if has_partial_static_credentials():
        return False
    return bool(S3_BUCKET and (has_static_credentials() or AWS_USE_IAM_ROLE))


def require_configured() -> None:
    """Crash if AWS is not configured. Call at app startup in production."""
    _env = os.getenv("ENV", "development").lower()
    if _env in ("production", "prod") and not is_configured():
        raise RuntimeError(
            "FATAL: AWS S3 credentials missing. "
            "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or set AWS_USE_IAM_ROLE=1 "
            "when running on an EC2/ECS/Lambda role, plus S3_BUCKET."
        )
