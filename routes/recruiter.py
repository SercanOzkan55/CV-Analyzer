import json
import logging
import os
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select, text

from auth import verify_supabase_jwt
from config.aws import MAX_UPLOAD_BYTES
import time
from typing import Any
from core.runtime_bridge import main_module, redis_rate_client
from database import get_db
from models import (
    Analysis,
    Candidate,
    CandidateAction,
    Organization,
    RecruiterJob,
    Reminder,
    User,
)
from services.report_service import generate_recruiter_report
from services.recruiter_service import (
    analyze_strengths_weaknesses as _rc_sw,
    build_preview as _rc_preview,
    create_email_template as _rc_create_tpl,
    create_job as _rc_create_job,
    delete_email_template as _rc_del_tpl,
    get_email_template as _rc_get_tpl,
    get_email_templates as _rc_get_tpls,
    get_jobs as _rc_get_jobs,
    get_actions_for_job as _rc_get_actions,
    mark_email_sent as _rc_mark_sent,
    rank_candidates as _rc_rank,
    render_template as _rc_render,
    save_candidate_action as _rc_save_action,
    validate_email_send as _rc_validate_email,
    extract_variables as _rc_vars,
)
from services.recruiter_helpers import (
    _MAX_SEARCH_QUERY_LEN,
    _do_send_email,
    _extract_pdf_text,
    _is_postgres_engine,
    _process_due_reminders,
    _resolve_job_description_text,
    _validate_pdf_upload,
    _validate_reminder_email,
    _ensure_not_expired,
)
from security.file_guard import read_upload_limited
from services.tasks import batch_recruiter_task

logger = logging.getLogger("app.recruiter")

_MAX_BATCH_FILES = int(os.getenv("RECRUITER_MAX_BATCH_FILES", "50"))


def _format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} bytes"


def _main():
    return main_module()


def _get_limiter():
    """Get rate limiter instance from FastAPI app state"""
    try:
        main = _main()
        if hasattr(main, 'app') and hasattr(main.app, 'state') and hasattr(main.app.state, 'limiter'):
            return main.app.state.limiter
        # Fallback if limiter not available
        class NoopLimiter:
            def limit(self, limit_string):
                def decorator(func):
                    return func
                return decorator
        return NoopLimiter()
    except:
        # If anything fails, return noop limiter
        class NoopLimiter:
            def limit(self, limit_string):
                def decorator(func):
                    return func
                return decorator
        return NoopLimiter()


def require_search_rate(request: Request, user=Depends(verify_supabase_jwt)):
    return _main().require_search_rate(request, user=user)


def require_abuse_check(request: Request):
    return _main().require_abuse_check(request)


def _log_event(event_type: str, **fields):
    return _main().audit_log(event_type, **fields)


def _get_user(db, supabase_id: str, email: str):
    return _main().get_or_create_user(db, supabase_id, email)


def _pipeline(cv_text: str, job_description: str, lang: str = ""):
    return _main().run_pipeline(cv_text, job_description, lang=lang)


def _billable_usage(db, recruiter: User | None, endpoint: str, response: Response | None = None):
    return _main()._consume_billable_usage(db, recruiter, endpoint, response=response)


def _serialize_action(action: CandidateAction) -> dict:
    snapshot = {}
    if action.analysis_snapshot:
        try:
            snapshot = json.loads(action.analysis_snapshot)
        except Exception:
            snapshot = {}
    return {
        "id": action.id,
        "job_id": action.job_id,
        "candidate_name": action.candidate_name,
        "candidate_email": action.candidate_email,
        "action": action.action,
        "stage": action.action,
        "final_score": action.final_score,
        "ats_score": action.ats_score,
        "email_sent": action.email_sent,
        "email_sent_at": str(action.email_sent_at) if action.email_sent_at else None,
        "notes": action.notes,
        "created_at": str(action.created_at) if action.created_at else None,
        "analysis_snapshot": snapshot,
    }

router = APIRouter(prefix="/api/v1/recruiter")

_ALLOWED_CANDIDATE_STAGES = {
    "pending",
    "shortlist",
    "interview",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
}

_GENERIC_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "mail.com",
    "protonmail.com",
    "yandex.com",
}


class RecruiterJobCreate(BaseModel):
    title: str
    description: str


class RecruiterEmailTemplateCreate(BaseModel):
    name: str
    template_type: str = "accept"
    subject: str
    body: str


class RecruiterActionRequest(BaseModel):
    job_id: int
    candidate_name: str
    candidate_email: str | None = None
    cv_text: str | None = None
    final_score: float | None = None
    ats_score: float | None = None
    action: str
    analysis_snapshot: dict | None = None
    template_id: int | None = None


class RecruiterStageUpdateRequest(BaseModel):
    stage: str
    notes: str | None = None


# Response models for consistent API contracts
class CandidatePreview(BaseModel):
    analysis_id: int | None
    user_id: int | None
    similarity_score: float | None
    interpretation: str | None
    confidence: float | None
    risk_level: str | None
    domain_id: int | None
    industry_id: int | None
    specialization_id: int | None
    created_at: datetime | None


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses"""
    total: int
    limit: int
    offset: int
    hasMore: bool


class CandidatesResponse(BaseModel):
    candidates: list[CandidatePreview]
    data: list[CandidatePreview] | None = None
    total: int | None = None
    pagination: PaginationMeta | None = None


class SearchResult(BaseModel):
    id: int
    organization_id: int
    cv_preview: str | None
    rank: float | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int | None = None
    query: str | None = None
    pagination: PaginationMeta | None = None


class JobResponse(BaseModel):
    id: int
    title: str
    description: str
    created_at: str


class JobsResponse(BaseModel):
    jobs: list[JobResponse]
    total: int | None = None
    pagination: PaginationMeta | None = None


class RecruiterRankRequest(BaseModel):
    job_description: str
    cv_texts: list[dict]
    lang: str = "en"


class RecruiterPreviewRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    candidate_name: str = ""
    candidate_email: str = ""
    lang: str = "en"


class RecruiterTemplatePreviewRequest(BaseModel):
    template_id: int
    variables: dict = {}


class RecruiterSendEmailRequest(BaseModel):
    template_id: int
    candidate_name: str = ""
    candidate_email: str = ""
    cv_text: str = ""
    job_description: str = ""
    job_id: int | None = None
    action_id: int | None = None
    sender_email: str = ""


class RecruiterReminderCreateRequest(BaseModel):
    title: str
    description: str | None = None
    reminder_type: str = "interview"
    event_date: datetime
    target_email: str | None = None
    is_active: bool = True


class RecruiterReminderUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    reminder_type: str | None = None
    event_date: datetime | None = None
    target_email: str | None = None
    is_active: bool | None = None


def recruiter_required(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    supabase_id = user.get("user_id")
    email = user.get("email", "")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")

    db_user = _get_user(db, supabase_id, email)

    _mock = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
    _env = os.getenv("ENV", "development").lower()
    if _mock and _env not in ("production", "prod") and db_user and db_user.role not in ("recruiter", "admin"):
        db_user.role = "recruiter"
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    if not db_user or db_user.role not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Recruiter role required")

    if db_user.role in ("admin", "recruiter") and not db_user.organization_id:
        try:
            _user_email = db_user.email or ""
            raw_domain = _user_email.split("@", 1)[1].lower() if "@" in _user_email else ""
            domain = f"auto-{raw_domain}" if raw_domain in _GENERIC_DOMAINS else (raw_domain or "auto.local")
            org = db.query(Organization).filter(Organization.domain == domain).first()
            if not org:
                org = Organization(name=f"Auto Org ({domain})", domain=domain)
                db.add(org)
                db.flush()
            db_user.organization_id = org.id
            db.flush()
            db.commit()
            logger.info("recruiter_required: provisioned org_id=%s for user_id=%s email=%s", org.id, db_user.id, _user_email)
        except Exception as exc:
            db.rollback()
            logger.error("recruiter_required: org auto-provision failed: %s", exc)

    return db_user


@router.get("/candidates")
def recruiter_candidates(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
) -> CandidatesResponse:
    """
    Retrieve candidates from recruiter's organization with pagination.
    
    **Parameters:**
    - `limit`: Number of records to return (1-1000, default 20)
    - `offset`: Starting position for pagination (default 0)
    
    **Returns:**
    - List of candidates with pagination metadata
    
    **Raises:**
    - 400: Recruiter has no organization
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
    
    # Get total count
    total_count = db.query(Analysis).filter(Analysis.user_id.in_(select(users_subq.c.id))).count()
    
    # Get paginated records
    records = (
        db.query(Analysis)
        .filter(Analysis.user_id.in_(select(users_subq.c.id)))
        .order_by(Analysis.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    candidates = [
        CandidatePreview(
            analysis_id=getattr(r, "id", None),
            user_id=getattr(r, "user_id", None),
            similarity_score=getattr(r, "similarity_score", None),
            interpretation=getattr(r, "interpretation", None),
            confidence=getattr(r, "confidence", None),
            risk_level=getattr(r, "risk_level", None),
            domain_id=getattr(r, "domain_id", None),
            industry_id=getattr(r, "industry_id", None),
            specialization_id=getattr(r, "specialization_id", None),
            created_at=getattr(r, "created_at", None),
        )
        for r in records
    ]

    pagination = PaginationMeta(
        total=total_count,
        limit=limit,
        offset=offset,
        hasMore=(offset + limit) < total_count
    )

    return CandidatesResponse(candidates=candidates, data=candidates, total=total_count, pagination=pagination)


@router.get("/top_candidates")
def recruiter_top_candidates(
    limit: int = 10,
    min_score: float = 0.0,
    start_date: str | None = None,
    end_date: str | None = None,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
    query = db.query(Analysis).filter(Analysis.user_id.in_(select(users_subq.c.id)))

    try:
        if min_score is not None:
            query = query.filter(Analysis.similarity_score >= float(min_score))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid min_score")

    from datetime import datetime as _dt

    if start_date:
        try:
            sd = _dt.fromisoformat(start_date)
            query = query.filter(Analysis.created_at >= sd)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format; expected ISO-8601")

    if end_date:
        try:
            ed = _dt.fromisoformat(end_date)
            query = query.filter(Analysis.created_at <= ed)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format; expected ISO-8601")

    records = query.order_by(Analysis.similarity_score.desc()).limit(limit).all()
    return {
        "top_candidates": [
            {
                "analysis_id": getattr(r, "id", None),
                "user_id": getattr(r, "user_id", None),
                "final_score": getattr(r, "similarity_score", None),
                "interpretation": getattr(r, "interpretation", None),
                "created_at": getattr(r, "created_at", None),
            }
            for r in records
        ]
    }


@router.get("/candidate/{analysis_id}")
def recruiter_candidate_detail(analysis_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    user = db.query(User).filter(User.id == analysis.user_id).first()
    if not user or user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "analysis_id": getattr(analysis, "id", None),
        "user_id": getattr(analysis, "user_id", None),
        "final_score": getattr(analysis, "similarity_score", None),
        "interpretation": getattr(analysis, "interpretation", None),
        "confidence": getattr(analysis, "confidence", None),
        "risk_level": getattr(analysis, "risk_level", None),
        "domain_id": getattr(analysis, "domain_id", None),
        "industry_id": getattr(analysis, "industry_id", None),
        "specialization_id": getattr(analysis, "specialization_id", None),
        "created_at": getattr(analysis, "created_at", None),
        "raw": {"ats": getattr(analysis, "ats", None)},
    }


@_get_limiter().limit("100/minute")
@router.get("/search")
def recruiter_search(
    q: str = Query(..., min_length=1, max_length=_MAX_SEARCH_QUERY_LEN),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    _search_guard: None = Depends(require_search_rate),
    request: Request = None,
) -> SearchResponse:
    """
    Search candidates in recruiter's organization by CV text with pagination.
    
    **Parameters:**
    - `q`: Search query (1-500 characters)
    - `limit`: Maximum results per page (1-1000, default 20)
    - `offset`: Starting position for pagination (default 0)
    
    **Returns:**
    - List of candidates matching search query with pagination metadata
    
    **Raises:**
    - 400: Missing query or recruiter has no organization
    - 429: Search rate limit exceeded
    - 500: Database error during search
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    query = (q or "").strip()
    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query 'q' is required and cannot be empty"
        )

    limit = min(max(1, int(limit)), 100)
    results: list[dict] = []
    total_count = 0

    try:
        use_postgres = False
        if getattr(getattr(db, 'bind', None), 'dialect', None):
            db_dialect = getattr(db.bind.dialect, 'name', '').lower()
            use_postgres = db_dialect in ("postgresql", "postgres")

        if use_postgres:
            # First get total count
            count_query = text(
                """
                SELECT COUNT(*) as cnt
                FROM candidates
                WHERE organization_id = :org_id
                  AND to_tsvector('english', coalesce(cv_text, '')) @@ plainto_tsquery(:q)
                """
            )
            try:
                count_result = db.execute(count_query, {"q": query, "org_id": org_id}).fetchone()
                total_count = count_result[0] if count_result else 0
            except Exception as db_err:
                logger.error("postgres_count_failed q=%s org_id=%s error=%s", query, org_id, db_err)
                use_postgres = False
                total_count = 0

            if use_postgres:
                # Then get paginated results
                sql_query = text(
                    """
                    SELECT id, organization_id, cv_text,
                           ts_rank_cd(
                               to_tsvector('english', coalesce(cv_text, '')),
                               plainto_tsquery(:q)
                           ) AS rank
                    FROM candidates
                    WHERE organization_id = :org_id
                      AND to_tsvector('english', coalesce(cv_text, '')) @@ plainto_tsquery(:q)
                    ORDER BY rank DESC
                    OFFSET :offset
                    LIMIT :limit
                    """
                )
                try:
                    rows = db.execute(sql_query, {"q": query, "org_id": org_id, "offset": int(offset), "limit": int(limit)}).fetchall()
                except Exception as db_err:
                    logger.error("postgres_search_failed q=%s org_id=%s error=%s", query, org_id, db_err)
                    use_postgres = False
                    rows = []

                if use_postgres:
                    for row in rows:
                        results.append(
                            SearchResult(
                                id=row[0],
                                organization_id=row[1],
                                cv_preview=(row[2][:200] + "...") if row[2] and len(row[2]) > 200 else row[2],
                                rank=float(row[3]),
                            ).dict()
                        )

        if not use_postgres:
            pattern = f"%{query}%"
            try:
                # Get total count
                total_count = (
                    db.query(Candidate)
                    .filter(Candidate.organization_id == org_id)
                    .filter(Candidate.cv_text.ilike(pattern))
                    .count()
                )
                
                # Get paginated results
                rows = (
                    db.query(Candidate)
                    .filter(Candidate.organization_id == org_id)
                    .filter(Candidate.cv_text.ilike(pattern))
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
            except Exception as db_err:
                logger.error("sqlite_search_failed q=%s org_id=%s error=%s", query, org_id, db_err)
                raise HTTPException(
                    status_code=500,
                    detail="Search failed (database error)"
                )
            for r in rows:
                cv_preview = None
                cv_text = getattr(r, "cv_text", None)
                if cv_text:
                    cv_preview = (cv_text[:200] + "...") if len(cv_text) > 200 else cv_text
                results.append(
                    SearchResult(
                        id=getattr(r, "id", None),
                        organization_id=getattr(r, "organization_id", None),
                        cv_preview=cv_preview,
                        rank=None,
                    ).dict()
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("search_unexpected_error q=%s org_id=%s error=%s", query, org_id, e)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during search"
        )

    pagination = PaginationMeta(
        total=total_count,
        limit=limit,
        offset=offset,
        hasMore=(offset + limit) < total_count
    )

    return SearchResponse(results=results, total=total_count, query=query, pagination=pagination)


@router.post("/batch-rank")
async def recruiter_batch_rank(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(...),
    job_description: str = Form(""),
    jd_file: UploadFile | None = File(None),
    db=Depends(get_db),
    _=Depends(require_abuse_check),
    recruiter=Depends(recruiter_required),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one CV file is required")
    if len(files) > _MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_BATCH_FILES} CV files allowed",
        )
    for upload in files:
        filename = (upload.filename or "").lower()
        content_type = (upload.content_type or "").lower()
        if not filename.endswith(".pdf") or content_type not in {"application/pdf", "application/x-pdf"}:
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    jd_text = await _resolve_job_description_text(job_description, jd_file)
    if not jd_text:
        raise HTTPException(status_code=400, detail="Job description is empty")
    _billable_usage(db, recruiter, "recruiter-batch-rank", response=response)

    ranked = []
    skill_counts: dict[str, int] = {}

    import re as _re_rank

    def _extract_candidate_info(text: str, fallback_name: str) -> tuple[str, str]:
        email = ""
        name = fallback_name
        lines = text.split("\n")
        for line in lines[:30]:
            m = _re_rank.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", line)
            if m:
                email = m.group(0)
                break
        for line in lines[:10]:
            cleaned = line.strip()
            if not cleaned or len(cleaned) < 2:
                continue
            if _re_rank.search(r"@|https?://|www\.|\.com|\.io|\(?\+?\d[\d()\-\s.]{7,}\d", cleaned, _re_rank.I):
                continue
            if cleaned.upper() == cleaned and len(cleaned) > 20:
                continue
            words = cleaned.split()
            if 1 < len(words) <= 5 and all(
                _re_rank.match(r"^[A-Za-zÀ-ÿĀ-žÇçĞğİıÖöŞşÜü\-'.]+$", w) for w in words
            ):
                name = cleaned
                break
        return name, email

    skipped = []
    for idx, upload in enumerate(files):
        try:
            contents = await read_upload_limited(upload)
            _validate_pdf_upload(contents, upload.content_type)
            cv_text, _ = _extract_pdf_text(contents)
            if not cv_text:
                skipped.append(upload.filename or f"candidate_{idx + 1}")
                continue

            autofix = _main().auto_fix_cv_text(
                cv_text=cv_text,
                job_description=jd_text,
                lang="en",
                use_ai=False,
                mode="safe",
            )
            normalized_text = autofix.get("optimized_cv_text") or cv_text
            result = _pipeline(normalized_text, jd_text)
            jd_quality = result.get("job_description_quality") or {}
            result_warnings = result.get("warnings") or []
            detected_skills = result.get("detected_skills") or []
            for s in detected_skills:
                key = str(s or "").strip().lower()
                if key:
                    skill_counts[key] = skill_counts.get(key, 0) + 1

            file_fallback = (upload.filename or f"candidate_{idx + 1}").replace(".pdf", "")
            builder_payload = autofix.get("builder_payload") or {}
            cand_name = builder_payload.get("full_name") or ""
            cand_email = builder_payload.get("email") or ""
            if not cand_name or not cand_email:
                fallback_name, fallback_email = _extract_candidate_info(cv_text, file_fallback)
                cand_name = cand_name or fallback_name
                cand_email = cand_email or fallback_email

            ranked.append(
                {
                    "candidate_name": cand_name,
                    "candidate_email": cand_email,
                    "file_name": upload.filename or f"candidate_{idx + 1}.pdf",
                    "final_score": float(result.get("final_score") or 0.0),
                    "final_score_breakdown": result.get("final_score_breakdown"),
                    "ats_score": float(result.get("ats_score") or 0.0),
                    "skill_score": float(result.get("skill_score") or 0.0),
                    "job_description_quality": jd_quality,
                    "warnings": result_warnings,
                    "score_version": result.get("score_version") or "",
                    "missing_skills": result.get("missing_skills") or [],
                    "keyword_gap": result.get("keyword_gap") or {},
                    "score_breakdown": result.get("score_breakdown") or {},
                    "recommendations": result.get("recommendations") or [],
                    "strengths": (result.get("detected_skills") or [])[:5],
                    "cv_text": normalized_text,
                    "original_cv_text": cv_text,
                    "builder_payload": builder_payload,
                }
            )
            
            # Record score to global benchmark anonymously
            try:
                from services.benchmark_service import record_ats_score, infer_profession_with_db
                profession = infer_profession_with_db(db, job_title=None, experience_titles=[jd_text])
                record_ats_score(
                    db=db,
                    ats_score=float(result.get("ats_score") or result.get("final_score") or 0.0),
                    profession=profession
                )
            except Exception as b_err:
                logger.warning("batch_rank: failed to record benchmark score: %s", b_err)
                
        except Exception as e:
            # Skip this CV and continue with next ones
            skipped.append((upload.filename or f"candidate_{idx + 1}", str(e)[:100]))
            continue

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    total = len(ranked)
    avg_score = round(sum(r["final_score"] for r in ranked) / max(1, total), 2)
    distribution = {
        "high": sum(1 for r in ranked if r["final_score"] >= 75),
        "medium": sum(1 for r in ranked if 50 <= r["final_score"] < 75),
        "low": sum(1 for r in ranked if r["final_score"] < 50),
    }
    top_skills = sorted(skill_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    try:
        _log_event(
            "recruiter_batch_rank",
            recruiter_id=getattr(recruiter, "id", None),
            organization_id=getattr(recruiter, "organization_id", None),
            cv_count=total,
            avg_score=avg_score,
        )
    except Exception:
        pass

    return {
        "total_candidates": total,
        "job_description_preview": jd_text[:300],
        "ranking": ranked,
        "job_description_quality": (ranked[0].get("job_description_quality") if ranked else {}),
        "score_version": (ranked[0].get("score_version") if ranked else ""),
        "warnings": sorted({
            str(w).strip()
            for row in ranked
            for w in (row.get("warnings") or [])
            if str(w).strip()
        }),
        "skipped_count": len(skipped),
        "skipped_files": skipped[:10] if skipped else [],  # Show first 10 skipped for user feedback
        "analytics": {
            "avg_score": avg_score,
            "top_skills": [
                {"skill": skill, "count": count} for skill, count in top_skills
            ],
            "candidate_distribution": distribution,
        },
    }


@_get_limiter().limit("30/minute")
@router.post("/dashboard/batch-upload")
async def recruiter_batch_upload(
    job_id: int = Form(..., gt=0),
    files: list[UploadFile] = File(...),
    response: Response = None,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
) -> dict:
    """
    Upload and process multiple CVs for a job position.
    
    **Parameters:**
    - `job_id`: Target job ID (must be > 0)
    - `files`: List of PDF/text files (required)
    
    **Validation:**
    - Each file must be a valid PDF or text file
    - Maximum 50 files per request
    - Total credits must be sufficient
    
    **Returns:**
    - Task ID for batch processing job
    - Count of processed CVs
    
    **Raises:**
    - 400: Invalid files, no text extracted, or insufficient credits
    - 404: Job not found
    - 429: Insufficient credits
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    # Validate files list
    if not files or len(files) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required"
        )
    
    if len(files) > _MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail="Maximum {} files per upload (you provided {})".format(
                _MAX_BATCH_FILES,
                len(files),
            )
        )

    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == job_id,
        RecruiterJob.organization_id == org_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or you do not have permission to access it"
        )

    cv_list = []
    valid_extensions = (".pdf", ".txt", ".docx")
    
    for idx, file in enumerate(files):
        if not file.filename:
            logger.warning("batch_upload: file %d has no filename", idx)
            continue
            
        # Validate file extension
        filename_lower = (file.filename or "").lower()
        if not any(filename_lower.endswith(ext) for ext in valid_extensions):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format: {}. Allowed: PDF, TXT, DOCX".format(file.filename)
            )

        try:
            contents = await read_upload_limited(file)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("batch_upload: failed to read file %s error=%s", file.filename, e)
            raise HTTPException(
                status_code=400,
                detail="Failed to read file: {}".format(file.filename)
            )

        # Validate file not empty
        if not contents or len(contents) == 0:
            raise HTTPException(
                status_code=400,
                detail="File is empty: {}".format(file.filename)
            )

        # Validate file size before text extraction.
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail="File too large (max {}): {}".format(
                    _format_bytes(MAX_UPLOAD_BYTES),
                    file.filename,
                )
            )

        # Extract text from file
        try:
            if filename_lower.endswith(".pdf"):
                _validate_pdf_upload(contents, file.content_type)
                text, _ = _extract_pdf_text(contents)
            else:
                # Plain text or DOCX
                try:
                    text = contents.decode("utf-8", errors="ignore").strip()
                except Exception:
                    text = ""
        except HTTPException:
            raise
        except Exception as e:
            logger.error("batch_upload: text extraction failed for %s error=%s", file.filename, e)
            raise HTTPException(
                status_code=400,
                detail="Failed to extract text from file: {}".format(file.filename)
            )

        # Validate extracted text
        if not text or len(text.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="File contains insufficient text or is unreadable: {}".format(file.filename)
            )

        cv_file_key = None
        if os.getenv("ENV") != "test":
            try:
                from services.storage_service import upload_original_cv
                cv_file_key = upload_original_cv(
                    contents,
                    str(recruiter.id),
                    content_type=file.content_type or "application/octet-stream",
                    filename=file.filename,
                )
            except Exception as e:
                logger.info("batch_upload: original file storage skipped for %s error=%s", file.filename, e)

        cv_list.append({
            "filename": file.filename,
            "cv_file_name": file.filename,
            "cv_file_type": filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else "txt",
            "cv_file_key": cv_file_key,
            "text": text[:100_000]  # Cap at 100k chars
        })

    if not cv_list:
        raise HTTPException(
            status_code=400,
            detail="No valid CVs could be extracted from uploaded files"
        )

    # Check organization credits
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=500,
            detail="Organization not found (internal error)"
        )

    requested_cv_count = len(cv_list)
    available_credits = org.cv_credit_limit - org.monthly_usage
    
    if available_credits < requested_cv_count:
        logger.warning(
            "batch_upload: insufficient_credits org_id=%s available=%d requested=%d",
            org_id, available_credits, requested_cv_count
        )
        raise HTTPException(
            status_code=429,
            detail="Insufficient credits. You need {} CVs analyzed but only have {} credits remaining this month.".format(
                requested_cv_count, available_credits
            )
        )
    _billable_usage(db, recruiter, "recruiter-batch-upload", response=response)

    # Deduct credits and queue batch task
    org.monthly_usage += requested_cv_count
    db.add(org)
    db.commit()

    try:
        task = batch_recruiter_task.delay(
            cv_list=cv_list,
            job_id=job.id,
            job_description=job.description,
            org_id=org_id,
            recruiter_id=recruiter.id,
        )
        
        logger.info(
            "batch_upload: queued task_id=%s org_id=%s job_id=%d cv_count=%d",
            task.id, org_id, job.id, len(cv_list)
        )
        
        return {
            "task_id": task.id,
            "count": len(cv_list),
            "message": "Batch processing started for {} CVs".format(len(cv_list)),
            "job_id": job.id,
        }
    except Exception as e:
        # Rollback credit deduction on task queuing failure
        org.monthly_usage -= requested_cv_count
        db.add(org)
        db.commit()
        logger.error("batch_upload: task_queueing_failed org_id=%s error=%s", org_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to queue batch processing job"
        )


_IN_MEMORY_CACHE = {}


def _get_cache(key: str) -> Any | None:
    client = redis_rate_client()
    if client:
        try:
            val = client.get(key)
            if val:
                return json.loads(val)
            return None
        except Exception as e:
            logger.warning("Redis cache get failed, using fallback: %s", e)

    if key in _IN_MEMORY_CACHE:
        expire, val = _IN_MEMORY_CACHE[key]
        if time.time() < expire:
            return val
        else:
            del _IN_MEMORY_CACHE[key]
    return None


def _set_cache(key: str, val: Any, ttl: int = 300) -> None:
    client = redis_rate_client()
    if client:
        try:
            client.setex(key, ttl, json.dumps(val))
            if key in _IN_MEMORY_CACHE:
                del _IN_MEMORY_CACHE[key]
            return
        except Exception as e:
            logger.warning("Redis cache set failed, using fallback: %s", e)

    _IN_MEMORY_CACHE[key] = (time.time() + ttl, val)


def _delete_cache(key: str) -> None:
    client = redis_rate_client()
    if client:
        try:
            client.delete(key)
        except Exception as e:
            logger.warning("Redis cache delete failed: %s", e)
    if key in _IN_MEMORY_CACHE:
        del _IN_MEMORY_CACHE[key]


def _get_jobs_cache_key(org_id: int, limit: int, offset: int) -> str:
    version = _get_cache(f"recruiter_jobs_version:{org_id}")
    if not version:
        version = str(time.time())
        _set_cache(f"recruiter_jobs_version:{org_id}", version, ttl=86400)
    return f"recruiter_jobs:{org_id}:{version}:{limit}:{offset}"


def _invalidate_jobs_cache(org_id: int) -> None:
    _delete_cache(f"recruiter_jobs_version:{org_id}")


@router.post("/jobs")
def recruiter_create_job(body: RecruiterJobCreate, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")

    job = _rc_create_job(db, org_id, recruiter.id, body.title.strip(), body.description.strip())
    _invalidate_jobs_cache(org_id)
    return {"id": job.id, "title": job.title, "created_at": str(job.created_at)}


@router.get("/jobs")
def recruiter_list_jobs(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
) -> JobsResponse:
    """
    List all job positions for recruiter's organization with pagination.
    
    **Parameters:**
    - `limit`: Number of records to return (1-1000, default 20)
    - `offset`: Starting position for pagination (default 0)
    
    **Returns:**
    - List of job positions with pagination metadata
    
    **Raises:**
    - 400: Recruiter has no organization
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    cache_key = _get_jobs_cache_key(org_id, limit, offset)
    cached_data = _get_cache(cache_key)
    if cached_data:
        return JobsResponse(**cached_data)

    if os.getenv("STORAGE_BACKEND") == "local":
        existing = db.query(RecruiterJob).filter(RecruiterJob.organization_id == org_id).first()
        if not existing:
            demo_job = RecruiterJob(
                organization_id=org_id,
                title="Yazılım Geliştirici - Enterprise Demo",
                description="Bu, lokal kurulumu test etmeniz için otomatik oluşturulmuş bir demo ilanıdır.",
                requirements="Python, React, SQL",
                lang="tr",
            )
            db.add(demo_job)
            db.commit()
            db.refresh(demo_job)

    # Get total count
    total_count = db.query(RecruiterJob).filter(RecruiterJob.organization_id == org_id).count()
    
    # Get paginated jobs
    jobs = (
        db.query(RecruiterJob)
        .filter(RecruiterJob.organization_id == org_id)
        .order_by(RecruiterJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    job_list = [
        JobResponse(
            id=j.id,
            title=j.title,
            description=j.description[:500] if j.description else "",  # Increased from 200 to 500
            created_at=str(j.created_at),
        )
        for j in jobs
    ]

    pagination = PaginationMeta(
        total=total_count,
        limit=limit,
        offset=offset,
        hasMore=(offset + limit) < total_count
    )

    response_data = JobsResponse(jobs=job_list, total=total_count, pagination=pagination)
    _set_cache(cache_key, response_data.dict(), ttl=300)
    return response_data


@_get_limiter().limit("120/hour")
@router.post("/dashboard/rank")
def recruiter_dashboard_rank(
    body: RecruiterRankRequest,
    response: Response,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
):
    if not body.cv_texts:
        raise HTTPException(status_code=400, detail="At least one CV is required")
    if len(body.cv_texts) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 CVs")
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is required")
    _billable_usage(db, recruiter, "recruiter-dashboard-rank", response=response)

    analyses = []
    for item in body.cv_texts:
        cv_text = item.get("cv_text", "")
        if not cv_text.strip():
            continue

        autofix = _main().auto_fix_cv_text(
            cv_text=cv_text,
            job_description=body.job_description,
            lang=body.lang,
            use_ai=False,
            mode="safe",
        )
        normalized_text = autofix.get("optimized_cv_text") or cv_text
        result = _pipeline(normalized_text, body.job_description, lang=body.lang)
        result["candidate_name"] = item.get("name", "")
        result["candidate_email"] = item.get("email", "")
        result["cv_text"] = normalized_text
        result["original_cv_text"] = cv_text
        result["builder_payload"] = autofix.get("builder_payload") or {}
        result["file_name"] = item.get("file_name", "")
        analyses.append(result)

    ranked = _rc_rank(analyses)
    for i, analysis in enumerate(analyses):
        if i < len(ranked):
            ranked[i]["analysis"] = _rc_sw(analysis)

    return {
        "total": len(ranked),
        "ranking": ranked,
        "job_description_quality": (analyses[0].get("job_description_quality") if analyses else {}),
        "score_version": (analyses[0].get("score_version") if analyses else ""),
        "warnings": sorted({
            str(w).strip()
            for analysis in analyses
            for w in (analysis.get("warnings") or [])
            if str(w).strip()
        }),
    }


@router.post("/dashboard/preview")
def recruiter_dashboard_preview(
    body: RecruiterPreviewRequest,
    response: Response,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    if not body.cv_text.strip():
        raise HTTPException(status_code=400, detail="CV text is required")
    _billable_usage(db, recruiter, "recruiter-dashboard-preview", response=response)

    result = _pipeline(body.cv_text, body.job_description, lang=body.lang)
    result["candidate_name"] = body.candidate_name
    result["candidate_email"] = body.candidate_email

    preview = _rc_preview(result)
    sw = _rc_sw(result)

    return {"preview": preview, "analysis": sw, "variables": _rc_vars(result)}


@router.post("/dashboard/action")
def recruiter_dashboard_action(body: RecruiterActionRequest, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    stage = str(body.action or "").strip().lower()
    if stage not in _ALLOWED_CANDIDATE_STAGES:
        raise HTTPException(status_code=400, detail=f"action must be one of {', '.join(sorted(_ALLOWED_CANDIDATE_STAGES))}")

    final_score = body.final_score
    ats_score = body.ats_score

    if final_score is None and body.cv_text:
        try:
            job = db.query(RecruiterJob).filter(RecruiterJob.id == body.job_id).first()
            jd = job.description if job else ""
            result = _pipeline(body.cv_text, jd)
            final_score = float(result.get("final_score") or 0)
            ats_score = float(result.get("ats_score") or 0)
        except Exception:
            pass

    record = _rc_save_action(
        db=db,
        org_id=org_id,
        job_id=body.job_id,
        recruiter_id=recruiter.id,
        candidate_name=body.candidate_name,
        candidate_email=body.candidate_email,
        cv_text=body.cv_text,
        final_score=final_score,
        ats_score=ats_score,
        action=stage,
        analysis_snapshot=body.analysis_snapshot,
    )

    response_data = {
        "id": record.id,
        "action": record.action,
        "stage": record.action,
        "candidate_name": record.candidate_name,
        "final_score": record.final_score,
        "ats_score": record.ats_score,
    }

    if stage == "accepted" and body.template_id:
        tpl = _rc_get_tpl(db, body.template_id, org_id)
        if tpl:
            variables = {"name": body.candidate_name, "email": body.candidate_email or ""}
            rendered = _rc_render(tpl.body, tpl.subject, variables)
            response_data["email_preview"] = rendered

    return response_data


@router.get("/dashboard/actions/{job_id}")
def recruiter_dashboard_actions(job_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    actions = _rc_get_actions(db, job_id, org_id)
    return {
        "actions": [_serialize_action(a) for a in actions]
    }


@router.put("/dashboard/actions/{action_id}/stage")
def recruiter_update_action_stage(
    action_id: int,
    body: RecruiterStageUpdateRequest,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    stage = str(body.stage or "").strip().lower()
    if stage not in _ALLOWED_CANDIDATE_STAGES:
        raise HTTPException(status_code=400, detail=f"stage must be one of {', '.join(sorted(_ALLOWED_CANDIDATE_STAGES))}")

    record = (
        db.query(CandidateAction)
        .filter(CandidateAction.id == action_id, CandidateAction.organization_id == org_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Candidate action not found")

    record.action = stage
    if body.notes is not None:
        record.notes = str(body.notes or "")[:2000]
    db.add(record)
    db.commit()
    db.refresh(record)
    _log_event("candidate_stage_updated", action_id=record.id, stage=stage, recruiter_id=recruiter.id)
    return {"action": _serialize_action(record)}


@router.get("/pipeline/{job_id}")
def recruiter_pipeline(job_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    actions = _rc_get_actions(db, job_id, org_id)
    grouped = {stage: [] for stage in ("pending", "shortlist", "interview", "offer", "accepted", "rejected", "withdrawn")}
    for action in actions:
        stage = str(action.action or "pending").lower()
        grouped.setdefault(stage, []).append(_serialize_action(action))

    return {
        "job_id": job_id,
        "stages": [
            {"stage": stage, "count": len(items), "actions": items}
            for stage, items in grouped.items()
        ],
    }


@router.get("/report/{job_id}")
def recruiter_batch_report(job_id: int, format: str = Query("xlsx", pattern="^(xlsx|csv)$"), db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    actions = _rc_get_actions(db, job_id, org_id)
    if not actions:
        raise HTTPException(status_code=404, detail="No candidate analyses found for this job")

    report_data = []
    for action in actions:
        snapshot = {}
        if action.analysis_snapshot:
            try:
                snapshot = json.loads(action.analysis_snapshot)
            except Exception:
                pass
        report_data.append(
            {
                "candidate_name": action.candidate_name,
                "candidate_email": action.candidate_email,
                "ats_score": action.ats_score,
                "final_score": action.final_score,
                **snapshot,
            }
        )

    file_content = generate_recruiter_report(report_data, format=format)
    filename = f"Batch_Report_Job_{job_id}.{format}"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "text/csv"

    return StreamingResponse(
        file_content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/templates")
def recruiter_create_template(body: RecruiterEmailTemplateCreate, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    if body.template_type not in ("accept", "reject", "custom"):
        raise HTTPException(status_code=400, detail="template_type must be 'accept', 'reject', or 'custom'")

    tpl = _rc_create_tpl(
        db,
        org_id,
        recruiter.id,
        body.name.strip(),
        body.template_type,
        body.subject.strip(),
        body.body.strip(),
    )
    _delete_cache(f"recruiter_templates:{org_id}")
    return {"id": tpl.id, "name": tpl.name, "template_type": tpl.template_type}


@router.get("/templates")
def recruiter_list_templates(db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    cache_key = f"recruiter_templates:{org_id}"
    cached_data = _get_cache(cache_key)
    if cached_data:
        return cached_data

    templates = _rc_get_tpls(db, org_id)
    response_data = {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "template_type": t.template_type,
                "subject": t.subject,
                "body": t.body[:200],
                "created_at": str(t.created_at),
            }
            for t in templates
        ]
    }
    _set_cache(cache_key, response_data, ttl=300)
    return response_data


@router.delete("/templates/{template_id}")
def recruiter_delete_template(template_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    ok = _rc_del_tpl(db, template_id, org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")
    _delete_cache(f"recruiter_templates:{org_id}")
    return {"deleted": True}


@router.post("/templates/preview")
def recruiter_preview_template(body: RecruiterTemplatePreviewRequest, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    tpl = _rc_get_tpl(db, body.template_id, org_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    rendered = _rc_render(tpl.body, tpl.subject, body.variables)
    return rendered


@_get_limiter().limit("60/minute")
@router.post("/send-email")
def recruiter_send_email(
    body: RecruiterSendEmailRequest,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
) -> dict:
    """
    Send email to candidate using email template.
    
    **Parameters:**
    - `action_id` or `candidate_email`: Email recipient (one is required)
    - `template_id`: Email template to use
    - `sender_email`: Optional sender email (defaults to recruiter email)
    
    **Validation:**
    - Template must exist and belong to recruiter's organization
    - Candidate email must be valid
    - Action record must exist if action_id provided
    
    **Returns:**
    - Confirmation of sent email with subject and recipient
    
    **Raises:**
    - 400: Invalid email or missing required fields
    - 404: Template or action not found
    - 500: Email sending failed
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    candidate_name = body.candidate_name or ""
    candidate_email = body.candidate_email or ""
    action_record = None

    # Resolve candidate email from action record if provided
    if body.action_id:
        action_record = db.query(CandidateAction).filter(
            CandidateAction.id == body.action_id,
            CandidateAction.organization_id == org_id
        ).first()
        if not action_record:
            raise HTTPException(
                status_code=404,
                detail="Candidate action record not found"
            )
        candidate_name = action_record.candidate_name or candidate_name
        candidate_email = action_record.candidate_email or candidate_email

    # Validate candidate email
    if not candidate_email or "@" not in candidate_email or "." not in candidate_email:
        raise HTTPException(
            status_code=400,
            detail="Valid candidate email is required (either provide candidate_email or action_id with valid email)"
        )

    err = _rc_validate_email(candidate_name, candidate_email)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Load and validate template
    tpl = _rc_get_tpl(db, body.template_id, org_id)
    if not tpl:
        raise HTTPException(
            status_code=404,
            detail="Email template not found or you do not have permission to use it"
        )

    # Build template variables
    variables = {
        "name": candidate_name.strip() or "Candidate",
        "email": candidate_email.strip(),
    }
    
    if action_record and action_record.analysis_snapshot:
        try:
            snapshot = json.loads(action_record.analysis_snapshot)
            extra = _rc_vars(snapshot)
            for k, v in extra.items():
                if v and k not in variables:
                    variables[k] = v
        except Exception as e:
            logger.warning("email_send: failed_to_parse_analysis_snapshot action_id=%s error=%s", body.action_id, e)

    # Render template
    try:
        rendered = _rc_render(tpl.body, tpl.subject, variables)
    except Exception as e:
        logger.error("email_send: template_rendering_failed template_id=%s error=%s", body.template_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to render email template"
        )

    # Resolve sender email
    sender = (body.sender_email or "").strip()
    if not sender or "@" not in sender:
        sender = recruiter.email or ""
    
    if not sender:
        logger.warning("email_send: no_sender_email recruiter_id=%s", recruiter.id)
        raise HTTPException(
            status_code=400,
            detail="Sender email is required (set your email in profile or provide sender_email)"
        )

    # Send email
    try:
        _send_ok = _do_send_email(
            to_email=candidate_email,
            subject=rendered["subject"],
            body=rendered["body"],
            recruiter_email=sender,
        )
    except Exception as e:
        logger.error("email_send: send_failed to=%s sender=%s error=%s", candidate_email, sender, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to send email (check mail server configuration)"
        )

    if _send_ok:
        if action_record:
            try:
                _rc_mark_sent(db, action_record.id)
            except Exception as e:
                logger.warning("email_send: failed_to_mark_sent action_id=%s error=%s", action_record.id, e)
        
        logger.info("email_send: success to=%s template_id=%s", candidate_email, body.template_id)
        return {
            "sent": True,
            "to": candidate_email,
            "subject": rendered["subject"],
            "timestamp": str(datetime.utcnow()),
        }
    
    logger.warning("email_send: provider_returned_false to=%s", candidate_email)
    raise HTTPException(
        status_code=500,
        detail="Email provider returned failure (check email configuration and try again)"
    )


@router.get("/reminders")
def recruiter_list_reminders(
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
) -> dict:
    """
    List all reminders for recruiter's organization.
    
    **Returns:**
    - List of reminders sorted by event date (ascending)
    
    **Raises:**
    - 400: Recruiter has no organization
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    try:
        reminders = (
            db.query(Reminder)
            .filter(Reminder.organization_id == org_id)
            .order_by(Reminder.event_date.asc())
            .all()
        )
    except Exception as e:
        logger.error("reminders_list_failed org_id=%s error=%s", org_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve reminders"
        )

    return {
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "reminder_type": r.reminder_type,
                "event_date": str(r.event_date),
                "target_email": r.target_email,
                "is_active": r.is_active,
                "notified_3d_at": str(r.notified_3d_at) if r.notified_3d_at else None,
                "notified_1d_at": str(r.notified_1d_at) if r.notified_1d_at else None,
                "created_at": str(r.created_at),
                "updated_at": str(r.updated_at),
            }
            for r in reminders
        ],
        "total": len(reminders),
    }


@router.post("/reminders")
def recruiter_create_reminder(
    body: RecruiterReminderCreateRequest,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
) -> dict:
    """
    Create a new reminder for recruiter's organization.
    
    **Parameters:**
    - `title`: Reminder title (required)
    - `event_date`: Event date (ISO format, required)
    - `target_email`: Email to send reminder to (optional, defaults to recruiter email)
    - `reminder_type`: Type of reminder (optional)
    - `description`: Additional description (optional)
    - `is_active`: Whether reminder is active (default: true)
    
    **Validation:**
    - Event date must be in the future
    - Target email must be valid
    - Title cannot be empty
    
    **Returns:**
    - Created reminder with ID
    
    **Raises:**
    - 400: Invalid input data
    - 500: Database error
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    # Validate title
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=400,
            detail="Title is required"
        )
    
    if len(title) > 500:
        raise HTTPException(
            status_code=400,
            detail="Title too long (max 500 characters)"
        )

    # Validate event date
    try:
        if isinstance(body.event_date, str):
            event_date = datetime.fromisoformat(body.event_date.replace("Z", "+00:00"))
        else:
            event_date = body.event_date
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_date format: {e}. Use ISO format (e.g., 2026-05-15T10:00:00)"
        )
    
    now = datetime.utcnow()
    if event_date <= now:
        raise HTTPException(
            status_code=400,
            detail="Event date must be in the future"
        )

    # Validate target email
    target_email = body.target_email or recruiter.email or ""
    target_email = _validate_reminder_email(target_email)

    # Create reminder
    try:
        reminder = Reminder(
            organization_id=org_id,
            created_by=recruiter.id,
            title=title,
            description=(body.description or "").strip()[:1000],  # Cap description
            reminder_type=body.reminder_type.strip() or "other",
            target_email=target_email,
            event_date=event_date,
            is_active=body.is_active if body.is_active is not None else True,
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        
        logger.info("reminder_created reminder_id=%s org_id=%s event_date=%s", reminder.id, org_id, event_date)
        
        return {
            "id": reminder.id,
            "title": reminder.title,
            "event_date": str(reminder.event_date),
            "target_email": reminder.target_email,
            "is_active": reminder.is_active,
            "created_at": str(reminder.created_at),
        }
    except Exception as e:
        db.rollback()
        logger.error("reminder_create_failed org_id=%s error=%s", org_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to create reminder"
        )
    db.refresh(reminder)
    return {"id": reminder.id, "created_at": str(reminder.created_at)}


@router.put("/reminders/{reminder_id}")
def recruiter_update_reminder(reminder_id: int, body: RecruiterReminderUpdateRequest, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.organization_id == org_id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if body.title is not None:
        reminder.title = body.title.strip()
    if body.description is not None:
        reminder.description = body.description.strip()
    if body.reminder_type is not None:
        reminder.reminder_type = body.reminder_type.strip()
    if body.event_date is not None:
        reminder.event_date = body.event_date
    if body.target_email is not None:
        reminder.target_email = _validate_reminder_email(body.target_email)
    if body.is_active is not None:
        reminder.is_active = body.is_active

    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return {"updated": True}


@router.delete("/reminders/{reminder_id}")
def recruiter_delete_reminder(reminder_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.organization_id == org_id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    db.delete(reminder)
    db.commit()
    return {"deleted": True}


@router.post("/reminders/trigger")
def recruiter_trigger_reminders(db=Depends(get_db), recruiter=Depends(recruiter_required)):
    _process_due_reminders(db)
    return {"triggered": True}


@router.post("/scan-cv")
async def recruiter_scan_cv(
    request: Request,
    response: Response,
    images: list[UploadFile] = File(..., description="CV page images (JPEG/PNG)"),
    job_description: str = Form(""),
    lang: str = Form("en"),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Scan physical CV pages via camera images → OCR → ATS analysis → PDF.

    Accepts 1-10 images of CV pages, performs OCR text extraction,
    runs the full ATS analysis pipeline, and returns results + downloadable PDF.
    """
    from fastapi.responses import JSONResponse

    _ensure_not_expired(user)
    _main()._metric_request("scan-cv")

    # ── Validate images ──
    if len(images) > _main()._SCAN_MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {_main()._SCAN_MAX_FILES} images allowed")
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    all_image_bytes: list[bytes] = []
    for img_file in images:
        ct = (img_file.content_type or "").lower()
        if ct not in _main()._SCAN_ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image type: {ct}. Allowed: JPEG, PNG, WebP, BMP, TIFF",
            )
        contents = await img_file.read()
        if len(contents) > _main()._SCAN_MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"Image too large (max {_main()._SCAN_MAX_FILE_SIZE // 1_000_000}MB)")
        if len(contents) < 100:
            raise HTTPException(status_code=400, detail="Image file appears empty or corrupt")
        all_image_bytes.append(contents)

    # ── User / quota checks ──
    supabase_id = (user or {}).get("user_id", "mock-user") if _main().MOCK_SERVICES_ON else user.get("user_id")
    email = (user or {}).get("email", "dev@example.com") if _main().MOCK_SERVICES_ON else user.get("email")
    db_user = _get_user(db, str(supabase_id), email)
    _billable_usage(db, db_user, "recruiter-scan-cv", response=response)

    # ── OCR all pages ──
    page_texts = []
    for idx, img_bytes in enumerate(all_image_bytes):
        try:
            text = await _main().run_in_threadpool(_main()._ocr_extract_text, img_bytes, lang)
            page_texts.append(text)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OCR failed on page {idx + 1}: {e}")

    combined_text = "\n\n".join(page_texts)
    combined_text = _main()._normalize_ocr_text_for_cv_processing(combined_text)

    if not combined_text.strip() or len(combined_text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from the images. Please ensure the CV is clearly visible and well-lit.",
        )

    # ── CV detection ──
    from security.validators import is_probably_cv
    if not is_probably_cv(combined_text):
        raise HTTPException(
            status_code=400,
            detail="The scanned document does not appear to be a CV/resume. Please scan a valid CV.",
        )

    # ── Auto-detect language from OCR text if not specified ──
    if lang == "en":
        detected = _main().detect_language(combined_text)
        if detected != "en":
            lang = detected
            # Re-OCR with correct language for better accuracy
            page_texts_v2 = []
            for img_bytes in all_image_bytes:
                try:
                    text = await _main().run_in_threadpool(_main()._ocr_extract_text, img_bytes, lang)
                    page_texts_v2.append(text)
                except Exception:
                    pass
            if page_texts_v2 and len("\n".join(page_texts_v2).strip()) > len(combined_text.strip()) * 0.5:
                combined_text = "\n\n".join(page_texts_v2)

    # ── Run analysis pipeline (same as analyze-pdf) ──
    from renderers.blocks import fix_decomposed_diacritics
    combined_text = fix_decomposed_diacritics(combined_text)

    autofix = _main().auto_fix_cv_text(
        cv_text=combined_text,
        job_description=job_description,
        lang=lang,
        use_ai=False,
        mode="light_fix",
    )
    normalized_text = autofix.get("optimized_cv_text") or combined_text
    payload = autofix.get("builder_payload") or _main().structured_text_to_builder_payload(
        normalized_text,
        job_description=job_description,
        lang=lang,
    ).model_dump()

    result = _pipeline(normalized_text, job_description, lang)
    result["builder_payload"] = payload
    result["ocr_text"] = combined_text
    result["optimized_cv_text"] = normalized_text
    result["scan_pages"] = len(all_image_bytes)

    # ── Global ATS Benchmark ──
    try:
        from services.benchmark_service import (
            infer_profession as _bm_infer,
            record_ats_score as _bm_record,
            get_benchmark_comparison as _bm_compare,
        )
        _bm_prof = _bm_infer(
            job_title=_main()._extract_job_title_from_jd(job_description),
            experience_titles=[],
            skills=result.get("detected_skills") or [],
            db=db,
        )
        _bm_record(db, float(result.get("ats_score") or 0), _bm_prof)
        result["global_benchmark"] = _bm_compare(
            db, float(result.get("ats_score") or 0), _bm_prof,
        )
    except Exception:
        result["global_benchmark"] = None

    # ── Generate PDF ──
    try:
        pdf_bytes = await _main().run_in_threadpool(
            _main()._generate_scanned_pdf,
            payload,
            job_description,
            lang,
            normalized_text,
            all_image_bytes,
        )
        import base64
        result["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
        result["pdf_size"] = len(pdf_bytes)
    except Exception as e:
        logging.getLogger("app.scan").error("pdf_generation_failed error=%s", e)
        result["pdf_base64"] = None
        result["pdf_size"] = 0

    return result
