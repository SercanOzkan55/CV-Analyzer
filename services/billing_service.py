import os


_PLAN_DEFAULTS = {
    "free": {
        "daily_cv_limit": int(os.getenv("ENTITLE_FREE_DAILY_CV", "3")),
        "ai_rewrite": False,
        "recruiter_dashboard": False,
    },
    "pro": {
        "daily_cv_limit": int(os.getenv("ENTITLE_PRO_DAILY_CV", "50")),
        "ai_rewrite": True,
        "recruiter_dashboard": False,
    },
    "enterprise": {
        "daily_cv_limit": int(os.getenv("ENTITLE_ENTERPRISE_DAILY_CV", "200")),
        "ai_rewrite": True,
        "recruiter_dashboard": True,
    },
}


def normalize_plan(plan_type: str | None) -> str:
    value = (plan_type or "free").strip().lower()
    if value not in _PLAN_DEFAULTS:
        return "free"
    return value


def get_entitlements(plan_type: str | None) -> dict:
    """Return feature entitlements for a normalized plan.

    This is the central mapping from billing plan -> feature access and
    coarse limits. It intentionally stays in memory and environment-based
    for simplicity; future versions can move this to a DB table or config
    file without changing call sites.
    """

    plan = normalize_plan(plan_type)
    data = _PLAN_DEFAULTS.get(plan, _PLAN_DEFAULTS["free"])
    # return a shallow copy so callers can't mutate global defaults
    return {"plan": plan, **data}


def is_feature_enabled(plan_type: str | None, feature: str) -> bool:
    ent = get_entitlements(plan_type)
    return bool(ent.get(feature))
