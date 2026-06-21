"""CV analysis and history endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

import ipaddress
import socket
import urllib.parse

from fastapi import APIRouter
from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403
from models import AsyncTaskOwner


router = APIRouter(tags=["analysis"])
_ANALYSIS_TASK_OWNERS: dict[str, dict[str, int | None]] = {}


_SUPPORTED_CV_UPLOAD_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def _upload_extension(filename: str | None) -> str:
    _, ext = os.path.splitext(str(filename or "").lower())
    return ext.lstrip(".")


def _extract_uploaded_cv_text(contents: bytes, file: UploadFile) -> tuple[str, bool, str]:
    """Validate and extract CV text from PDF, TXT, or DOCX uploads."""
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        from security.file_guard import validate_file_upload

        validate_file_upload(contents, file.filename, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ext = _upload_extension(file.filename)
    content_type = (file.content_type or "").lower()
    if content_type in _SUPPORTED_CV_UPLOAD_TYPES:
        file_type = _SUPPORTED_CV_UPLOAD_TYPES[content_type]
    elif ext in {"pdf", "txt", "docx"}:
        file_type = ext
    else:
        raise HTTPException(status_code=400, detail="Unsupported CV file type. Use PDF, TXT, or DOCX.")

    try:
        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise
    except Exception:
        if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail="Virus scanner error")

    if file_type == "pdf":
        text, truncated = _main_module()._extract_pdf_text(contents)
    elif file_type == "txt":
        text = contents.decode("utf-8", errors="ignore")
        truncated = len(text) > _MAX_PDF_EXTRACTED_CHARS
        text = text[:_MAX_PDF_EXTRACTED_CHARS]
    elif file_type == "docx":
        from utils.cv_processor import extract_docx_text_fast

        text = extract_docx_text_fast(contents)
        truncated = len(text) > _MAX_PDF_EXTRACTED_CHARS
        text = text[:_MAX_PDF_EXTRACTED_CHARS]
    else:
        raise HTTPException(status_code=400, detail="Unsupported CV file type. Use PDF, TXT, or DOCX.")

    from renderers.blocks import fix_decomposed_diacritics

    text = fix_decomposed_diacritics(str(text or "").strip())
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded CV")
    return text, bool(truncated), file_type


def _analysis_candidate_embedding_enabled() -> bool:
    return os.getenv("ANALYSIS_SAVE_CANDIDATE_EMBEDDINGS", "0").lower() in {
        "1",
        "true",
        "yes",
    }


def _maybe_get_analysis_candidate_embedding(text: str):
    if not _analysis_candidate_embedding_enabled():
        return None
    try:
        return get_embedding(text)
    except Exception:
        return None


@router.post("/api/v1/analyze")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PER_MIN}/minute")
def analyze(
    request: Request,
    response: Response,
    body: AnalyzeRequest,
    _: None = Depends(require_captcha),
    __: None = Depends(require_abuse_check),
    ___: None = Depends(require_user_global_rate),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Analyze CV against job description with JWT authentication.
    User must provide valid Supabase JWT token in Authorization header.
    """
    _ensure_not_expired(user)
    _metric_request("analyze")

    # In MOCK_SERVICES mode skip DB user creation and quota checks
    if _main_module().MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        mock_plan = _resolve_effective_plan(db, mock_db_user)
        mock_is_admin = _is_admin_user(mock_db_user)

        user_throttle = _consume_user_rate_limit(
            str(mock_user_id), _main_module().RATE_LIMIT_USER_ANALYZE_PER_MIN, "analyze"
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(user_throttle["remaining"])
            if not user_throttle["allowed"]:
                _metric_quota_hit("analyze", "user_per_minute")
                raise HTTPException(
                    status_code=429,
                    detail=(f"User rate limit exceeded ({user_throttle['limit']}/minute)"),
                )

        if not mock_is_admin and not _is_premium_plan(mock_plan):
            redis_quota = _consume_daily_quota(str(mock_user_id), limit=_resolve_daily_limit_for_plan(mock_plan))
            if redis_quota is not None:
                response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
                response.headers["X-Daily-Used"] = str(redis_quota["used"])
                response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
                if not redis_quota["allowed"]:
                    _metric_quota_hit("analyze", "user_daily")
                    raise HTTPException(
                        status_code=403,
                        detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                    )

        try:
            result = _main_module().run_pipeline(body.cv_text, body.job_description, body.lang)
        except Exception:
            _metric_error("analyze", "pipeline")
            raise

        # ── Global ATS Benchmark (mock path) ──
        try:
            from services.benchmark_service import (
                infer_profession as _bm_infer,
                record_ats_score as _bm_record,
                get_benchmark_comparison as _bm_compare,
            )

            mock_db = SessionLocal()
            try:
                _bm_prof = _bm_infer(
                    job_title=_extract_job_title_from_jd(body.job_description),
                    experience_titles=[],
                    skills=result.get("detected_skills") or [],
                    db=mock_db,
                )
                _bm_record(mock_db, float(result.get("ats_score") or 0), _bm_prof)
                result["global_benchmark"] = _bm_compare(
                    mock_db,
                    float(result.get("ats_score") or 0),
                    _bm_prof,
                )
            finally:
                mock_db.close()
        except Exception:
            result["global_benchmark"] = None

        result = _apply_plan_based_result_features(result, mock_plan)
        return result

    # Get or create user in database
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Additional per-user throttling (Redis) on top of IP rate limiting.
    user_throttle = _consume_user_rate_limit(
        db_user.supabase_id or str(db_user.id),
        _main_module().RATE_LIMIT_USER_ANALYZE_PER_MIN,
        "analyze",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(user_throttle["remaining"])
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(f"User rate limit exceeded ({user_throttle['limit']}/minute)"),
            )

    # reset daily/monthly counters if a new quota day/month has started
    quota_today = _quota_today_date()
    now_utc = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < quota_today:
        db_user.daily_usage = 0
        db_user.last_reset = now_utc
    if db_user.updated_at is None or (db_user.updated_at.year, db_user.updated_at.month) != (
        quota_today.year,
        quota_today.month,
    ):
        db_user.monthly_usage = 0
        db_user.updated_at = now_utc

    # enforce limits: individual users use their own quota; recruiters use org quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        # organization daily/monthly quota based on org.plan_type
        if org:
            org_daily_limit = ORG_PLAN_LIMITS_DAILY.get(_normalize_plan(org.plan_type), ORG_PLAN_LIMITS_DAILY["free"])
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_MONTHLY["free"]
            )
            if (org.daily_usage or 0) >= org_daily_limit:
                _metric_quota_hit("analyze", "org_daily")
                raise HTTPException(status_code=403, detail="Organization daily limit reached")
            if (org.monthly_usage or 0) >= org_monthly_limit:
                _metric_quota_hit("analyze", "org_monthly")
                raise HTTPException(status_code=403, detail="Organization monthly limit reached")
        redis_quota = _consume_daily_quota(
            db_user.supabase_id or str(db_user.id),
            limit=_resolve_daily_limit_for_plan(_resolve_effective_plan(db, db_user)),
        )
        _apply_daily_quota_headers(response, redis_quota)
        if redis_quota is not None and not redis_quota["allowed"]:
            _metric_quota_hit("analyze", "user_daily")
            raise HTTPException(
                status_code=403,
                detail=f"Daily limit reached ({redis_quota['limit']}/day)",
            )
    elif not _is_admin_user(db_user):
        # individual user quota using plan mapping
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_MONTHLY["free"]
        )

        redis_quota = _consume_daily_quota(
            db_user.supabase_id or str(db_user.id),
            limit=_resolve_daily_limit_for_plan(db_user.plan_type),
        )

        if redis_quota is not None:
            response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
            response.headers["X-Daily-Used"] = str(redis_quota["used"])
            response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
            if not redis_quota["allowed"]:
                _metric_quota_hit("analyze", "user_daily")
                raise HTTPException(
                    status_code=403,
                    detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                )
        elif (db_user.daily_usage or 0) >= user_daily_limit:
            _metric_quota_hit("analyze", "user_daily")
            raise HTTPException(status_code=403, detail="Daily limit reached")

        if (db_user.monthly_usage or 0) >= user_monthly_limit:
            _metric_quota_hit("analyze", "user_monthly")
            raise HTTPException(status_code=403, detail="Monthly limit reached")

    # Run analysis pipeline
    try:
        result = _main_module().run_pipeline(body.cv_text, body.job_description, body.lang)
        # Add AI recommendations
        score = result.get("final_score", 0)
        if score > 0.8:
            result["recommendations"] = [
                "Strong match! Prepare for behavioral and technical interviews.",
                "Highlight relevant projects and achievements in your CV.",
                "Practice common interview questions for this role.",
            ]
        elif score > 0.6:
            result["recommendations"] = [
                "Good potential. Tailor your CV to emphasize matching skills.",
                "Consider gaining more experience in key areas.",
                "Network with professionals in this field.",
            ]
        else:
            result["recommendations"] = [
                "Consider upskilling in required technologies.",
                "Seek entry-level positions or internships to build experience.",
                "Get feedback on your CV from mentors.",
            ]
    except Exception:
        _metric_error("analyze", "pipeline")
        raise

    # Save analysis record linked to user
    analysis_record = Analysis(
        user_id=db_user.id,
        organization_id=db_user.organization_id,
        similarity_score=float(result["final_score"]),
        interpretation=result["interpretation"],
        confidence=float(result["confidence"]),
        risk_level=result["risk_level"],
        domain_id=int(result["domain"]["domain_id"]),
        industry_id=int(result["industry"]["industry_id"]),
        specialization_id=int(result["specialization"]["id"]),
        job_title=_extract_job_title_from_jd(body.job_description),
        result={
            "final_score": result.get("final_score"),
            "semantic_score": result.get("semantic_score"),
            "keyword_score": result.get("keyword_score"),
            "skill_score": result.get("skill_score"),
            "experience_score": result.get("experience_score"),
            "ats_score": result.get("ats_score"),
            "job_description_quality": result.get("job_description_quality"),
            "warnings": result.get("warnings", []),
            "score_version": result.get("score_version"),
            "missing_skills": result.get("missing_skills", []),
            "recommendations": result.get("recommendations", []),
        },
    )

    try:
        # increment counters now that the request is allowed
        if db_user.role == "recruiter" and db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
            if org:
                org.daily_usage = (org.daily_usage or 0) + 1
                org.monthly_usage = (org.monthly_usage or 0) + 1
                db.add(org)
        elif not _is_admin_user(db_user):
            db_user.daily_usage = (db_user.daily_usage or 0) + 1
            db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
            db.add(db_user)

        # Track daily usage for history chart
        _record_usage_daily(db, db_user.id)

        db.add(analysis_record)
        db.commit()
        db.refresh(analysis_record)
    except Exception as e:
        db.rollback()
        _metric_error("analyze", "db_insert")
        print("DB INSERT ERROR:", str(e))
        raise

    # --- Auto-save candidate and its embedding for later semantic retrieval ---
    try:
        cv_embedding = _maybe_get_analysis_candidate_embedding(body.cv_text)
        cand = Candidate(
            organization_id=db_user.organization_id,
            cv_text=body.cv_text,
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)
        if cv_embedding:
            # Save embedding using helper (handles DB types)
            save_candidate_embedding(db, cand.id, cv_embedding)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    effective_plan = _resolve_effective_plan(db, db_user)

    try:
        result["benchmark"] = _build_analysis_benchmark(db, analysis_record)
    except Exception:
        result["benchmark"] = {
            "available": False,
            "reason": "benchmark_error",
        }

    # ── Global ATS Benchmark ──
    try:
        from services.benchmark_service import (
            infer_profession as _bm_infer,
            record_ats_score as _bm_record,
            get_benchmark_comparison as _bm_compare,
        )

        _bm_prof = _bm_infer(
            job_title=_extract_job_title_from_jd(body.job_description),
            experience_titles=[],
            skills=result.get("detected_skills") or [],
            db=db,
        )
        _bm_record(db, float(result.get("ats_score") or 0), _bm_prof)
        result["global_benchmark"] = _bm_compare(
            db,
            float(result.get("ats_score") or 0),
            _bm_prof,
        )
    except Exception:
        result["global_benchmark"] = None

    result = _apply_plan_based_result_features(result, effective_plan)

    # Include analysis record ID for frontend bookmarking
    result["analysis_id"] = analysis_record.id

    # Audit log for CV analysis events
    try:
        audit_log(
            "cv_analysis",
            source="text",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            analysis_id=getattr(analysis_record, "id", None),
            effective_plan=effective_plan,
        )
    except Exception:
        pass

    return result


class AnalyzeAsyncRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    lang: str = "en"


def _record_analysis_task_owner(task_id: str, db_user, db) -> None:
    if task_id:
        _ANALYSIS_TASK_OWNERS[str(task_id)] = {
            "user_id": int(getattr(db_user, "id", 0) or 0),
            "organization_id": getattr(db_user, "organization_id", None),
        }
        try:
            existing = db.query(AsyncTaskOwner).filter(AsyncTaskOwner.task_id == str(task_id)).first()
            if existing:
                existing.user_id = int(getattr(db_user, "id", 0) or 0)
                existing.organization_id = getattr(db_user, "organization_id", None)
                existing.task_type = "analysis"
                existing.expires_at = datetime.utcnow() + timedelta(hours=24)
            else:
                db.add(
                    AsyncTaskOwner(
                        task_id=str(task_id),
                        task_type="analysis",
                        user_id=int(getattr(db_user, "id", 0) or 0),
                        organization_id=getattr(db_user, "organization_id", None),
                        expires_at=datetime.utcnow() + timedelta(hours=24),
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("analysis task owner persistence failed task_id=%s", task_id)


def _require_analysis_task_owner(task_id: str, db_user, db) -> None:
    owner = None
    try:
        owner_row = db.query(AsyncTaskOwner).filter(AsyncTaskOwner.task_id == str(task_id)).first()
        if owner_row:
            if owner_row.expires_at and owner_row.expires_at < datetime.utcnow():
                raise HTTPException(status_code=404, detail="Analysis job not found")
            owner = {
                "user_id": int(owner_row.user_id or 0),
                "organization_id": owner_row.organization_id,
            }
    except HTTPException:
        raise
    except Exception:
        logger.exception("analysis task owner lookup failed task_id=%s", task_id)

    if owner is None:
        owner = _ANALYSIS_TASK_OWNERS.get(str(task_id))
    if owner is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if int(owner.get("user_id") or 0) != int(getattr(db_user, "id", 0) or 0):
        raise HTTPException(status_code=403, detail="Analysis job access denied")


def _validate_job_import_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="Import URL is too long")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Only http(s) import URLs are allowed")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Import URL credentials are not allowed")

    host = parsed.hostname.lower().strip(".")
    allowed_hosts = {
        item.strip().lower() for item in os.getenv("JOB_IMPORT_ALLOWED_HOSTS", "").split(",") if item.strip()
    }
    if allowed_hosts and host not in allowed_hosts:
        raise HTTPException(status_code=403, detail="Import URL host is not allowed")

    try:
        infos = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Import URL host could not be resolved")

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise HTTPException(status_code=400, detail="Import URL resolved to an invalid address")
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise HTTPException(status_code=403, detail="Import URL host is not allowed")

    return url


@router.post("/api/v1/analyze-async")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PER_MIN}/minute")
def analyze_async(
    request: Request,
    response: Response,
    body: AnalyzeAsyncRequest,
    _: None = Depends(require_captcha),
    __: None = Depends(require_abuse_check),
    ___: None = Depends(require_user_global_rate),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Asynchronous variant of /api/v1/analyze using Celery/LocalTask.

    Returns a job_id that can be polled via /api/v1/analysis/{job_id}.
    Quota and rate limits mirror the synchronous analyze endpoint.
    """

    _ensure_not_expired(user)
    _metric_request("analyze-async")

    # For async we still enforce the same per-user quotas as analyze
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    user_throttle = _consume_user_rate_limit(
        db_user.supabase_id or str(db_user.id),
        _main_module().RATE_LIMIT_USER_ANALYZE_PER_MIN,
        "analyze-async",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(user_throttle["remaining"])
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze-async", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(f"User rate limit exceeded ({user_throttle['limit']}/minute)"),
            )

    # Daily/monthly quota checks (reuse logic from analyze).
    quota_today = _quota_today_date()
    now_utc = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < quota_today:
        db_user.daily_usage = 0
        db_user.last_reset = now_utc
    if db_user.updated_at is None or (db_user.updated_at.year, db_user.updated_at.month) != (
        quota_today.year,
        quota_today.month,
    ):
        db_user.monthly_usage = 0
        db_user.updated_at = now_utc

    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        if org:
            org_daily_limit = ORG_PLAN_LIMITS_DAILY.get(_normalize_plan(org.plan_type), ORG_PLAN_LIMITS_DAILY["free"])
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_MONTHLY["free"]
            )
            if (org.daily_usage or 0) >= org_daily_limit:
                _metric_quota_hit("analyze-async", "org_daily")
                raise HTTPException(status_code=403, detail="Organization daily limit reached")
            if (org.monthly_usage or 0) >= org_monthly_limit:
                _metric_quota_hit("analyze-async", "org_monthly")
                raise HTTPException(status_code=403, detail="Organization monthly limit reached")
    elif not _is_admin_user(db_user):
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_MONTHLY["free"]
        )

        redis_quota = _consume_daily_quota(
            db_user.supabase_id or str(db_user.id),
            limit=_resolve_daily_limit_for_plan(db_user.plan_type),
        )

        if redis_quota is not None:
            response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
            response.headers["X-Daily-Used"] = str(redis_quota["used"])
            response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
            if not redis_quota["allowed"]:
                _metric_quota_hit("analyze-async", "user_daily")
                raise HTTPException(
                    status_code=403,
                    detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                )
        elif (db_user.daily_usage or 0) >= user_daily_limit:
            _metric_quota_hit("analyze-async", "user_daily")
            raise HTTPException(status_code=403, detail="Daily limit reached")

        if (db_user.monthly_usage or 0) >= user_monthly_limit:
            _metric_quota_hit("analyze-async", "user_monthly")
            raise HTTPException(status_code=403, detail="Monthly limit reached")

    # At this point the job is allowed; enqueue async analysis.
    if celery_app is None:
        # If Celery is not configured, fall back to synchronous pipeline
        # but still wrap response in a completed job shape for API
        result = _main_module().run_pipeline(body.cv_text, body.job_description, body.lang)
        return {"job_id": "local-sync", "status": "completed", "result": result}

    task = analyze_text_task.delay(body.cv_text, body.job_description, body.lang)
    _record_analysis_task_owner(str(task.id), db_user, db)
    return {"job_id": task.id, "status": "queued"}


# =====================================================
# PDF ANALYZE
# =====================================================


@router.post("/api/v1/analyze-pdf")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN}/minute")
async def analyze_pdf(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    job_description: str = Form(""),
    lang: str = Form("en"),
    _: None = Depends(require_captcha),
    __: None = Depends(require_abuse_check),
    ___: None = Depends(require_user_global_rate),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Analyze PDF CV against job description with JWT authentication.
    User must provide valid Supabase JWT token in Authorization header.
    """
    from fastapi import HTTPException

    _ensure_not_expired(user)
    _metric_request("analyze-pdf")
    try:
        UPLOADS_TOTAL.inc()
    except Exception:
        pass
    _check_cost_guard("upload", COST_UPLOAD_PER_DAY)
    _check_disk_safety()

    # Repeated request guard — reject identical uploads within dedup window
    _pdf_dedup_key = _make_dedup_key(request, (file.filename or "").encode()[:64])
    if _is_duplicate_request(_pdf_dedup_key):
        _guard_logger.warning("guard:dedup_request path=%s", request.url.path)
        raise HTTPException(status_code=429, detail="Duplicate request detected. Please wait.")

    # In MOCK_SERVICES mode skip DB user creation and quota checks
    # Use the normalized boolean `MOCK_SERVICES_ON` so values like "0" don't
    # accidentally enable mock behaviour (string "0" is truthy).
    if _main_module().MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        mock_plan = _resolve_effective_plan(db, mock_db_user)
        mock_is_admin = _is_admin_user(mock_db_user)

        user_throttle = _consume_user_rate_limit(
            str(mock_user_id), _main_module().RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN, "analyze-pdf"
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(user_throttle["remaining"])
            if not user_throttle["allowed"]:
                _metric_quota_hit("analyze-pdf", "user_per_minute")
                raise HTTPException(
                    status_code=429,
                    detail=(f"User rate limit exceeded ({user_throttle['limit']}/minute)"),
                )

        if not mock_is_admin and not _is_premium_plan(mock_plan):
            redis_quota = _consume_daily_quota(str(mock_user_id), limit=_resolve_daily_limit_for_plan(mock_plan))
            if redis_quota is not None:
                response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
                response.headers["X-Daily-Used"] = str(redis_quota["used"])
                response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
                if not redis_quota["allowed"]:
                    _metric_quota_hit("analyze-pdf", "user_daily")
                    raise HTTPException(
                        status_code=403,
                        detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                    )

        contents = await _read_upload_or_400(file)
        text, _pdf_truncated, _cv_file_type = _extract_uploaded_cv_text(contents, file)

        # ── CV detection: reject non-CV documents early ──
        from security.validators import is_probably_cv

        if not is_probably_cv(text):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not appear to be a CV/resume. Please upload a valid CV.",
            )

        # Analyze the extracted CV as submitted. Auto-fix is a separate,
        # explicit action; running it here rewrites fields before scoring.
        result = _main_module().run_pipeline(text, job_description, lang)
        result["cv_text"] = text
        result["cv_file_type"] = _cv_file_type
        if _pdf_truncated:
            result["truncated"] = True
            result["truncation_warning"] = (
                f"CV content exceeded {_MAX_PDF_EXTRACTED_CHARS:,} characters and was truncated. "
                "Analysis may be incomplete for very long documents."
            )

        # ── Global ATS Benchmark (mock PDF path) ──
        try:
            from services.benchmark_service import (
                infer_profession as _bm_infer,
                record_ats_score as _bm_record,
                get_benchmark_comparison as _bm_compare,
            )

            mock_db = SessionLocal()
            try:
                _bm_prof = _bm_infer(
                    job_title=_extract_job_title_from_jd(job_description),
                    experience_titles=[],
                    skills=result.get("detected_skills") or [],
                    db=mock_db,
                )
                _bm_record(mock_db, float(result.get("ats_score") or 0), _bm_prof)
                result["global_benchmark"] = _bm_compare(
                    mock_db,
                    float(result.get("ats_score") or 0),
                    _bm_prof,
                )
            finally:
                mock_db.close()
        except Exception:
            result["global_benchmark"] = None

        return result

    # Get or create user in database *before* running the pipeline
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Additional per-user throttling (Redis) on top of IP rate limiting.
    user_throttle = _consume_user_rate_limit(
        db_user.supabase_id or str(db_user.id),
        _main_module().RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN,
        "analyze-pdf",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(user_throttle["remaining"])
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze-pdf", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(f"User rate limit exceeded ({user_throttle['limit']}/minute)"),
            )

    # reset daily counter if a new day has started
    if db_user.last_reset is None or db_user.last_reset.date() < _quota_today_date():
        db_user.daily_usage = 0
        db_user.last_reset = datetime.utcnow()

    # enforce limits: individual users use personal quota; recruiters use org monthly quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        if org and org.plan_type == "free" and org.monthly_usage >= ORG_PLAN_LIMITS_MONTHLY["free"]:
            _metric_quota_hit("analyze-pdf", "org_monthly")
            raise HTTPException(status_code=429, detail="Organization monthly limit reached")
        redis_quota = _consume_daily_quota(
            db_user.supabase_id or str(db_user.id),
            limit=_resolve_daily_limit_for_plan(_resolve_effective_plan(db, db_user)),
        )
        _apply_daily_quota_headers(response, redis_quota)
        if redis_quota is not None and not redis_quota["allowed"]:
            _metric_quota_hit("analyze-pdf", "user_daily")
            raise HTTPException(
                status_code=403,
                detail=f"Daily limit reached ({redis_quota['limit']}/day)",
            )
        # usage increment BEFORE parse
        if org:
            org.daily_usage = (org.daily_usage or 0) + 1
            org.monthly_usage = (org.monthly_usage or 0) + 1
            db.add(org)
            db.commit()
    elif not _is_admin_user(db_user):
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            _normalize_plan(db_user.plan_type), USER_PLAN_LIMITS_MONTHLY["free"]
        )

        redis_quota = _consume_daily_quota(
            db_user.supabase_id or str(db_user.id),
            limit=_resolve_daily_limit_for_plan(db_user.plan_type),
        )

        if redis_quota is not None:
            response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
            response.headers["X-Daily-Used"] = str(redis_quota["used"])
            response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
            if not redis_quota["allowed"]:
                _metric_quota_hit("analyze-pdf", "user_daily")
                raise HTTPException(
                    status_code=403,
                    detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                )
        elif (db_user.daily_usage or 0) >= user_daily_limit:
            _metric_quota_hit("analyze-pdf", "user_daily")
            raise HTTPException(status_code=403, detail="Daily quota exceeded")

        if (db_user.monthly_usage or 0) >= user_monthly_limit:
            _metric_quota_hit("analyze-pdf", "user_monthly")
            raise HTTPException(status_code=403, detail="Monthly limit reached")

        # usage increment BEFORE parse
        db_user.daily_usage = (db_user.daily_usage or 0) + 1
        db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
        db.add(db_user)
        db.commit()

    # Only after quota check and increment, read and parse file
    contents = await _read_upload_or_400(file)
    text, _pdf_truncated, _cv_file_type = _extract_uploaded_cv_text(contents, file)
    from security.validators import is_probably_cv

    if not is_probably_cv(text):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a CV/resume. Please upload a valid CV.",
        )

    # Disable Zero Data Retention: Upload CV to storage
    from services.storage_service import upload_original_cv

    s3_key = None
    try:
        safe_user_id = db_user.supabase_id or str(db_user.id)
        s3_key = upload_original_cv(
            file_bytes=contents,
            user_id=safe_user_id,
            content_type=file.content_type or "application/pdf",
            filename=file.filename,
        )
    except Exception as e:
        logger.warning(f"Failed to upload CV to S3 in analyze-pdf: {e}")
    # Text was already extracted by _extract_uploaded_cv_text above.

    # Force extract → normalize pipeline before analysis task enqueue.
    # Queue the analysis job (or run synchronously in LocalTask fallback)
    # Keep scoring faithful to the uploaded CV. Auto-fix remains available
    # from /api/v1/cv/auto-fix when the user explicitly requests it.
    task = analyze_pdf_task.delay(text, job_description, lang)
    _record_analysis_task_owner(str(task.id), db_user, db)

    # If the task ran synchronously (LocalTask), the wrapper returns a
    # DummyResult with `.status` and `.result` attributes — return the
    # actual analysis result immediately in that case for a better UX.
    try:
        if getattr(task, "status", None) == "SUCCESS" and hasattr(task, "result"):
            result = dict(task.result) if task.result else {}
            result["cv_text"] = text
            result["cv_file_type"] = _cv_file_type
            # Save Analysis + Candidate records and compute benchmark
            try:
                analysis_record = Analysis(
                    user_id=db_user.id,
                    organization_id=db_user.organization_id,
                    similarity_score=float(result.get("final_score", 0)),
                    interpretation=result.get("interpretation", ""),
                    confidence=float(result.get("confidence", 0)),
                    risk_level=result.get("risk_level", ""),
                    domain_id=int((result.get("domain") or {}).get("domain_id", 0) or 0),
                    industry_id=int((result.get("industry") or {}).get("industry_id", 0) or 0),
                    specialization_id=int((result.get("specialization") or {}).get("id", 0) or 0),
                    job_title=_extract_job_title_from_jd(job_description),
                    result={
                        "final_score": result.get("final_score"),
                        "semantic_score": result.get("semantic_score"),
                        "keyword_score": result.get("keyword_score"),
                        "skill_score": result.get("skill_score"),
                        "experience_score": result.get("experience_score"),
                        "ats_score": result.get("ats_score"),
                        "job_description_quality": result.get("job_description_quality"),
                        "warnings": result.get("warnings", []),
                        "score_version": result.get("score_version"),
                        "missing_skills": result.get("missing_skills", []),
                        "recommendations": result.get("recommendations", []),
                    },
                )
                db.add(analysis_record)
                db.commit()
                db.refresh(analysis_record)

                cv_embedding = _maybe_get_analysis_candidate_embedding(text)
                cand = Candidate(
                    organization_id=db_user.organization_id,
                    cv_text=text,
                )
                db.add(cand)
                db.commit()
                db.refresh(cand)
                if cv_embedding:
                    save_candidate_embedding(db, cand.id, cv_embedding)

                # Link uploaded CV to user Data Center
                try:
                    if s3_key:
                        from models import CVVersion

                        cv_ver = CVVersion(
                            user_id=db_user.id,
                            organization_id=db_user.organization_id,
                            version_label="Analyzed CV",
                            source="analyze-pdf",
                            lang=lang,
                            cv_text=text,
                            job_description=job_description,
                            match_score=float(result.get("final_score", 0)),
                            original_s3_key=s3_key,
                        )
                        db.add(cv_ver)
                        db.commit()
                except Exception as e:
                    logger.warning(f"Failed to save CVVersion in analyze-pdf: {e}")
                    pass

                effective_plan = _resolve_effective_plan(db, db_user)
                result["benchmark"] = _build_analysis_benchmark(db, analysis_record)

                # ── Global ATS Benchmark (PDF real path) ──
                try:
                    from services.benchmark_service import (
                        infer_profession as _bm_infer,
                        record_ats_score as _bm_record,
                        get_benchmark_comparison as _bm_compare,
                    )

                    _bm_prof = _bm_infer(
                        job_title=_extract_job_title_from_jd(job_description),
                        experience_titles=[],
                        skills=result.get("detected_skills") or [],
                        db=db,
                    )
                    _bm_record(db, float(result.get("ats_score") or 0), _bm_prof)
                    result["global_benchmark"] = _bm_compare(
                        db,
                        float(result.get("ats_score") or 0),
                        _bm_prof,
                    )
                except Exception:
                    result["global_benchmark"] = None

                result = _apply_plan_based_result_features(result, effective_plan)
                try:
                    audit_log(
                        "cv_analysis",
                        source="pdf",
                        user_id=db_user.id,
                        organization_id=db_user.organization_id,
                        analysis_id=getattr(analysis_record, "id", None),
                        effective_plan=effective_plan,
                    )
                except Exception:
                    pass
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                result.setdefault("benchmark", {"available": False, "reason": "benchmark_error"})
            return result
    except Exception:
        pass

    return {"task_id": task.id, "status": "queued"}


@router.get("/api/v1/analysis/{job_id}")
def get_analysis_result(job_id: str, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Poll the status/result of an async analysis job.

    For LocalTask fallback, the original analyze-async endpoint will already
    have returned the result inline, but this endpoint remains useful when
    Celery/Redis are enabled.
    """
    _ensure_not_expired(user)
    db_user = get_or_create_user(db, user.get("user_id"), user.get("email"))
    _require_analysis_task_owner(job_id, db_user, db)

    if celery_app is None:
        raise HTTPException(status_code=503, detail="Async processing disabled")

    async_result = celery_app.AsyncResult(job_id)
    state = async_result.state
    if state in ("PENDING", "RECEIVED"):
        return {"status": "pending"}
    if state == "STARTED":
        return {"status": "running"}
    if state == "FAILURE":
        return {"status": "failed", "error": "Analysis failed"}

    # SUCCESS
    try:
        result = async_result.result
    except Exception as e:
        return {"status": "failed", "error": "Analysis failed"}
    return {"status": "completed", "result": result}


# =====================================================
# HISTORY
# =====================================================


@router.get("/api/v1/history")
def get_history(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    q: str = Query(None, description="Search query for job title or interpretation"),
    job_title: str = Query(None, description="Filter by job title"),
    from_date: str = Query(None, description="Filter from date (ISO format)"),
    to_date: str = Query(None, description="Filter to date (ISO format)"),
    min_score: float = Query(None, ge=0, le=1, description="Minimum similarity score"),
    max_score: float = Query(None, ge=0, le=1, description="Maximum similarity score"),
):
    """
    Get analysis history for authenticated user with JWT.
    Returns user's own analyses only, with pagination and advanced filters.
    """
    from datetime import datetime

    # Get or create user in database
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Build base query
    base_query = db.query(Analysis).filter(Analysis.user_id == db_user.id)

    # Apply filters
    if q:
        base_query = base_query.filter(Analysis.interpretation.ilike(f"%{q}%") | Analysis.job_title.ilike(f"%{q}%"))
    if job_title:
        base_query = base_query.filter(Analysis.job_title.ilike(f"%{job_title}%"))
    if from_date:
        try:
            base_query = base_query.filter(Analysis.created_at >= datetime.fromisoformat(from_date))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format")
    if to_date:
        try:
            base_query = base_query.filter(Analysis.created_at <= datetime.fromisoformat(to_date))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format")
    if min_score is not None:
        base_query = base_query.filter(Analysis.similarity_score >= min_score)
    if max_score is not None:
        base_query = base_query.filter(Analysis.similarity_score <= max_score)

    # Total count for pagination metadata
    total = base_query.count()

    # Return user's analysis records with pagination
    records = base_query.order_by(Analysis.id.desc()).offset(offset).limit(limit).all()

    return {"items": records, "total": total, "limit": limit, "offset": offset}


# ── Analytics Dashboard ────────────────────────────────────────


@router.get("/api/v1/analytics")
def get_analytics(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Get analytics data for user's analyses: totals, averages, top jobs.
    """
    from sqlalchemy import func
    from datetime import datetime, timedelta

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Total analyses
    total_analyses = db.query(Analysis).filter(Analysis.user_id == db_user.id).count()

    # Average similarity score
    avg_score = db.query(func.avg(Analysis.similarity_score)).filter(Analysis.user_id == db_user.id).scalar()
    avg_score = round(avg_score, 2) if avg_score else 0.0

    # Top job titles
    top_jobs = (
        db.query(Analysis.job_title, func.count(Analysis.id).label("count"))
        .filter(Analysis.user_id == db_user.id, Analysis.job_title.isnot(None))
        .group_by(Analysis.job_title)
        .order_by(func.count(Analysis.id).desc())
        .limit(5)
        .all()
    )
    top_jobs = [{"job_title": jt, "count": c} for jt, c in top_jobs]

    # Analyses in last 30 days
    cutoff = datetime.utcnow() - timedelta(days=30)
    recent_count = db.query(Analysis).filter(Analysis.user_id == db_user.id, Analysis.created_at >= cutoff).count()

    return {
        "total_analyses": total_analyses,
        "average_similarity_score": avg_score,
        "top_job_titles": top_jobs,
        "recent_analyses_30_days": recent_count,
    }


# ── Export and Reporting ───────────────────────────────────────


@router.get("/api/v1/analysis-trends")
def get_analysis_trends(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
    days: int = Query(90, ge=7, le=365),
):
    """Return daily score trend data for the authenticated user."""
    from sqlalchemy import func
    from datetime import timedelta

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("count"),
            func.avg(Analysis.similarity_score).label("average_score"),
            func.max(Analysis.similarity_score).label("best_score"),
        )
        .filter(Analysis.user_id == db_user.id, Analysis.created_at >= cutoff)
        .group_by(func.date(Analysis.created_at))
        .order_by(func.date(Analysis.created_at).asc())
        .all()
    )

    return {
        "days": [
            {
                "date": str(day),
                "count": int(count or 0),
                "average_score": round(float(average_score or 0), 2),
                "best_score": round(float(best_score or 0), 2),
            }
            for day, count, average_score, best_score in rows
        ]
    }


@router.get("/api/v1/export/analysis/{analysis_id}")
def export_analysis_pdf(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Export analysis as PDF.
    """
    from fpdf import FPDF
    from fastapi.responses import StreamingResponse

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"CV Analysis Report", ln=True, align="C")
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Job Title: {analysis.job_title or 'N/A'}", ln=True)
    pdf.cell(200, 10, txt=f"Similarity Score: {analysis.similarity_score:.2f}", ln=True)
    pdf.cell(200, 10, txt=f"Confidence: {analysis.confidence or 'N/A'}", ln=True)
    pdf.cell(200, 10, txt=f"Risk Level: {analysis.risk_level or 'N/A'}", ln=True)
    pdf.ln(10)
    pdf.multi_cell(0, 10, txt=f"Interpretation:\n{analysis.interpretation}")
    if analysis.result:
        pdf.ln(10)
        pdf.multi_cell(0, 10, txt=f"Details: {str(analysis.result)}")

    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode("latin-1", errors="replace")
    return StreamingResponse(
        iter([pdf_output]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.pdf"},
    )


# ── Integration Options ────────────────────────────────────────


@router.post("/api/v1/integrations/import-jobs")
def import_jobs(
    url: str = Form(...),  # Mock URL for job board
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Import jobs from external API (mock implementation).
    """
    import requests
    from models import Job

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        safe_url = _validate_job_import_url(url)
        response = requests.get(safe_url, timeout=10, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise HTTPException(status_code=400, detail="Import URL redirects are not allowed")
        response.raise_for_status()
        jobs_data = response.json()  # Assume list of {"title": str, "description": str}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch jobs: {str(e)}")

    imported = 0
    for job in jobs_data.get("jobs", []):
        new_job = Job(
            organization_id=db_user.organization_id,
            raw_text=job.get("description", ""),
        )
        db.add(new_job)
        imported += 1
    db.commit()

    return {"message": f"Imported {imported} jobs"}


# ── Collaboration Tools ────────────────────────────────────────


@router.post("/api/v1/share-legacy/{analysis_id}")
def share_analysis(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Generate a share token for public access to analysis.
    """
    import uuid

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    token = str(uuid.uuid4())
    share_tokens[token] = analysis_id

    return {"share_url": f"/api/v1/shared/{token}"}


@router.get("/api/v1/shared-legacy/{token}")
def view_shared_analysis(token: str, db=Depends(get_db)):
    """
    View shared analysis publicly.
    """
    analysis_id = share_tokens.get(token)
    if not analysis_id:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "job_title": analysis.job_title,
        "similarity_score": analysis.similarity_score,
        "interpretation": analysis.interpretation,
        "result": analysis.result,
    }


# ── Usage History (daily chart data) ────────────────────────────


@router.get("/api/v1/usage-history")
def get_usage_history(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
    days: int = Query(30, ge=7, le=90),
):
    """Return daily analysis counts for the last N days for usage chart."""
    from models import UsageDaily
    from datetime import timedelta

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(UsageDaily)
        .filter(UsageDaily.user_id == db_user.id, UsageDaily.date >= cutoff)
        .order_by(UsageDaily.date.asc())
        .all()
    )

    return {"days": [{"date": r.date.strftime("%Y-%m-%d"), "count": r.count} for r in rows]}


# ── Favorites CRUD ──────────────────────────────────────────────
