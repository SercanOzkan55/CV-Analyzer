"""Plan-gated AI feature helpers."""

from __future__ import annotations

from fastapi import HTTPException

from core.runtime_bridge import main_value
from services.billing_service import is_feature_enabled


def ensure_ai_rewrite_allowed(db, db_user) -> str:
    """Return the effective plan or raise when AI rewrite is unavailable.

    Two independent gates:
    1. ``ai_rewrite`` entitlement — whether the plan may use AI tools at all.
    2. ``ai_daily_limit`` — a per-day counter kept apart from the CV-analysis
       quota, so trying an AI tool never eats a user's analysis allowance.
    """
    override = main_value("_ensure_ai_rewrite_allowed")
    if override is not None and override is not ensure_ai_rewrite_allowed:
        return override(db, db_user)

    resolve_effective_plan = main_value("_resolve_effective_plan")
    if resolve_effective_plan is None:
        raise HTTPException(status_code=500, detail="Plan resolver unavailable")

    plan = resolve_effective_plan(db, db_user)
    if not is_feature_enabled(plan, "ai_rewrite"):
        raise HTTPException(status_code=403, detail="AI rewrite not enabled for plan")

    _enforce_ai_daily_limit(db_user, plan)
    return plan


def _enforce_ai_daily_limit(db_user, plan: str) -> None:
    """Consume one AI unit for today; raise 429 once the plan's limit is spent."""
    from core.quota import _consume_ai_daily_quota, _resolve_ai_daily_limit_for_plan

    limit = _resolve_ai_daily_limit_for_plan(plan)
    if limit <= 0:
        return

    user_key = str(getattr(db_user, "supabase_id", None) or getattr(db_user, "id", "") or "")
    if not user_key:
        return

    quota = _consume_ai_daily_quota(user_key, limit)
    if quota is not None and not quota["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily AI limit reached ({quota['limit']}/day). Resets at midnight.",
        )
