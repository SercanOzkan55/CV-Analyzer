"""System, health, and admin-control endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move shared helpers into dedicated services.
"""

from fastapi import APIRouter
from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403


router = APIRouter(tags=["system"])

@router.get("/")
def read_root():
    """Root endpoint for health checks and basic landing."""
    return JSONResponse(
        content={
            "status": "online",
            "mode": "private" if os.getenv("STORAGE_BACKEND") == "local" else "cloud",
            "message": "CV Analyzer API is running. Access frontend via http://localhost:5173 or /static"
        }
    )


@router.get("/api/v1/demo/sample-workspace")
def demo_sample_workspace():
    """Public, synthetic demo data for UI previews without real user CVs."""
    return {
        "candidate": {
            "name": "Demo Candidate",
            "role": "Backend Developer",
            "email": "demo@example.com",
            "cv_text": (
                "Demo Candidate\nBackend Developer\nSummary\n"
                "Python and API-focused developer with measurable project outcomes.\n"
                "Experience\nBuilt FastAPI services, improved query latency by 35%.\n"
                "Education\nBSc Computer Engineering\nSkills\nPython, FastAPI, SQL, Docker\nLanguages\nEnglish"
            ),
        },
        "job_description": (
            "Backend Developer role requiring Python, FastAPI, SQL, Docker, API design, "
            "testing, and clear communication with product teams."
        ),
        "pipeline": [
            {"stage": "shortlist", "count": 4},
            {"stage": "interview", "count": 2},
            {"stage": "offer", "count": 1},
        ],
        "reminder": {
            "title": "Backend Developer interview",
            "days_left": 1,
            "target_email": "demo@example.com",
        },
    }


# ── Production guard middleware ──────────────────────────────────────────


@router.get("/api/v1/fonts")
def list_fonts():
    """Return available font families for CV generation."""
    from renderers.theme import ALLOWED_FONTS, DEFAULT_FONT
    return {
        "fonts": [
            {"id": fid, "label": label}
            for fid, label in ALLOWED_FONTS.items()
        ],
        "default": DEFAULT_FONT,
    }


@router.get("/health")
def health_check(request: Request = None):
    # ── Ops: Blue/green — health must fail until startup complete ──
    if not _main_module()._app_ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "detail": "Server not ready"},
        )

    # Update uptime gauge on every health/metrics scrape
    try:
        UPTIME_SECONDS.set(time.time() - _APP_START_TIME)
    except Exception:
        pass

    if _main_module().MOCK_SERVICES_ON:
        return {"status": "ok", "mode": "mock"}

    checks: dict = {}

    # Database
    _db_t = time.time()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
        _cb_record_success("db")
    except Exception:
        checks["database"] = "fail"
        _cb_record_failure("db")
    finally:
        db.close()
        _observe_dep("db", _db_t)

    # Redis
    _redis_t = time.time()
    try:
        if _main_module().redis_rate is not None:
            _main_module().redis_rate.ping()
            checks["redis"] = "ok"
            _cb_record_success("redis")
        else:
            checks["redis"] = "unavailable"
    except Exception:
        checks["redis"] = "fail"
        _cb_record_failure("redis")
    finally:
        _observe_dep("redis", _redis_t)

    # S3
    _s3_t = time.time()
    try:
        from config.aws import is_configured as _s3_configured
        if _s3_configured():
            from services.storage_service import check_health as _s3_health
            if _s3_health():
                checks["s3"] = "ok"
                _cb_record_success("s3")
            else:
                checks["s3"] = "fail"
                _cb_record_failure("s3")
        else:
            checks["s3"] = "not_configured"
    except Exception:
        checks["s3"] = "fail"
        _cb_record_failure("s3")
    finally:
        _observe_dep("s3", _s3_t)

    # pgvector extension
    _vec_db = SessionLocal()
    try:
        row = _vec_db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        checks["vector"] = "ok" if row else "missing"
    except Exception:
        checks["vector"] = "unknown"
    finally:
        _vec_db.close()

    # Model worker
    _wk_t = time.time()
    try:
        from services.model_worker import _proc as _mw_proc
        if _mw_proc is not None and _mw_proc.is_alive():
            checks["worker"] = "ok"
            _cb_record_success("worker")
        else:
            checks["worker"] = "stopped"
            _cb_record_failure("worker")
    except Exception:
        checks["worker"] = "unavailable"
    finally:
        _observe_dep("worker", _wk_t)

    # Parser circuit breaker
    try:
        acquired = _global_parse_semaphore.acquire(blocking=False)
        if acquired:
            _global_parse_semaphore.release()
            checks["parser_semaphore"] = "ok"
        else:
            checks["parser_semaphore"] = "saturated"
    except Exception:
        checks["parser_semaphore"] = "unknown"

    checks["parser_limit"] = _GLOBAL_PARSE_LIMIT
    checks["safe_mode"] = _is_safe_mode()

    # Feature flags
    with _live_flags_lock:
        checks["feature_flags"] = {
            "classifier": ENABLE_CLASSIFIER,
            "ai_review": ENABLE_AI_REVIEW,
            "sanitizer": ENABLE_SANITIZER,
            "fallback": ENABLE_FALLBACK,
            **{k: v for k, v in _live_flags.items()},
        }
    checks["maintenance_mode"] = MAINTENANCE_MODE
    checks["kill_switch"] = _is_killed()
    checks["drain_mode"] = _is_draining()
    checks["panic_mode"] = _is_panic()

    # Disk usage
    try:
        _disk = _get_disk_usage()
        checks["disk_percent"] = _disk
    except Exception:
        checks["disk_percent"] = "unknown"

    overall = "ok"
    if checks.get("database") != "ok":
        overall = "degraded"
    if checks.get("redis") == "fail":
        overall = "degraded"
    if checks.get("s3") == "fail":
        overall = "degraded"
    if checks.get("parser_semaphore") == "saturated":
        overall = "degraded"
    if checks.get("safe_mode"):
        overall = "degraded"
    if any(_cb_is_open(s) for s in ("db", "redis", "s3", "worker")):
        overall = "degraded"
    if checks.get("worker") == "stopped":
        overall = "degraded"

    # Guard infrastructure stats
    checks["guards"] = {
        "global_concurrency_limit": _GLOBAL_CONCURRENCY_LIMIT,
        "request_queue_size": _REQUEST_QUEUE_SIZE,
        "cpu_limit": _CPU_USAGE_LIMIT,
        "cpu_current": round(_get_cpu_percent(), 1),
        "memory_rss_limit_mb": _MEMORY_RSS_LIMIT_MB,
        "memory_rss_current_mb": round(_get_rss_bytes() / (1024 * 1024), 1),
        "circuit_breakers_open": [
            svc for svc, st in _circuit_breaker_state.items()
            if st.get("open_until", 0) > time.time()
        ],
        "ban_dict_size": len(_LOCAL_ABUSE_BANS),
        "rate_dict_sizes": {
            "ip_global": len(_ip_global_counts),
            "user_global": len(_user_global_counts),
            "user_embed": len(_user_embed_counts),
            "search": len(_search_counts),
        },
    }

    # Task 7 additions:
    is_prod = os.getenv("ENV", "development").lower() in ("production", "prod")
    has_admin = False
    if request is not None:
        has_admin = (_admin_access_error(request) is None)

    if is_prod and not has_admin:
        return {
            "status": overall,
        }

    return {
        "status": overall,
        "build_id": BUILD_ID,
        "git_sha": GIT_SHA,
        "parser_build": PARSER_BUILD,
        "instance_id": INSTANCE_ID,
        **checks,
    }


# Readiness check endpoint
@router.get("/ready")
def readiness_check():
    if not _main_module()._app_ready:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()
        return {"migration_head": head, "status": "ready"}
    except Exception as e:
        return {"status": "fail", "error": "internal readiness check failed"}


# Liveness probe (minimal, always returns 200 if the process is alive)
@router.get("/liveness")
def liveness_check():
    return {"status": "alive"}


# ── SRE: Backup age check helper ─────────────────────────────────────────
_BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(__file__), "backups"))


def _check_backup_age() -> dict:
    """Return info about the most recent backup file.  Warns if >24h old."""
    try:
        if not os.path.isdir(_BACKUP_DIR):
            return {"status": "no_backup_dir"}
        files = sorted(
            (os.path.join(_BACKUP_DIR, f) for f in os.listdir(_BACKUP_DIR)
             if f.endswith((".sql.gz", ".sql", ".dump"))),
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )
        if not files:
            return {"status": "no_backups"}
        newest = files[0]
        age_hours = (time.time() - os.path.getmtime(newest)) / 3600
        status = "ok" if age_hours < 24 else "stale"
        if age_hours >= 24:
            _alert("backup_stale", f"Latest backup is {age_hours:.1f}h old", level="warning")
        return {"status": status, "latest": os.path.basename(newest), "age_hours": round(age_hours, 1)}
    except Exception:
        return {"status": "check_failed"}


# ── SRE: /health/full endpoint ───────────────────────────────────────────
@router.get("/health/full")
def health_full(request: Request):
    """Extended health check with backup, metrics, and resource details."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    base = health_check(request)

    # Backup age
    base["backup"] = _check_backup_age()

    # Uptime
    base["uptime_seconds"] = round(time.time() - _APP_START_TIME, 1)

    # Redis connected gauge
    base["redis_connected"] = _main_module().redis_rate is not None
    try:
        if _main_module().redis_rate:
            _main_module().redis_rate.ping()
    except Exception:
        base["redis_connected"] = False

    # Worker restart count
    try:
        from services.model_worker import _worker_restart_count
        base["worker_restarts"] = _worker_restart_count
    except Exception:
        base["worker_restarts"] = "unknown"

    # ML model health
    try:
        from services.ml_model import health_check as ml_health_check
        base["ml_models"] = ml_health_check()
    except Exception:
        base["ml_models"] = {"error": "could not check"}

    # Circuit breaker detail
    now = time.time()
    base["circuit_breakers"] = {
        svc: {
            "failures": st.get("failures", 0),
            "open": st.get("open_until", 0) > now,
            "open_remaining_s": max(0, round(st.get("open_until", 0) - now, 1)),
        }
        for svc, st in _circuit_breaker_state.items()
    }

    # Config snapshot
    with _live_flags_lock:
        _snap_flags = dict(_live_flags)
    base["config_snapshot"] = {
        "live_flags": _snap_flags,
        "kill_switch": _is_killed(),
        "drain_mode": _is_draining(),
        "panic_mode": _is_panic(),
        "maintenance_mode": MAINTENANCE_MODE,
        "concurrency_limit": _GLOBAL_CONCURRENCY_LIMIT,
        "request_timeout_s": _REQUEST_TIMEOUT_SECONDS,
        "cb_failure_threshold": _CB_FAILURE_THRESHOLD,
        "cb_cooldown_s": _CB_COOLDOWN_SECONDS,
        "panic_error_threshold": _PANIC_ERROR_THRESHOLD,
        "panic_error_window_s": _PANIC_ERROR_WINDOW,
        "sample_rate": _SAMPLE_RATE,
        "inflight_requests": _inflight_get(),
    }

    return base


# ── Admin safe endpoints ─────────────────────────────────────────────────

@router.get("/admin/status")
def admin_status(request: Request):
    """Runtime control status overview. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    return {
        "app_ready": _main_module()._app_ready,
        "kill_switch": _is_killed(),
        "drain_mode": _is_draining(),
        "panic_mode": _is_panic(),
        "inflight_requests": _inflight_get(),
        "maintenance_mode": MAINTENANCE_MODE,
        "uptime_seconds": round(time.time() - _APP_START_TIME, 1),
    }


@router.get("/admin/flags")
def admin_flags_get(request: Request):
    """Read live feature flags. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    with _live_flags_lock:
        return dict(_live_flags)


@router.post("/admin/flags")
async def admin_flags_set(request: Request):
    """Update live feature flags. Body: {flag_name: bool}. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    body = await request.json()
    changed = {}
    with _live_flags_lock:
        known = set(_live_flags.keys())
    for k, v in body.items():
        if k in known and isinstance(v, bool):
            _set_flag(k, v)
            changed[k] = v
    return {"updated": changed}


@router.post("/admin/kill-switch")
async def admin_kill_switch(request: Request):
    """Toggle kill switch. Body: {"enabled": bool}. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    body = await request.json()
    val = body.get("enabled")
    if not isinstance(val, bool):
        return JSONResponse({"error": "enabled must be bool"}, status_code=400)
    _set_kill_switch(val)
    return {"kill_switch": val}


@router.post("/admin/drain")
async def admin_drain(request: Request):
    """Toggle drain mode. Body: {"enabled": bool}. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    body = await request.json()
    val = body.get("enabled")
    if not isinstance(val, bool):
        return JSONResponse({"error": "enabled must be bool"}, status_code=400)
    _set_drain(val)
    return {"drain_mode": val}


@router.post("/admin/panic/clear")
def admin_panic_clear(request: Request):
    """Clear panic mode. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    _clear_panic()
    try:
        ADMIN_ACTIONS_TOTAL.labels(action="panic_clear").inc()
    except Exception:
        pass
    return {"panic_mode": False}


@router.get("/admin/breakers")
def admin_breakers_get(request: Request):
    """Read circuit breaker states. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    now = time.time()
    return {
        svc: {
            "failures": st.get("failures", 0),
            "open": st.get("open_until", 0) > now,
            "open_remaining_s": max(0, round(st.get("open_until", 0) - now, 1)),
        }
        for svc, st in _circuit_breaker_state.items()
    }


@router.post("/admin/breakers")
async def admin_breakers_reset(request: Request):
    """Reset a circuit breaker. Body: {"service": "name"}. Requires admin token."""
    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error
    body = await request.json()
    svc = body.get("service", "")
    if svc not in _circuit_breaker_state:
        return JSONResponse({"error": f"unknown service: {svc}"}, status_code=400)
    _circuit_breaker_state[svc] = {"failures": 0, "open_until": 0}
    _audit_event("breaker_reset", service=svc)
    try:
        BREAKER_OPEN.labels(service=svc).set(0)
        ADMIN_ACTIONS_TOTAL.labels(action="breaker_reset").inc()
    except Exception:
        pass
    return {"service": svc, "reset": True}


# NOTE: we used to call ``Base.metadata.create_all`` here to ensure the
# schema matched the models. With Alembic migrations in place that is no
# longer desirable (it can lead to drift and won't add/remove columns).
# In development you can still bootstrap the database by running
# ``python setup_db.py`` or ``alembic upgrade head``; this automatic call
# is intentionally disabled.


