from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from schemas.feedback import FeedbackRequest


def create_router(
    *,
    verify_supabase_jwt: Callable,
    get_db: Callable,
    ensure_not_expired: Callable,
    get_or_create_user: Callable,
    append_feedback_record: Callable,
    read_feedback_records: Callable,
    send_feedback_email: Callable,
    audit_log: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/feedback")
    def submit_feedback(
        body: FeedbackRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        message = str(body.message or "").strip()
        if len(message) < 5:
            raise HTTPException(status_code=400, detail="Feedback message is too short")
        if len(message) > 3000:
            raise HTTPException(status_code=400, detail="Feedback message is too long")

        category = str(body.category or "bug").strip().lower()
        allowed_categories = {"bug", "feature", "ux", "other"}
        if category not in allowed_categories:
            category = "other"

        score = body.score
        if score is not None and (score < 1 or score > 5):
            raise HTTPException(status_code=400, detail="score must be between 1 and 5")

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)

        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": str(db_user.id) if getattr(db_user, "id", None) is not None else None,
            "supabase_id": supabase_id,
            "email": email,
            "category": category,
            "page": str(body.page or "").strip()[:120],
            "lang": str(body.lang or "").strip()[:12],
            "score": score,
            "message": message,
            "context": body.context if isinstance(body.context, dict) else {},
        }

        append_feedback_record(payload)
        emailed = send_feedback_email(payload)

        try:
            audit_log(
                "user_feedback",
                user_id=payload.get("user_id"),
                organization_id=getattr(db_user, "organization_id", None),
                category=category,
                page=payload.get("page"),
                score=score,
            )
        except Exception:
            pass

        return {"ok": True, "message": "Feedback received", "emailed": emailed}

    @router.get("/api/v1/feedback")
    def list_feedback(
        limit: int = Query(default=50, ge=1, le=200),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        role = (getattr(db_user, "role", "individual") or "individual").lower()

        include_all = role == "recruiter"
        items = read_feedback_records(
            limit=limit,
            supabase_id=str(supabase_id) if supabase_id else None,
            include_all=include_all,
        )

        cleaned = []
        for row in items:
            cleaned.append(
                {
                    "timestamp": row.get("timestamp"),
                    "category": row.get("category"),
                    "page": row.get("page"),
                    "lang": row.get("lang"),
                    "score": row.get("score"),
                    "message": row.get("message"),
                    "context": row.get("context") or {},
                    "submitter": row.get("email") if include_all else None,
                }
            )

        return {"items": cleaned, "count": len(cleaned), "scope": "all" if include_all else "self"}

    return router
