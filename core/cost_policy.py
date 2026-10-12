"""Explicit switches for preventing external AI charges."""

import os

from fastapi import HTTPException


def paid_ai_enabled() -> bool:
    """Preserve existing deployments; malformed explicit values fail closed."""
    return os.getenv("PAID_AI_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def require_paid_ai() -> None:
    if not paid_ai_enabled():
        raise HTTPException(status_code=503, detail="AI features are disabled by the spending policy.")
