import time

try:
    from celery import Celery

    # Prefer Celery only if Redis broker/backend are reachable. If Redis is
    # not available (e.g. in CI), fall back to a synchronous LocalTask so the
    # app and tests don't fail at runtime trying to reconnect to Redis.
    redis_url = "redis://localhost:6379/0"
    _use_celery = True
    try:
        import redis as _redis_pkg

        _r = _redis_pkg.Redis.from_url(redis_url)
        _r.ping()
    except Exception:
        _use_celery = False

    if _use_celery:
        celery_app = Celery("cv_analyzer", broker=redis_url, backend=redis_url)

        @celery_app.task
        def analyze_pdf_task(cv_text, job_description):
            from services.ats_service import analyze_cv

            return analyze_cv(cv_text, job_description)

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

    def _analyze_pdf(cv_text, job_description):
        from services.ats_service import analyze_cv

        return analyze_cv(cv_text, job_description)

    analyze_pdf_task = LocalTask(_analyze_pdf)
