"""Quota management, daily/monthly limits, rate limiting, cost guards.

Extracted from ``main.py`` to reduce monolith size.
"""
from __future__ import annotations

import json
import logging
import os
import threading as _threading
import time
from datetime import datetime, timedelta

from fastapi import HTTPException

from core.metrics import _metric_quota_hit, _metric_error
from core.ops_runtime import (
    _audit_event,
    _record_ai_usage,
    _record_ops_event,
)
from security.redaction import redact_for_log

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

logger = logging.getLogger("app.quota")

# ── Timezone-aware quota reset ───────────────────────────────────────────
_QUOTA_RESET_TIMEZONE = (
    os.getenv("QUOTA_RESET_TIMEZONE", os.getenv("APP_TIMEZONE", "Europe/Istanbul"))
    .strip()
    or "Europe/Istanbul"
)


def _quota_now() -> datetime:
    if ZoneInfo is None:
        return datetime.utcnow()
    try:
        return datetime.now(ZoneInfo(_QUOTA_RESET_TIMEZONE))
    except Exception:
        return datetime.utcnow()


def _quota_today_date():
    return _quota_now().date()


# ── Local quota persistence ──────────────────────────────────────────────
_QUOTA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".local_quota.json")


def _load_local_quota() -> dict:
    """Load persisted daily quota from disk."""
    try:
        with open(_QUOTA_FILE, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        quota_now = _quota_now()
        today_compact = quota_now.strftime("%Y%m%d")
        today_hyphen = quota_now.strftime("%Y-%m-%d")

        cleaned = {}
        for k, v in data.items():
            key = str(k or "")
            suffix = key.rsplit(":", 1)[-1]
            if suffix in (today_compact, today_hyphen):
                try:
                    cleaned[key] = int(v)
                except Exception:
                    cleaned[key] = 0
        return cleaned
    except Exception:
        return {}


def _save_local_quota():
    """Persist daily quota to disk (best-effort)."""
    try:
        with open(_QUOTA_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(_LOCAL_DAILY_QUOTA))
    except Exception:
        pass


_LOCAL_DAILY_QUOTA = _load_local_quota()
_LOCAL_USER_THROTTLE: dict = {}

# Max entries in local throttle dict
_THROTTLE_MAX_ENTRIES = int(os.getenv("THROTTLE_MAX_ENTRIES", "10000"))


def _extract_minute_bucket(key: str) -> int:
    """Extract the minute-bucket integer from a throttle key."""
    try:
        return int(key.rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return 0


# ── Plan normalization ───────────────────────────────────────────────────
_PLAN_ALIASES: dict[str, str] = {
    "professional": "pro",
    "premium": "pro",
    "business": "enterprise",
    "team": "enterprise",
    "admin": "admin",
}


def _normalize_plan(plan_type: str | None) -> str:
    """Normalize plan_type to one of: free, pro, enterprise, admin."""
    raw = (plan_type or "free").strip().lower()
    return _PLAN_ALIASES.get(raw, raw) if raw else "free"


def _is_premium_plan(plan_type: str | None) -> bool:
    return _normalize_plan(plan_type) in ("pro", "enterprise", "admin")


# ── Plan-based quota mappings ────────────────────────────────────────────
USER_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("USER_FREE_DAILY", "5")),
    "pro": int(os.getenv("USER_PRO_DAILY", "100")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_DAILY", "1000")),
}

USER_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("USER_FREE_MONTHLY", "20")),
    "pro": int(os.getenv("USER_PRO_MONTHLY", "500")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_MONTHLY", "5000")),
}

ORG_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("ORG_FREE_DAILY", "50")),
    "pro": int(os.getenv("ORG_PRO_DAILY", "500")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_DAILY", "5000")),
}

ORG_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("ORG_FREE_MONTHLY", "500")),
    "pro": int(os.getenv("ORG_PRO_MONTHLY", "5000")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_MONTHLY", "50000")),
}

REDIS_FREE_DAILY_LIMIT = int(
    os.getenv("REDIS_FREE_DAILY_LIMIT", str(USER_PLAN_LIMITS_DAILY["free"]))
)

# ── Cost guard limits ────────────────────────────────────────────────────
COST_OPTIMIZE_PER_DAY = int(os.getenv("COST_OPTIMIZE_PER_DAY", "500"))
COST_UPLOAD_PER_DAY = int(os.getenv("COST_UPLOAD_PER_DAY", "1000"))
COST_ANALYZE_PER_DAY = int(os.getenv("COST_ANALYZE_PER_DAY", str(COST_UPLOAD_PER_DAY)))


def _seconds_until_next_quota_day() -> int:
    now = _quota_now()
    if now.tzinfo is not None:
        tomorrow = (now + timedelta(days=1)).date()
        next_midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)
    else:
        next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
    return max(1, int((next_midnight - now).total_seconds()))


def _daily_quota_key(user_id: str, now: datetime | None = None) -> str:
    dt = now or _quota_now()
    return f"quota:daily:{user_id}:{dt.strftime('%Y%m%d')}"


def _resolve_daily_limit_for_plan(plan_type: str | None) -> int:
    normalized = _normalize_plan(plan_type)
    if normalized == "admin":
        return 10**12
    if normalized == "free":
        return int(os.getenv("REDIS_FREE_DAILY_LIMIT", str(USER_PLAN_LIMITS_DAILY["free"])))
    return int(USER_PLAN_LIMITS_DAILY.get(normalized, USER_PLAN_LIMITS_DAILY["free"]))


def _get_redis_rate():
    """Get redis_rate from main module (avoids circular import)."""
    from core.runtime_bridge import redis_rate_client
    return redis_rate_client()


def _get_daily_quota_status(user_id: str, limit: int = REDIS_FREE_DAILY_LIMIT):
    """Return quota status from Redis, or None if Redis isn't available."""
    if limit <= 0:
        return None
    key = _daily_quota_key(user_id)
    redis_rate = _get_redis_rate()
    if not redis_rate:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0))
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used < limit, "source": "memory",
        }

    try:
        raw_used = redis_rate.get(key)
        used = int(raw_used) if raw_used is not None else 0
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used < limit, "source": "redis",
        }
    except Exception:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0))
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used < limit, "source": "memory",
        }


def _consume_daily_quota(user_id: str, limit: int = REDIS_FREE_DAILY_LIMIT):
    """Atomically consume one daily quota unit."""
    if limit <= 0:
        return None

    key = _daily_quota_key(user_id)
    redis_rate = _get_redis_rate()
    if not redis_rate:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
        _LOCAL_DAILY_QUOTA[key] = used
        _save_local_quota()
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used <= limit, "source": "memory",
        }

    try:
        used = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if used == 1 or ttl < 0:
            redis_rate.expire(key, _seconds_until_next_quota_day())
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used <= limit, "source": "redis",
        }
    except Exception:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
        _LOCAL_DAILY_QUOTA[key] = used
        _save_local_quota()
        remaining = max(0, limit - used)
        return {
            "key": key, "used": used, "remaining": remaining,
            "limit": limit, "allowed": used <= limit, "source": "memory",
        }


def _apply_daily_quota_headers(response, quota: dict | None) -> None:
    if response is None or quota is None:
        return
    try:
        response.headers["X-Daily-Limit"] = str(quota["limit"])
        response.headers["X-Daily-Used"] = str(quota["used"])
        response.headers["X-Daily-Remaining"] = str(quota["remaining"])
    except Exception:
        pass


def _consume_user_rate_limit(user_id: str, limit_per_minute: int, scope: str):
    """Consume one request from a per-user, per-minute throttle bucket."""
    if limit_per_minute <= 0:
        return None

    minute_bucket = int(time.time()) // 60
    key = f"throttle:user:{scope}:{user_id}:{minute_bucket}"
    redis_rate = _get_redis_rate()
    if not redis_rate:
        used = int(_LOCAL_USER_THROTTLE.get(key, 0)) + 1
        _LOCAL_USER_THROTTLE[key] = used
        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key, "used": used, "limit": int(limit_per_minute),
            "remaining": remaining, "allowed": used <= int(limit_per_minute),
            "scope": scope, "source": "memory",
        }

    try:
        used = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if used == 1 or ttl < 0:
            redis_rate.expire(key, 60)
        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key, "used": used, "limit": int(limit_per_minute),
            "remaining": remaining, "allowed": used <= int(limit_per_minute),
            "scope": scope, "source": "redis",
        }
    except Exception:
        used = int(_LOCAL_USER_THROTTLE.get(key, 0)) + 1
        _LOCAL_USER_THROTTLE[key] = used
        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key, "used": used, "limit": int(limit_per_minute),
            "remaining": remaining, "allowed": used <= int(limit_per_minute),
            "scope": scope, "source": "memory",
        }


# ── Concurrent request limiter (per-user) ────────────────────────────────
_CONCURRENT_LIMIT_PER_USER = int(os.getenv("CONCURRENT_LIMIT_PER_USER", "3"))
_LOCAL_CONCURRENT: dict[str, int] = {}


def _acquire_concurrent_slot(user_id: str) -> bool:
    if _CONCURRENT_LIMIT_PER_USER <= 0:
        return True
    key = f"concurrent:user:{user_id}"
    redis_rate = _get_redis_rate()
    if redis_rate:
        try:
            current = int(redis_rate.incr(key))
            if current == 1:
                redis_rate.expire(key, 120)
            if current > _CONCURRENT_LIMIT_PER_USER:
                redis_rate.decr(key)
                return False
            return True
        except Exception:
            pass
    current = _LOCAL_CONCURRENT.get(key, 0) + 1
    if current > _CONCURRENT_LIMIT_PER_USER:
        return False
    _LOCAL_CONCURRENT[key] = current
    return True


def _release_concurrent_slot(user_id: str) -> None:
    key = f"concurrent:user:{user_id}"
    redis_rate = _get_redis_rate()
    if redis_rate:
        try:
            val = redis_rate.decr(key)
            if val is not None and int(val) <= 0:
                redis_rate.delete(key)
            return
        except Exception:
            pass
    current = _LOCAL_CONCURRENT.get(key, 0)
    if current <= 1:
        _LOCAL_CONCURRENT.pop(key, None)
    else:
        _LOCAL_CONCURRENT[key] = current - 1


# ── Cost guard ───────────────────────────────────────────────────────────
def _check_cost_guard(scope: str, limit: int) -> None:
    """Enforce a global per-day hard cap for costly operations."""
    from shared import _alert
    _cost_logger = logging.getLogger("app.cost")
    today = datetime.now().strftime("%Y%m%d")
    key = f"cost:{scope}:{today}"

    def _warn_and_block(count: int, source: str) -> None:
        pct = (count / limit * 100) if limit else 0
        if pct >= 80 and count <= limit:
            _cost_logger.warning(
                "cost:high_usage scope=%s count=%d limit=%d pct=%.0f%% source=%s",
                scope, count, limit, pct, source,
            )
            _alert("cost_high", f"Cost usage {scope} at {pct:.0f}% ({count}/{limit})", level="warning")
        if count > limit:
            _cost_logger.error(
                "cost:blocked scope=%s count=%d limit=%d source=%s",
                scope, count, limit, source,
            )
            _alert("cost_blocked", f"Cost limit exceeded for {scope}: {count}/{limit}")
            raise HTTPException(
                status_code=429,
                detail=f"Daily {scope} limit reached ({limit}/day)",
            )

    redis_rate = _get_redis_rate()
    if redis_rate:
        try:
            count = int(redis_rate.incr(key))
            if count == 1:
                redis_rate.expire(key, 86400)
            _warn_and_block(count, "redis")
            return
        except HTTPException:
            raise
        except Exception:
            pass

    count = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
    _LOCAL_DAILY_QUOTA[key] = count
    _warn_and_block(count, "memory")


# ── Billable usage ───────────────────────────────────────────────────────
def _consume_billable_usage(db, db_user, endpoint: str, response=None):
    """Consume one dashboard-visible daily usage unit for billable actions."""
    from models import User, Organization

    if db_user is None:
        return None

    plan_type = _resolve_effective_plan(db, db_user)
    if _normalize_plan(plan_type) == "admin" or _is_admin_user(db_user):
        return None

    quota_today = _quota_today_date()
    now_utc = datetime.utcnow()
    try:
        if db_user.last_reset is None or db_user.last_reset.date() < quota_today:
            db_user.daily_usage = 0
            db_user.last_reset = now_utc
        if db_user.updated_at is None or (db_user.updated_at.year, db_user.updated_at.month) != (quota_today.year, quota_today.month):
            db_user.monthly_usage = 0
            db_user.updated_at = now_utc
    except Exception:
        pass

    daily_limit = _resolve_daily_limit_for_plan(plan_type)
    monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
        _normalize_plan(plan_type), USER_PLAN_LIMITS_MONTHLY["free"]
    )

    quota = _consume_daily_quota(db_user.supabase_id or str(db_user.id), limit=daily_limit)
    _apply_daily_quota_headers(response, quota)
    if quota is not None:
        if not quota["allowed"]:
            _metric_quota_hit(endpoint, "user_daily")
            raise HTTPException(
                status_code=403,
                detail=f"Daily limit reached ({quota['limit']}/day)",
            )
    elif (db_user.daily_usage or 0) >= daily_limit:
        _metric_quota_hit(endpoint, "user_daily")
        raise HTTPException(status_code=403, detail="Daily limit reached")

    if (db_user.monthly_usage or 0) >= monthly_limit:
        _metric_quota_hit(endpoint, "user_monthly")
        raise HTTPException(status_code=403, detail="Monthly limit reached")

    try:
        db_user.daily_usage = (db_user.daily_usage or 0) + 1
        db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
        db.add(db_user)
        db.commit()
    except Exception:
        db.rollback()
        _metric_error(endpoint, "usage")
        raise

    try:
        _record_usage_daily(db, db_user.id)
        db.commit()
    except Exception:
        db.rollback()

    _record_ai_usage(
        endpoint=endpoint,
        user_id=getattr(db_user, "id", None),
        used_ai=endpoint in {
            "cv-auto-fix", "rewrite-cv", "rewrite-bullets",
            "rewrite-cover-letter", "interview-questions",
            "interview-evaluate", "linkedin-optimize",
            "cv-builder-suggest-summary", "recruiter-scan-cv",
        },
        billable_units=1,
    )
    _record_ops_event(
        "billable_usage", "ok",
        endpoint=endpoint,
        user_id=getattr(db_user, "id", None),
        daily_usage=getattr(db_user, "daily_usage", None),
        monthly_usage=getattr(db_user, "monthly_usage", None),
    )

    return quota


def _record_usage_daily(db, user_id: int):
    """Upsert a row in usage_daily for today, incrementing count by 1."""
    try:
        from models import UsageDaily
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        row = (
            db.query(UsageDaily)
            .filter(UsageDaily.user_id == user_id, UsageDaily.date == today)
            .first()
        )
        if row:
            row.count = (row.count or 0) + 1
        else:
            row = UsageDaily(user_id=user_id, date=today, count=1)
            db.add(row)
    except Exception:
        pass


# ── User/plan helpers (needed by quota) ──────────────────────────────────
def _is_admin_user(db_user) -> bool:
    return bool(db_user and str(getattr(db_user, "role", "") or "").strip().lower() == "admin")


def _resolve_effective_plan(db, db_user) -> str:
    from models import Organization
    if _is_admin_user(db_user):
        return "admin"
    if db_user and db_user.role == "recruiter" and db_user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == db_user.organization_id)
            .first()
        )
        if org and getattr(org, "plan_type", None):
            return _normalize_plan(str(org.plan_type))
    return _normalize_plan(str((db_user.plan_type or "free") if db_user else "free"))
