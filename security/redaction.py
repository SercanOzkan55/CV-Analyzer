"""Log and audit redaction helpers.

Keep secrets and personal data out of logs without breaking debugging value.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{7,}\d)(?!\w)")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|pwd|smtp_pass|stripe_secret|openai_api_key)"
    r"\s*[:=]\s*['\"]?[^'\"\s,;]+"
)
_COMMON_SECRET_RE = re.compile(
    r"\b("
    r"sk-[A-Za-z0-9_-]{16,}|"
    r"sk_live_[A-Za-z0-9_-]{16,}|"
    r"sk_test_[A-Za-z0-9_-]{16,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"ASIA[0-9A-Z]{16}"
    r")\b"
)

_SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "api_key",
    "secret",
    "password",
    "smtp_pass",
    "stripe_secret_key",
    "openai_api_key",
    "supabase_jwt_secret",
}

_TEXT_PAYLOAD_KEYS = {
    "cv_text",
    "optimized_cv_text",
    "job_description",
    "analysis_snapshot",
    "resume_text",
    "raw_text",
}

_EMAIL_KEYS = {"email", "target_email", "candidate_email", "to_email", "recruiter_email", "sender"}
_PHONE_KEYS = {"phone", "phone_number", "candidate_phone"}


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def redact_sensitive_text(value: str, max_length: int = 2000) -> str:
    """Redact common PII/secrets in a free-form string."""
    if not value:
        return value

    text = str(value)
    text = _BEARER_RE.sub("Bearer [redacted-token]", text)
    text = _JWT_RE.sub("[redacted-jwt]", text)
    text = _COMMON_SECRET_RE.sub("[redacted-secret]", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=[redacted-secret]", text)
    text = _EMAIL_RE.sub(lambda m: f"[redacted-email:{_fingerprint(m.group(0).lower())}]", text)
    text = _PHONE_RE.sub(lambda m: f"[redacted-phone:{_fingerprint(m.group(0))}]", text)

    if len(text) > max_length:
        return text[:max_length] + f"...[truncated:{len(text)}]"
    return text


def redact_for_log(value: Any, key: str | None = None, max_depth: int = 4) -> Any:
    """Redact a value for structured logging/audit payloads."""
    normalized_key = str(key or "").strip().lower()

    if normalized_key in _SENSITIVE_KEYS or any(part in normalized_key for part in ("password", "secret", "token", "api_key")):
        return "[redacted-secret]"

    if value is None or isinstance(value, bool | int | float):
        return value

    if isinstance(value, str):
        if normalized_key in _TEXT_PAYLOAD_KEYS:
            return {
                "redacted": True,
                "sha256": _fingerprint(value),
                "length": len(value),
            }
        if normalized_key in _EMAIL_KEYS:
            return f"[redacted-email:{_fingerprint(value.lower())}]"
        if normalized_key in _PHONE_KEYS:
            return f"[redacted-phone:{_fingerprint(value)}]"
        return redact_sensitive_text(value)

    if max_depth <= 0:
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:
            serialized = str(value)
        return redact_sensitive_text(serialized, max_length=500)

    if isinstance(value, Mapping):
        return {
            str(k): redact_for_log(v, key=str(k), max_depth=max_depth - 1)
            for k, v in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return [redact_for_log(item, max_depth=max_depth - 1) for item in list(value)[:50]]

    if isinstance(value, bytes | bytearray):
        return {"redacted": True, "bytes": len(value)}

    return redact_sensitive_text(str(value))


def redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): redact_for_log(v, key=str(k)) for k, v in mapping.items()}
