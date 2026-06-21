"""Low-level AWS S3 client wrapper.

All S3 operations go through this module.  Higher-level business logic
lives in storage_service.py — this file only knows about boto3.
"""

import logging
import time

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - exercised when optional AWS deps are absent
    boto3 = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


from config.aws import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET,
    S3_KMS_KEY_ID,
    S3_SSE_ALGORITHM,
    PRESIGNED_URL_EXPIRY,
    has_partial_static_credentials,
    has_static_credentials,
    is_configured,
)
from security.s3_guard import clamp_presigned_expiry, redact_s3_key, validate_s3_key

logger = logging.getLogger(__name__)


def _s3_error():
    """Increment S3 error metric and alert (best-effort)."""
    try:
        from shared import S3_ERRORS_TOTAL, _alert

        S3_ERRORS_TOTAL.inc()
        _alert("s3_error", "S3 operation failed", level="warning")
    except Exception:
        pass


# ── S3 client (lazy singleton) ──────────────────────────────────────
_client = None


def _get_client():
    global _client
    if boto3 is None:
        raise RuntimeError("boto3 is not installed")
    if _client is None:
        if not is_configured():
            raise RuntimeError("AWS S3 credentials are not configured")
        if has_partial_static_credentials():
            raise RuntimeError("AWS S3 credentials are partially configured")
        client_kwargs = {"region_name": AWS_REGION}
        if has_static_credentials():
            client_kwargs.update(
                {
                    "aws_access_key_id": AWS_ACCESS_KEY_ID,
                    "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
                }
            )
        _client = boto3.client("s3", **client_kwargs)
    return _client


def _encryption_args() -> dict:
    algorithm = (S3_SSE_ALGORITHM or "AES256").strip()
    args = {"ServerSideEncryption": algorithm}
    if algorithm == "aws:kms":
        if not S3_KMS_KEY_ID:
            raise RuntimeError("S3_KMS_KEY_ID is required when S3_SSE_ALGORITHM=aws:kms")
        args["SSEKMSKeyId"] = S3_KMS_KEY_ID
    return args


def validate_key(key: str) -> None:
    """Ensure the S3 key matches the expected pattern.

    Delegates to security.s3_guard for centralised validation.
    """
    validate_s3_key(key)


# ── Core operations ─────────────────────────────────────────────────


def upload(file_bytes: bytes, key: str, content_type: str = "application/pdf", _retries: int = 3) -> str:
    """Upload bytes to S3.  Returns the key on success. Retries transient errors."""
    validate_key(key)
    log_key = redact_s3_key(key)
    last_exc = None
    for attempt in range(1, _retries + 1):
        try:
            _get_client().put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
                Metadata={"app": "cv-analyzer", "content-class": "cv"},
                **_encryption_args(),
            )
            logger.info("s3:upload key=%s size=%d attempt=%d", log_key, len(file_bytes), attempt)
            return key
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            logger.error("s3:upload_failed key=%s error=%s attempt=%d", log_key, code, attempt)
            _s3_error()
            if code == "InvalidAccessKeyId":
                raise RuntimeError("AWS credentials are invalid") from exc
            if code == "AccessDenied":
                raise PermissionError("S3 access denied") from exc
            last_exc = exc
        except BotoCoreError as exc:
            logger.error("s3:upload_error key=%s error=%s attempt=%d", log_key, exc, attempt)
            _s3_error()
            last_exc = exc
        if attempt < _retries:
            time.sleep(min(2**attempt, 8))
    raise last_exc  # type: ignore[misc]


def get_presigned_url(key: str, expires: int = PRESIGNED_URL_EXPIRY) -> str:
    """Generate a time-limited download URL.  Never returns a public URL."""
    validate_key(key)
    log_key = redact_s3_key(key)
    expires = clamp_presigned_expiry(expires)
    try:
        url = _get_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{key.rsplit("/", 1)[-1]}"',
            },
            ExpiresIn=expires,
        )
        logger.info("s3:presign key=%s expires=%ds", log_key, expires)
        return url
    except (ClientError, BotoCoreError) as exc:
        logger.error("s3:presign_failed key=%s error=%s", log_key, exc)
        _s3_error()
        raise


def delete(key: str) -> None:
    """Delete an object from S3."""
    validate_key(key)
    log_key = redact_s3_key(key)
    try:
        _get_client().delete_object(Bucket=S3_BUCKET, Key=key)
        logger.info("s3:delete key=%s", log_key)
    except (ClientError, BotoCoreError) as exc:
        logger.error("s3:delete_failed key=%s error=%s", log_key, exc)
        _s3_error()
        raise


def head(key: str) -> dict | None:
    """Return object metadata, or None if the key doesn't exist."""
    validate_key(key)
    try:
        return _get_client().head_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return None
        raise


def validate_bucket() -> bool:
    """Check that the configured bucket is reachable."""
    try:
        _get_client().head_bucket(Bucket=S3_BUCKET)
        logger.info("s3:bucket_ok bucket=%s", S3_BUCKET)
        return True
    except (ClientError, BotoCoreError) as exc:
        logger.error("s3:bucket_check_failed bucket=%s error=%s", S3_BUCKET, exc)
        return False


def check_permissions() -> dict:
    """Verify read/write permissions on the configured bucket.

    Returns dict with 'read' and 'write' boolean results.
    """
    result = {"read": False, "write": False}
    test_key = "user_healthcheck/original/healthcheck.pdf"
    try:
        _get_client().put_object(
            Bucket=S3_BUCKET,
            Key=test_key,
            Body=b"ok",
            ContentType="text/plain",
            **_encryption_args(),
        )
        result["write"] = True
    except Exception as exc:
        logger.warning("s3:permission_check write failed: %s", exc)

    try:
        _get_client().head_object(Bucket=S3_BUCKET, Key=test_key)
        result["read"] = True
    except Exception as exc:
        logger.warning("s3:permission_check read failed: %s", exc)

    # Cleanup probe object
    try:
        _get_client().delete_object(Bucket=S3_BUCKET, Key=test_key)
    except Exception:
        pass

    return result
