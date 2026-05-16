from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StripeSignatureVerificationError(Exception):
    message: str
    status_code: int = 401

    def __str__(self) -> str:
        return self.message


def get_secret_or_file(env_name: str, file_env_name: str, default: str = "") -> str:
    value = os.getenv(env_name, "").strip()
    if value:
        return value

    file_path = os.getenv(file_env_name, "").strip()
    if not file_path:
        return default

    try:
        return Path(file_path).read_text(encoding="utf-8").strip() or default
    except Exception:
        return default


def parse_signature_header(sig_header: str) -> tuple[str, list[str]]:
    timestamp = ""
    provided_sigs: list[str] = []
    for part in (sig_header or "").split(","):
        part = part.strip()
        if part.startswith("t="):
            timestamp = part.split("=", 1)[1]
        elif part.startswith("v1="):
            provided_sigs.append(part.split("=", 1)[1])
    return timestamp, provided_sigs


def verify_stripe_signature(
    *,
    payload: bytes,
    sig_header: str,
    secret: str,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> None:
    timestamp, provided_sigs = parse_signature_header(sig_header)
    if not timestamp or not provided_sigs:
        raise StripeSignatureVerificationError("Invalid signature", status_code=401)

    try:
        event_ts = int(timestamp)
    except ValueError:
        raise StripeSignatureVerificationError("Invalid signature timestamp", status_code=400)

    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - event_ts) > tolerance_seconds:
        raise StripeSignatureVerificationError("Signature timestamp expired", status_code=401)

    signed_payload = timestamp.encode("utf-8") + b"." + payload
    expected_sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected_sig, sig) for sig in provided_sigs):
        raise StripeSignatureVerificationError("Invalid signature", status_code=401)


def load_event(payload: bytes) -> dict:
    try:
        event = json.loads(payload)
    except Exception as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise ValueError("Invalid JSON: event must be an object")
    return event
