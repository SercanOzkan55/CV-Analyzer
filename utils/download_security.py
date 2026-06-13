import hashlib
import hmac
import os


def _download_secret() -> str:
    secret = (
        os.getenv("TEMP_DOWNLOAD_SIGNING_SECRET")
        or os.getenv("WORKER_DOWNLOAD_SIGNING_SECRET")
        or os.getenv("ADMIN_TOKEN")
        or os.getenv("SUPABASE_JWT_SECRET")
        or ""
    ).strip()
    env = os.getenv("ENV", "development").lower()
    if not secret and env in ("production", "prod"):
        raise RuntimeError("TEMP_DOWNLOAD_SIGNING_SECRET is required in production")
    return secret or "dev-temp-download-secret"


def sign_download_id(download_id: str) -> str:
    return hmac.new(
        _download_secret().encode("utf-8"),
        str(download_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_download_signature(download_id: str, token: str | None) -> bool:
    if not token:
        return False
    expected = sign_download_id(download_id)
    return hmac.compare_digest(expected, str(token))
