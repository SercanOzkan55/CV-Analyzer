"""User management: create, plan resolution, premium insights, benchmarking.

Extracted from ``main.py`` to reduce monolith size.
"""

from __future__ import annotations
from core.timeutils import utcnow

import logging
import os

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from models import Analysis, Organization, User
from core.quota import (
    _is_premium_plan,
)

logger = logging.getLogger("app.user")


def get_or_create_user(db, supabase_id: str, email: str):
    """Get existing user or create new one."""
    user = db.query(User).filter(User.supabase_id == supabase_id).first()
    adopted_pending_member = False

    if not user:
        user = _adopt_pending_owner_member(db, supabase_id, email)
        adopted_pending_member = user is not None
        if not user:
            initial_plan = _resolve_initial_user_plan(email)
            initial_billing = "trialing" if initial_plan != "free" else "trialing"
            user = User(
                supabase_id=supabase_id,
                email=email,
                plan_type=initial_plan,
                billing_status=initial_billing,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    # Auto-detect admin role from BILLING_ADMIN_ALLOWED_EMAILS env
    admin_emails_raw = str(os.getenv("BILLING_ADMIN_ALLOWED_EMAILS", "")).strip()
    admin_emails = {e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()}
    user_email = (email or "").strip().lower()
    if user_email and user_email in admin_emails and (user.role or "") != "admin":
        user.role = "admin"
        db.add(user)
        db.commit()
        db.refresh(user)

    # Domain-based auto role assignment
    if user.role != "admin" and not adopted_pending_member:
        try:
            domain = None
            if isinstance(email, str) and "@" in email:
                domain = email.split("@", 1)[1].lower()

            if domain:
                org = db.query(Organization).filter(Organization.domain == domain).first()
                if org and user.organization_id != org.id:
                    user.role = "recruiter"
                    user.organization_id = org.id
                    db.add(user)
                    db.commit()
                    db.refresh(user)
        except SQLAlchemyError as exc:
            db.rollback()
            logger.warning("Organization auto-assignment skipped: %s", exc)
        except Exception:
            pass

    return user


def _adopt_pending_owner_member(db, supabase_id: str, email: str) -> User | None:
    """Convert an owner-created pending member into the real authenticated user."""
    email_value = str(email or "").strip().lower()
    supabase_value = str(supabase_id or "").strip()
    if not email_value or not supabase_value:
        return None

    pending = (
        db.query(User)
        .filter(
            func.lower(User.email) == email_value,
            User.supabase_id.like("pending-owner-%"),
        )
        .order_by(User.created_at.desc(), User.id.desc())
        .first()
    )
    if not pending:
        return None

    old_supabase_id = pending.supabase_id
    pending.supabase_id = supabase_value
    pending.email = email_value
    db.add(pending)
    db.flush()

    try:
        from services.owner_workflow_service import (
            candidate_event_title,
            create_audit_log,
            create_owner_notification,
        )

        if pending.organization_id:
            audit = create_audit_log(
                db,
                organization_id=pending.organization_id,
                event_type="hr_user_activated",
                actor_user_id=pending.id,
                actor_role=pending.role,
                resource_type="user",
                resource_id=pending.id,
                description=f"{pending.email} activated pending access.",
                old_values={"supabase_id": old_supabase_id},
                new_values={"supabase_id": pending.supabase_id, "role": pending.role},
                metadata={"source": "get_or_create_user"},
            )
            create_owner_notification(
                db,
                organization_id=pending.organization_id,
                event_type="hr_user_activated",
                title=candidate_event_title("hr_user_activated"),
                message=f"{pending.email} activated pending access.",
                recipient_user_id=None,
                actor_user_id=pending.id,
                audit_log_id=audit.id,
                metadata={"source": "get_or_create_user", "member_user_id": pending.id},
            )
    except Exception as exc:
        logger.warning("Pending owner member activation audit skipped: %s", exc)

    db.commit()
    db.refresh(pending)
    return pending


def _get_owned_analysis_or_404(db, analysis_id: int, db_user: User) -> Analysis:
    """Return an analysis only when it belongs to the authenticated user."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _resolve_initial_user_plan(email: str | None) -> str:
    """Resolve default plan for newly created users."""
    requested = str(os.getenv("AUTO_NEW_USER_PLAN", "free")).strip().lower()
    if requested not in User.PLAN_TYPES:
        requested = "free"

    allowed_emails_raw = str(os.getenv("AUTO_PREMIUM_EMAILS", "")).strip()
    allowed_domains_raw = str(os.getenv("AUTO_PREMIUM_DOMAINS", "")).strip()

    if requested == "free":
        return "free"

    email_value = (email or "").strip().lower()
    domain_value = email_value.split("@", 1)[1] if "@" in email_value else ""

    allowed_emails = {x.strip().lower() for x in allowed_emails_raw.split(",") if x.strip()}
    allowed_domains = {x.strip().lower() for x in allowed_domains_raw.split(",") if x.strip()}

    if allowed_emails or allowed_domains:
        if email_value in allowed_emails or domain_value in allowed_domains:
            return requested
        return "free"

    return requested


def _ensure_not_expired(user_payload: dict):
    if isinstance(user_payload, dict) and user_payload.get("signature"):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = user_payload.get("payload") if isinstance(user_payload, dict) else None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if exp is None:
        return
    try:
        exp_ts = int(exp)
    except (TypeError, ValueError):
        return
    if exp_ts <= int(utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")


BENCHMARK_MIN_PEERS = int(os.getenv("BENCHMARK_MIN_PEERS", "5"))


def _compute_percentile_position(current_score: float, peer_scores: list[float]) -> dict | None:
    if not peer_scores:
        return None

    n = len(peer_scores)
    lower = sum(1 for s in peer_scores if float(s) < current_score)
    equal = sum(1 for s in peer_scores if float(s) == current_score)
    percentile = ((lower + 0.5 * equal) / n) * 100.0
    ahead = max(0.0, percentile - 50.0)
    avg_peer = sum(float(s) for s in peer_scores) / n
    delta_avg = float(current_score) - avg_peer

    return {
        "peer_count": n,
        "percentile": round(percentile, 1),
        "ahead_percent": round(ahead, 1),
        "average_peer_score": round(avg_peer, 2),
        "delta_vs_average": round(delta_avg, 2),
    }


def _build_analysis_benchmark(db, analysis_record: Analysis) -> dict:
    """Benchmark one analysis against similar analyses."""
    if not analysis_record:
        return {"available": False, "reason": "analysis_not_found"}

    scope = "global"
    query = db.query(Analysis.similarity_score).filter(Analysis.id != analysis_record.id)

    if analysis_record.specialization_id:
        scope = "specialization"
        query = query.filter(Analysis.specialization_id == analysis_record.specialization_id)
    elif analysis_record.industry_id:
        scope = "industry"
        query = query.filter(Analysis.industry_id == analysis_record.industry_id)
    elif analysis_record.domain_id:
        scope = "domain"
        query = query.filter(Analysis.domain_id == analysis_record.domain_id)

    peer_rows = query.limit(2000).all()
    peer_scores = [float(r[0]) for r in peer_rows if r and r[0] is not None]

    if len(peer_scores) < BENCHMARK_MIN_PEERS:
        return {
            "available": False,
            "scope": scope,
            "peer_count": len(peer_scores),
            "min_peers": BENCHMARK_MIN_PEERS,
            "reason": "not_enough_peers",
        }

    stats = _compute_percentile_position(float(analysis_record.similarity_score), peer_scores)
    if not stats:
        return {"available": False, "scope": scope, "reason": "no_peer_scores"}

    ahead = stats["ahead_percent"]
    if ahead >= 1.0:
        summary = f"Bu CV benzer gruptaki adaylardan yaklasik %{ahead} daha onde."
    else:
        summary = "Bu CV benzer grupla benzer seviyede."

    return {"available": True, "scope": scope, **stats, "summary": summary}


def _build_premium_insights(result: dict) -> dict:
    dimensions = {
        "semantic": float(result.get("semantic_score") or 0),
        "keyword": float(result.get("keyword_score") or 0),
        "skill": float(result.get("skill_score") or 0),
        "experience": float(result.get("experience_score") or 0),
        "ats": float(result.get("ats_score") or 0),
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    gap = round(dimensions[strongest] - dimensions[weakest], 1)

    missing_skills = list(result.get("missing_skills") or [])
    top_skills = [str(s) for s in missing_skills[:3]]

    action_plan = []
    for skill in top_skills:
        action_plan.append(
            {
                "title": f"Mini proje ile {skill} guclendir",
                "detail": f"{skill} iceren olculebilir bir proje ciktisi ekleyin (repo, demo, metrik).",
            }
        )

    interview_questions = [
        f"{skill} kullanarak cozdugunuz bir problemi adim adim anlatir misiniz?" for skill in top_skills
    ]

    return {
        "strongest_dimension": strongest,
        "strongest_score": round(dimensions[strongest], 1),
        "weakest_dimension": weakest,
        "weakest_score": round(dimensions[weakest], 1),
        "balance_gap": gap,
        "action_plan": action_plan,
        "interview_questions": interview_questions,
    }


def _apply_plan_based_result_features(result: dict, effective_plan: str) -> dict:
    premium_access = _is_premium_plan(effective_plan)
    result["effective_plan"] = effective_plan
    result["premium_access"] = premium_access

    if premium_access:
        result["premium_insights"] = _build_premium_insights(result)
        return result

    recs = result.get("recommendations") or []
    if isinstance(recs, list) and len(recs) > 2:
        result["recommendations"] = recs[:2]
        result["recommendations_truncated"] = True

    missing = result.get("missing_skills") or []
    if isinstance(missing, list) and len(missing) > 6:
        result["missing_skills"] = missing[:6]
        result["missing_skills_truncated"] = True

    result["premium_locked"] = {
        "advanced_breakdown": True,
        "full_recommendations": True,
    }
    return result
