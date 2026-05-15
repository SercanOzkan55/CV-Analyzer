"""Plan-gated AI feature helpers."""

from __future__ import annotations

from fastapi import HTTPException

from core.runtime_bridge import main_value
from services.billing_service import is_feature_enabled


def ensure_ai_rewrite_allowed(db, db_user) -> str:
    """Return the effective plan or raise when AI rewrite is unavailable."""
    override = main_value("_ensure_ai_rewrite_allowed")
    if override is not None and override is not ensure_ai_rewrite_allowed:
        return override(db, db_user)

    resolve_effective_plan = main_value("_resolve_effective_plan")
    if resolve_effective_plan is None:
        raise HTTPException(status_code=500, detail="Plan resolver unavailable")

    plan = resolve_effective_plan(db, db_user)
    if not is_feature_enabled(plan, "ai_rewrite"):
        raise HTTPException(status_code=403, detail="AI rewrite not enabled for plan")
    return plan
