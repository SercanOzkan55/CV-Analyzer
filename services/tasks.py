from core.timeutils import utcnow
import json
import logging
import os
import time

from core.runtime_bridge import main_value

_task_logger = logging.getLogger("celery.tasks")


def _run_pipeline(cv_text, job_description, lang="en"):
    pipeline = main_value("run_pipeline")
    if pipeline is None:
        from services.pipeline_runtime import run_pipeline as pipeline
    return pipeline(cv_text, job_description, lang)


def persist_analysis_result(
    result: dict,
    *,
    user_id: int,
    organization_id: int | None,
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    source: str = "analyze-async",
    original_s3_key: str | None = None,
    db=None,
) -> dict:
    """Persist a completed worker result so async and sync flows stay aligned."""
    from database import SessionLocal
    from models import Analysis, Candidate, CVVersion, User
    from services.pipeline_runtime import _extract_job_title_from_jd
    from services.user_service import _apply_plan_based_result_features
    from core.quota import _record_usage_daily, _resolve_effective_plan

    owns_session = db is None
    session = db or SessionLocal()
    try:
        db_user = session.query(User).filter(User.id == int(user_id)).first()
        if db_user is None:
            raise RuntimeError("Analysis owner no longer exists")

        effective_plan = _resolve_effective_plan(session, db_user)
        result = _apply_plan_based_result_features(dict(result or {}), effective_plan)
        analysis_record = Analysis(
            user_id=db_user.id,
            organization_id=organization_id,
            similarity_score=float(result.get("final_score") or 0),
            interpretation=str(result.get("interpretation") or ""),
            confidence=float(result.get("confidence") or 0),
            risk_level=str(result.get("risk_level") or ""),
            domain_id=int((result.get("domain") or {}).get("domain_id") or 0),
            industry_id=int((result.get("industry") or {}).get("industry_id") or 0),
            specialization_id=int((result.get("specialization") or {}).get("id") or 0),
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
        session.add(analysis_record)
        _record_usage_daily(session, db_user.id)

        if organization_id is not None:
            session.add(
                Candidate(
                    organization_id=organization_id,
                    cv_text=cv_text,
                )
            )

        if source == "analyze-pdf" and original_s3_key:
            session.add(
                CVVersion(
                    user_id=db_user.id,
                    organization_id=organization_id,
                    version_label="Analyzed CV",
                    source=source,
                    lang=lang,
                    cv_text=cv_text,
                    job_description=job_description,
                    match_score=float(result.get("final_score") or 0),
                    original_s3_key=original_s3_key,
                )
            )

        session.commit()
        session.refresh(analysis_record)
        result["analysis_id"] = analysis_record.id
        result["effective_plan"] = effective_plan
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


try:
    from celery import Celery, Task

    # Prefer Celery only if Redis broker/backend are reachable. If Redis is
    # not available (e.g. in CI), fall back to a synchronous LocalTask so the
    # app and tests don't fail at runtime trying to reconnect to Redis.
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _use_celery = True
    try:
        import redis as _redis_pkg

        ping_timeout = float(os.getenv("REDIS_PING_TIMEOUT_SECONDS", "1.0") or "1.0")
        _r = _redis_pkg.Redis.from_url(
            redis_url,
            socket_connect_timeout=ping_timeout,
            socket_timeout=ping_timeout,
            retry_on_timeout=False,
        )
        _r.ping()
        try:
            _r.close()
        except Exception:
            pass
    except Exception:
        _use_celery = False

    if _use_celery:
        from database import SessionLocal
        from models import FailedTask

        class DBLoggingTask(Task):
            """Base Celery Task with sane defaults and dead-letter logging.

            - Retries up to 3 times with exponential backoff for exceptions
            - Enforces hard/soft time limits to prevent stuck CV parsing
            - On final failure, writes an entry to the FailedTask table
            - Logs retries and crashes for operational visibility
            """

            autoretry_for = (Exception,)
            retry_backoff = True
            max_retries = 3
            time_limit = 60
            soft_time_limit = 45

            def on_retry(self, exc, task_id, args, kwargs, einfo):
                _task_logger.warning(
                    "task:retry task=%s id=%s attempt=%d/%d error=%s",
                    self.name,
                    task_id,
                    self.request.retries,
                    self.max_retries,
                    exc,
                )

            def on_failure(self, exc, task_id, args, kwargs, einfo):
                _task_logger.error(
                    "task:failed task=%s id=%s error=%s",
                    self.name,
                    task_id,
                    exc,
                )
                try:
                    session = SessionLocal()
                    payload = None
                    try:
                        payload = json.dumps({"args": args, "kwargs": kwargs}, default=str)
                    except Exception:
                        payload = None
                    record = FailedTask(
                        task_name=self.name or type(self).__name__,
                        task_id=str(task_id),
                        payload=payload,
                        error=str(exc),
                    )
                    session.add(record)
                    session.commit()
                except Exception:
                    try:
                        session.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass

        celery_app = Celery(
            "cv_analyzer",
            broker=redis_url,
            backend=redis_url,
            task_default_queue="default",
        )
        celery_app.Task = DBLoggingTask

        # ── Worker safety limits ──
        celery_app.conf.update(
            worker_max_memory_per_child=512_000,  # 512 MB → recycle worker
            worker_max_tasks_per_child=200,  # recycle after 200 tasks
            task_default_rate_limit="30/m",  # max 30 tasks/min per worker
            task_acks_late=True,  # ack after execution
            task_reject_on_worker_lost=True,  # re-queue if worker dies
            worker_prefetch_multiplier=1,  # one task at a time
            broker_connection_retry_on_startup=True,
            task_soft_time_limit=45,  # soft limit → SoftTimeLimitExceeded
            task_time_limit=60,  # hard kill after 60s
            worker_hijack_root_logger=False,  # keep app logging config
            beat_schedule={
                "cleanup-expired-worker-claims": {
                    "task": "cleanup_expired_claims",
                    "schedule": 300.0,
                }
            },
        )

        @celery_app.task(bind=True, name="analyze_pdf_task", queue="pdf_processing")
        def analyze_pdf_task(
            self,
            cv_text,
            job_description,
            lang="en",
            user_id=None,
            organization_id=None,
            original_s3_key=None,
        ):
            # Analyze the uploaded/extracted CV faithfully. Field rewriting is
            # reserved for the explicit auto-fix endpoint.
            result = _run_pipeline(cv_text, job_description, lang)
            if user_id is not None:
                result = persist_analysis_result(
                    result,
                    user_id=user_id,
                    organization_id=organization_id,
                    cv_text=cv_text,
                    job_description=job_description,
                    lang=lang,
                    source="analyze-pdf",
                    original_s3_key=original_s3_key,
                )
            return result

        @celery_app.task(bind=True, name="analyze_text_task", queue="ai_tasks")
        def analyze_text_task(self, cv_text, job_description, lang="en", user_id=None, organization_id=None):
            result = _run_pipeline(cv_text, job_description, lang)
            if user_id is not None:
                result = persist_analysis_result(
                    result,
                    user_id=user_id,
                    organization_id=organization_id,
                    cv_text=cv_text,
                    job_description=job_description,
                    lang=lang,
                )
            return result

        @celery_app.task(bind=True, name="batch_recruiter_task", queue="pdf_processing")
        def batch_recruiter_task(self, cv_list, job_id, job_description, org_id, recruiter_id):
            """Process multiple CVs, analyze against a job, and save results."""
            from services.cv_autofix_service import auto_fix_cv_text
            from services.recruiter_service import save_candidate_action
            from agents.extract_agent import extract_structured
            from database import SessionLocal

            db = SessionLocal()
            results = []
            try:
                for cv_data in cv_list:
                    cv_text = cv_data.get("text", "")
                    filename = cv_data.get("filename", "unknown.pdf")
                    candidate_name = cv_data.get("candidate_name")

                    # 1. Autofix & Structure
                    autofix = auto_fix_cv_text(cv_text=cv_text, job_description=job_description, use_ai=False)
                    normalized_text = autofix.get("optimized_cv_text") or cv_text

                    # 2. Match Pipeline
                    analysis = _run_pipeline(normalized_text, job_description)

                    # 3. Extract metadata if name is missing
                    if not candidate_name:
                        structured = extract_structured(cv_text)
                        candidate_name = structured.get("full_name") or filename

                    # 4. Save to Recruiter Dashboard
                    action = save_candidate_action(
                        db=db,
                        org_id=org_id,
                        job_id=job_id,
                        recruiter_id=recruiter_id,
                        candidate_name=candidate_name,
                        candidate_email=analysis.get("candidate_email"),
                        cv_text=cv_text,
                        final_score=analysis.get("final_score"),
                        ats_score=analysis.get("ats_score"),
                        action="pending",
                        analysis_snapshot=analysis,
                        cv_file_key=cv_data.get("cv_file_key") or cv_data.get("file_key"),
                        cv_file_name=cv_data.get("cv_file_name") or filename,
                        cv_file_type=cv_data.get("cv_file_type") or cv_data.get("file_type"),
                    )
                    results.append({"id": action.id, "name": candidate_name, "status": "success"})
            finally:
                db.close()
            return results

        @celery_app.task(name="cleanup_expired_claims")
        def cleanup_expired_claims():
            """Automatically clean up expired claims and restore worker quotas."""
            from database import SessionLocal
            from models import WorkerClaim, WorkerKey, QuotaEvent

            db = SessionLocal()
            try:
                now = utcnow()
                expired_claims = (
                    db.query(WorkerClaim)
                    .filter(WorkerClaim.status == "claimed", WorkerClaim.claim_expires_at < now)
                    .with_for_update(skip_locked=True)
                    .all()
                )

                released = 0
                for claim in expired_claims:
                    wk = db.query(WorkerKey).filter(WorkerKey.id == claim.worker_key_id).with_for_update().first()
                    if wk:
                        wk.quota_reserved = max(0, int(wk.quota_reserved or 0) - 1)
                        db.add(
                            QuotaEvent(
                                worker_key_id=wk.id,
                                organization_id=claim.organization_id,
                                job_id=claim.job_id,
                                cv_id=claim.cv_id,
                                event_type="expired",
                                amount=1,
                                metadata_={"claim_id": claim.id},
                            )
                        )
                    claim.status = "expired"
                    released += 1
                if released > 0:
                    db.commit()
                    _task_logger.info(f"Released {released} expired worker claims.")
            except Exception as e:
                db.rollback()
                _task_logger.error(f"Failed to cleanup expired worker claims: {str(e)}")
            finally:
                db.close()

    else:
        raise RuntimeError("Redis unavailable; fallback to LocalTask")
except Exception:
    # If Celery/Redis aren't available, provide a local synchronous fallback
    # that exposes a `.delay()` API used by the app.
    celery_app = None

    class LocalTask:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args, **kwargs):
            return self.fn(*args, **kwargs)

        def delay(self, *args, **kwargs):
            class DummyResult:
                def __init__(self, res, status="SUCCESS"):
                    self.id = f"local-{int(time.time() * 1000)}"
                    self.status = status
                    self.result = res

            try:
                res = self.fn(*args, **kwargs)
                return DummyResult(res)
            except Exception as e:
                return DummyResult(e, status="FAILURE")

    def _analyze_pdf(
        cv_text,
        job_description,
        lang="en",
        user_id=None,
        organization_id=None,
        original_s3_key=None,
    ):
        # Analyze the uploaded/extracted CV faithfully. Field rewriting is
        # reserved for the explicit auto-fix endpoint.
        result = _run_pipeline(cv_text, job_description, lang)
        if user_id is not None:
            result = persist_analysis_result(
                result,
                user_id=user_id,
                organization_id=organization_id,
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
                source="analyze-pdf",
                original_s3_key=original_s3_key,
            )
        return result

    analyze_pdf_task = LocalTask(_analyze_pdf)

    def _analyze_text(cv_text, job_description, lang="en", user_id=None, organization_id=None):
        result = _run_pipeline(cv_text, job_description, lang)
        if user_id is not None:
            result = persist_analysis_result(
                result,
                user_id=user_id,
                organization_id=organization_id,
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
            )
        return result

    analyze_text_task = LocalTask(_analyze_text)

    def _batch_recruiter(cv_list, job_id, job_description, org_id, recruiter_id):
        # Synchronous fallback for local testing
        from services.cv_autofix_service import auto_fix_cv_text
        from services.recruiter_service import save_candidate_action
        from agents.extract_agent import extract_structured
        from database import SessionLocal

        db = SessionLocal()
        results = []
        try:
            for cv_data in cv_list:
                cv_text = cv_data.get("text", "")
                filename = cv_data.get("filename", "unknown.pdf")
                autofix = auto_fix_cv_text(cv_text=cv_text, job_description=job_description)
                normalized_text = autofix.get("optimized_cv_text") or cv_text
                analysis = _run_pipeline(normalized_text, job_description)

                structured = extract_structured(cv_text)
                name = structured.get("full_name") or filename

                action = save_candidate_action(
                    db,
                    org_id,
                    job_id,
                    recruiter_id,
                    name,
                    analysis.get("candidate_email"),
                    cv_text,
                    analysis.get("final_score"),
                    analysis.get("ats_score"),
                    "pending",
                    analysis,
                    cv_file_key=cv_data.get("cv_file_key") or cv_data.get("file_key"),
                    cv_file_name=cv_data.get("cv_file_name") or filename,
                    cv_file_type=cv_data.get("cv_file_type") or cv_data.get("file_type"),
                )
                results.append({"id": action.id, "name": name, "status": "success"})
        finally:
            db.close()
        return results

    batch_recruiter_task = LocalTask(_batch_recruiter)

    def _cleanup_expired_claims():
        from database import SessionLocal
        from models import WorkerClaim, WorkerKey, QuotaEvent

        db = SessionLocal()
        try:
            now = utcnow()
            expired_claims = (
                db.query(WorkerClaim).filter(WorkerClaim.status == "claimed", WorkerClaim.claim_expires_at < now).all()
            )

            released = 0
            for claim in expired_claims:
                wk = db.query(WorkerKey).filter(WorkerKey.id == claim.worker_key_id).first()
                if wk:
                    wk.quota_reserved = max(0, int(wk.quota_reserved or 0) - 1)
                    db.add(
                        QuotaEvent(
                            worker_key_id=wk.id,
                            organization_id=claim.organization_id,
                            job_id=claim.job_id,
                            cv_id=claim.cv_id,
                            event_type="expired",
                            amount=1,
                            metadata_={"claim_id": claim.id},
                        )
                    )
                claim.status = "expired"
                released += 1
            if released > 0:
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    cleanup_expired_claims = LocalTask(_cleanup_expired_claims)
