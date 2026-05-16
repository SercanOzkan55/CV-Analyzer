"""User data, retention, reminders, and specialization endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

from fastapi import APIRouter
from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403


router = APIRouter(tags=["user-data"])

class UserReminderCreateRequest(BaseModel):
    title: str
    description: str | None = None
    reminder_type: str = "interview"
    event_date: datetime
    target_email: str | None = None
    is_active: bool = True


class UserReminderUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    reminder_type: str | None = None
    event_date: datetime | None = None
    target_email: str | None = None
    is_active: bool | None = None


def _get_current_db_user(user, db) -> User:
    _ensure_not_expired(user)
    if _main_module().MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        return get_or_create_user(
            db,
            str(mock_user_id or "mock-user"),
            mock_email or "dev@example.com",
        )
    return get_or_create_user(db, user.get("user_id"), user.get("email"))


def _storage_key_fingerprint(key: str | None) -> str | None:
    if not key:
        return None
    return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:16]


def _delete_cv_version_files(row: CVVersion, supabase_id: str) -> tuple[int, list[dict]]:
    """Delete S3/local objects referenced by one CVVersion row."""
    from services.storage_service import delete_cv

    deleted = 0
    errors: list[dict] = []
    seen: set[str] = set()
    for key in (row.original_s3_key, row.optimized_s3_key):
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            delete_cv(key, supabase_id)
            deleted += 1
        except Exception as exc:
            errors.append(
                {
                    "version_id": row.id,
                    "key_hash": _storage_key_fingerprint(key),
                    "error": exc.__class__.__name__,
                }
            )
    return deleted, errors


def _delete_cv_versions_for_user(db, db_user: User, rows: list[CVVersion]) -> dict:
    deleted_files = 0
    file_errors: list[dict] = []
    deletable_ids: list[int] = []

    for row in rows:
        files, errors = _delete_cv_version_files(row, db_user.supabase_id)
        deleted_files += files
        if errors:
            file_errors.extend(errors)
            continue
        deletable_ids.append(int(row.id))

    if deletable_ids:
        db.query(CVVersion).filter(
            CVVersion.user_id == db_user.id,
            CVVersion.id.in_(deletable_ids),
        ).delete(synchronize_session=False)

    return {
        "deleted_cv_versions": len(deletable_ids),
        "deleted_files": deleted_files,
        "file_errors": file_errors,
        "blocked_cv_versions": len(rows) - len(deletable_ids),
    }


def _delete_analysis_records_for_user(db, user_id: int) -> dict:
    from models import AnalysisNote, AnalysisShare, Favorite

    analysis_ids = [
        row[0]
        for row in db.query(Analysis.id)
        .filter(Analysis.user_id == user_id)
        .all()
    ]
    if not analysis_ids:
        return {
            "deleted_analyses": 0,
            "deleted_favorites": 0,
            "deleted_shares": 0,
            "deleted_notes": 0,
        }

    deleted_notes = db.query(AnalysisNote).filter(
        AnalysisNote.user_id == user_id,
        AnalysisNote.analysis_id.in_(analysis_ids),
    ).delete(synchronize_session=False)
    deleted_shares = db.query(AnalysisShare).filter(
        AnalysisShare.user_id == user_id,
        AnalysisShare.analysis_id.in_(analysis_ids),
    ).delete(synchronize_session=False)
    deleted_favorites = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.analysis_id.in_(analysis_ids),
    ).delete(synchronize_session=False)
    deleted_analyses = db.query(Analysis).filter(
        Analysis.user_id == user_id,
        Analysis.id.in_(analysis_ids),
    ).delete(synchronize_session=False)

    return {
        "deleted_analyses": int(deleted_analyses or 0),
        "deleted_favorites": int(deleted_favorites or 0),
        "deleted_shares": int(deleted_shares or 0),
        "deleted_notes": int(deleted_notes or 0),
    }


@router.get("/api/v1/me/data-summary")
def get_my_data_summary(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return a privacy-oriented summary of data held for the current user."""
    from models import (
        AnalysisNote,
        AnalysisShare,
        CandidateAction,
        Favorite,
        JobTemplate,
        UsageDaily,
    )

    db_user = _get_current_db_user(user, db)
    cv_rows = db.query(CVVersion).filter(CVVersion.user_id == db_user.id).all()
    stored_files = sum(
        1
        for row in cv_rows
        for key in (row.original_s3_key, row.optimized_s3_key)
        if key
    )

    return {
        "user_id": db_user.id,
        "email": db_user.email,
        "cv_versions": len(cv_rows),
        "stored_cv_files": stored_files,
        "analyses": db.query(Analysis).filter(Analysis.user_id == db_user.id).count(),
        "favorites": db.query(Favorite).filter(Favorite.user_id == db_user.id).count(),
        "analysis_shares": db.query(AnalysisShare).filter(AnalysisShare.user_id == db_user.id).count(),
        "analysis_notes": db.query(AnalysisNote).filter(AnalysisNote.user_id == db_user.id).count(),
        "job_templates": db.query(JobTemplate).filter(JobTemplate.user_id == db_user.id).count(),
        "usage_days": db.query(UsageDaily).filter(UsageDaily.user_id == db_user.id).count(),
        "reminders": db.query(Reminder).filter(Reminder.created_by == db_user.id).count(),
        "candidate_actions": db.query(CandidateAction).filter(CandidateAction.recruiter_id == db_user.id).count(),
    }


@router.get("/api/v1/me/data-export")
def export_my_data(
    include_raw: bool = Query(False),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Export user-owned data with raw CV text excluded by default."""
    from models import (
        AnalysisNote,
        AnalysisShare,
        CandidateAction,
        Favorite,
        JobTemplate,
        UsageDaily,
    )

    def _dt(value):
        try:
            return value.isoformat() + "Z" if value else None
        except Exception:
            return None

    def _text_meta(value: str | None):
        raw = value or ""
        return {
            "chars": len(raw),
            "preview": raw[:240] if include_raw else None,
            "value": raw if include_raw else None,
        }

    db_user = _get_current_db_user(user, db)
    cv_rows = db.query(CVVersion).filter(CVVersion.user_id == db_user.id).order_by(CVVersion.created_at.desc()).all()
    analyses = db.query(Analysis).filter(Analysis.user_id == db_user.id).order_by(Analysis.created_at.desc()).limit(500).all()
    favorites = db.query(Favorite).filter(Favorite.user_id == db_user.id).all()
    shares = db.query(AnalysisShare).filter(AnalysisShare.user_id == db_user.id).all()
    notes = db.query(AnalysisNote).filter(AnalysisNote.user_id == db_user.id).all()
    templates = db.query(JobTemplate).filter(JobTemplate.user_id == db_user.id).all()
    usage_days = db.query(UsageDaily).filter(UsageDaily.user_id == db_user.id).order_by(UsageDaily.date.desc()).limit(400).all()
    reminders = db.query(Reminder).filter(Reminder.created_by == db_user.id).order_by(Reminder.event_date.desc()).all()
    actions = db.query(CandidateAction).filter(CandidateAction.recruiter_id == db_user.id).order_by(CandidateAction.created_at.desc()).limit(500).all()

    payload = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "include_raw": bool(include_raw),
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "plan_type": db_user.plan_type,
            "billing_status": db_user.billing_status,
            "role": db_user.role,
            "organization_id": db_user.organization_id,
            "created_at": _dt(db_user.created_at),
        },
        "cv_versions": [
            {
                "id": row.id,
                "version_label": row.version_label,
                "source": row.source,
                "lang": row.lang,
                "match_score": row.match_score,
                "notes": row.notes,
                "created_at": _dt(row.created_at),
                "cv_text": _text_meta(row.cv_text),
                "optimized_cv_text": _text_meta(row.optimized_cv_text),
                "job_description": _text_meta(row.job_description),
                "stored_files": {
                    "original": bool(row.original_s3_key),
                    "optimized": bool(row.optimized_s3_key),
                },
            }
            for row in cv_rows
        ],
        "analyses": [
            {
                "id": row.id,
                "similarity_score": row.similarity_score,
                "confidence": row.confidence,
                "risk_level": row.risk_level,
                "job_title": row.job_title,
                "created_at": _dt(row.created_at),
            }
            for row in analyses
        ],
        "favorites": [{"analysis_id": row.analysis_id, "note": row.note, "created_at": _dt(row.created_at)} for row in favorites],
        "shares": [{"analysis_id": row.analysis_id, "active": row.is_active, "views": row.views, "created_at": _dt(row.created_at)} for row in shares],
        "notes": [{"analysis_id": row.analysis_id, "content": row.content if include_raw else None, "chars": len(row.content or ""), "created_at": _dt(row.created_at)} for row in notes],
        "job_templates": [{"id": row.id, "title": row.title, "description": _text_meta(row.description), "created_at": _dt(row.created_at)} for row in templates],
        "usage_days": [{"date": _dt(row.date), "count": row.count} for row in usage_days],
        "reminders": [
            {
                "id": row.id,
                "title": row.title,
                "type": row.reminder_type,
                "target_email": row.target_email,
                "event_date": _dt(row.event_date),
                "is_active": row.is_active,
                "notified_3d_at": _dt(row.notified_3d_at),
                "notified_1d_at": _dt(row.notified_1d_at),
            }
            for row in reminders
        ],
        "candidate_actions": [
            {
                "id": row.id,
                "job_id": row.job_id,
                "candidate_name": row.candidate_name,
                "candidate_email": row.candidate_email,
                "action": row.action,
                "final_score": row.final_score,
                "ats_score": row.ats_score,
                "email_sent": row.email_sent,
                "created_at": _dt(row.created_at),
                "cv_text": _text_meta(row.cv_text),
            }
            for row in actions
        ],
    }
    _record_ops_event("data_export", "ok", user_id=db_user.id, include_raw=bool(include_raw))
    return payload


@router.delete("/api/v1/me/data")
def delete_my_data(
    scope: str = Query("stored_cvs", pattern="^(stored_cvs|analyses|workspace|all)$"),
    confirm: str = Query(..., min_length=6, max_length=6),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Delete selected privacy-sensitive data for the current user."""
    from models import CandidateAction, JobTemplate, UsageDaily

    if confirm != "DELETE":
        raise HTTPException(status_code=400, detail="confirm=DELETE is required")

    db_user = _get_current_db_user(user, db)
    summary: dict[str, object] = {"scope": scope}

    try:
        if scope in ("stored_cvs", "all"):
            rows = db.query(CVVersion).filter(CVVersion.user_id == db_user.id).all()
            summary.update(_delete_cv_versions_for_user(db, db_user, rows))

        if scope in ("analyses", "all"):
            summary.update(_delete_analysis_records_for_user(db, db_user.id))

        if scope in ("workspace", "all"):
            deleted_templates = db.query(JobTemplate).filter(
                JobTemplate.user_id == db_user.id
            ).delete(synchronize_session=False)
            deleted_usage_days = db.query(UsageDaily).filter(
                UsageDaily.user_id == db_user.id
            ).delete(synchronize_session=False)
            deleted_reminders = db.query(Reminder).filter(
                Reminder.created_by == db_user.id
            ).delete(synchronize_session=False)
            deleted_candidate_actions = db.query(CandidateAction).filter(
                CandidateAction.recruiter_id == db_user.id
            ).delete(synchronize_session=False)
            summary.update(
                {
                    "deleted_job_templates": int(deleted_templates or 0),
                    "deleted_usage_days": int(deleted_usage_days or 0),
                    "deleted_reminders": int(deleted_reminders or 0),
                    "deleted_candidate_actions": int(deleted_candidate_actions or 0),
                }
            )

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("privacy:data_delete_failed user=%s scope=%s", db_user.id, scope)
        raise HTTPException(status_code=500, detail="Data deletion failed")

    try:
        audit_payload = dict(summary)
        audit_payload.pop("scope", None)
        audit_log("privacy_data_delete", user_id=db_user.id, scope=scope, **audit_payload)
    except Exception:
        pass

    return {"deleted": True, **summary}


def _purge_expired_cv_versions(db, days: int, limit: int, dry_run: bool = True) -> dict:
    days = max(1, min(int(days), 3650))
    limit = max(1, min(int(limit), 1000))
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(CVVersion)
        .filter(CVVersion.created_at < cutoff)
        .order_by(CVVersion.created_at.asc())
        .limit(limit)
        .all()
    )
    if dry_run:
        file_count = sum(
            1
            for row in rows
            for key in (row.original_s3_key, row.optimized_s3_key)
            if key
        )
        return {
            "dry_run": True,
            "retention_days": days,
            "eligible_cv_versions": len(rows),
            "eligible_files": file_count,
        }

    deleted_rows = 0
    deleted_files = 0
    file_errors: list[dict] = []
    for row in rows:
        owner = db.query(User).filter(User.id == row.user_id).first()
        if not owner:
            continue
        files, errors = _delete_cv_version_files(row, owner.supabase_id)
        deleted_files += files
        if errors:
            file_errors.extend(errors)
            continue
        db.delete(row)
        deleted_rows += 1

    return {
        "dry_run": False,
        "retention_days": days,
        "deleted_cv_versions": deleted_rows,
        "deleted_files": deleted_files,
        "file_errors": file_errors,
    }


@router.post("/api/v1/admin/storage/retention/run")
def run_storage_retention(
    request: Request,
    days: int = Query(default=int(os.getenv("CV_RETENTION_DAYS", "90")), ge=1, le=3650),
    limit: int = Query(default=int(os.getenv("CV_RETENTION_BATCH_LIMIT", "200")), ge=1, le=1000),
    dry_run: bool = Query(default=True),
    confirm: str = Query("", max_length=6),
    db=Depends(get_db),
):
    """Admin-only cleanup for expired stored CV versions and their files."""
    admin_error = _admin_access_error(request)
    if admin_error:
        detail = "Rate limited" if admin_error.status_code == 429 else "Forbidden"
        raise HTTPException(status_code=admin_error.status_code, detail=detail)
    if not dry_run and confirm != "DELETE":
        raise HTTPException(status_code=400, detail="confirm=DELETE is required for deletion")

    try:
        result = _purge_expired_cv_versions(db, days=days, limit=limit, dry_run=dry_run)
        if not dry_run:
            db.commit()
        audit_log("storage_retention_run", **result)
        return result
    except Exception:
        db.rollback()
        logger.exception("storage_retention_failed")
        raise HTTPException(status_code=500, detail="Storage retention failed")


def _normalize_reminder_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _ensure_reminder_organization(db, db_user: User) -> int:
    if db_user.organization_id:
        return int(db_user.organization_id)

    domain = f"personal-user-{db_user.id}.cvanalyzer.local"
    org = db.query(Organization).filter(Organization.domain == domain).first()
    if org:
        return int(org.id)

    org = Organization(
        name=f"{(db_user.email or 'User').split('@')[0]} Personal Workspace",
        domain=domain,
        plan_type="free",
        billing_status="trialing",
    )
    try:
        db.add(org)
        db.commit()
        db.refresh(org)
        return int(org.id)
    except Exception:
        db.rollback()
        org = db.query(Organization).filter(Organization.domain == domain).first()
        if org:
            return int(org.id)
        raise


def _reminder_type_label(value: str) -> str:
    labels = {
        "interview": "Mülakat",
        "offer": "Teklif",
        "deadline": "Son tarih",
        "follow_up": "Takip",
        "other": "Hatırlatma",
    }
    return labels.get(str(value or "").strip().lower(), "Hatırlatma")


def _serialize_reminder(reminder: Reminder) -> dict:
    now = datetime.utcnow()
    delta = reminder.event_date - now if reminder.event_date else timedelta()
    hours_left = max(0, int(delta.total_seconds() // 3600))
    days_left = max(0, int((delta.total_seconds() + 86399) // 86400))
    return {
        "id": reminder.id,
        "title": reminder.title,
        "description": reminder.description,
        "reminder_type": reminder.reminder_type,
        "reminder_type_label": _reminder_type_label(reminder.reminder_type),
        "event_date": reminder.event_date.isoformat() + "Z" if reminder.event_date else None,
        "target_email": reminder.target_email,
        "is_active": reminder.is_active,
        "notified_3d_at": reminder.notified_3d_at.isoformat() + "Z" if reminder.notified_3d_at else None,
        "notified_1d_at": reminder.notified_1d_at.isoformat() + "Z" if reminder.notified_1d_at else None,
        "days_left": days_left,
        "hours_left": hours_left,
        "created_at": reminder.created_at.isoformat() + "Z" if reminder.created_at else None,
        "updated_at": reminder.updated_at.isoformat() + "Z" if reminder.updated_at else None,
    }


def _get_user_reminder_or_404(db, db_user: User, reminder_id: int) -> Reminder:
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.created_by == db_user.id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.get("/api/v1/reminders")
def list_user_reminders(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    db_user = _get_current_db_user(user, db)
    reminders = (
        db.query(Reminder)
        .filter(Reminder.created_by == db_user.id)
        .order_by(Reminder.event_date.asc())
        .all()
    )
    return {"reminders": [_serialize_reminder(r) for r in reminders], "total": len(reminders)}


@router.post("/api/v1/reminders")
def create_user_reminder(
    body: UserReminderCreateRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    db_user = _get_current_db_user(user, db)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if len(title) > 500:
        raise HTTPException(status_code=400, detail="Title too long")

    event_date = _normalize_reminder_datetime(body.event_date)
    if event_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Event date must be in the future")

    target_email = _validate_reminder_email(body.target_email or db_user.email or "")
    org_id = _ensure_reminder_organization(db, db_user)

    reminder = Reminder(
        organization_id=org_id,
        created_by=db_user.id,
        title=title,
        description=(body.description or "").strip()[:1000],
        reminder_type=(body.reminder_type or "interview").strip()[:40],
        target_email=target_email,
        event_date=event_date,
        is_active=bool(body.is_active),
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return _serialize_reminder(reminder)


@router.put("/api/v1/reminders/{reminder_id}")
def update_user_reminder(
    reminder_id: int,
    body: UserReminderUpdateRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    db_user = _get_current_db_user(user, db)
    reminder = _get_user_reminder_or_404(db, db_user, reminder_id)

    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required")
        reminder.title = title[:500]
    if body.description is not None:
        reminder.description = body.description.strip()[:1000]
    if body.reminder_type is not None:
        reminder.reminder_type = (body.reminder_type or "other").strip()[:40]
    if body.event_date is not None:
        event_date = _normalize_reminder_datetime(body.event_date)
        if event_date <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="Event date must be in the future")
        reminder.event_date = event_date
        reminder.notified_3d_at = None
        reminder.notified_1d_at = None
    if body.target_email is not None:
        reminder.target_email = _validate_reminder_email(body.target_email)
    if body.is_active is not None:
        reminder.is_active = bool(body.is_active)

    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return _serialize_reminder(reminder)


@router.delete("/api/v1/reminders/{reminder_id}")
def delete_user_reminder(
    reminder_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    db_user = _get_current_db_user(user, db)
    reminder = _get_user_reminder_or_404(db, db_user, reminder_id)
    db.delete(reminder)
    db.commit()
    return {"deleted": True}


@router.post("/api/v1/reminders/{reminder_id}/send-test")
def send_user_reminder_test(
    reminder_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    db_user = _get_current_db_user(user, db)
    reminder = _get_user_reminder_or_404(db, db_user, reminder_id)
    delta = reminder.event_date - datetime.utcnow()
    days_left = max(1, int((delta.total_seconds() + 86399) // 86400))
    if not _send_reminder_email(reminder, days_left, reminder.target_email):
        raise HTTPException(
            status_code=503,
            detail="Email provider is not configured or failed to send",
        )
    return {"sent": True, "to": reminder.target_email}


@router.get("/api/v1/benchmark/specializations")
def get_benchmark_specializations(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return per-specialization benchmark statistics.

    Aggregates Analysis records grouped by specialization_id and joins
    the specializations table for human-readable names. Only specializations
    with at least BENCHMARK_MIN_PEERS analyses are returned.
    """
    _ensure_not_expired(user)
    from sqlalchemy import func, text as sa_text

    # Aggregate analysis scores per specialization
    rows = (
        db.query(
            Analysis.specialization_id,
            func.count(Analysis.id).label("count"),
            func.avg(Analysis.similarity_score).label("avg_score"),
            func.min(Analysis.similarity_score).label("min_score"),
            func.max(Analysis.similarity_score).label("max_score"),
        )
        .filter(Analysis.specialization_id.isnot(None))
        .group_by(Analysis.specialization_id)
        .having(func.count(Analysis.id) >= BENCHMARK_MIN_PEERS)
        .order_by(func.count(Analysis.id).desc())
        .limit(50)
        .all()
    )

    if not rows:
        return {"specializations": []}

    # Fetch specialization names from DB
    spec_ids = [r.specialization_id for r in rows]
    try:
        name_rows = db.execute(
            sa_text("SELECT id, name FROM specializations WHERE id = ANY(:ids)"),
            {"ids": spec_ids},
        ).fetchall()
        spec_names = {r[0]: r[1] for r in name_rows}
    except Exception:
        spec_names = {}

    return {
        "specializations": [
            {
                "specialization_id": r.specialization_id,
                "specialization_name": spec_names.get(r.specialization_id, f"Specialization {r.specialization_id}"),
                "count": r.count,
                "avg_score": round(float(r.avg_score or 0), 1),
                "min_score": round(float(r.min_score or 0), 1),
                "max_score": round(float(r.max_score or 0), 1),
            }
            for r in rows
        ]
    }


# =====================================================
# SEMANTIC SEARCH (job -> candidate retrieval)
# =====================================================


