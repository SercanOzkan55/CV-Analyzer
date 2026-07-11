from __future__ import annotations

import logging
import os
import time

from sqlalchemy import text

from core.metrics import ACTIVE_REQUESTS, FLAG_ENABLED
from core.ops_runtime import (
    _CPU_USAGE_LIMIT,
    _DISK_BLOCK_PERCENT,
    _DISK_WARN_PERCENT,
    _MEMORY_RSS_LIMIT_MB,
    _app_ready_lock,
    _clear_panic,
    _get_disk_usage,
    _inflight_get,
    _is_draining,
    _is_killed,
    _is_panic,
    _live_flags,
    _live_flags_lock,
    _set_drain,
    _set_kill_switch,
)
from core.runtime_bridge import main_module, main_value
from database import SessionLocal, engine
from services.cv_builder_service import (
    BUILD_ID,
    ENABLE_AI_REVIEW,
    ENABLE_CLASSIFIER,
    ENABLE_FALLBACK,
    ENABLE_SANITIZER,
    GIT_SHA,
    PARSER_BUILD,
    _GLOBAL_PARSE_LIMIT,
    _global_parse_semaphore,
)
from services.email_service import _start_reminder_worker


def _ensure_sqlite_column(connection, table_name: str, column_name: str, column_sql: str):
    columns = {row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()}
    if column_name not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def _ensure_mock_sqlite_schema_columns():
    with engine.begin() as connection:
        _ensure_sqlite_column(connection, "candidate_actions", "cv_file_key", "cv_file_key VARCHAR")
        _ensure_sqlite_column(connection, "candidate_actions", "cv_file_name", "cv_file_name VARCHAR")
        _ensure_sqlite_column(connection, "candidate_actions", "cv_file_type", "cv_file_type VARCHAR")
        _ensure_sqlite_column(connection, "candidate_actions", "assigned_user_id", "assigned_user_id INTEGER")
        _ensure_sqlite_column(connection, "candidate_actions", "deleted_at", "deleted_at DATETIME")
        _ensure_sqlite_column(connection, "candidate_actions", "anonymized_at", "anonymized_at DATETIME")


def _configure_logging():
    try:
        from logging_config import setup_logging

        setup_logging()
    except Exception:
        logging.getLogger("app.startup").warning("Log rotation setup skipped")


def _ensure_new_tables():
    try:
        from sqlalchemy import inspect as sa_inspect
        from database import Base as _Base, DATABASE_URL as _DATABASE_URL
        from models import AnalysisNote, AnalysisShare, Favorite, JobTemplate, Reminder, UsageDaily

        if main_value("MOCK_SERVICES_ON", False) and str(_DATABASE_URL or "").startswith("sqlite"):
            _Base.metadata.create_all(engine)
            _ensure_mock_sqlite_schema_columns()
            logging.getLogger("app.startup").info("Mock sqlite schema ensured for all models")
            return

        inspector = sa_inspect(engine)
        existing = set(inspector.get_table_names())
        tables_to_create = []
        for model in [UsageDaily, Favorite, JobTemplate, AnalysisShare, AnalysisNote, Reminder]:
            if model.__tablename__ not in existing:
                tables_to_create.append(model.__table__)
        if tables_to_create:
            _Base.metadata.create_all(engine, tables=tables_to_create)
            logging.getLogger("app.startup").info("Created tables: %s", [t.name for t in tables_to_create])
    except Exception as exc:
        logging.getLogger("app.startup").warning("Table auto-create skipped: %s", exc)


def _validate_safe_defaults():
    _sd_logger = logging.getLogger("app.startup.safe_defaults")
    if _is_killed() and not os.getenv("KILL_SWITCH"):
        _set_kill_switch(False)
        _sd_logger.warning("safe_default: kill switch was on without env; reset to off")
    if _is_draining():
        _set_drain(False)
        _sd_logger.warning("safe_default: drain mode was on at startup; reset to off")
    if _is_panic():
        _clear_panic()
        _sd_logger.warning("safe_default: panic mode was on at startup; cleared")
    with _live_flags_lock:
        for key, value in list(_live_flags.items()):
            if not isinstance(value, bool):
                _live_flags[key] = True
                _sd_logger.warning("safe_default: flag %s had non-bool value; reset to True", key)
    _sd_logger.info("safe_defaults: startup validation passed")
    with _live_flags_lock:
        for key, value in _live_flags.items():
            try:
                FLAG_ENABLED.labels(flag=key).set(1 if value else 0)
            except Exception:
                pass


def start_model_worker():
    try:
        if os.getenv("MODEL_WORKER_DISABLED"):
            return
        from services import model_worker

        model_worker.start()
        try:
            _ = model_worker.predict_sync([0.0] * 29, timeout=5.0)
            logging.getLogger("app.warmup").info("warmup: worker prediction ok")
        except Exception:
            logging.getLogger("app.warmup").warning("warmup: worker prediction failed (non-fatal)")
    except Exception:
        pass


def warmup_pipeline():
    _logger = logging.getLogger("app.warmup")
    try:
        from services.section_classifier import PARSER_VERSION, _PARSER_REGISTRY, get_parser

        parser_fn = get_parser()
        _logger.info(
            "warmup: parser registry ok (%d versions), active=%s, fn=%s",
            len(_PARSER_REGISTRY),
            PARSER_VERSION,
            parser_fn.__name__,
        )
        parser_fn("John Doe\njohn@example.com\nExperience\nSoftware Engineer at ACME 2020-2023")
        _logger.info("warmup: dry-run parse completed")
    except Exception:
        _logger.warning("warmup: parser dry-run failed (non-fatal)", exc_info=True)

    try:
        acquired = _global_parse_semaphore.acquire(blocking=False)
        if acquired:
            _global_parse_semaphore.release()
        _logger.info("warmup: semaphore ok (limit=%d)", _GLOBAL_PARSE_LIMIT)
    except Exception:
        _logger.warning("warmup: semaphore check failed (non-fatal)", exc_info=True)

    try:
        ACTIVE_REQUESTS.labels() if hasattr(ACTIVE_REQUESTS, "labels") else None
        _logger.info("warmup: metrics initialised")
    except Exception:
        pass

    _logger.info("warmup: build_id=%s git_sha=%s parser_build=%s", BUILD_ID, GIT_SHA, PARSER_BUILD)


def start_reminder_worker():
    try:
        if os.getenv("DISABLE_REMINDER_WORKER", "").lower() in ("1", "true", "yes"):
            return
        _start_reminder_worker()
        logging.getLogger("app.startup").info("reminder_worker: started")
    except Exception as exc:
        logging.getLogger("app.startup").warning("reminder_worker startup failed: %s", exc)


def validate_startup_config():
    _logger = logging.getLogger("app.startup")
    warnings: list[str] = []
    fatals: list[str] = []
    env_mode = main_value("_ENV_MODE", os.getenv("ENV", "development").lower())
    cors_origins = main_value("_cors_origins", [])
    csrf_protection = bool(main_value("_CSRF_PROTECTION_ENABLED", False))
    admin_token = main_value("_ADMIN_TOKEN", "")
    admin_allowlist = main_value("_ADMIN_IP_ALLOWLIST", [])
    admin_rate = int(main_value("_ADMIN_RATE_LIMIT_PER_MIN", 20))
    redis_rate = main_value("redis_rate")
    request_timeout = int(main_value("_REQUEST_TIMEOUT_SECONDS", 600))
    global_concurrency = int(main_value("_GLOBAL_CONCURRENCY_LIMIT", 20))
    request_queue_size = int(main_value("_REQUEST_QUEUE_SIZE", 100))
    heavy_endpoints = main_value("_HEAVY_ENDPOINTS", set())
    path_timeouts = main_value("_PATH_TIMEOUTS", {})
    path_concurrency = main_value("_PATH_CONCURRENCY", {})

    if env_mode in ("production", "prod"):

        def _truthy(name: str) -> bool:
            return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")

        cors_lower = [origin.lower() for origin in cors_origins]
        if not os.getenv("SUPABASE_JWT_SECRET") and not os.getenv("SUPABASE_JWT_SECRET_FILE"):
            fatals.append("SUPABASE_JWT_SECRET (or _FILE) is required in production")
        if not os.getenv("DATABASE_URL"):
            fatals.append("DATABASE_URL is required in production")
        if main_value("MOCK_SERVICES_ON", False):
            fatals.append("MOCK_SERVICES must be disabled in production")
        if _truthy("DEV_ALLOW_SELF_PREMIUM"):
            fatals.append("DEV_ALLOW_SELF_PREMIUM must be disabled in production")
        if not admin_token or len(admin_token) < 32:
            fatals.append("ADMIN_TOKEN is required in production and must be at least 32 characters")
        if str(admin_token).lower() in ("changeme", "admin", "secret", "password"):
            fatals.append("ADMIN_TOKEN uses a known unsafe default")
        if not admin_allowlist:
            warnings.append("ADMIN_IP_ALLOWLIST not set; admin endpoints rely only on bearer token")
        if admin_rate <= 0:
            warnings.append("ADMIN_RATE_LIMIT_PER_MIN is disabled")
        if not csrf_protection:
            warnings.append("CSRF_PROTECTION_ENABLED is off; cookie-auth unsafe requests are not protected")
        if not os.getenv("BILLING_ADMIN_TOKEN", "").strip():
            warnings.append("BILLING_ADMIN_TOKEN not set (billing admin panel is disabled)")
        if not cors_origins:
            fatals.append("CORS_ORIGINS must list the production frontend origin")
        if "*" in cors_origins:
            fatals.append("CORS_ORIGINS cannot contain '*' in production")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in cors_lower):
            fatals.append("CORS_ORIGINS cannot include localhost/127.0.0.1 in production")
        if os.getenv("STORAGE_BACKEND", "s3").strip().lower() == "local" and not _truthy("ALLOW_LOCAL_STORAGE_IN_PROD"):
            fatals.append("STORAGE_BACKEND=local is not allowed in production without ALLOW_LOCAL_STORAGE_IN_PROD=1")

    from auth import SUPABASE_JWT_SECRET as _jwt_secret

    if _jwt_secret:
        if len(_jwt_secret) < 32:
            warnings.append(f"SUPABASE_JWT_SECRET is short ({len(_jwt_secret)} chars, recommend >=32)")
        if _jwt_secret in (
            "super-secret-jwt-token-with-at-least-32-characters-long",
            "your-super-secret-jwt-token",
            "changeme",
            "secret",
        ):
            fatals.append("SUPABASE_JWT_SECRET is a known default; change it immediately")

    redis_password = os.getenv("REDIS_PASSWORD", "")
    if env_mode in ("production", "prod") and redis_password in ("changeme", "password", "redis", "secret"):
        warnings.append("REDIS_PASSWORD uses a known weak default")
    if global_concurrency < 1:
        warnings.append(f"GLOBAL_CONCURRENCY_LIMIT={global_concurrency} is too low")
    if request_timeout < 5:
        warnings.append(f"REQUEST_TIMEOUT_SECONDS={request_timeout} is too low")
    if _MEMORY_RSS_LIMIT_MB < 128:
        warnings.append(f"MEMORY_RSS_LIMIT_MB={_MEMORY_RSS_LIMIT_MB} is too low")
    if _CPU_USAGE_LIMIT < 50:
        warnings.append(f"CPU_USAGE_LIMIT={_CPU_USAGE_LIMIT} is too low")
    if request_queue_size < 10:
        warnings.append(f"REQUEST_QUEUE_SIZE={request_queue_size} is too low")

    from security.runtime_guard import (
        _DOWNLOAD_LIMIT_PER_MIN,
        _GLOBAL_OPTIMIZE_LIMIT,
        _MAX_USER_OPTIMIZE_CONCURRENT,
        _SIGNED_URL_LIMIT_PER_MIN,
    )

    if _MAX_USER_OPTIMIZE_CONCURRENT < 1:
        warnings.append(f"MAX_USER_OPTIMIZE_CONCURRENT={_MAX_USER_OPTIMIZE_CONCURRENT} is too low")
    if _GLOBAL_OPTIMIZE_LIMIT < 1:
        warnings.append(f"GLOBAL_OPTIMIZE_CONCURRENT={_GLOBAL_OPTIMIZE_LIMIT} is too low")
    if _DOWNLOAD_LIMIT_PER_MIN < 1:
        warnings.append(f"DOWNLOAD_LIMIT_PER_MIN={_DOWNLOAD_LIMIT_PER_MIN} is too low")
    if _SIGNED_URL_LIMIT_PER_MIN < 1:
        warnings.append(f"SIGNED_URL_LIMIT_PER_MIN={_SIGNED_URL_LIMIT_PER_MIN} is too low")

    if not os.getenv("OPENAI_API_KEY"):
        _logger.info("startup: OPENAI_API_KEY not set (embeddings/AI review disabled)")
    if redis_rate is None:
        _logger.info("startup: Redis unavailable (using local fallback for rate limiting)")
        if env_mode in ("production", "prod"):
            fatals.append("Redis is unreachable (required in production)")

    try:
        startup_db = SessionLocal()
        startup_db.execute(text("SELECT 1"))
        startup_db.close()
        _logger.info("startup: database connection OK")
    except Exception as exc:
        _logger.error("startup: database connection failed - %s", exc)
        if env_mode in ("production", "prod"):
            fatals.append(f"Database unreachable: {exc}")

    try:
        vec_db = SessionLocal()
        row = vec_db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).fetchone()
        vec_db.close()
        if row:
            _logger.info("startup: pgvector extension OK")
        else:
            _logger.warning("startup: pgvector extension not found")
    except Exception:
        _logger.warning("startup: pgvector check skipped (non-fatal)")

    try:
        disk_pct = _get_disk_usage()
        if disk_pct >= _DISK_BLOCK_PERCENT:
            fatals.append(f"Disk usage critical: {disk_pct}%")
        elif disk_pct >= _DISK_WARN_PERCENT:
            _logger.warning("startup: disk usage high - %.1f%%", disk_pct)
        else:
            _logger.info("startup: disk usage %.1f%%", disk_pct)
    except Exception:
        _logger.warning("startup: disk check skipped")

    for path in path_timeouts:
        if path not in heavy_endpoints and path not in path_concurrency:
            pass

    for warning in warnings:
        _logger.warning("startup:config_warning %s", warning)

    if main_value("MOCK_SERVICES_ON", False):
        _logger.info("startup: S3 check skipped in MOCK_SERVICES mode")
    else:
        try:
            from config.aws import S3_BUCKET, is_configured, require_configured

            require_configured()
            if is_configured():
                from services.storage_service import check_health

                if check_health():
                    _logger.info("startup: S3 bucket '%s' OK", S3_BUCKET)
                else:
                    _logger.warning("startup: S3 bucket '%s' unreachable", S3_BUCKET)
        except RuntimeError as exc:
            _logger.error("startup: S3 FATAL - %s", exc)
            if env_mode in ("production", "prod"):
                fatals.append(f"S3 configuration error: {exc}")
        except Exception as exc:
            _logger.warning("startup: S3 check skipped - %s", exc)

    if fatals:
        for fatal in fatals:
            _logger.critical("startup:FATAL %s", fatal)
        if env_mode in ("production", "prod"):
            raise RuntimeError(f"Server cannot start: {len(fatals)} fatal config error(s): " + "; ".join(fatals))

    _logger.info(
        "startup: validation complete (%d warnings), guards=%d, path_concurrency=%d, queue=%d",
        len(warnings),
        global_concurrency,
        len(main_value("_path_semaphores", {})),
        request_queue_size,
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level == "DEBUG" and env_mode in ("production", "prod"):
        _logger.warning("startup:WARN LOG_LEVEL=DEBUG in production - verbose logging active")
    _logger.info(
        "startup:banner env=%s log_level=%s redis=%s workers=%s concurrency=%d queue=%d timeout=%ds build=%s sha=%s",
        env_mode,
        log_level,
        "ok" if redis_rate else "unavailable",
        os.getenv("WEB_CONCURRENCY", "auto"),
        global_concurrency,
        request_queue_size,
        request_timeout,
        BUILD_ID,
        GIT_SHA,
    )

    module = main_module()
    with _app_ready_lock:
        module._app_ready = True
    _logger.info("startup: app marked READY - accepting traffic")


def graceful_shutdown():
    shutdown_logger = logging.getLogger("app.shutdown")
    shutdown_logger.info("shutdown: starting graceful shutdown sequence")
    drain_timeout = 10
    drain_start = time.time()
    while _inflight_get() > 0 and (time.time() - drain_start) < drain_timeout:
        time.sleep(0.25)
    remaining = _inflight_get()
    if remaining:
        shutdown_logger.warning("shutdown: %d requests still in-flight after %ds", remaining, drain_timeout)
    else:
        shutdown_logger.info("shutdown: all in-flight requests completed")

    try:
        from services import model_worker

        model_worker.stop()
        shutdown_logger.info("shutdown: model worker stopped")
    except Exception:
        shutdown_logger.warning("shutdown: model worker stop failed", exc_info=True)

    try:
        module = main_module()
        redis_rate = getattr(module, "redis_rate", None)
        if redis_rate is not None:
            redis_rate.close()
            module.redis_rate = None
            shutdown_logger.info("shutdown: redis connection closed")
    except Exception:
        shutdown_logger.warning("shutdown: redis close failed", exc_info=True)

    try:
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass
        shutdown_logger.info("shutdown: logs flushed")
    except Exception:
        pass

    shutdown_logger.info("shutdown: complete")


def register_lifecycle_events(app):
    app.on_event("startup")(_configure_logging)
    app.on_event("startup")(_ensure_new_tables)
    app.on_event("startup")(_validate_safe_defaults)
    app.on_event("startup")(start_model_worker)
    app.on_event("startup")(warmup_pipeline)
    app.on_event("startup")(start_reminder_worker)
    app.on_event("startup")(validate_startup_config)
    app.on_event("shutdown")(graceful_shutdown)
