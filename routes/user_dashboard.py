from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from models import Analysis


def create_router(
    *,
    verify_supabase_jwt: Callable,
    get_db: Callable,
    ensure_not_expired: Callable,
    get_or_create_user: Callable,
    current_db_user: Callable,
    resolve_effective_plan: Callable,
    resolve_daily_limit_for_plan: Callable,
    get_daily_quota_status: Callable,
    mock_services_on: bool,
    user_plan_limits_monthly: Mapping[str, int],
) -> APIRouter:
    router = APIRouter()

    def monthly_limit_for(plan: str) -> int:
        return int(user_plan_limits_monthly.get(plan, user_plan_limits_monthly["free"]))

    @router.get("/api/v1/usage")
    def get_usage(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        """Return usage counters for UI usage widgets."""
        ensure_not_expired(user)

        if mock_services_on:
            mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
            if not mock_user_id:
                mock_user_id = "mock-user"
            mock_email = (user or {}).get("email") if isinstance(user, dict) else None
            db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
            effective_plan = resolve_effective_plan(db, db_user)
            daily_limit = resolve_daily_limit_for_plan(effective_plan)
            redis_quota = get_daily_quota_status(str(mock_user_id), limit=daily_limit)
            monthly_limit = monthly_limit_for(effective_plan)
            if redis_quota is None:
                daily_used = int(db_user.daily_usage or 0)
                monthly_used = int(db_user.monthly_usage or 0)
                return {
                    "plan_type": effective_plan,
                    "role": db_user.role or "individual",
                    "source": "mock",
                    "daily": {
                        "used": daily_used,
                        "limit": daily_limit,
                        "remaining": max(0, int(daily_limit - daily_used)),
                    },
                    "monthly": {
                        "used": monthly_used,
                        "limit": monthly_limit,
                        "remaining": max(0, monthly_limit - monthly_used),
                    },
                }
            return {
                "plan_type": effective_plan,
                "role": db_user.role or "individual",
                "source": "redis",
                "daily": {
                    "used": redis_quota["used"],
                    "limit": redis_quota["limit"],
                    "remaining": redis_quota["remaining"],
                },
                "monthly": {
                    "used": int(db_user.monthly_usage or 0),
                    "limit": monthly_limit,
                    "remaining": max(0, monthly_limit - int(db_user.monthly_usage or 0)),
                },
            }

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)

        plan_type = db_user.plan_type or "free"
        user_monthly_limit = monthly_limit_for(plan_type)
        redis_quota = get_daily_quota_status(
            db_user.supabase_id or str(db_user.id),
            limit=resolve_daily_limit_for_plan(plan_type),
        )

        if redis_quota is not None:
            daily_used = redis_quota["used"]
            daily_limit = redis_quota["limit"]
            daily_remaining = redis_quota["remaining"]
            source = "redis"
        else:
            daily_used = int(db_user.daily_usage or 0)
            daily_limit = int(resolve_daily_limit_for_plan(plan_type))
            daily_remaining = max(0, daily_limit - daily_used)
            source = "db"

        monthly_used = int(db_user.monthly_usage or 0)

        return {
            "plan_type": plan_type,
            "role": db_user.role or "individual",
            "source": source,
            "daily": {
                "used": daily_used,
                "limit": daily_limit,
                "remaining": daily_remaining,
            },
            "monthly": {
                "used": monthly_used,
                "limit": user_monthly_limit,
                "remaining": max(0, user_monthly_limit - monthly_used),
            },
        }

    @router.get("/api/v1/usage-history")
    def get_usage_history(
        days: int = Query(default=30, ge=1, le=180),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        """Return daily analysis counts for dashboard activity widgets."""
        db_user = current_db_user(user, db)
        since = datetime.utcnow() - timedelta(days=days - 1)
        rows = (
            db.query(Analysis)
            .filter(Analysis.user_id == db_user.id)
            .filter(Analysis.created_at >= since)
            .all()
        )
        counts: dict[str, int] = {}
        score_totals: dict[str, list[float]] = {}
        for row in rows:
            created = getattr(row, "created_at", None) or datetime.utcnow()
            key = created.date().isoformat()
            counts[key] = counts.get(key, 0) + 1
            score_totals.setdefault(key, []).append(float(getattr(row, "similarity_score", 0) or 0))

        output = []
        today = datetime.utcnow().date()
        for offset in range(days - 1, -1, -1):
            day = today - timedelta(days=offset)
            key = day.isoformat()
            scores = score_totals.get(key, [])
            output.append(
                {
                    "date": key,
                    "count": counts.get(key, 0),
                    "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
                }
            )
        return {"days": output}

    @router.get("/api/v1/usage-streak")
    def get_usage_streak(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        """Return current and longest analysis streaks based on analysis history."""
        db_user = current_db_user(user, db)
        rows = db.query(Analysis.created_at).filter(Analysis.user_id == db_user.id).all()
        active_days = set()
        for row in rows:
            created = row[0] if isinstance(row, (tuple, list)) else getattr(row, "created_at", None)
            if created is not None:
                active_days.add(created.date())
        today = datetime.utcnow().date()
        current = 0
        day = today
        while day in active_days:
            current += 1
            day -= timedelta(days=1)

        longest = 0
        running = 0
        for day in sorted(active_days):
            if not active_days or (day - timedelta(days=1)) not in active_days:
                running = 1
            else:
                running += 1
            longest = max(longest, running)

        return {"current_streak": current, "longest_streak": longest, "active_days": len(active_days)}

    @router.get("/api/v1/insights")
    def get_dashboard_insights(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        rows = (
            db.query(Analysis)
            .filter(Analysis.user_id == db_user.id)
            .order_by(Analysis.created_at.desc())
            .limit(20)
            .all()
        )
        insights = []
        if not rows:
            insights.append({"type": "tip", "icon": "💡", "text": "Run your first analysis to unlock personalized insights."})
        else:
            scores = [float(r.similarity_score or 0) for r in rows]
            latest = scores[0]
            best = max(scores)
            avg = sum(scores) / len(scores)
            insights.append({"type": "achievement", "icon": "🏆", "text": f"Best score so far: {round(best)}%."})
            if latest >= avg:
                insights.append({"type": "positive", "icon": "↗", "text": "Your latest analysis is at or above your recent average."})
            else:
                insights.append({"type": "warning", "icon": "⚠", "text": "Latest score is below your recent average; review missing skills before applying."})
            if len(rows) >= 3:
                insights.append({"type": "tip", "icon": "📈", "text": f"Recent average score: {round(avg)}% across {len(rows)} analyses."})
        return {"insights": insights}

    @router.get("/api/v1/me")
    def get_me(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        """Return authenticated user's profile: role, plan, email."""
        ensure_not_expired(user)
        if mock_services_on:
            mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
            mock_email = (user or {}).get("email") if isinstance(user, dict) else None
            db_user = get_or_create_user(db, str(mock_user_id or "mock-user"), mock_email or "dev@example.com")
        else:
            supabase_id = user.get("user_id")
            email = user.get("email")
            db_user = get_or_create_user(db, supabase_id, email)
        return {
            "role": db_user.role or "individual",
            "plan_type": db_user.plan_type or "free",
            "email": db_user.email,
            "organization_id": db_user.organization_id,
        }

    return router
