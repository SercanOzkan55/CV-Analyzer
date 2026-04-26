import json
import logging
import os
import time

_task_logger = logging.getLogger("celery.tasks")

try:
    from celery import Celery, Task
    from celery.exceptions import SoftTimeLimitExceeded

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
                    self.name, task_id, self.request.retries, self.max_retries, exc,
                )

            def on_failure(self, exc, task_id, args, kwargs, einfo):
                _task_logger.error(
                    "task:failed task=%s id=%s error=%s",
                    self.name, task_id, exc,
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
            worker_max_memory_per_child=512_000,   # 512 MB → recycle worker
            worker_max_tasks_per_child=200,        # recycle after 200 tasks
            task_default_rate_limit="30/m",         # max 30 tasks/min per worker
            task_acks_late=True,                    # ack after execution
            task_reject_on_worker_lost=True,        # re-queue if worker dies
            worker_prefetch_multiplier=1,           # one task at a time
            broker_connection_retry_on_startup=True,
            task_soft_time_limit=45,                # soft limit → SoftTimeLimitExceeded
            task_time_limit=60,                     # hard kill after 60s
            worker_hijack_root_logger=False,        # keep app logging config
        )

        @celery_app.task(bind=True, name="analyze_pdf_task", queue="pdf_processing")
        def analyze_pdf_task(self, cv_text, job_description, lang="en"):
            # Keep PDF and text analysis responses consistent.
            from main import run_pipeline
            from services.cv_autofix_service import auto_fix_cv_text

            autofix = auto_fix_cv_text(
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
                use_ai=False,
                mode="safe",
            )
            normalized_text = autofix.get("optimized_cv_text") or cv_text
            return run_pipeline(normalized_text, job_description, lang)

        @celery_app.task(bind=True, name="analyze_text_task", queue="ai_tasks")
        def analyze_text_task(self, cv_text, job_description, lang="en"):
            # Import locally to avoid hard dependency at module import time.
            from main import run_pipeline

            return run_pipeline(cv_text, job_description, lang)

        @celery_app.task(bind=True, name="batch_recruiter_task", queue="pdf_processing")
        def batch_recruiter_task(self, cv_list, job_id, job_description, org_id, recruiter_id):
            """Process multiple CVs, analyze against a job, and save results."""
            from main import run_pipeline
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
                    analysis = run_pipeline(normalized_text, job_description)
                    
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
                        analysis_snapshot=analysis
                    )
                    results.append({"id": action.id, "name": candidate_name, "status": "success"})
            finally:
                db.close()
            return results

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
                def __init__(self, res):
                    self.id = f"local-{int(time.time()*1000)}"
                    self.status = "SUCCESS"
                    self.result = res

            try:
                res = self.fn(*args, **kwargs)
            except Exception as e:
                res = e
            return DummyResult(res)

    def _analyze_pdf(cv_text, job_description, lang="en"):
        from main import run_pipeline
        from services.cv_autofix_service import auto_fix_cv_text

        autofix = auto_fix_cv_text(
            cv_text=cv_text,
            job_description=job_description,
            lang=lang,
            use_ai=False,
            mode="safe",
        )
        normalized_text = autofix.get("optimized_cv_text") or cv_text
        return run_pipeline(normalized_text, job_description, lang)

    analyze_pdf_task = LocalTask(_analyze_pdf)

    def _analyze_text(cv_text, job_description, lang="en"):
        from main import run_pipeline

        return run_pipeline(cv_text, job_description, lang)

    analyze_text_task = LocalTask(_analyze_text)

    def _batch_recruiter(cv_list, job_id, job_description, org_id, recruiter_id):
        # Synchronous fallback for local testing
        from main import run_pipeline
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
                analysis = run_pipeline(normalized_text, job_description)
                
                structured = extract_structured(cv_text)
                name = structured.get("full_name") or filename
                
                action = save_candidate_action(
                    db, org_id, job_id, recruiter_id, name,
                    analysis.get("candidate_email"), cv_text, 
                    analysis.get("final_score"), analysis.get("ats_score"), "pending",
                    analysis
                )
                results.append({"id": action.id, "name": name, "status": "success"})
        finally:
            db.close()
        return results

    batch_recruiter_task = LocalTask(_batch_recruiter)
