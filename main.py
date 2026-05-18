import logging

from dotenv import load_dotenv

load_dotenv()
import os
import random as _random

# Setup structured logging early
try:
    from logging_config import setup_logging
    setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logging.warning(f"Failed to setup structured logging: {e}")

# Re-export shared infra symbols so any remaining `from main import ...`
# statements continue to work without circular dependency issues.
from shared import (  # noqa: F401
    S3_ERRORS_TOTAL as _shared_S3_ERRORS_TOTAL,
    WORKER_RESTARTS_TOTAL as _shared_WORKER_RESTARTS_TOTAL,
    _cb_record_failure as _shared_cb_record_failure,
    _cb_record_success as _shared_cb_record_success,
    _cb_is_open as _shared_cb_is_open,
    _alert as _shared_alert,
    _cb_lock,
    _circuit_breaker_state,
    _cb_record_failure,
    _cb_record_success,
    _cb_is_open,
    _alert,
)

_ENV_MODE = os.getenv("ENV", "development").lower()
MOCK_SERVICES_ON = (
    os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
    and _ENV_MODE not in ("production", "prod")
)
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "auto").lower()
OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "").strip()
OCR_SERVICE_KEY = os.getenv("OCR_SERVICE_KEY", "").strip()
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip() or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import hashlib
import hmac
import io
import ipaddress
import json
import os
import re
import smtplib
import threading as _threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from fastapi import (Depends, FastAPI, File, Form, Header, HTTPException, Query,
                     Request, Response, UploadFile)
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except Exception:
    Instrumentator = None

try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
except Exception:
    Counter = None
    Gauge = None
    Histogram = None
    REGISTRY = None

from alembic.config import Config
from alembic.script import ScriptDirectory
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool
from sqlalchemy import or_, select, text

try:
    from redis import Redis
except Exception:
    Redis = None
from limits.storage import RedisStorage

from auth import verify_supabase_jwt
from database import SessionLocal, get_db
from models import Analysis, CVVersion, Candidate, Job, Organization, RecruiterJob, Reminder, User
from services.ats_service import analyze_cv
from services.domain_service import (detect_or_create_domain,
                                     get_domain_similarity)
from services.embedding_service import (find_similar_candidates, get_embedding,
                                        save_candidate_embedding,
                                        save_job_embedding)
import services.embedding_service as _embedding_service_module
from services.experience_service import experience_score
from services.industry_service import detect_industry_and_specialization
from services.keyword_service import keyword_match_score, compute_keyword_gap, compare
from services.language_service import (detect_language,
                                       interpret_score_localized,
                                       localize_risk_level)
from services.model_service import predict_match, predict_hire
from services.ml_model import predict_score as ml_predict_score
from services.recommendation_service import generate_recommendations
from services.scoring_service import calculate_similarity
from services.skill_service import skill_coverage_score
from services.tasks import analyze_pdf_task, analyze_text_task, batch_recruiter_task, celery_app
from services.cv_builder_service import (
    build_cv, get_available_templates, compile_cv_model,
    _global_parse_semaphore, _GLOBAL_PARSE_LIMIT, _is_safe_mode,
    ENABLE_CLASSIFIER, ENABLE_AI_REVIEW, ENABLE_SANITIZER, ENABLE_FALLBACK,
    BUILD_ID, GIT_SHA, PARSER_BUILD, INSTANCE_ID,
)
from services.billing_service import get_entitlements, is_feature_enabled
from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload
from services import rewrite_service
from services.ats_config import get_ats_weights
from security.redaction import redact_for_log, redact_mapping
from database import engine

if not hasattr(_embedding_service_module, "_EMBED_MAX_CALLS_PER_MIN"):
    _embedding_service_module._EMBED_MAX_CALLS_PER_MIN = int(os.getenv("EMBED_MAX_CALLS_PER_MIN", "60"))
if not hasattr(_embedding_service_module, "_embed_rate_ok"):
    _embedding_service_module._embed_rate_ok = lambda: True

# ── Re-exports from extracted modules ────────────────────────────────────
from core.metrics import (  # noqa: F401
    _NoopMetric, _get_or_create_counter, _get_or_create_histogram, _get_or_create_gauge,
    ANALYSIS_REQUESTS_TOTAL, ANALYSIS_ERRORS_TOTAL, QUOTA_HITS_TOTAL,
    PARSE_LATENCY, FALLBACK_TRIGGERS_TOTAL, ACTIVE_REQUESTS, UPTIME_SECONDS,
    UPLOADS_TOTAL, OPTIMIZES_TOTAL, DOWNLOADS_TOTAL, ERRORS_TOTAL, TIMEOUTS_TOTAL,
    PROCESS_RSS_BYTES, PROCESS_VMS_BYTES, GC_COLLECTIONS_TOTAL, PROCESS_CPU_PERCENT,
    WORKER_ACTIVE_TASKS, WORKER_QUEUE_SIZE, BREAKER_OPEN, FLAG_ENABLED,
    PANIC_TRIGGERS_TOTAL, PANIC_ACTIVE, ADMIN_ACTIONS_TOTAL,
    S3_ERRORS_TOTAL, JWT_FAILURES_TOTAL, REDIS_CONNECTED, WORKER_RESTARTS_TOTAL,
    DEP_LATENCY, GUARD_REJECTIONS_TOTAL, GUARD_CIRCUIT_BREAKER_TRIPS,
    GUARD_QUEUE_FULL, GUARD_CPU_REJECTIONS, GUARD_CONCURRENCY_REJECTIONS,
    GUARD_SAFE_MODE_TRIGGERS,
    _metric_guard_reject, _metric_request, _metric_error, _metric_quota_hit,
    _metric_parse_latency, _metric_fallback, _metric_active_inc, _metric_active_dec,
    _observe_dep, _record_guard_rejection,
    _GUARD_REJECT_TIMESTAMPS, _GUARD_REJECT_LOCK,
)
from core.metrics import _APP_START_TIME  # noqa: F401

from core.ops_runtime import (  # noqa: F401
    FEATURE_OPTIMIZE, FEATURE_AUTO_FIX, FEATURE_SEMANTIC_SEARCH, FEATURE_HTML_EXPORT,
    MAINTENANCE_MODE,
    _live_flags, _live_flags_lock,
    _get_flag, _set_flag, _reload_flags_from_file,
    _kill_switch, _is_killed, _set_kill_switch,
    _drain_mode, _is_draining, _set_drain,
    _inflight_count, _inflight_inc, _inflight_dec, _inflight_get,
    _panic_mode, _is_panic, _record_error_for_panic, _clear_panic,
    _PANIC_ERROR_THRESHOLD, _PANIC_ERROR_WINDOW,
    _audit_event,
    _OPS_EVENT_LIMIT, _ops_events, _security_events, _ai_usage_events,
    _ops_events_lock, _security_events_lock, _ai_usage_events_lock,
    _push_limited_event, _recent_events,
    _record_ops_event, _record_security_event, _record_ai_usage,
    _safe_request_ip, _extract_client_ip,
    _SAMPLE_RATE, _sample_logger,
    _rate_limited_log,
    _app_ready, _app_ready_lock, _set_app_ready, _is_app_ready,
    _CPU_USAGE_LIMIT, _get_cpu_percent,
    _MEMORY_RSS_LIMIT_MB, _MEMORY_RSS_LIMIT_BYTES, _get_rss_bytes,
    _DISK_WARN_PERCENT, _DISK_BLOCK_PERCENT, _get_disk_usage, _check_disk_safety,
    start_background_threads, start_guard_cleanup_thread,
    _check_auto_safe_mode_from_guards,
    _GUARD_SAFE_MODE_THRESHOLD, _GUARD_SAFE_MODE_WINDOW,
)

from core.quota import (  # noqa: F401
    _quota_now, _quota_today_date,
    _LOCAL_DAILY_QUOTA, _LOCAL_USER_THROTTLE,
    _load_local_quota, _save_local_quota,
    _normalize_plan, _is_premium_plan,
    _PLAN_ALIASES,
    USER_PLAN_LIMITS_DAILY, USER_PLAN_LIMITS_MONTHLY,
    ORG_PLAN_LIMITS_DAILY, ORG_PLAN_LIMITS_MONTHLY,
    REDIS_FREE_DAILY_LIMIT,
    COST_OPTIMIZE_PER_DAY, COST_UPLOAD_PER_DAY, COST_ANALYZE_PER_DAY,
    _seconds_until_next_quota_day, _daily_quota_key,
    _resolve_daily_limit_for_plan,
    _get_daily_quota_status, _consume_daily_quota,
    _apply_daily_quota_headers,
    _consume_user_rate_limit,
    _CONCURRENT_LIMIT_PER_USER, _acquire_concurrent_slot, _release_concurrent_slot,
    _check_cost_guard,
    _consume_billable_usage, _record_usage_daily,
    _is_admin_user, _resolve_effective_plan,
)

from services.user_service import (  # noqa: F401
    get_or_create_user,
    _get_owned_analysis_or_404,
    _resolve_initial_user_plan,
    _ensure_not_expired,
    BENCHMARK_MIN_PEERS,
    _compute_percentile_position,
    _build_analysis_benchmark,
    _build_premium_insights,
    _apply_plan_based_result_features,
)

from services.email_service import (  # noqa: F401
    _append_feedback_record, _read_feedback_records,
    _send_feedback_email,
    _do_send_email,
    _validate_reminder_email, _send_reminder_email,
    _render_reminder_subject, _render_reminder_body,
    _reminder_type_label,
    _process_due_reminders, _start_reminder_worker,
)


# FastAPI docs hardening for production
if os.getenv("ENV", "dev") == "prod":
    app = FastAPI(docs_url=None, redoc_url=None)
else:
    app = FastAPI()

from routes.recruiter import router as recruiter_router
from routes.recruiter_extended import router as recruiter_extended_router
from routes.recruiter_local import router as recruiter_local_router
from routes.downloads import router as downloads_router


app.include_router(recruiter_router)
app.include_router(recruiter_extended_router)
app.include_router(recruiter_local_router)
app.include_router(downloads_router)

from config.aws import MAX_PDF_OBJECTS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES
from core.request_utils import (
    LimitUploadSizeMiddleware,
    _format_bytes,
    _get_max_request_body_bytes,
    _read_upload_or_400,
)
from core.http_runtime import (
    ABUSE_BAN_SECONDS,
    ABUSE_BURST_HARD_LIMIT,
    ABUSE_BURST_SOFT_LIMIT,
    ABUSE_FINGERPRINT_WINDOW_SECONDS,
    ABUSE_PROTECTION_ENABLED,
    ABUSE_SCORE_AUDIT_THRESHOLD,
    ABUSE_SCORE_BLOCK_THRESHOLD,
    MOCK_SERVICES_ON,
    RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN,
    RATE_LIMIT_IP_ANALYZE_PER_MIN,
    RATE_LIMIT_IP_EMBED_PER_MIN,
    RATE_LIMIT_IP_MATCH_PER_MIN,
    RATE_LIMIT_IP_RENDER_PER_MIN,
    RATE_LIMIT_IP_REWRITE_PER_MIN,
    RATE_LIMIT_IP_UPLOAD_PER_MIN,
    RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN,
    RATE_LIMIT_USER_ANALYZE_PER_MIN,
    _ADMIN_IP_ALLOWLIST,
    _ADMIN_RATE_LIMIT_PER_MIN,
    _ADMIN_TOKEN,
    _ABUSE_BAN_SECONDS,
    _ABUSE_COUNTER_MAX_ENTRIES,
    _BAN_DICT_MAX_ENTRIES,
    _BLOCKED_IPS,
    _CB_COOLDOWN_SECONDS,
    _CB_FAILURE_THRESHOLD,
    _CSRF_PROTECTION_ENABLED,
    _DEDUP_WINDOW_SECONDS,
    _ENV_MODE,
    _GLOBAL_CONCURRENCY_LIMIT,
    _HEAVY_ENDPOINTS,
    _IP_GLOBAL_LIMIT_PER_MIN,
    _LOCAL_ABUSE_BANS,
    _LOCAL_ABUSE_COUNTERS,
    _LOCAL_ABUSE_LOCK,
    _MAX_LOG_LINE_LEN,
    _MAX_REQUEST_BODY_BYTES,
    _MAX_RESPONSE_BODY_BYTES,
    _MAX_SEARCH_QUERY_LEN,
    _PATH_CONCURRENCY,
    _PATH_TIMEOUTS,
    _RATE_DICT_MAX_KEYS,
    _REQUEST_QUEUE_SIZE,
    _REQUEST_TIMEOUT_SECONDS,
    _SEARCH_LIMIT_PER_MIN,
    _USER_EMBED_LIMIT_PER_MIN,
    _USER_GLOBAL_LIMIT_PER_MIN,
    _admin_access_error,
    _admin_ip_allowed,
    _admin_rate_limited,
    _check_admin_token,
    _compute_abuse_risk_score,
    _consume_abuse_fingerprint,
    _cors_origins,
    _dedup_cache,
    _dedup_lock,
    _escalate_abuse_ban,
    _get_path_semaphore,
    _global_semaphore,
    _get_request_fingerprint,
    _ip_global_counts,
    _ip_global_lock,
    _ip_global_rate_ok,
    _is_abuse_banned,
    _is_duplicate_request,
    _make_dedup_key,
    _path_semaphore_lock,
    _path_semaphores,
    _prune_abuse_dicts,
    _prune_rate_bucket,
    _rate_ok,
    _request_queue,
    _safe_log_message,
    _search_counts,
    _search_lock,
    _search_rate_ok,
    _set_abuse_ban,
    _user_embed_counts,
    _user_embed_lock,
    _user_embed_rate_ok,
    _user_global_counts,
    _user_global_lock,
    _user_global_rate_ok,
    audit_log,
    limiter,
    rate_limit,
    redis_rate,
    redis_url,
    register_http_runtime,
    require_abuse_check,
    require_embed_rate,
    require_search_rate,
    require_user_global_rate,
    share_tokens,
    track_event,
)
from core.app_lifecycle import (
    _configure_logging,
    _ensure_new_tables,
    _validate_safe_defaults,
    graceful_shutdown,
    register_lifecycle_events,
    start_model_worker,
    start_reminder_worker,
    validate_startup_config,
    warmup_pipeline,
)

register_http_runtime(app, logger)

# Optional Sentry integration: initialize if `SENTRY_DSN` is present in env
try:
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    if SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

            sentry_sdk.init(
                dsn=SENTRY_DSN,
                environment=os.getenv("SENTRY_ENV", "dev"),
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            )
            # Wrap the ASGI app so errors are captured
            app = SentryAsgiMiddleware(app)
        except Exception:
            # Don't fail startup if Sentry is not available
            pass
except Exception:
    pass

if Instrumentator:
    try:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except Exception:
        pass


# Health check endpoint
# Health and admin-control routes moved to routes/system.py


register_lifecycle_events(app)


MODEL_WEIGHT = float(os.getenv("MODEL_WEIGHT", 0.30))
ATS_WEIGHT = float(os.getenv("ATS_WEIGHT", 0.70))

# Endpoint rate limiting defaults (can be tightened in SaaS/prod)
RATE_LIMIT_IP_ANALYZE_PER_MIN = int(os.getenv("RATE_LIMIT_IP_ANALYZE_PER_MIN", "10"))
RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN = int(
    os.getenv("RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN", "10")
)
RATE_LIMIT_USER_ANALYZE_PER_MIN = int(
    os.getenv("RATE_LIMIT_USER_ANALYZE_PER_MIN", "10")
)
RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN = int(
    os.getenv("RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN", "10")
)
RATE_LIMIT_IP_UPLOAD_PER_MIN = int(os.getenv("RATE_LIMIT_IP_UPLOAD_PER_MIN", "5"))
RATE_LIMIT_IP_RENDER_PER_MIN = int(os.getenv("RATE_LIMIT_IP_RENDER_PER_MIN", "10"))
RATE_LIMIT_IP_MATCH_PER_MIN = int(os.getenv("RATE_LIMIT_IP_MATCH_PER_MIN", "10"))
RATE_LIMIT_IP_REWRITE_PER_MIN = int(os.getenv("RATE_LIMIT_IP_REWRITE_PER_MIN", "5"))
RATE_LIMIT_IP_EMBED_PER_MIN = int(os.getenv("RATE_LIMIT_IP_EMBED_PER_MIN", "10"))


# CV builder routes moved to routes/cv_builder.py


from services.pipeline_runtime import (  # noqa: E402
    ANALYSIS_CACHE_TTL,
    ANALYSIS_SCORE_VERSION,
    _analysis_mem_cache,
    _assess_job_description_quality,
    _build_match_score_v2,
    _detect_seniority,
    _extract_job_title_from_jd,
    _extract_probable_job_title,
    _seniority_match_score,
    _stable_hash,
    _title_match_score,
    build_features,
    interpret_score,
    run_pipeline,
)


# PDF/OCR runtime moved to services/pdf_runtime.py
from services.pdf_runtime import (  # noqa: E402
    CAPTCHA_ENABLED,
    CAPTCHA_PROVIDER,
    CAPTCHA_SECRET,
    CLAMAV_ENABLED,
    CLAMAV_HOST,
    CLAMAV_PORT,
    _MAX_PDF_EXTRACTED_CHARS,
    _MAX_PDF_OBJECTS,
    _MAX_PDF_PAGES,
    _build_tesseract_lang,
    _extract_pdf_text,
    _generate_scanned_pdf,
    _generate_scanned_pdf_from_text,
    _is_tesseract_available,
    _normalize_ocr_text_for_cv_processing,
    _ocr_extract_text,
    _ocr_extract_text_remote,
    _reflow_ocr_lines,
    _resolve_job_description_text,
    _scan_upload_for_viruses,
    _validate_pdf_upload,
    require_captcha,
)


# Pipeline matching helpers moved to services/pipeline_runtime.py


# AI tooling, rewrite, interview, keyword, and CV version routes moved to routes/ai_tools.py


# Billing, admin ops, and Stripe routes moved to routes/billing.py




# ═══════════════════════════════════════════════════════════════════════════
# CAMERA CV SCAN — OCR + ATS Analysis + PDF Generation
# ═══════════════════════════════════════════════════════════════════════════



# recruiter scan-cv moved to routes/recruiter.py# recruiter scan-cv moved to routes/recruiter.py


# ═══════════════════════════════════════════════════════════════════════════
# SCORE BREAKDOWN — ATS + Job Match + Recruiter Score
# ═══════════════════════════════════════════════════════════════════════════


# Score breakdown and CV storage routes moved to routes/cv_storage.py



start_guard_cleanup_thread(
    _prune_rate_bucket,
    _ip_global_lock, _ip_global_counts,
    _user_global_lock, _user_global_counts,
    _user_embed_lock, _user_embed_counts,
    _search_lock, _search_counts,
    _dedup_lock, _dedup_cache,
    _prune_abuse_dicts,
)

# Extracted routers registered after shared helpers are initialized.
from routes.system import router as system_router  # noqa: E402
from routes.cv_builder import router as cv_builder_router  # noqa: E402
from routes.analysis import router as analysis_router  # noqa: E402
from routes.dashboard import router as dashboard_router  # noqa: E402
from routes.user_data import router as user_data_router  # noqa: E402
from services.ai_feature_service import ensure_ai_rewrite_allowed as _ensure_ai_rewrite_allowed  # noqa: E402
from routes.ai_tools import router as ai_tools_router  # noqa: E402
from routes.billing import router as billing_router  # noqa: E402
from routes.cv_storage import router as cv_storage_router  # noqa: E402
from routes.worker import router as worker_router  # noqa: E402

app.include_router(system_router)
app.include_router(cv_builder_router)
app.include_router(analysis_router)
app.include_router(dashboard_router)
app.include_router(user_data_router)
app.include_router(ai_tools_router)
app.include_router(billing_router)
app.include_router(cv_storage_router)
app.include_router(worker_router, prefix="/api")
