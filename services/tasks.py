import json
import os
import time

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
            """

            autoretry_for = (Exception,)
            retry_backoff = True
            max_retries = 3
            time_limit = 60
            soft_time_limit = 45

            def on_failure(self, exc, task_id, args, kwargs, einfo):
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

        @celery_app.task(bind=True, name="analyze_pdf_task", queue="pdf_processing")
        def analyze_pdf_task(self, cv_text, job_description, lang="en"):
            # Keep PDF and text analysis responses consistent.
            from main import run_pipeline

            return run_pipeline(cv_text, job_description, lang)

        @celery_app.task(bind=True, name="analyze_text_task", queue="ai_tasks")
        def analyze_text_task(self, cv_text, job_description, lang="en"):
            # Import locally to avoid hard dependency at module import time.
            from main import run_pipeline

            return run_pipeline(cv_text, job_description, lang)

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

        return run_pipeline(cv_text, job_description, lang)

    analyze_pdf_task = LocalTask(_analyze_pdf)

    def _analyze_text(cv_text, job_description, lang="en"):
        from main import run_pipeline

        return run_pipeline(cv_text, job_description, lang)

    analyze_text_task = LocalTask(_analyze_text)
