import logging

from dotenv import load_dotenv

load_dotenv()
import os

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
import json
import os
import re
import smtplib
import threading as _threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
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
from models import Analysis, CVVersion, Candidate, Job, Organization, Reminder, User
from services.ats_service import analyze_cv
from services.domain_service import (detect_or_create_domain,
                                     get_domain_similarity)
from services.embedding_service import (find_similar_candidates, get_embedding,
                                        save_candidate_embedding,
                                        save_job_embedding)
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
from database import engine

share_tokens = {}  # In-memory store for share tokens

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

# Middleware to allow large uploads (up to 1GB)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        max_body_size = 1024 * 1024 * 1024  # 1 GB
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            return Response("Request too large", status_code=413)
        return await call_next(request)

app.add_middleware(LimitUploadSizeMiddleware)

# Add request logging middleware for structured observability
import uuid
from time import time as current_time

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add request context and timing to logs."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = current_time()
    
    try:
        response = await call_next(request)
        duration_ms = (current_time() - start_time) * 1000
        
        # Log successful request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        duration_ms = (current_time() - start_time) * 1000
        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True
        )
        raise

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


class _NoopMetric:
    def labels(self, **kwargs):
        return self

    def inc(self, amount: float = 1.0):
        return None

    def dec(self, amount: float = 1.0):
        return None

    def set(self, value: float):
        return None

    def observe(self, amount: float):
        return None


def _get_or_create_counter(name: str, description: str, labelnames=()):
    if not Counter:
        return _NoopMetric()
    try:
        return Counter(name, description, labelnames=labelnames)
    except ValueError:
        # Counter can already exist if module gets imported more than once.
        if REGISTRY is not None:
            existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
            if existing is not None:
                return existing
        return _NoopMetric()


def _get_or_create_histogram(name: str, description: str, labelnames=(), buckets=None):
    if not Histogram:
        return _NoopMetric()
    try:
        kwargs = {"labelnames": labelnames}
        if buckets:
            kwargs["buckets"] = buckets
        return Histogram(name, description, **kwargs)
    except ValueError:
        if REGISTRY is not None:
            existing = REGISTRY._names_to_collectors.get(name)
            if existing is not None:
                return existing
        return _NoopMetric()


def _get_or_create_gauge(name: str, description: str, labelnames=()):
    if not Gauge:
        return _NoopMetric()
    try:
        return Gauge(name, description, labelnames=labelnames)
    except ValueError:
        if REGISTRY is not None:
            existing = REGISTRY._names_to_collectors.get(name)
            if existing is not None:
                return existing
        return _NoopMetric()


ANALYSIS_REQUESTS_TOTAL = _get_or_create_counter(
    "analysis_requests_total",
    "Total number of analysis requests",
    labelnames=("endpoint",),
)
ANALYSIS_ERRORS_TOTAL = _get_or_create_counter(
    "analysis_errors_total",
    "Total number of analysis errors",
    labelnames=("endpoint", "error_type"),
)
QUOTA_HITS_TOTAL = _get_or_create_counter(
    "quota_hits_total",
    "Total number of quota/rate-limit rejections",
    labelnames=("endpoint", "reason"),
)

# ── Observability metrics ─────────────────────────────────────────────────
PARSE_LATENCY = _get_or_create_histogram(
    "cv_parse_latency_seconds",
    "Time spent parsing CV text through the pipeline",
    labelnames=("stage",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
FALLBACK_TRIGGERS_TOTAL = _get_or_create_counter(
    "cv_fallback_triggers_total",
    "Number of times a fallback path was activated",
    labelnames=("stage",),
)
ACTIVE_REQUESTS = _get_or_create_gauge(
    "cv_active_requests",
    "Number of currently in-flight CV processing requests",
)
UPTIME_SECONDS = _get_or_create_gauge(
    "cv_uptime_seconds",
    "Seconds since the application started",
)
_APP_START_TIME = time.time()

# ── Operational counters ───────────────────────────────────────────────
UPLOADS_TOTAL = _get_or_create_counter(
    "cv_uploads_total", "Total PDF/DOCX uploads",
)
OPTIMIZES_TOTAL = _get_or_create_counter(
    "cv_optimizes_total", "Total CV optimize/auto-fix requests",
)
DOWNLOADS_TOTAL = _get_or_create_counter(
    "cv_downloads_total", "Total CV download requests",
)
ERRORS_TOTAL = _get_or_create_counter(
    "cv_errors_total", "Total unhandled errors",
)
TIMEOUTS_TOTAL = _get_or_create_counter(
    "cv_timeouts_total", "Total request timeouts",
)

# ── Observability: process metrics ────────────────────────────────────────
PROCESS_RSS_BYTES = _get_or_create_gauge(
    "cv_process_rss_bytes", "Resident set size in bytes",
)
PROCESS_VMS_BYTES = _get_or_create_gauge(
    "cv_process_vms_bytes", "Virtual memory size in bytes",
)
GC_COLLECTIONS_TOTAL = _get_or_create_gauge(
    "cv_gc_collections_total", "GC collection count per generation",
    labelnames=("generation",),
)
PROCESS_CPU_PERCENT = _get_or_create_gauge(
    "cv_process_cpu_percent", "Process CPU usage percent",
)

# ── Observability: worker metrics ─────────────────────────────────────────
WORKER_ACTIVE_TASKS = _get_or_create_gauge(
    "cv_worker_active_tasks", "Active worker tasks",
)
WORKER_QUEUE_SIZE = _get_or_create_gauge(
    "cv_worker_queue_size", "Worker task queue size",
)

# ── Observability: circuit breaker gauge ──────────────────────────────────
BREAKER_OPEN = _get_or_create_gauge(
    "cv_circuit_breaker_open", "Circuit breaker state (1=open, 0=closed)",
    labelnames=("service",),
)

# ── Observability: feature flag gauge ─────────────────────────────────────
FLAG_ENABLED = _get_or_create_gauge(
    "cv_feature_flag_enabled", "Feature flag state (1=enabled, 0=disabled)",
    labelnames=("flag",),
)

# ── Observability: panic metrics ──────────────────────────────────────────
PANIC_TRIGGERS_TOTAL = _get_or_create_counter(
    "cv_panic_triggers_total", "Times panic mode was triggered",
)
PANIC_ACTIVE = _get_or_create_gauge(
    "cv_panic_active", "Panic mode active (1=yes, 0=no)",
)

# ── Observability: admin action counter ───────────────────────────────────
ADMIN_ACTIONS_TOTAL = _get_or_create_counter(
    "cv_admin_actions_total", "Admin control-plane actions",
    labelnames=("action",),
)

# Fallback stores when Redis is unavailable (local runtime memory).
# Daily quota is persisted to a JSON file so it survives server restarts.
_QUOTA_FILE = os.path.join(os.path.dirname(__file__), ".local_quota.json")
_QUOTA_RESET_TIMEZONE = (
    os.getenv("QUOTA_RESET_TIMEZONE", os.getenv("APP_TIMEZONE", "Europe/Istanbul"))
    .strip()
    or "Europe/Istanbul"
)


def _quota_now() -> datetime:
    if ZoneInfo is None:
        return datetime.utcnow()
    try:
        return datetime.now(ZoneInfo(_QUOTA_RESET_TIMEZONE))
    except Exception:
        return datetime.utcnow()


def _quota_today_date():
    return _quota_now().date()


def _load_local_quota() -> dict:
    """Load persisted daily quota from disk."""
    try:
        with open(_QUOTA_FILE, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        # Prune entries older than today based on quota key suffix.
        # Key format: quota:daily:<user_id>:YYYYMMDD
        quota_now = _quota_now()
        today_compact = quota_now.strftime("%Y%m%d")
        today_hyphen = quota_now.strftime("%Y-%m-%d")

        cleaned = {}
        for k, v in data.items():
            key = str(k or "")
            suffix = key.rsplit(":", 1)[-1]
            if suffix in (today_compact, today_hyphen):
                try:
                    cleaned[key] = int(v)
                except Exception:
                    cleaned[key] = 0
        return cleaned
    except Exception:
        return {}


def _save_local_quota():
    """Persist daily quota to disk (best-effort)."""
    try:
        with open(_QUOTA_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(_LOCAL_DAILY_QUOTA))
    except Exception:
        pass


_LOCAL_DAILY_QUOTA = _load_local_quota()
_LOCAL_USER_THROTTLE = {}
_LOCAL_ABUSE_COUNTERS: dict = {}
_LOCAL_ABUSE_BANS: dict = {}
_LOCAL_ABUSE_LOCK = _threading.Lock()


# Max entries in local abuse dicts (hard cap to prevent memory leak)
_BAN_DICT_MAX_ENTRIES = int(os.getenv("BAN_DICT_MAX_ENTRIES", "5000"))
_ABUSE_COUNTER_MAX_ENTRIES = int(os.getenv("ABUSE_COUNTER_MAX_ENTRIES", "5000"))
_THROTTLE_MAX_ENTRIES = int(os.getenv("THROTTLE_MAX_ENTRIES", "10000"))


def _extract_minute_bucket(key: str) -> int:
    """Extract the minute-bucket integer from a throttle key like 'throttle:user:scope:uid:12345'."""
    try:
        return int(key.rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _prune_abuse_dicts(now: float) -> None:
    """Remove expired bans and stale abuse counters, enforce hard caps."""
    with _LOCAL_ABUSE_LOCK:
        # Prune expired bans
        expired = [k for k, v in _LOCAL_ABUSE_BANS.items()
                   if isinstance(v, (int, float)) and v < now]
        for k in expired:
            del _LOCAL_ABUSE_BANS[k]
        # Hard cap: drop oldest bans if still over limit
        if len(_LOCAL_ABUSE_BANS) > _BAN_DICT_MAX_ENTRIES:
            by_expiry = sorted(_LOCAL_ABUSE_BANS, key=lambda k: _LOCAL_ABUSE_BANS.get(k, 0))
            for k in by_expiry[:len(by_expiry) - _BAN_DICT_MAX_ENTRIES]:
                del _LOCAL_ABUSE_BANS[k]
        # Prune stale counters (window_start + window older than 10 min)
        stale = []
        for k, v in _LOCAL_ABUSE_COUNTERS.items():
            if isinstance(v, dict):
                ws = v.get("window_start", 0)
                if ws and (now - ws) > 600:
                    stale.append(k)
        for k in stale:
            del _LOCAL_ABUSE_COUNTERS[k]
        # Hard cap on counters
        if len(_LOCAL_ABUSE_COUNTERS) > _ABUSE_COUNTER_MAX_ENTRIES:
            by_ws = sorted(_LOCAL_ABUSE_COUNTERS,
                           key=lambda k: (_LOCAL_ABUSE_COUNTERS.get(k) or {}).get("window_start", 0))
            for k in by_ws[:len(by_ws) - _ABUSE_COUNTER_MAX_ENTRIES]:
                del _LOCAL_ABUSE_COUNTERS[k]

        # Prune stale throttle buckets (keys contain minute_bucket; older than 5 min ago)
        current_bucket = int(now) // 60
        stale_throttle = [k for k in _LOCAL_USER_THROTTLE
                          if _extract_minute_bucket(k) < current_bucket - 5]
        for k in stale_throttle:
            del _LOCAL_USER_THROTTLE[k]
        # Hard cap on throttle dict
        if len(_LOCAL_USER_THROTTLE) > _THROTTLE_MAX_ENTRIES:
            sorted_keys = sorted(_LOCAL_USER_THROTTLE,
                                 key=lambda k: _extract_minute_bucket(k))
            for k in sorted_keys[:len(sorted_keys) - _THROTTLE_MAX_ENTRIES]:
                del _LOCAL_USER_THROTTLE[k]


# ── Circuit breaker for external services ────────────────────────────────
_CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
_CB_COOLDOWN_SECONDS = float(os.getenv("CB_COOLDOWN_SECONDS", "30"))
_circuit_breaker_state: dict[str, dict] = {}  # service -> {failures, last_failure, open_until}
_cb_lock = _threading.Lock()


def _cb_record_failure(service: str) -> None:
    """Record a failure for *service*. Opens circuit if threshold exceeded."""
    now = time.time()
    opened = False
    with _cb_lock:
        state = _circuit_breaker_state.setdefault(service, {"failures": 0, "last_failure": 0, "open_until": 0})
        state["failures"] += 1
        state["last_failure"] = now
        if state["failures"] >= _CB_FAILURE_THRESHOLD:
            state["open_until"] = now + _CB_COOLDOWN_SECONDS
            opened = True
            logging.getLogger("app.guard").warning(
                "circuit_breaker:open service=%s failures=%d cooldown=%.0fs",
                service, state["failures"], _CB_COOLDOWN_SECONDS)
    if opened:
        try:
            GUARD_CIRCUIT_BREAKER_TRIPS.labels(service=service).inc()
            BREAKER_OPEN.labels(service=service).set(1)
        except Exception:
            pass


def _cb_record_success(service: str) -> None:
    """Reset failure counter for *service* on success."""
    with _cb_lock:
        if service in _circuit_breaker_state:
            _circuit_breaker_state[service] = {"failures": 0, "last_failure": 0, "open_until": 0}
    try:
        BREAKER_OPEN.labels(service=service).set(0)
    except Exception:
        pass


def _cb_is_open(service: str) -> bool:
    """Return True if the circuit is open (service should be skipped)."""
    with _cb_lock:
        state = _circuit_breaker_state.get(service)
        if not state:
            return False
        if state["open_until"] > time.time():
            return True
        # Cooldown expired: half-open → allow one attempt
        if state["failures"] >= _CB_FAILURE_THRESHOLD:
            state["failures"] = _CB_FAILURE_THRESHOLD - 1  # allow exactly one probe
        return False


# ── Guard-level metrics counters ────────────────────────────────────────
GUARD_REJECTIONS_TOTAL = _get_or_create_counter(
    "guard_rejections_total",
    "Total guard-level rejections by reason",
    labelnames=("reason",),
)
GUARD_CIRCUIT_BREAKER_TRIPS = _get_or_create_counter(
    "guard_circuit_breaker_trips_total",
    "Number of times a circuit breaker opened",
    labelnames=("service",),
)
GUARD_QUEUE_FULL = _get_or_create_counter(
    "guard_queue_full_total",
    "Number of requests rejected because the queue was full",
)
GUARD_CPU_REJECTIONS = _get_or_create_counter(
    "guard_cpu_rejections_total",
    "Number of requests rejected due to high CPU",
)
GUARD_CONCURRENCY_REJECTIONS = _get_or_create_counter(
    "guard_concurrency_rejections_total",
    "Number of requests rejected due to per-path concurrency cap",
    labelnames=("path",),
)
GUARD_SAFE_MODE_TRIGGERS = _get_or_create_counter(
    "guard_safe_mode_triggers_total",
    "Number of times auto safe-mode was triggered from guard layer",
)


def _metric_guard_reject(reason: str) -> None:
    try:
        GUARD_REJECTIONS_TOTAL.labels(reason=reason).inc()
    except Exception:
        pass
    try:
        _record_guard_rejection()
    except Exception:
        pass


def _metric_request(endpoint: str):
    try:
        ANALYSIS_REQUESTS_TOTAL.labels(endpoint=endpoint).inc()
    except Exception:
        pass


def _metric_error(endpoint: str, error_type: str):
    try:
        ANALYSIS_ERRORS_TOTAL.labels(endpoint=endpoint, error_type=error_type).inc()
    except Exception:
        pass


def _metric_quota_hit(endpoint: str, reason: str):
    try:
        QUOTA_HITS_TOTAL.labels(endpoint=endpoint, reason=reason).inc()
    except Exception:
        pass


def _metric_parse_latency(stage: str, seconds: float):
    try:
        PARSE_LATENCY.labels(stage=stage).observe(seconds)
    except Exception:
        pass


def _metric_fallback(stage: str):
    try:
        FALLBACK_TRIGGERS_TOTAL.labels(stage=stage).inc()
    except Exception:
        pass


def _metric_active_inc():
    try:
        ACTIVE_REQUESTS.inc()
    except Exception:
        pass


def _metric_active_dec():
    try:
        ACTIVE_REQUESTS.dec()
    except Exception:
        pass


# ── SRE: Additional Prometheus metrics ────────────────────────────────────
S3_ERRORS_TOTAL = _get_or_create_counter(
    "cv_s3_errors_total", "Total S3 operation errors",
)
JWT_FAILURES_TOTAL = _get_or_create_counter(
    "cv_jwt_failures_total", "Total JWT authentication failures",
)
REDIS_CONNECTED = _get_or_create_gauge(
    "cv_redis_connected", "Whether Redis is reachable (1=yes, 0=no)",
)
WORKER_RESTARTS_TOTAL = _get_or_create_counter(
    "cv_worker_restarts_total", "Total model worker auto-restarts",
)


# ── SRE: Alerting system ─────────────────────────────────────────────────
_alert_logger = logging.getLogger("app.alert")
_alert_cooldowns: dict[str, float] = {}
_alert_lock = _threading.Lock()
_ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))


def _alert(name: str, message: str, *, level: str = "critical") -> None:
    """Emit a rate-limited alert log.  Same alert suppressed for cooldown period."""
    now = time.time()
    with _alert_lock:
        last = _alert_cooldowns.get(name, 0.0)
        if now - last < _ALERT_COOLDOWN_SECONDS:
            return
        _alert_cooldowns[name] = now
    log_fn = getattr(_alert_logger, level, _alert_logger.critical)
    log_fn("ALERT:%s %s", name, message)


# ── SRE: Rate-limited logger ─────────────────────────────────────────────
_rl_log_state: dict[str, float] = {}
_rl_log_lock = _threading.Lock()
_RL_LOG_INTERVAL = float(os.getenv("RL_LOG_INTERVAL_SECONDS", "60"))


def _rate_limited_log(logger_obj, level: str, key: str, msg: str, *args) -> None:
    """Log at most once per _RL_LOG_INTERVAL for a given key."""
    now = time.time()
    with _rl_log_lock:
        last = _rl_log_state.get(key, 0.0)
        if now - last < _RL_LOG_INTERVAL:
            return
        _rl_log_state[key] = now
    getattr(logger_obj, level)(msg, *args)


# ── Ops: Feature flags (env-driven) ──────────────────────────────────────
FEATURE_OPTIMIZE = os.getenv("FEATURE_OPTIMIZE", "1").lower() not in ("0", "false", "no")
FEATURE_AUTO_FIX = os.getenv("FEATURE_AUTO_FIX", "1").lower() not in ("0", "false", "no")
FEATURE_SEMANTIC_SEARCH = os.getenv("FEATURE_SEMANTIC_SEARCH", "1").lower() not in ("0", "false", "no")
FEATURE_HTML_EXPORT = os.getenv("FEATURE_HTML_EXPORT", "1").lower() not in ("0", "false", "no")

# ── Ops: Maintenance mode ────────────────────────────────────────────────
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "").lower() in ("1", "true", "yes")

# ── Runtime: Live feature toggle store ───────────────────────────────────
# Mutable dict — can be changed at runtime via admin endpoints or reload thread.
_live_flags: dict[str, bool] = {
    "optimize": FEATURE_OPTIMIZE,
    "auto_fix": FEATURE_AUTO_FIX,
    "semantic_search": FEATURE_SEMANTIC_SEARCH,
    "html_export": FEATURE_HTML_EXPORT,
}
_live_flags_lock = _threading.Lock()
_LIVE_FLAGS_FILE = os.getenv("LIVE_FLAGS_FILE", "")


def _get_flag(name: str) -> bool:
    """Read a live feature flag (thread-safe)."""
    with _live_flags_lock:
        return _live_flags.get(name, True)


def _set_flag(name: str, value: bool) -> None:
    """Set a live feature flag and audit-log the change."""
    with _live_flags_lock:
        old = _live_flags.get(name)
        _live_flags[name] = value
    try:
        FLAG_ENABLED.labels(flag=name).set(1 if value else 0)
    except Exception:
        pass
    if old != value:
        _audit_event("feature_change", flag=name, old=old, new=value)
        try:
            ADMIN_ACTIONS_TOTAL.labels(action="flag_change").inc()
        except Exception:
            pass


def _reload_flags_from_file() -> None:
    """Reload flags from JSON file if configured (non-fatal)."""
    if not _LIVE_FLAGS_FILE:
        return
    try:
        with open(_LIVE_FLAGS_FILE, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        if not isinstance(data, dict):
            return
        with _live_flags_lock:
            for k, v in data.items():
                if k in _live_flags and isinstance(v, bool):
                    if _live_flags[k] != v:
                        _audit_event("feature_change", flag=k, old=_live_flags[k], new=v, source="file")
                    _live_flags[k] = v
    except Exception:
        pass


def _flag_reload_loop() -> None:
    """Background thread: reload flags every 5 seconds from file."""
    while True:
        time.sleep(5)
        _reload_flags_from_file()


if _LIVE_FLAGS_FILE:
    _threading.Thread(target=_flag_reload_loop, daemon=True).start()


# ── Runtime: Global kill switch ──────────────────────────────────────────
_kill_switch = os.getenv("KILL_SWITCH", "").lower() in ("1", "true", "yes")
_kill_switch_lock = _threading.Lock()


def _is_killed() -> bool:
    with _kill_switch_lock:
        return _kill_switch


def _set_kill_switch(val: bool) -> None:
    global _kill_switch
    with _kill_switch_lock:
        old = _kill_switch
        _kill_switch = val
    if old != val:
        _audit_event("kill_switch", enabled=val)
        try:
            ADMIN_ACTIONS_TOTAL.labels(action="kill_switch").inc()
        except Exception:
            pass


# ── Runtime: Traffic drain mode ──────────────────────────────────────────
_drain_mode = False
_drain_lock = _threading.Lock()


def _is_draining() -> bool:
    with _drain_lock:
        return _drain_mode


def _set_drain(val: bool) -> None:
    global _drain_mode
    with _drain_lock:
        old = _drain_mode
        _drain_mode = val
    if old != val:
        _audit_event("drain_mode", enabled=val)
        try:
            ADMIN_ACTIONS_TOTAL.labels(action="drain").inc()
        except Exception:
            pass


# ── Runtime: In-flight request counter (for safe restart) ────────────────
_inflight_count = 0
_inflight_lock = _threading.Lock()


def _inflight_inc() -> None:
    global _inflight_count
    with _inflight_lock:
        _inflight_count += 1


def _inflight_dec() -> None:
    global _inflight_count
    with _inflight_lock:
        _inflight_count = max(0, _inflight_count - 1)


def _inflight_get() -> int:
    with _inflight_lock:
        return _inflight_count


# ── Runtime: Panic mode ──────────────────────────────────────────────────
_panic_mode = False
_panic_lock = _threading.Lock()
_PANIC_ERROR_THRESHOLD = int(os.getenv("PANIC_ERROR_THRESHOLD", "20"))
_PANIC_ERROR_WINDOW = float(os.getenv("PANIC_ERROR_WINDOW", "60"))
_panic_error_timestamps: list[float] = []


def _is_panic() -> bool:
    with _panic_lock:
        return _panic_mode


def _record_error_for_panic() -> None:
    """Track error timestamps and trigger panic if rate is too high."""
    global _panic_mode
    now = time.time()
    with _panic_lock:
        _panic_error_timestamps.append(now)
        cutoff = now - _PANIC_ERROR_WINDOW
        while _panic_error_timestamps and _panic_error_timestamps[0] < cutoff:
            _panic_error_timestamps.pop(0)
        if len(_panic_error_timestamps) >= _PANIC_ERROR_THRESHOLD and not _panic_mode:
            _panic_mode = True
            _audit_event("panic_mode", enabled=True, errors=len(_panic_error_timestamps))
            _alert("panic_mode", f"Panic triggered: {len(_panic_error_timestamps)} errors in {_PANIC_ERROR_WINDOW}s")
            try:
                PANIC_TRIGGERS_TOTAL.inc()
                PANIC_ACTIVE.set(1)
            except Exception:
                pass
            # Open circuit breakers for all services
            for svc in ("s3", "redis", "db", "worker"):
                _cb_record_failure(svc)
            # Disable heavy features
            _set_flag("optimize", False)
            _set_flag("auto_fix", False)


def _clear_panic() -> None:
    """Reset panic mode (admin action)."""
    global _panic_mode
    with _panic_lock:
        _panic_mode = False
        _panic_error_timestamps.clear()
    _audit_event("panic_mode", enabled=False, action="manual_reset")
    try:
        PANIC_ACTIVE.set(0)
    except Exception:
        pass


# ── Runtime: Audit event logger ──────────────────────────────────────────
_audit_rt_logger = logging.getLogger("app.audit.runtime")


def _audit_event(event: str, **kwargs) -> None:
    """Log a structured audit event for runtime control changes."""
    _audit_rt_logger.warning("AUDIT:%s %s", event, " ".join(f"{k}={v}" for k, v in kwargs.items()))


# ── Runtime: Request sampling (1%) ───────────────────────────────────────
import random as _random
_SAMPLE_RATE = float(os.getenv("REQUEST_SAMPLE_RATE", "0.01"))
_sample_logger = logging.getLogger("app.sample")


# ── Runtime: Admin token ─────────────────────────────────────────────────
_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_admin_token(request: Request) -> bool:
    """Validate admin bearer token from Authorization header."""
    if not _ADMIN_TOKEN:
        return False
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth[7:].strip(), _ADMIN_TOKEN)

# ── Ops: Blue/Green readiness gate ───────────────────────────────────────
_app_ready = False
_app_ready_lock = _threading.Lock()

# ── Ops: Debug safety ────────────────────────────────────────────────────
if os.getenv("DEBUG", "").lower() in ("1", "true", "yes") and _ENV_MODE in ("production", "prod"):
    raise RuntimeError("FATAL: DEBUG=true is not allowed in production. Refusing to start.")

# ── Ops: Dependency latency histograms ───────────────────────────────────
DEP_LATENCY = _get_or_create_histogram(
    "cv_dependency_latency_seconds",
    "Latency of dependency calls (db, redis, s3, worker)",
    labelnames=("dependency",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def _observe_dep(dep: str, start: float) -> None:
    """Record dependency call latency."""
    try:
        DEP_LATENCY.labels(dependency=dep).observe(time.time() - start)
    except Exception:
        pass


# CORS middleware
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
]

if _ENV_MODE in ("production", "prod"):
    # Production: only explicit origins, NO localhost regex
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins or ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID", "X-Trace-ID"],
    )
else:
    # Development: allow localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "https://localhost:5173",
            "https://127.0.0.1:5173",
            "https://localhost:5174",
            "https://127.0.0.1:5174",
        ] + _cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID", "X-Trace-ID"],
    )

# Serve only the built frontend assets under /static (never the project root).
_static_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# Security headers middleware
import uuid as _uuid

@app.middleware("http")
async def add_security_headers(request, call_next):
    # ── Ops: Request tracing — generate or propagate request_id ──
    req_id = request.headers.get("X-Request-ID") or _uuid.uuid4().hex[:16]
    request.state.request_id = req_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'none'; object-src 'none'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def read_root():
    """Root endpoint for health checks and basic landing."""
    return JSONResponse(
        content={
            "status": "online",
            "mode": "private" if os.getenv("STORAGE_BACKEND") == "local" else "cloud",
            "message": "CV Analyzer API is running. Access frontend via http://localhost:5173 or /static"
        }
    )


# ── Production guard middleware ──────────────────────────────────────────
@app.middleware("http")
async def production_guard_middleware(request: Request, call_next):
    """Enforce global IP rate, concurrency, timeout, memory, CPU, queue, body size."""
    path = request.url.path

    # Skip health / readiness / liveness / admin probes
    _passthrough = ("/", "/health", "/readiness", "/liveness", "/health/full", "/ready", "/metrics")
    if path in _passthrough or path.startswith("/admin/"):
        return await call_next(request)

    # Let CORS preflight through — browser OPTIONS must reach CORSMiddleware
    if request.method == "OPTIONS":
        return await call_next(request)

    # ── Ops: Blue/green readiness gate — reject all traffic until startup complete ──
    if not _app_ready:
        return JSONResponse(status_code=503, content={"detail": "Server starting up"})

    # ── Runtime: Global kill switch — reject everything except health/admin ──
    if _is_killed():
        return JSONResponse(status_code=503, content={"detail": "Service disabled (kill switch)"})

    # ── Runtime: Traffic drain mode — reject new requests ──
    if _is_draining():
        return JSONResponse(status_code=503, content={"detail": "Service draining"})

    # ── Runtime: Panic mode — reject heavy endpoints ──
    if _is_panic() and path in _HEAVY_ENDPOINTS:
        _metric_guard_reject("panic_mode")
        return JSONResponse(status_code=503, content={"detail": "Service in panic mode"})

    # ── Ops: Maintenance mode ──
    if MAINTENANCE_MODE:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service under maintenance. Please retry later."},
        )

    # ── Ops: API version safety — reject unknown /api/vN prefixes ──
    if path.startswith("/api/"):
        if not path.startswith("/api/v1/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Unsupported API version"},
            )

    # ── Ops: Circuit breaker gate — reject heavy ops when dependency breaker open ──
    if path in _HEAVY_ENDPOINTS:
        _open_breakers = [s for s in ("s3", "redis", "db", "worker") if _cb_is_open(s)]
        if _open_breakers:
            _guard_logger.warning("guard:circuit_breaker_reject path=%s open=%s", path, _open_breakers)
            _metric_guard_reject("circuit_breaker")
            return JSONResponse(
                status_code=503,
                content={"detail": f"Service degraded (circuit open: {', '.join(_open_breakers)})"},
            )

    # ── SRE: Safe mode gate — reject heavy ops when critical services are down ──
    if path in _HEAVY_ENDPOINTS and _is_safe_mode():
        _guard_logger.warning("guard:safe_mode_reject path=%s", path)
        _metric_guard_reject("safe_mode")
        return JSONResponse(
            status_code=503,
            content={"detail": "Service in safe mode. Please retry later."},
        )

    # ── Large request body guard ──
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_REQUEST_BODY_BYTES:
        _guard_logger.warning(
            "guard:large_request ip=%s path=%s bytes=%s",
            request.client.host if request.client else "?", path, content_length,
        )
        _metric_guard_reject("large_request")
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})

    # ── Per-IP global rate limit ──
    client_ip = request.client.host if request.client else None
    if client_ip and not _ip_global_rate_ok(client_ip):
        _guard_logger.warning("guard:ip_global_rate ip=%s path=%s", client_ip, path)
        _metric_guard_reject("ip_global_rate")
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})

    # ── CPU guard for heavy endpoints ──
    if path in _HEAVY_ENDPOINTS:
        cpu = _get_cpu_percent()
        if cpu > _CPU_USAGE_LIMIT:
            _guard_logger.warning("guard:cpu_pressure cpu=%.1f%% limit=%.0f%% path=%s", cpu, _CPU_USAGE_LIMIT, path)
            _metric_guard_reject("cpu_pressure")
            try:
                GUARD_CPU_REJECTIONS.inc()
            except Exception:
                pass
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable (CPU pressure)"},
            )

    # ── Memory guard for heavy endpoints ──
    if path in _HEAVY_ENDPOINTS:
        rss = _get_rss_bytes()
        if rss > 0 and rss > _MEMORY_RSS_LIMIT_BYTES:
            _guard_logger.warning(
                "guard:memory_pressure rss_mb=%d limit_mb=%d path=%s",
                rss // (1024 * 1024), _MEMORY_RSS_LIMIT_MB, path,
            )
            _metric_guard_reject("memory_pressure")
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable (memory pressure)"},
            )

    # ── Request queue (backpressure) ──
    if path in _HEAVY_ENDPOINTS:
        if not _request_queue.locked():
            pass  # queue has room
        try:
            await asyncio.wait_for(_request_queue.acquire(), timeout=0.05)
        except asyncio.TimeoutError:
            _guard_logger.warning("guard:queue_full path=%s", path)
            _metric_guard_reject("queue_full")
            try:
                GUARD_QUEUE_FULL.inc()
            except Exception:
                pass
            return JSONResponse(
                status_code=503,
                content={"detail": "Server queue full. Please retry shortly."},
            )
    else:
        # Non-heavy: no queue gating
        pass

    queue_acquired = path in _HEAVY_ENDPOINTS

    try:
        # ── Global semaphore concurrency guard ──
        try:
            await asyncio.wait_for(_global_semaphore.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            _guard_logger.warning("guard:concurrency_full path=%s", path)
            _metric_guard_reject("concurrency_full")
            return JSONResponse(
                status_code=503,
                content={"detail": "Server at capacity. Please retry shortly."},
            )

        # ── Per-path concurrency guard ──
        path_sem = _path_semaphores.get(path)
        path_sem_acquired = False
        if path_sem is not None:
            try:
                await asyncio.wait_for(path_sem.acquire(), timeout=0.05)
                path_sem_acquired = True
            except asyncio.TimeoutError:
                _guard_logger.warning("guard:path_concurrency path=%s", path)
                _metric_guard_reject("path_concurrency")
                try:
                    GUARD_CONCURRENCY_REJECTIONS.labels(path=path).inc()
                except Exception:
                    pass
                _global_semaphore.release()
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Too many concurrent requests for this endpoint"},
                )

        try:
            # ── Per-path timeout ──
            timeout = _PATH_TIMEOUTS.get(path, _REQUEST_TIMEOUT_SECONDS)
            try:
                response = await asyncio.wait_for(
                    call_next(request),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                _guard_logger.warning(
                    "guard:request_timeout path=%s timeout_s=%.0f",
                    path, timeout,
                )
                _metric_guard_reject("timeout")
                try:
                    TIMEOUTS_TOTAL.inc()
                except Exception:
                    pass
                _alert("timeout_spike", f"Request timeout on {path} ({timeout}s)", level="warning")
                return JSONResponse(
                    status_code=504,
                    content={"detail": "Request timed out"},
                )
        finally:
            if path_sem_acquired:
                path_sem.release()
            _global_semaphore.release()

    finally:
        if queue_acquired:
            _request_queue.release()

    return response

# ── Log flood protection ──────────────────────────────────────────────────
_MAX_LOG_LINE_LEN = 500
_MAX_LOGS_PER_REQUEST = 50
_request_log_counts: dict[str, int] = {}
_request_log_lock = __import__("threading").Lock()


def _safe_log_message(msg: str) -> str:
    """Truncate a log message to prevent log flooding."""
    if len(msg) > _MAX_LOG_LINE_LEN:
        return msg[:_MAX_LOG_LINE_LEN] + "...[truncated]"
    return msg


# ── Global exception handler — never expose stacktraces ───────────────────
_security_logger = logging.getLogger("app.security")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions, log internally, return safe message."""
    _security_logger.exception(
        "unhandled_exception: %s %s — %s",
        request.method,
        request.url.path,
        _safe_log_message(str(exc)),
    )
    try:
        ERRORS_TOTAL.inc()
    except Exception:
        pass
    _alert("error_spike", f"Unhandled exception on {request.url.path}: {type(exc).__name__}")
    _record_error_for_panic()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Forward HTTP exceptions but sanitize detail length."""
    detail = str(exc.detail or "Error")
    if len(detail) > _MAX_LOG_LINE_LEN:
        detail = detail[:_MAX_LOG_LINE_LEN]
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
    )


logger = logging.getLogger("app.access")
audit_logger = logging.getLogger("app.audit")
_guard_logger = logging.getLogger("app.guard")

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING GUARDS
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import threading as _threading

# ── 1. Per-IP global request limit (beyond per-endpoint) ─────────────────
_IP_GLOBAL_LIMIT_PER_MIN = int(os.getenv("IP_GLOBAL_LIMIT_PER_MIN", "60"))
_RATE_DICT_MAX_KEYS = int(os.getenv("RATE_DICT_MAX_KEYS", "10000"))
_ip_global_counts: dict[str, list[float]] = {}
_ip_global_lock = _threading.Lock()


def _prune_rate_bucket(bucket: dict[str, list[float]], lock: _threading.Lock,
                       cutoff: float) -> None:
    """Remove empty/stale keys from a rate-tracking dict (under lock)."""
    with lock:
        stale = [k for k, ts in bucket.items() if not ts or ts[-1] < cutoff]
        for k in stale:
            del bucket[k]
        # Hard cap: if still too many keys, drop oldest half
        if len(bucket) > _RATE_DICT_MAX_KEYS:
            by_last = sorted(bucket, key=lambda k: bucket[k][-1] if bucket[k] else 0)
            for k in by_last[:len(by_last) // 2]:
                del bucket[k]


def _ip_global_rate_ok(client_ip: str) -> bool:
    """Return True if *client_ip* hasn't exceeded global per-min budget."""
    if _IP_GLOBAL_LIMIT_PER_MIN <= 0 or not client_ip:
        return True
    now = time.time()
    cutoff = now - 60
    with _ip_global_lock:
        ts = _ip_global_counts.get(client_ip)
        if ts is None:
            ts = []
            _ip_global_counts[client_ip] = ts
        # Prune old entries
        while ts and ts[0] < cutoff:
            ts.pop(0)
        # Remove key if empty (prevent dict leak)
        if not ts and len(ts) == 0:
            _ip_global_counts.pop(client_ip, None)
        if len(ts) >= _IP_GLOBAL_LIMIT_PER_MIN:
            return False
        ts.append(now)
        return True


# ── 2. Per-user global request limit (API key abuse) ─────────────────────
_USER_GLOBAL_LIMIT_PER_MIN = int(os.getenv("USER_GLOBAL_LIMIT_PER_MIN", "30"))
_user_global_counts: dict[str, list[float]] = {}
_user_global_lock = _threading.Lock()


def _user_global_rate_ok(user_id: str) -> bool:
    """Return True if *user_id* hasn't exceeded global per-min budget."""
    if _USER_GLOBAL_LIMIT_PER_MIN <= 0 or not user_id:
        return True
    now = time.time()
    cutoff = now - 60
    with _user_global_lock:
        ts = _user_global_counts.get(user_id)
        if ts is None:
            ts = []
            _user_global_counts[user_id] = ts
        while ts and ts[0] < cutoff:
            ts.pop(0)
        if not ts:
            _user_global_counts.pop(user_id, None)
        if len(ts) >= _USER_GLOBAL_LIMIT_PER_MIN:
            return False
        ts.append(now)
        return True


# ── 3. Global async semaphore (concurrency spike guard) ──────────────────
_GLOBAL_CONCURRENCY_LIMIT = int(os.getenv("GLOBAL_CONCURRENCY_LIMIT", "20"))
_global_semaphore = asyncio.Semaphore(_GLOBAL_CONCURRENCY_LIMIT)

# ── 3a. Per-path concurrency caps ───────────────────────────────────────
_PATH_CONCURRENCY: dict[str, int] = {
    "/api/v1/analyze": int(os.getenv("CONCURRENCY_ANALYZE", "10")),
    "/api/v1/analyze-pdf": int(os.getenv("CONCURRENCY_ANALYZE_PDF", "8")),
    "/api/v1/cv-builder/generate": int(os.getenv("CONCURRENCY_CV_BUILDER", "10")),
    "/api/v1/rewrite/cv": int(os.getenv("CONCURRENCY_REWRITE", "5")),
    "/api/v1/cv/auto-fix": int(os.getenv("CONCURRENCY_OPTIMIZE", "5")),
    "/api/v1/cv/rewrite": int(os.getenv("CONCURRENCY_OPTIMIZE", "5")),
    "/api/v1/cv/optimize-keywords": int(os.getenv("CONCURRENCY_OPTIMIZE", "5")),
    "/api/v1/embeddings/index-cv": int(os.getenv("CONCURRENCY_EMBED", "6")),
    "/api/v1/embeddings/index-job": int(os.getenv("CONCURRENCY_EMBED", "6")),
    "/api/v1/embeddings/find-candidates": int(os.getenv("CONCURRENCY_EMBED", "6")),
    "/api/v1/embeddings/find-jobs": int(os.getenv("CONCURRENCY_EMBED", "6")),
}
_path_semaphores: dict[str, asyncio.Semaphore] = {
    p: asyncio.Semaphore(c) for p, c in _PATH_CONCURRENCY.items()
}

# ── 3b. Small request queue (bounded backpressure for heavy endpoints) ──
_REQUEST_QUEUE_SIZE = int(os.getenv("REQUEST_QUEUE_SIZE", "100"))
_request_queue = asyncio.Semaphore(_REQUEST_QUEUE_SIZE)


# ── 4. Request timeout guard (seconds) ──────────────────────────────────
_REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "600"))  # 10 minutes for batch processing
# Per-path overrides: heavy endpoints get shorter timeouts
_PATH_TIMEOUTS: dict[str, float] = {
    "/api/v1/analyze": float(os.getenv("TIMEOUT_ANALYZE", "60")),
    "/api/v1/analyze-pdf": float(os.getenv("TIMEOUT_ANALYZE_PDF", "60")),
    "/api/v1/analyze-async": float(os.getenv("TIMEOUT_ANALYZE_ASYNC", "30")),
    "/api/v1/cv-builder/generate": float(os.getenv("TIMEOUT_CV_BUILDER", "90")),
    "/api/v1/rewrite/cv": float(os.getenv("TIMEOUT_REWRITE", "60")),
    "/api/v1/cv/auto-fix": float(os.getenv("TIMEOUT_OPTIMIZE", "10")),
    "/api/v1/cv/rewrite": float(os.getenv("TIMEOUT_OPTIMIZE", "10")),
    "/api/v1/cv/optimize-keywords": float(os.getenv("TIMEOUT_OPTIMIZE", "10")),
    "/api/v1/embeddings/index-cv": float(os.getenv("TIMEOUT_EMBED", "30")),
    "/api/v1/embeddings/index-job": float(os.getenv("TIMEOUT_EMBED", "30")),
    "/api/v1/embeddings/find-candidates": float(os.getenv("TIMEOUT_EMBED", "30")),
    "/api/v1/embeddings/find-jobs": float(os.getenv("TIMEOUT_EMBED", "30")),
    "/api/v1/recruiter/search": float(os.getenv("TIMEOUT_SEARCH", "15")),
}


# ── 4a. CPU guard ─────────────────────────────────────────────────────────
_CPU_USAGE_LIMIT = float(os.getenv("CPU_USAGE_LIMIT", "90"))  # percent
_cpu_last_check: float = 0.0
_cpu_last_value: float = 0.0
_CPU_CHECK_INTERVAL = 5.0  # seconds between actual psutil calls


def _get_cpu_percent() -> float:
    """Return system CPU usage (0-100). Cached for _CPU_CHECK_INTERVAL seconds."""
    global _cpu_last_check, _cpu_last_value
    now = time.time()
    if now - _cpu_last_check < _CPU_CHECK_INTERVAL:
        return _cpu_last_value
    try:
        import psutil
        _cpu_last_value = psutil.cpu_percent(interval=0)
    except Exception:
        _cpu_last_value = 0.0
    _cpu_last_check = now
    return _cpu_last_value


# ── 5. Memory guard (bytes) — reject new heavy requests when RSS high ───
_MEMORY_RSS_LIMIT_MB = int(os.getenv("MEMORY_RSS_LIMIT_MB", "1024"))
_MEMORY_RSS_LIMIT_BYTES = _MEMORY_RSS_LIMIT_MB * 1024 * 1024
_HEAVY_ENDPOINTS = frozenset({
    "/api/v1/analyze", "/api/v1/analyze-pdf", "/api/v1/analyze-async",
    "/api/v1/cv-builder/generate", "/api/v1/rewrite/cv",
    "/api/v1/cv/auto-fix", "/api/v1/cv/rewrite", "/api/v1/cv/optimize-keywords",
    "/api/v1/embeddings/index-cv", "/api/v1/embeddings/find-candidates",
})


def _get_rss_bytes() -> int:
    """Return process RSS in bytes (best-effort, 0 on failure)."""
    try:
        import psutil
        return psutil.Process().memory_info().rss
    except Exception:
        pass
    # Linux fallback: /proc/self/status
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024  # KiB → bytes
    except Exception:
        pass
    return 0


# ── 6. Request deduplication cache (repeated request guard) ──────────────
_DEDUP_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW_SECONDS", "5"))
_dedup_cache: dict[str, float] = {}
_dedup_lock = _threading.Lock()
_DEDUP_MAX_ENTRIES = 10_000


def _is_duplicate_request(fingerprint: str) -> bool:
    """Return True if an identical request fingerprint was seen recently."""
    if _DEDUP_WINDOW_SECONDS <= 0 or not fingerprint:
        return False
    now = time.time()
    cutoff = now - _DEDUP_WINDOW_SECONDS
    with _dedup_lock:
        # Always prune stale entries first
        stale = [k for k, v in _dedup_cache.items() if v < cutoff]
        for k in stale:
            del _dedup_cache[k]
        # Hard cap: reject insert if still at max (prevent unbounded growth)
        prev = _dedup_cache.get(fingerprint)
        if prev is not None and prev > cutoff:
            return True
        if len(_dedup_cache) >= _DEDUP_MAX_ENTRIES:
            return False  # drop silently rather than grow past limit
        _dedup_cache[fingerprint] = now
        return False


def _make_dedup_key(request: Request, body_sample: bytes = b"") -> str:
    """Create a dedup fingerprint from IP + path + method + body prefix."""
    ip = request.client.host if request.client else ""
    raw = f"{ip}|{request.method}|{request.url.path}|{body_sample[:256].hex()}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── 7. Per-user embedding call limiter (embedding spam) ──────────────────
_USER_EMBED_LIMIT_PER_MIN = int(os.getenv("USER_EMBED_LIMIT_PER_MIN", "15"))
_user_embed_counts: dict[str, list[float]] = {}
_user_embed_lock = _threading.Lock()


def _user_embed_rate_ok(user_id: str) -> bool:
    """Return True if user hasn't exceeded embedding call budget."""
    if _USER_EMBED_LIMIT_PER_MIN <= 0 or not user_id:
        return True
    now = time.time()
    cutoff = now - 60
    with _user_embed_lock:
        ts = _user_embed_counts.get(user_id)
        if ts is None:
            ts = []
            _user_embed_counts[user_id] = ts
        while ts and ts[0] < cutoff:
            ts.pop(0)
        if not ts:
            _user_embed_counts.pop(user_id, None)
        if len(ts) >= _USER_EMBED_LIMIT_PER_MIN:
            return False
        ts.append(now)
        return True


# ── 8. Search abuse guard ────────────────────────────────────────────────
_SEARCH_LIMIT_PER_MIN = int(os.getenv("SEARCH_LIMIT_PER_MIN", "30"))
_MAX_SEARCH_QUERY_LEN = int(os.getenv("MAX_SEARCH_QUERY_LEN", "500"))
_search_counts: dict[str, list[float]] = {}
_search_lock = _threading.Lock()


def _search_rate_ok(user_id: str) -> bool:
    """Return True if user hasn't exceeded search call budget."""
    if _SEARCH_LIMIT_PER_MIN <= 0 or not user_id:
        return True
    now = time.time()
    cutoff = now - 60
    with _search_lock:
        ts = _search_counts.get(user_id)
        if ts is None:
            ts = []
            _search_counts[user_id] = ts
        while ts and ts[0] < cutoff:
            ts.pop(0)
        if not ts:
            _search_counts.pop(user_id, None)
        if len(ts) >= _SEARCH_LIMIT_PER_MIN:
            return False
        ts.append(now)
        return True


# ── 9. Large allocation guard ────────────────────────────────────────────
_MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1024 * 1024 * 1024)))  # 1 GB
_MAX_RESPONSE_BODY_BYTES = int(os.getenv("MAX_RESPONSE_BODY_BYTES", str(50 * 1024 * 1024)))  # 50 MB


# ── 10. FastAPI dependency: per-user global rate guard ───────────────────
_ABUSE_BAN_SECONDS = int(os.getenv("ABUSE_BAN_SECONDS", "300"))  # 5-min ban


def _escalate_abuse_ban(request: Request, uid: str, reason: str) -> None:
    """Escalate a rate-limit violation to a timed abuse ban."""
    ip = getattr(request, "client", None)
    client_ip = ip.host if ip else None
    fp = uid  # fingerprint: use UID as proxy
    try:
        _set_abuse_ban(client_ip, fp, _ABUSE_BAN_SECONDS)
    except Exception:
        pass
    _guard_logger.warning("guard:abuse_ban_escalated reason=%s user=%s ip=%s", reason, uid, client_ip)


def require_user_global_rate(request: Request, user=Depends(verify_supabase_jwt)):
    """Reject if the user has exceeded global request budget."""
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _user_global_rate_ok(uid):
        _guard_logger.warning("guard:user_global_rate user=%s path=%s", uid, request.url.path)
        _escalate_abuse_ban(request, uid, "user_global_rate")
        raise HTTPException(status_code=429, detail="User request budget exceeded")
    return user


# ── 11. FastAPI dependency: per-user embedding spam guard ────────────────
def require_embed_rate(request: Request, user=Depends(verify_supabase_jwt)):
    """Reject if user has exceeded per-user embedding budget."""
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _user_embed_rate_ok(uid):
        _guard_logger.warning("guard:embed_spam user=%s", uid)
        _escalate_abuse_ban(request, uid, "embed_spam")
        raise HTTPException(status_code=429, detail="Embedding rate limit exceeded")
    return user


# ── 12. FastAPI dependency: search abuse guard ───────────────────────────
def require_search_rate(request: Request, user=Depends(verify_supabase_jwt)):
    """Reject if user has exceeded search call budget."""
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _search_rate_ok(uid):
        _guard_logger.warning("guard:search_abuse user=%s", uid)
        _escalate_abuse_ban(request, uid, "search_abuse")
        raise HTTPException(status_code=429, detail="Search rate limit exceeded")
    return user


def audit_log(event_type: str, **fields):
    """Emit a structured audit log event.

    Used for security-sensitive actions such as CV uploads, analyses,
    and billing events. Downstream log aggregation (e.g. Cloudflare,
    Loki, Datadog) can consume these JSON lines.
    """

    try:
        payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **fields,
        }
        audit_logger.info("%s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Never break the request path because of logging issues.
        pass


def _append_feedback_record(record: dict):
    """Persist feedback as JSONL for lightweight bug triage in dev/prod."""
    try:
        feedback_path = os.path.join(os.path.dirname(__file__), "feedback_records.jsonl")
        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Feedback storage should not break API responses.
        pass


def _read_feedback_records(
    limit: int = 50,
    supabase_id: str | None = None,
    include_all: bool = False,
) -> list[dict]:
    """Read feedback JSONL records from disk, newest first."""
    feedback_path = os.path.join(os.path.dirname(__file__), "feedback_records.jsonl")
    if not os.path.exists(feedback_path):
        return []

    records: list[dict] = []
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    for raw in reversed(lines):
        if len(records) >= limit:
            break
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        if not include_all and supabase_id:
            if str(item.get("supabase_id") or "") != str(supabase_id):
                continue
        records.append(item)

    return records


def _env_bool(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def _send_feedback_email(record: dict) -> bool:
    """Send feedback notification mail if SMTP env vars are configured."""
    smtp_host = str(os.getenv("SMTP_HOST", "")).strip()
    try:
        smtp_port = int(str(os.getenv("SMTP_PORT", "587") or "587"))
    except Exception:
        smtp_port = 587
    smtp_user = str(os.getenv("SMTP_USER", "")).strip()
    smtp_pass = str(os.getenv("SMTP_PASS", "")).strip()
    smtp_from = str(
        os.getenv("FEEDBACK_EMAIL_FROM")
        or os.getenv("SMTP_FROM")
        or smtp_user
        or ""
    ).strip()
    smtp_to = str(
        os.getenv("FEEDBACK_EMAIL_TO")
        or os.getenv("SUPPORT_EMAIL")
        or "sikayet.cvanalizor@gmail.com"
        or ""
    ).strip()

    if not smtp_host or not smtp_from or not smtp_to:
        return False

    use_ssl = _env_bool("SMTP_USE_SSL", default=False)
    use_tls = _env_bool("SMTP_USE_TLS", default=True)

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    sender_email = str(record.get("email") or "").strip()
    if sender_email and "@" in sender_email:
        msg["Reply-To"] = sender_email
    msg["Subject"] = (
        f"[CV Analyzer][Feedback] {record.get('category', 'other')} - {record.get('email', 'unknown')}"
    )

    body = [
        "New feedback submitted:",
        "",
        f"Timestamp: {record.get('timestamp', '-')}",
        f"Category: {record.get('category', '-')}",
        f"Sender Email: {record.get('email', '-')}",
        f"User ID: {record.get('user_id', '-')}",
        f"Supabase ID: {record.get('supabase_id', '-')}",
        f"Page: {record.get('page', '-')}",
        f"Language: {record.get('lang', '-')}",
        f"Score: {record.get('score', '-')}",
        "",
        "Message:",
        str(record.get("message", "")),
        "",
        "Context:",
        json.dumps(record.get("context") or {}, ensure_ascii=False, indent=2),
    ]
    msg.set_content("\n".join(body))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        with server:
            if not use_ssl and use_tls:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("feedback email send failed")
        return False


def track_event(event_name: str, **fields):
    """Emit product analytics events via the existing structured audit logger."""

    try:
        payload = {
            "event_name": event_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **fields,
        }
        audit_log("product_event", **payload)
    except Exception:
        # Event tracking must never block request processing.
        pass


def _extract_client_ip(request: Request) -> str | None:
    """Best-effort client IP extraction, aware of proxies.

    In production behind Cloudflare or a reverse proxy, set
    TRUSTED_PROXY_COUNT>0 so X-Forwarded-For is honored.
    """

    trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "0") or "0")
    xff = request.headers.get("X-Forwarded-For")
    if trusted_proxy_count > 0 and xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            # left-most IP is original client in standard XFF semantics
            return parts[0]
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        return client.host
    return None


_BLOCKED_IPS = {
    ip.strip()
    for ip in os.getenv("BLOCKED_IPS", "").split(",")
    if ip.strip()
}

ABUSE_PROTECTION_ENABLED = os.getenv("ABUSE_PROTECTION_ENABLED", "1").lower() in (
    "1",
    "true",
    "yes",
)
ABUSE_SCORE_BLOCK_THRESHOLD = int(os.getenv("ABUSE_SCORE_BLOCK_THRESHOLD", "100"))
ABUSE_SCORE_AUDIT_THRESHOLD = int(os.getenv("ABUSE_SCORE_AUDIT_THRESHOLD", "60"))
ABUSE_BAN_SECONDS = int(os.getenv("ABUSE_BAN_SECONDS", "900"))
ABUSE_FINGERPRINT_WINDOW_SECONDS = int(
    os.getenv("ABUSE_FINGERPRINT_WINDOW_SECONDS", "600")
)
ABUSE_BURST_SOFT_LIMIT = int(os.getenv("ABUSE_BURST_SOFT_LIMIT", "20"))
ABUSE_BURST_HARD_LIMIT = int(os.getenv("ABUSE_BURST_HARD_LIMIT", "40"))

SENSITIVE_ABUSE_PATHS = {
    "/api/v1/analyze",
    "/api/v1/analyze-async",
    "/api/v1/analyze-pdf",
    "/api/v1/cv-builder/generate",
    "/api/v1/recruiter/batch-rank",
}


def _abuse_counter_key(fingerprint: str) -> str:
    window = max(1, int(ABUSE_FINGERPRINT_WINDOW_SECONDS))
    bucket = int(time.time()) // window
    return f"abuse:fp:{fingerprint}:{bucket}"


def _abuse_ban_key(kind: str, value: str) -> str:
    return f"abuse:ban:{kind}:{value}"


def _get_request_fingerprint(request: Request, client_ip: str | None = None) -> str:
    """Generate a low-cost fingerprint to detect repeated abuse attempts."""

    ip = client_ip or _extract_client_ip(request) or "unknown"
    ua = (request.headers.get("User-Agent") or "").strip().lower()
    lang = (request.headers.get("Accept-Language") or "").strip().lower()
    raw = "|".join([ip, ua, lang, request.method, request.url.path])
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _consume_abuse_fingerprint(fingerprint: str) -> dict:
    key = _abuse_counter_key(fingerprint)
    window = max(1, int(ABUSE_FINGERPRINT_WINDOW_SECONDS))

    if not redis_rate:
        now = time.time()
        current = _LOCAL_ABUSE_COUNTERS.get(key)
        if not current or float(current.get("expires_at", 0)) <= now:
            current = {"count": 0, "expires_at": now + window}
        current["count"] = int(current.get("count", 0)) + 1
        _LOCAL_ABUSE_COUNTERS[key] = current
        return {
            "key": key,
            "count": int(current["count"]),
            "window_seconds": window,
            "source": "memory",
        }

    try:
        count = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if count == 1 or ttl < 0:
            redis_rate.expire(key, window)
        return {
            "key": key,
            "count": count,
            "window_seconds": window,
            "source": "redis",
        }
    except Exception:
        now = time.time()
        current = _LOCAL_ABUSE_COUNTERS.get(key)
        if not current or float(current.get("expires_at", 0)) <= now:
            current = {"count": 0, "expires_at": now + window}
        current["count"] = int(current.get("count", 0)) + 1
        _LOCAL_ABUSE_COUNTERS[key] = current
        return {
            "key": key,
            "count": int(current["count"]),
            "window_seconds": window,
            "source": "memory",
        }


def _set_abuse_ban(client_ip: str | None, fingerprint: str, seconds: int) -> None:
    ttl = max(1, int(seconds))

    if redis_rate:
        try:
            if client_ip:
                redis_rate.setex(_abuse_ban_key("ip", client_ip), ttl, "1")
            redis_rate.setex(_abuse_ban_key("fp", fingerprint), ttl, "1")
            return
        except Exception:
            pass

    until = time.time() + ttl
    if client_ip:
        _LOCAL_ABUSE_BANS[_abuse_ban_key("ip", client_ip)] = until
    _LOCAL_ABUSE_BANS[_abuse_ban_key("fp", fingerprint)] = until


def _is_abuse_banned(client_ip: str | None, fingerprint: str | None) -> bool:
    keys = []
    if client_ip:
        keys.append(_abuse_ban_key("ip", client_ip))
    if fingerprint:
        keys.append(_abuse_ban_key("fp", fingerprint))
    if not keys:
        return False

    if redis_rate:
        try:
            for k in keys:
                raw = redis_rate.get(k)
                if raw:
                    return True
            return False
        except Exception:
            pass

    now = time.time()
    for k in keys:
        expires_at = float(_LOCAL_ABUSE_BANS.get(k, 0))
        if expires_at > now:
            return True
    return False


def _compute_abuse_risk_score(
    request: Request, client_ip: str | None, fingerprint_count: int
) -> int:
    score = 0
    ua = (request.headers.get("User-Agent") or "").lower()
    content_length = int(request.headers.get("Content-Length", "0") or "0")

    if not ua:
        score += 20

    suspicious_tokens = (
        "sqlmap",
        "scanner",
        "nikto",
        "nmap",
        "fuzzer",
        "bot",
        "crawler",
    )
    if any(token in ua for token in suspicious_tokens):
        score += 35

    if request.url.path in SENSITIVE_ABUSE_PATHS:
        score += 10

    if request.method not in ("GET", "POST", "OPTIONS"):
        score += 15

    if content_length > 5_000_000:
        score += 25

    if fingerprint_count > ABUSE_BURST_SOFT_LIMIT:
        score += 20
    if fingerprint_count > ABUSE_BURST_HARD_LIMIT:
        score += 45

    if client_ip and client_ip in _BLOCKED_IPS:
        score += 100

    return int(score)


def require_abuse_check(request: Request):
    """Risk-score based abuse prevention with temporary bans.

    Uses request fingerprinting and short-lived bans when risk threshold
    is exceeded. This complements static IP blocklists and rate limits.
    """

    if not ABUSE_PROTECTION_ENABLED:
        return None

    client_ip = _extract_client_ip(request)
    fingerprint = _get_request_fingerprint(request, client_ip)

    if _is_abuse_banned(client_ip, fingerprint):
        try:
            audit_log(
                "abuse_request_rejected",
                client_ip=client_ip,
                endpoint=request.url.path,
                method=request.method,
                reason="temporary_ban_active",
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=429,
            detail="Request blocked by abuse protection",
        )

    fp_usage = _consume_abuse_fingerprint(fingerprint)
    risk_score = _compute_abuse_risk_score(
        request=request,
        client_ip=client_ip,
        fingerprint_count=int(fp_usage.get("count", 0)),
    )

    request.state.abuse_risk_score = risk_score

    if risk_score >= ABUSE_SCORE_BLOCK_THRESHOLD:
        _set_abuse_ban(client_ip, fingerprint, ABUSE_BAN_SECONDS)
        try:
            audit_log(
                "abuse_request_blocked",
                client_ip=client_ip,
                endpoint=request.url.path,
                method=request.method,
                risk_score=risk_score,
                fingerprint_count=int(fp_usage.get("count", 0)),
                ban_seconds=ABUSE_BAN_SECONDS,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=429,
            detail="Request blocked by abuse protection",
        )

    if risk_score >= ABUSE_SCORE_AUDIT_THRESHOLD:
        try:
            audit_log(
                "abuse_risk_detected",
                client_ip=client_ip,
                endpoint=request.url.path,
                method=request.method,
                risk_score=risk_score,
                fingerprint_count=int(fp_usage.get("count", 0)),
            )
        except Exception:
            pass

    return None


@app.middleware("http")
async def ip_blocklist_middleware(request, call_next):
    """Simple IP blocklist for abuse prevention.

    Populate BLOCKED_IPS with comma-separated IPs in production or
    integrate with Cloudflare firewall rules for coarse-grained blocks.
    """
    path = request.url.path
    if path in ("/health", "/readiness", "/liveness"):
        return await call_next(request)

    try:
        client_ip = _extract_client_ip(request)
        if client_ip and client_ip in _BLOCKED_IPS:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        fingerprint = _get_request_fingerprint(request, client_ip)
        if _is_abuse_banned(client_ip, fingerprint):
            return JSONResponse(
                status_code=429,
                content={"detail": "Request blocked by abuse protection"},
            )
    except Exception:
        # On any failure, fall back to normal processing.
        pass
    return await call_next(request)


# Structured logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    _inflight_inc()
    start = time.time()
    try:
        response = await call_next(request)
    finally:
        _inflight_dec()
    duration = int((time.time() - start) * 1000)
    # Try to extract user info if available
    user = None
    try:
        user = getattr(request.state, "user", None)
    except Exception:
        user = None
    user_id = None
    organization_id = None
    plan_type = None
    if user:
        user_id = getattr(user, "id", None) or user.get("user_id")
        organization_id = getattr(user, "organization_id", None) or user.get(
            "organization_id"
        )
        plan_type = getattr(user, "plan_type", None) or user.get("plan_type")
    log_payload = {
        "request_id": getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID"),
        "user_id": user_id,
        "organization_id": organization_id,
        "plan_type": plan_type,
        "endpoint": request.url.path,
        "duration_ms": duration,
        "status_code": response.status_code,
    }
    logger.info("%s", json.dumps(log_payload, ensure_ascii=False))
    # ── Ops: Slow request log ──
    if duration > 1000:
        logging.getLogger("app.slow").warning(
            "slow_request path=%s duration_ms=%d status=%d request_id=%s",
            request.url.path, duration, response.status_code,
            log_payload["request_id"] or "-",
        )
    # ── Runtime: Request sampling ──
    if _random.random() < _SAMPLE_RATE:
        _sample_logger.info(
            "sample path=%s method=%s duration_ms=%d status=%d request_id=%s user_agent=%s",
            request.url.path, request.method, duration, response.status_code,
            log_payload["request_id"] or "-",
            (request.headers.get("user-agent") or "-")[:200],
        )
    return response


# Health check endpoint
@app.get("/api/v1/fonts")
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


@app.get("/health")
def health_check():
    # ── Ops: Blue/green — health must fail until startup complete ──
    if not _app_ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "detail": "Server not ready"},
        )

    # Update uptime gauge on every health/metrics scrape
    try:
        UPTIME_SECONDS.set(time.time() - _APP_START_TIME)
    except Exception:
        pass

    if MOCK_SERVICES_ON:
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
        if redis_rate is not None:
            redis_rate.ping()
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

    return {
        "status": overall,
        "build_id": BUILD_ID,
        "git_sha": GIT_SHA,
        "parser_build": PARSER_BUILD,
        "instance_id": INSTANCE_ID,
        **checks,
    }


# Readiness check endpoint
@app.get("/ready")
def readiness_check():
    if not _app_ready:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()
        return {"migration_head": head, "status": "ready"}
    except Exception as e:
        return {"status": "fail", "error": "internal readiness check failed"}


# Liveness probe (minimal, always returns 200 if the process is alive)
@app.get("/liveness")
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
@app.get("/health/full")
def health_full():
    """Extended health check with backup, metrics, and resource details."""
    base = health_check()

    # Backup age
    base["backup"] = _check_backup_age()

    # Uptime
    base["uptime_seconds"] = round(time.time() - _APP_START_TIME, 1)

    # Redis connected gauge
    base["redis_connected"] = redis_rate is not None
    try:
        if redis_rate:
            redis_rate.ping()
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

@app.get("/admin/status")
def admin_status(request: Request):
    """Runtime control status overview. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return {
        "app_ready": _app_ready,
        "kill_switch": _is_killed(),
        "drain_mode": _is_draining(),
        "panic_mode": _is_panic(),
        "inflight_requests": _inflight_get(),
        "maintenance_mode": MAINTENANCE_MODE,
        "uptime_seconds": round(time.time() - _APP_START_TIME, 1),
    }


@app.get("/admin/flags")
def admin_flags_get(request: Request):
    """Read live feature flags. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with _live_flags_lock:
        return dict(_live_flags)


@app.post("/admin/flags")
async def admin_flags_set(request: Request):
    """Update live feature flags. Body: {flag_name: bool}. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    changed = {}
    with _live_flags_lock:
        known = set(_live_flags.keys())
    for k, v in body.items():
        if k in known and isinstance(v, bool):
            _set_flag(k, v)
            changed[k] = v
    return {"updated": changed}


@app.post("/admin/kill-switch")
async def admin_kill_switch(request: Request):
    """Toggle kill switch. Body: {"enabled": bool}. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    val = body.get("enabled")
    if not isinstance(val, bool):
        return JSONResponse({"error": "enabled must be bool"}, status_code=400)
    _set_kill_switch(val)
    return {"kill_switch": val}


@app.post("/admin/drain")
async def admin_drain(request: Request):
    """Toggle drain mode. Body: {"enabled": bool}. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    val = body.get("enabled")
    if not isinstance(val, bool):
        return JSONResponse({"error": "enabled must be bool"}, status_code=400)
    _set_drain(val)
    return {"drain_mode": val}


@app.post("/admin/panic/clear")
def admin_panic_clear(request: Request):
    """Clear panic mode. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    _clear_panic()
    try:
        ADMIN_ACTIONS_TOTAL.labels(action="panic_clear").inc()
    except Exception:
        pass
    return {"panic_mode": False}


@app.get("/admin/breakers")
def admin_breakers_get(request: Request):
    """Read circuit breaker states. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    now = time.time()
    return {
        svc: {
            "failures": st.get("failures", 0),
            "open": st.get("open_until", 0) > now,
            "open_remaining_s": max(0, round(st.get("open_until", 0) - now, 1)),
        }
        for svc, st in _circuit_breaker_state.items()
    }


@app.post("/admin/breakers")
async def admin_breakers_reset(request: Request):
    """Reset a circuit breaker. Body: {"service": "name"}. Requires admin token."""
    if not _check_admin_token(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
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


@app.on_event("startup")
def _configure_logging():
    try:
        from logging_config import setup_logging
        setup_logging()
    except Exception:
        logging.getLogger("app.startup").warning("Log rotation setup skipped")


@app.on_event("startup")
def _ensure_new_tables():
    """Create new feature tables if they don't exist."""
    try:
        from sqlalchemy import inspect as sa_inspect
        from database import Base as _Base
        from models import UsageDaily, Favorite, JobTemplate, AnalysisShare, AnalysisNote, Reminder
        inspector = sa_inspect(engine)
        existing = set(inspector.get_table_names())
        tables_to_create = []
        for model in [UsageDaily, Favorite, JobTemplate, AnalysisShare, AnalysisNote, Reminder]:
            tname = model.__tablename__
            if tname not in existing:
                tables_to_create.append(model.__table__)
        if tables_to_create:
            _Base.metadata.create_all(engine, tables=tables_to_create)
            logging.getLogger("app.startup").info(
                f"Created tables: {[t.name for t in tables_to_create]}"
            )
    except Exception as e:
        logging.getLogger("app.startup").warning(f"Table auto-create skipped: {e}")


@app.on_event("startup")
def _validate_safe_defaults():
    """Ensure runtime control state is sane at startup — fix invalid combos."""
    _sd_logger = logging.getLogger("app.startup.safe_defaults")
    # Kill switch should start off unless explicitly set
    if _is_killed() and not os.getenv("KILL_SWITCH"):
        _set_kill_switch(False)
        _sd_logger.warning("safe_default: kill switch was on without env — reset to off")
    # Drain mode must be off at startup
    if _is_draining():
        _set_drain(False)
        _sd_logger.warning("safe_default: drain mode was on at startup — reset to off")
    # Panic should not persist across restarts
    if _is_panic():
        _clear_panic()
        _sd_logger.warning("safe_default: panic mode was on at startup — cleared")
    # Live flags must all be bool
    with _live_flags_lock:
        for k, v in list(_live_flags.items()):
            if not isinstance(v, bool):
                _live_flags[k] = True
                _sd_logger.warning("safe_default: flag %s had non-bool value — reset to True", k)
    _sd_logger.info("safe_defaults: startup validation passed")
    # Seed flag gauges so they appear on first /metrics scrape
    with _live_flags_lock:
        for k, v in _live_flags.items():
            try:
                FLAG_ENABLED.labels(flag=k).set(1 if v else 0)
            except Exception:
                pass


@app.on_event("startup")
def start_model_worker():
    try:
        # Allow tests to disable the worker without enabling MOCK_SERVICES
        if os.getenv("MODEL_WORKER_DISABLED"):
            return
        from services import model_worker

        model_worker.start()
        # Worker warmup: send a dummy prediction to load the model into memory
        try:
            # Warmup should send a full-length feature vector to match
            # the model's expected input (29 features).
            _ = model_worker.predict_sync([0.0] * 29, timeout=5.0)
            logging.getLogger("app.warmup").info("warmup: worker prediction ok")
        except Exception:
            logging.getLogger("app.warmup").warning("warmup: worker prediction failed (non-fatal)")
    except Exception:
        pass


@app.on_event("startup")
def warmup_pipeline():
    """Pre-load heavy components so the first real request doesn't spike.

    Runs a minimal dry-run parse to warm the classifier regex caches,
    validates the parser registry, and ensures metrics objects exist.
    """
    _logger = logging.getLogger("app.warmup")
    try:
        from services.section_classifier import get_parser, _PARSER_REGISTRY, PARSER_VERSION

        # Verify registry is populated and selected version exists
        parser_fn = get_parser()
        _logger.info(
            "warmup: parser registry ok (%d versions), active=%s, fn=%s",
            len(_PARSER_REGISTRY), PARSER_VERSION, parser_fn.__name__,
        )

        # Dry-run parse with minimal text to warm regex caches
        _warmup_text = "John Doe\\njohn@example.com\\nExperience\\nSoftware Engineer at ACME 2020-2023"
        parser_fn(_warmup_text)
        _logger.info("warmup: dry-run parse completed")
    except Exception:
        _logger.warning("warmup: parser dry-run failed (non-fatal)", exc_info=True)

    try:
        # Touch the semaphore to ensure it's initialised
        _acq = _global_parse_semaphore.acquire(blocking=False)
        if _acq:
            _global_parse_semaphore.release()
        _logger.info("warmup: semaphore ok (limit=%d)", _GLOBAL_PARSE_LIMIT)
    except Exception:
        _logger.warning("warmup: semaphore check failed (non-fatal)", exc_info=True)

    try:
        # Ensure Prometheus metrics objects are created (they lazy-init on first use)
        ACTIVE_REQUESTS.labels() if hasattr(ACTIVE_REQUESTS, "labels") else None
        _logger.info("warmup: metrics initialised")
    except Exception:
        pass

    _logger.info(
        "warmup: build_id=%s git_sha=%s parser_build=%s",
        BUILD_ID, GIT_SHA, PARSER_BUILD,
    )


@app.on_event("startup")
def start_reminder_worker():
    try:
        if os.getenv("DISABLE_REMINDER_WORKER", "").lower() in ("1", "true", "yes"):
            return
        _start_reminder_worker()
        logging.getLogger("app.startup").info("reminder_worker: started")
    except Exception as exc:
        logging.getLogger("app.startup").warning("reminder_worker startup failed: %s", exc)


@app.on_event("startup")
def validate_startup_config():
    """Validate critical environment and guard configuration at startup."""
    _logger = logging.getLogger("app.startup")
    warnings = []
    fatals = []

    # ── Required secrets in production ──
    if _ENV_MODE in ("production", "prod"):
        if not os.getenv("SUPABASE_JWT_SECRET") and not os.getenv("SUPABASE_JWT_SECRET_FILE"):
            fatals.append("SUPABASE_JWT_SECRET (or _FILE) is required in production")
        if not os.getenv("DATABASE_URL"):
            fatals.append("DATABASE_URL is required in production")
        # S3 is checked below via require_configured()

        # Billing / Stripe — required for payment processing in prod
        if not os.getenv("STRIPE_API_KEY"):
            warnings.append("STRIPE_API_KEY not set (billing will fail)")
        if not os.getenv("STRIPE_WEBHOOK_SECRET"):
            warnings.append("STRIPE_WEBHOOK_SECRET not set (webhook verification disabled)")

        # S3 explicit env check (budget sanity — require_configured() does detailed check below)
        if not os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_ROLE_ARN"):
            warnings.append("AWS credentials not configured (S3 storage will fail)")
        if not os.getenv("AWS_S3_BUCKET") and not os.getenv("S3_BUCKET"):
            warnings.append("S3 bucket name not set")

        # Supabase URL (frontend auth redirect)
        if not os.getenv("SUPABASE_URL"):
            warnings.append("SUPABASE_URL not set (auth callbacks may fail)")

    # ── SRE: Secret safety ──
    from auth import SUPABASE_JWT_SECRET as _jwt_secret
    if _jwt_secret:
        if len(_jwt_secret) < 32:
            warnings.append(f"SUPABASE_JWT_SECRET is short ({len(_jwt_secret)} chars, recommend >=32)")
        if _jwt_secret in ("super-secret-jwt-token-with-at-least-32-characters-long",
                           "your-super-secret-jwt-token", "changeme", "secret"):
            fatals.append("SUPABASE_JWT_SECRET is a known default — change it immediately")
    _redis_pw = os.getenv("REDIS_PASSWORD", "")
    if _ENV_MODE in ("production", "prod") and _redis_pw and _redis_pw in (
        "changeme", "password", "redis", "secret"
    ):
        warnings.append("REDIS_PASSWORD uses a known weak default")

    # Check guard constants are sane
    if _GLOBAL_CONCURRENCY_LIMIT < 1:
        warnings.append(f"GLOBAL_CONCURRENCY_LIMIT={_GLOBAL_CONCURRENCY_LIMIT} is too low")
    if _REQUEST_TIMEOUT_SECONDS < 5:
        warnings.append(f"REQUEST_TIMEOUT_SECONDS={_REQUEST_TIMEOUT_SECONDS} is too low")
    if _MEMORY_RSS_LIMIT_MB < 128:
        warnings.append(f"MEMORY_RSS_LIMIT_MB={_MEMORY_RSS_LIMIT_MB} is too low")
    if _CPU_USAGE_LIMIT < 50:
        warnings.append(f"CPU_USAGE_LIMIT={_CPU_USAGE_LIMIT} is too low")
    if _IP_GLOBAL_LIMIT_PER_MIN < 1:
        warnings.append(f"IP_GLOBAL_LIMIT_PER_MIN={_IP_GLOBAL_LIMIT_PER_MIN} is too low")
    if _REQUEST_QUEUE_SIZE < 10:
        warnings.append(f"REQUEST_QUEUE_SIZE={_REQUEST_QUEUE_SIZE} is too low")

    # Check runtime guard limits
    from security.runtime_guard import (
        _MAX_USER_OPTIMIZE_CONCURRENT, _GLOBAL_OPTIMIZE_LIMIT,
        _DOWNLOAD_LIMIT_PER_MIN, _SIGNED_URL_LIMIT_PER_MIN,
    )
    if _MAX_USER_OPTIMIZE_CONCURRENT < 1:
        warnings.append(f"MAX_USER_OPTIMIZE_CONCURRENT={_MAX_USER_OPTIMIZE_CONCURRENT} is too low")
    if _GLOBAL_OPTIMIZE_LIMIT < 1:
        warnings.append(f"GLOBAL_OPTIMIZE_CONCURRENT={_GLOBAL_OPTIMIZE_LIMIT} is too low")
    if _DOWNLOAD_LIMIT_PER_MIN < 1:
        warnings.append(f"DOWNLOAD_LIMIT_PER_MIN={_DOWNLOAD_LIMIT_PER_MIN} is too low")
    if _SIGNED_URL_LIMIT_PER_MIN < 1:
        warnings.append(f"SIGNED_URL_LIMIT_PER_MIN={_SIGNED_URL_LIMIT_PER_MIN} is too low")

    # Check optional services
    if not os.getenv("OPENAI_API_KEY"):
        _logger.info("startup: OPENAI_API_KEY not set (embeddings/AI review disabled)")
    if redis_rate is None:
        _logger.info("startup: Redis unavailable (using local fallback for rate limiting)")
        if _ENV_MODE in ("production", "prod"):
            fatals.append("Redis is unreachable (required in production)")

    # Check database connectivity
    try:
        _startup_db = SessionLocal()
        _startup_db.execute(text("SELECT 1"))
        _startup_db.close()
        _logger.info("startup: database connection OK")
    except Exception as exc:
        _logger.error("startup: database connection failed — %s", exc)
        if _ENV_MODE in ("production", "prod"):
            fatals.append(f"Database unreachable: {exc}")

    # Check pgvector extension
    try:
        _vec_db = SessionLocal()
        row = _vec_db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        _vec_db.close()
        if row:
            _logger.info("startup: pgvector extension OK")
        else:
            _logger.warning("startup: pgvector extension not found")
    except Exception:
        _logger.warning("startup: pgvector check skipped (non-fatal)")

    # Check disk space at startup
    try:
        disk_pct = _get_disk_usage()
        if disk_pct >= _DISK_BLOCK_PERCENT:
            fatals.append(f"Disk usage critical: {disk_pct}%")
        elif disk_pct >= _DISK_WARN_PERCENT:
            _logger.warning("startup: disk usage high — %.1f%%", disk_pct)
        else:
            _logger.info("startup: disk usage %.1f%%", disk_pct)
    except Exception:
        _logger.warning("startup: disk check skipped")

    # Check for mismatched path configs
    for path in _PATH_TIMEOUTS:
        if path not in _HEAVY_ENDPOINTS and path not in _PATH_CONCURRENCY:
            pass  # timeout-only paths are fine

    for w in warnings:
        _logger.warning("startup:config_warning %s", w)

    # Validate S3 bucket connectivity
    try:
        from config.aws import is_configured, require_configured, S3_BUCKET
        require_configured()
        if is_configured():
            from services.storage_service import check_health
            if check_health():
                _logger.info("startup: S3 bucket '%s' OK", S3_BUCKET)
            else:
                _logger.warning("startup: S3 bucket '%s' unreachable", S3_BUCKET)
    except RuntimeError as exc:
        _logger.error("startup: S3 FATAL — %s", exc)
        if _ENV_MODE in ("production", "prod"):
            fatals.append(f"S3 configuration error: {exc}")
    except Exception as exc:
        _logger.warning("startup: S3 check skipped — %s", exc)

    # ── Fatal check: stop server if required config is missing ──
    if fatals:
        for f in fatals:
            _logger.critical("startup:FATAL %s", f)
        if _ENV_MODE in ("production", "prod"):
            raise RuntimeError(
                f"Server cannot start: {len(fatals)} fatal config error(s): "
                + "; ".join(fatals)
            )

    _logger.info(
        "startup: validation complete (%d warnings), guards=%d, path_concurrency=%d, queue=%d",
        len(warnings), _GLOBAL_CONCURRENCY_LIMIT, len(_PATH_CONCURRENCY), _REQUEST_QUEUE_SIZE,
    )

    # ── SRE: Deploy safety banner ──
    _log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if _log_level == "DEBUG" and _ENV_MODE in ("production", "prod"):
        _logger.warning("startup:WARN LOG_LEVEL=DEBUG in production — verbose logging active")
    _logger.info(
        "startup:banner env=%s log_level=%s redis=%s workers=%s "
        "concurrency=%d queue=%d timeout=%ds build=%s sha=%s",
        _ENV_MODE, _log_level,
        "ok" if redis_rate else "unavailable",
        os.getenv("WEB_CONCURRENCY", "auto"),
        _GLOBAL_CONCURRENCY_LIMIT, _REQUEST_QUEUE_SIZE,
        _REQUEST_TIMEOUT_SECONDS, BUILD_ID, GIT_SHA,
    )

    # ── Ops: Mark app as ready — enables health check and traffic ──
    global _app_ready
    with _app_ready_lock:
        _app_ready = True
    _logger.info("startup: app marked READY — accepting traffic")


@app.on_event("shutdown")
def graceful_shutdown():
    """Ordered shutdown: wait for in-flight → stop workers → close Redis → flush logs."""
    _shutdown_logger = logging.getLogger("app.shutdown")
    _shutdown_logger.info("shutdown: starting graceful shutdown sequence")

    # 0. Wait for in-flight requests to finish (up to 10 seconds)
    _DRAIN_TIMEOUT = 10
    _drain_start = time.time()
    while _inflight_get() > 0 and (time.time() - _drain_start) < _DRAIN_TIMEOUT:
        time.sleep(0.25)
    remaining = _inflight_get()
    if remaining:
        _shutdown_logger.warning("shutdown: %d requests still in-flight after %ds", remaining, _DRAIN_TIMEOUT)
    else:
        _shutdown_logger.info("shutdown: all in-flight requests completed")

    # 1. Stop model worker
    try:
        from services import model_worker
        model_worker.stop()
        _shutdown_logger.info("shutdown: model worker stopped")
    except Exception:
        _shutdown_logger.warning("shutdown: model worker stop failed", exc_info=True)

    # 2. Close Redis connection
    try:
        global redis_rate
        if redis_rate is not None:
            redis_rate.close()
            redis_rate = None
            _shutdown_logger.info("shutdown: redis connection closed")
    except Exception:
        _shutdown_logger.warning("shutdown: redis close failed", exc_info=True)

    # 3. Flush all log handlers
    try:
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass
        _shutdown_logger.info("shutdown: logs flushed")
    except Exception:
        pass

    _shutdown_logger.info("shutdown: complete")


# ── Observability: background metrics collector ─────────────────────────
import gc as _gc

_METRICS_COLLECT_INTERVAL = 15  # seconds


def _metrics_collector_loop():
    """Background thread: update process, worker, breaker, flag gauges."""
    while True:
        time.sleep(_METRICS_COLLECT_INTERVAL)
        try:
            # Memory: RSS + VMS
            rss = _get_rss_bytes()
            if rss > 0:
                PROCESS_RSS_BYTES.set(rss)
            try:
                import psutil
                mem = psutil.Process().memory_info()
                PROCESS_RSS_BYTES.set(mem.rss)
                PROCESS_VMS_BYTES.set(mem.vms)
            except Exception:
                pass

            # GC collection counts
            counts = _gc.get_stats() if hasattr(_gc, "get_stats") else []
            for i, gen in enumerate(counts):
                GC_COLLECTIONS_TOTAL.labels(generation=str(i)).set(gen.get("collections", 0))

            # CPU
            cpu = _get_cpu_percent()
            PROCESS_CPU_PERCENT.set(cpu)

            # Worker: active tasks + queue size
            try:
                from services.model_worker import _proc as _mw_proc, _request_queue as _mw_q
                WORKER_ACTIVE_TASKS.set(1 if (_mw_proc and _mw_proc.is_alive()) else 0)
                WORKER_QUEUE_SIZE.set(_mw_q.qsize() if _mw_q else 0)
            except Exception:
                pass

            # Breaker gauges (refresh from state dict)
            now = time.time()
            with _cb_lock:
                for svc, st in _circuit_breaker_state.items():
                    BREAKER_OPEN.labels(service=svc).set(1 if st.get("open_until", 0) > now else 0)

            # Flag gauges
            with _live_flags_lock:
                for k, v in _live_flags.items():
                    FLAG_ENABLED.labels(flag=k).set(1 if v else 0)

            # Panic gauge
            PANIC_ACTIVE.set(1 if _is_panic() else 0)

        except Exception:
            pass


_threading.Thread(target=_metrics_collector_loop, daemon=True, name="metrics-collector").start()


# ── Guard cleanup: periodically prune in-memory rate tracking dicts ──────
_GUARD_CLEANUP_INTERVAL = 300  # seconds


def _guard_cleanup_loop():
    """Background thread to prune stale entries from rate-tracking dicts."""
    while True:
        time.sleep(_GUARD_CLEANUP_INTERVAL)
        now = time.time()
        cutoff = now - 120  # keep entries from last 2 minutes
        for lock, bucket in [
            (_ip_global_lock, _ip_global_counts),
            (_user_global_lock, _user_global_counts),
            (_user_embed_lock, _user_embed_counts),
            (_search_lock, _search_counts),
        ]:
            _prune_rate_bucket(bucket, lock, cutoff)
        with _dedup_lock:
            stale = [k for k, v in _dedup_cache.items() if v < cutoff]
            for k in stale:
                del _dedup_cache[k]
        # Prune local abuse dicts (fallback for no-Redis mode)
        _prune_abuse_dicts(now)
        # Auto safe mode: trigger when guard rejections spike
        _check_auto_safe_mode_from_guards(now)


# ── Auto safe mode from guard rejections ─────────────────────────────────
_GUARD_REJECT_TIMESTAMPS: list[float] = []
_GUARD_REJECT_LOCK = _threading.Lock()
_GUARD_SAFE_MODE_THRESHOLD = int(os.getenv("GUARD_SAFE_MODE_THRESHOLD", "50"))
_GUARD_SAFE_MODE_WINDOW = float(os.getenv("GUARD_SAFE_MODE_WINDOW", "60"))


def _record_guard_rejection() -> None:
    """Track guard-level rejection timestamps for auto safe mode."""
    now = time.time()
    with _GUARD_REJECT_LOCK:
        _GUARD_REJECT_TIMESTAMPS.append(now)
        # Keep only last window
        cutoff = now - _GUARD_SAFE_MODE_WINDOW
        while _GUARD_REJECT_TIMESTAMPS and _GUARD_REJECT_TIMESTAMPS[0] < cutoff:
            _GUARD_REJECT_TIMESTAMPS.pop(0)


def _check_auto_safe_mode_from_guards(now: float) -> None:
    """If too many guard rejections in window, trigger safe mode."""
    with _GUARD_REJECT_LOCK:
        cutoff = now - _GUARD_SAFE_MODE_WINDOW
        while _GUARD_REJECT_TIMESTAMPS and _GUARD_REJECT_TIMESTAMPS[0] < cutoff:
            _GUARD_REJECT_TIMESTAMPS.pop(0)
        count = len(_GUARD_REJECT_TIMESTAMPS)
    if count >= _GUARD_SAFE_MODE_THRESHOLD:
        try:
            from services.cv_builder_service import _safe_mode_auto, _safe_mode_lock
            import services.cv_builder_service as _cbs
            with _safe_mode_lock:
                if not _cbs._safe_mode_auto:
                    _cbs._safe_mode_auto = True
                    _guard_logger.warning(
                        "guard:auto_safe_mode_triggered rejections=%d window=%.0fs",
                        count, _GUARD_SAFE_MODE_WINDOW,
                    )
                    try:
                        GUARD_SAFE_MODE_TRIGGERS.inc()
                    except Exception:
                        pass
        except Exception:
            pass

_guard_cleanup_thread = _threading.Thread(target=_guard_cleanup_loop, daemon=True)
_guard_cleanup_thread.start()


# Redis connection for rate limiting
# Use a Redis URI string for limits.storage.RedisStorage (it expects a URI)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
if Redis:
    try:
        redis_timeout = float(os.getenv("REDIS_TIMEOUT_SECONDS", "1.0") or "1.0")
        redis_rate = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=redis_timeout,
            socket_timeout=redis_timeout,
            retry_on_timeout=False,
        )
        # Eagerly verify the connection to avoid per-request timeouts
        redis_rate.ping()
        # Share with runtime guard so download/signed-url limits use Redis
        from security.runtime_guard import set_redis as _set_runtime_redis
        _set_runtime_redis(redis_rate, url=redis_url)
        try:
            REDIS_CONNECTED.set(1)
        except Exception:
            pass
    except Exception:
        redis_rate = None
        try:
            REDIS_CONNECTED.set(0)
        except Exception:
            pass
else:
    redis_rate = None

# Create limiter, but fall back to a no-op limiter if Redis/limits storage isn't available
try:
    limiter = Limiter(key_func=get_remote_address, storage=RedisStorage(redis_url))
except Exception:

    class NoopLimiter:
        def limit(self, limit_string):
            def decorator(func):
                return func

            return decorator

    limiter = NoopLimiter()

app.state.limiter = limiter


# When mocking (testing), allow unlimited requests; otherwise apply rate limits
def rate_limit(limit_string):
    """Conditional rate limiter: no-op in MOCK_SERVICES mode."""
    if MOCK_SERVICES_ON:
        # Return a no-op decorator that does nothing
        def noop_decorator(func):
            return func

        return noop_decorator
    else:
        # Return the real limiter
        return limiter.limit(limit_string)


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

# Plan name normalization — map DB/UI variants to canonical keys.
_PLAN_ALIASES: dict[str, str] = {
    "professional": "pro",
    "premium": "pro",
    "business": "enterprise",
    "team": "enterprise",
    "admin": "admin",
}

def _normalize_plan(plan_type: str | None) -> str:
    """Normalize plan_type to one of: free, pro, enterprise, admin."""
    raw = (plan_type or "free").strip().lower()
    return _PLAN_ALIASES.get(raw, raw) if raw else "free"

# Plan-based quota mappings (configurable via env)
USER_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("USER_FREE_DAILY", "5")),
    "pro": int(os.getenv("USER_PRO_DAILY", "100")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_DAILY", "1000")),
}

USER_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("USER_FREE_MONTHLY", "20")),
    "pro": int(os.getenv("USER_PRO_MONTHLY", "500")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_MONTHLY", "5000")),
}

ORG_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("ORG_FREE_DAILY", "50")),
    "pro": int(os.getenv("ORG_PRO_DAILY", "500")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_DAILY", "5000")),
}

ORG_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("ORG_FREE_MONTHLY", "500")),
    "pro": int(os.getenv("ORG_PRO_MONTHLY", "5000")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_MONTHLY", "50000")),
}

# Backward-compatible free-tier override for Redis-backed daily quota.
# If unset, `USER_FREE_DAILY` is used.
REDIS_FREE_DAILY_LIMIT = int(
    os.getenv("REDIS_FREE_DAILY_LIMIT", str(USER_PLAN_LIMITS_DAILY["free"]))
)

# ── Cost guard: hard daily caps (env-override) ──────────────────────
COST_OPTIMIZE_PER_DAY = int(os.getenv("COST_OPTIMIZE_PER_DAY", "500"))
COST_UPLOAD_PER_DAY = int(os.getenv("COST_UPLOAD_PER_DAY", "1000"))


class AnalyzeRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    job_text: str | None = None
    lang: str = "en"

    def model_post_init(self, __context):
        if (not self.job_description) and self.job_text:
            self.job_description = self.job_text


class CVBuilderRequest(BaseModel):
    full_name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    summary: str = ""
    experiences: list = []
    education: list = []
    skills: list = []
    certifications: list = []
    projects: list = []
    languages: list = []
    social_links: list = []
    job_description: str = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = "en"
    font_family: str = ""


class CVSummarySuggestRequest(BaseModel):
    summary: str
    job_description: str = ""
    lang: str = "en"
    count: int = 3


def _cv_builder_payload(body: CVBuilderRequest) -> dict:
    """Convert CV builder request models into the dict expected by the renderer."""
    data = body.model_dump()
    data["experiences"] = data.get("experiences") or []
    data["projects"] = data.get("projects") or []
    data["languages"] = data.get("languages") or []
    data["language"] = data.get("lang") or "en"
    data["template"] = body.template
    data["output_format"] = body.output_format
    return data


def _resolve_request_user(db, user_payload: dict) -> User:
    supabase_id = user_payload.get("user_id")
    email = user_payload.get("email")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    return get_or_create_user(db, supabase_id, email)


@app.get("/api/v1/cv-builder/templates")
def cv_builder_templates(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)
    templates = get_available_templates(plan)
    return {"plan": plan, "templates": templates}


@app.post("/api/v1/cv-builder/preview")
def cv_builder_preview(
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)

    payload = _cv_builder_payload(body)
    cv_model = compile_cv_model(payload)
    template = body.template if body.template in get_available_templates(plan) else "classic"
    return {
        "template": template,
        "enhanced_data": cv_model.model_dump(),
        "cache_hit": False,
    }


@app.post("/api/v1/cv-builder/preview-html")
def cv_builder_preview_html(
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    _resolve_request_user(db, user)

    payload = _cv_builder_payload(body)
    cv_model = compile_cv_model(payload)
    try:
        from renderers.preview_renderer import render_html_preview

        html = render_html_preview(cv_model, body.template, font_override=body.font_family)
    except Exception:
        logger.exception("CV builder HTML preview failed")
        raise HTTPException(status_code=500, detail="CV preview failed")

    return {
        "template": body.template,
        "html": html,
        "enhanced_data": cv_model.model_dump(),
    }


@app.post("/api/v1/cv-builder/generate")
def cv_builder_generate(
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    if body.output_format not in ("docx", "pdf", "html", "typst"):
        raise HTTPException(status_code=400, detail="Unsupported output_format")

    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)
    font_family = body.font_family if _is_premium_plan(plan) else ""

    try:
        result = build_cv(
            cv_data=_cv_builder_payload(body),
            job_description=body.job_description or "",
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=plan,
            font_family=font_family,
        )
    except RuntimeError as exc:
        if "overloaded" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc))
        raise HTTPException(status_code=500, detail="CV generation failed")
    except Exception:
        logger.exception("CV builder generation failed")
        raise HTTPException(status_code=500, detail="CV generation failed")

    buf = result["buffer"]
    if hasattr(buf, "getbuffer") and buf.getbuffer().nbytes > _MAX_RESPONSE_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Generated file too large")

    try:
        audit_log(
            "cv_builder_generate",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            output_format=body.output_format,
            template=body.template,
            plan=plan,
        )
    except Exception:
        pass

    return StreamingResponse(
        buf,
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@app.post("/api/v1/cv-builder/suggest-summary")
def cv_builder_suggest_summary(
    body: CVSummarySuggestRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    count = max(1, min(int(body.count or 3), 5))
    try:
        suggestions = rewrite_service.suggest_summaries(
            summary=body.summary,
            job_description=body.job_description or "",
            lang=body.lang,
            count=count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"suggestions": suggestions, "plan": plan}


# =====================================================
# USER MANAGEMENT
# =====================================================


def get_or_create_user(db, supabase_id: str, email: str):
    """
    Get existing user or create new one.
    Called on first API request from authenticated user.
    """
    user = db.query(User).filter(User.supabase_id == supabase_id).first()

    if not user:
        initial_plan = _resolve_initial_user_plan(email)
        initial_billing = "trialing" if initial_plan != "free" else "trialing"
        user = User(
            supabase_id=supabase_id,
            email=email,
            plan_type=initial_plan,
            billing_status=initial_billing,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Auto-detect admin role from BILLING_ADMIN_ALLOWED_EMAILS env
    admin_emails_raw = str(os.getenv("BILLING_ADMIN_ALLOWED_EMAILS", "")).strip()
    admin_emails = {e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()}
    user_email = (email or "").strip().lower()
    if user_email and user_email in admin_emails and (user.role or "") != "admin":
        user.role = "admin"
        db.add(user)
        db.commit()
        db.refresh(user)

    # Domain-based auto role assignment: if user's email domain matches an
    # existing Organization, mark them as a recruiter and attach the org.
    # Skip if user is already admin (admin supersedes recruiter).
    if user.role != "admin":
        try:
            domain = None
            if isinstance(email, str) and "@" in email:
                domain = email.split("@", 1)[1].lower()

            if domain:
                org = db.query(Organization).filter(Organization.domain == domain).first()
                if org and user.organization_id != org.id:
                    user.role = "recruiter"
                    user.organization_id = org.id
                    db.add(user)
                    db.commit()
                    db.refresh(user)
        except Exception:
            # non-fatal: if org lookup fails, return the user as-is
            pass

    return user


def _record_usage_daily(db, user_id: int):
    """Upsert a row in usage_daily for today, incrementing count by 1."""
    try:
        from models import UsageDaily
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        row = (
            db.query(UsageDaily)
            .filter(UsageDaily.user_id == user_id, UsageDaily.date == today)
            .first()
        )
        if row:
            row.count = (row.count or 0) + 1
        else:
            row = UsageDaily(user_id=user_id, date=today, count=1)
            db.add(row)
    except Exception:
        pass  # Non-fatal — don't break analysis


def _resolve_initial_user_plan(email: str | None) -> str:
    """Resolve default plan for newly created users.

    Set `AUTO_NEW_USER_PLAN=pro` (or enterprise) for local/demo flows where
    every new account should start with premium access.
    """
    requested = str(os.getenv("AUTO_NEW_USER_PLAN", "free")).strip().lower()
    if requested not in User.PLAN_TYPES:
        requested = "free"

    # Optional allow-lists to limit automatic premium grants.
    allowed_emails_raw = str(os.getenv("AUTO_PREMIUM_EMAILS", "")).strip()
    allowed_domains_raw = str(os.getenv("AUTO_PREMIUM_DOMAINS", "")).strip()

    if requested == "free":
        return "free"

    email_value = (email or "").strip().lower()
    domain_value = email_value.split("@", 1)[1] if "@" in email_value else ""

    allowed_emails = {
        x.strip().lower() for x in allowed_emails_raw.split(",") if x.strip()
    }
    allowed_domains = {
        x.strip().lower() for x in allowed_domains_raw.split(",") if x.strip()
    }

    # If allow-lists are provided, enforce them; otherwise apply to all new users.
    if allowed_emails or allowed_domains:
        if email_value in allowed_emails or domain_value in allowed_domains:
            return requested
        return "free"

    return requested


def _ensure_not_expired(user_payload: dict):
    if isinstance(user_payload, dict) and user_payload.get("signature"):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = user_payload.get("payload") if isinstance(user_payload, dict) else None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if exp is None:
        return
    try:
        exp_ts = int(exp)
    except (TypeError, ValueError):
        return
    if exp_ts <= int(datetime.utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")


def _seconds_until_next_quota_day() -> int:
    now = _quota_now()
    if now.tzinfo is not None:
        tomorrow = (now + timedelta(days=1)).date()
        next_midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)
    else:
        next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
    return max(1, int((next_midnight - now).total_seconds()))


def _daily_quota_key(user_id: str, now: datetime | None = None) -> str:
    dt = now or _quota_now()
    return f"quota:daily:{user_id}:{dt.strftime('%Y%m%d')}"


def _resolve_daily_limit_for_plan(plan_type: str | None) -> int:
    """Resolve the effective daily limit for a user's plan.

    For backward compatibility, free users can still override via
    `REDIS_FREE_DAILY_LIMIT`; other plans use USER_PLAN_LIMITS_DAILY.
    """
    normalized = _normalize_plan(plan_type)
    if normalized == "admin":
        return 10**12
    if normalized == "free":
        return int(os.getenv("REDIS_FREE_DAILY_LIMIT", str(USER_PLAN_LIMITS_DAILY["free"])))
    return int(USER_PLAN_LIMITS_DAILY.get(normalized, USER_PLAN_LIMITS_DAILY["free"]))


def _get_daily_quota_status(user_id: str, limit: int = REDIS_FREE_DAILY_LIMIT):
    """Return quota status from Redis, or None if Redis isn't available."""
    if limit <= 0:
        return None
    key = _daily_quota_key(user_id)
    if not redis_rate:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0))
        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used < limit,
            "source": "memory",
        }

    try:
        raw_used = redis_rate.get(key)
        used = int(raw_used) if raw_used is not None else 0
        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used < limit,
            "source": "redis",
        }
    except Exception:
        # Redis configured but unavailable: fall back to in-memory status.
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0))
        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used < limit,
            "source": "memory",
        }


def _consume_daily_quota(user_id: str, limit: int = REDIS_FREE_DAILY_LIMIT):
    """Atomically consume one daily quota unit in Redis.

    Returns None if Redis is unavailable. Callers can fall back to DB counters.
    """
    if limit <= 0:
        return None

    key = _daily_quota_key(user_id)
    if not redis_rate:
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
        _LOCAL_DAILY_QUOTA[key] = used
        _save_local_quota()
        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used <= limit,
            "source": "memory",
        }

    try:
        used = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if used == 1 or ttl < 0:
            redis_rate.expire(key, _seconds_until_next_quota_day())

        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used <= limit,
            "source": "redis",
        }
    except Exception:
        # Redis configured but unavailable: fall back to in-memory counter.
        used = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
        _LOCAL_DAILY_QUOTA[key] = used
        _save_local_quota()
        remaining = max(0, limit - used)
        return {
            "key": key,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "allowed": used <= limit,
            "source": "memory",
        }


# ── Disk safety ──────────────────────────────────────────────────────────
_DISK_WARN_PERCENT = float(os.getenv("DISK_WARN_PERCENT", "80"))
_DISK_BLOCK_PERCENT = float(os.getenv("DISK_BLOCK_PERCENT", "95"))
_disk_logger = logging.getLogger("app.disk")


def _get_disk_usage() -> float:
    """Return disk usage percentage for the app partition."""
    import shutil
    total, used, free = shutil.disk_usage(os.path.dirname(__file__) or "/")
    return round(used / total * 100, 1) if total > 0 else 0.0


def _check_disk_safety() -> None:
    """Warn >80%, block >95% disk usage. Raises HTTPException(503)."""
    try:
        pct = _get_disk_usage()
    except Exception:
        return  # can't check — don't block
    if pct >= _DISK_BLOCK_PERCENT:
        _disk_logger.critical("disk:full pct=%.1f%% limit=%.0f%%", pct, _DISK_BLOCK_PERCENT)
        _alert("disk_critical", f"Disk usage {pct}% >= {_DISK_BLOCK_PERCENT}%")
        raise HTTPException(
            status_code=503,
            detail="Disk space critically low. Uploads blocked.",
        )
    if pct >= _DISK_WARN_PERCENT:
        _disk_logger.warning("disk:high pct=%.1f%% warn=%.0f%%", pct, _DISK_WARN_PERCENT)
        _alert("disk_high", f"Disk usage {pct}% >= {_DISK_WARN_PERCENT}%", level="warning")


def _check_cost_guard(scope: str, limit: int) -> None:
    """Enforce a global per-day hard cap for costly operations.

    Raises HTTPException(429) if the daily limit is exceeded.
    Logs warning at 80% usage. Uses Redis when available, falls back to local.
    """
    _cost_logger = logging.getLogger("app.cost")
    today = datetime.now().strftime("%Y%m%d")
    key = f"cost:{scope}:{today}"

    def _warn_and_block(count: int, source: str) -> None:
        pct = (count / limit * 100) if limit else 0
        if pct >= 80 and count <= limit:
            _cost_logger.warning(
                "cost:high_usage scope=%s count=%d limit=%d pct=%.0f%% source=%s",
                scope, count, limit, pct, source,
            )
            _alert("cost_high", f"Cost usage {scope} at {pct:.0f}% ({count}/{limit})", level="warning")
        if count > limit:
            _cost_logger.error(
                "cost:blocked scope=%s count=%d limit=%d source=%s",
                scope, count, limit, source,
            )
            _alert("cost_blocked", f"Cost limit exceeded for {scope}: {count}/{limit}")
            raise HTTPException(
                status_code=429,
                detail=f"Daily {scope} limit reached ({limit}/day)",
            )

    if redis_rate:
        try:
            count = int(redis_rate.incr(key))
            if count == 1:
                redis_rate.expire(key, 86400)
            _warn_and_block(count, "redis")
            return
        except HTTPException:
            raise
        except Exception:
            pass  # fall through to local

    count = int(_LOCAL_DAILY_QUOTA.get(key, 0)) + 1
    _LOCAL_DAILY_QUOTA[key] = count
    _warn_and_block(count, "memory")


def _consume_user_rate_limit(user_id: str, limit_per_minute: int, scope: str):
    """Consume one request from a per-user, per-minute Redis throttle bucket.

    Returns None if Redis isn't available so callers can gracefully skip.
    """
    if limit_per_minute <= 0:
        return None

    minute_bucket = int(time.time()) // 60
    key = f"throttle:user:{scope}:{user_id}:{minute_bucket}"
    if not redis_rate:
        used = int(_LOCAL_USER_THROTTLE.get(key, 0)) + 1
        _LOCAL_USER_THROTTLE[key] = used
        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key,
            "used": used,
            "limit": int(limit_per_minute),
            "remaining": remaining,
            "allowed": used <= int(limit_per_minute),
            "scope": scope,
            "source": "memory",
        }

    try:
        used = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if used == 1 or ttl < 0:
            redis_rate.expire(key, 60)

        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key,
            "used": used,
            "limit": int(limit_per_minute),
            "remaining": remaining,
            "allowed": used <= int(limit_per_minute),
            "scope": scope,
            "source": "redis",
        }
    except Exception:
        # Redis configured but unavailable: fall back to in-memory bucket.
        used = int(_LOCAL_USER_THROTTLE.get(key, 0)) + 1
        _LOCAL_USER_THROTTLE[key] = used
        remaining = max(0, int(limit_per_minute) - used)
        return {
            "key": key,
            "used": used,
            "limit": int(limit_per_minute),
            "remaining": remaining,
            "allowed": used <= int(limit_per_minute),
            "scope": scope,
            "source": "memory",
        }


BENCHMARK_MIN_PEERS = int(os.getenv("BENCHMARK_MIN_PEERS", "5"))

# ── Concurrent request limiter (per-user) ─────────────────────────────────
_CONCURRENT_LIMIT_PER_USER = int(os.getenv("CONCURRENT_LIMIT_PER_USER", "3"))
_LOCAL_CONCURRENT: dict[str, int] = {}


def _acquire_concurrent_slot(user_id: str) -> bool:
    """Try to reserve a concurrent-request slot for *user_id*.

    Returns ``True`` if the slot was granted, ``False`` if the user
    already has ``_CONCURRENT_LIMIT_PER_USER`` requests in flight.
    Uses Redis when available, otherwise an in-memory counter.
    """
    if _CONCURRENT_LIMIT_PER_USER <= 0:
        return True

    key = f"concurrent:user:{user_id}"

    if redis_rate:
        try:
            current = int(redis_rate.incr(key))
            # First use — set short TTL as a safety net.
            if current == 1:
                redis_rate.expire(key, 120)
            if current > _CONCURRENT_LIMIT_PER_USER:
                redis_rate.decr(key)
                return False
            return True
        except Exception:
            pass

    # In-memory fallback
    current = _LOCAL_CONCURRENT.get(key, 0) + 1
    if current > _CONCURRENT_LIMIT_PER_USER:
        return False
    _LOCAL_CONCURRENT[key] = current
    return True


def _release_concurrent_slot(user_id: str) -> None:
    """Release a previously acquired concurrent-request slot."""
    key = f"concurrent:user:{user_id}"

    if redis_rate:
        try:
            val = redis_rate.decr(key)
            if val is not None and int(val) <= 0:
                redis_rate.delete(key)
            return
        except Exception:
            pass

    # In-memory fallback
    current = _LOCAL_CONCURRENT.get(key, 0)
    if current <= 1:
        _LOCAL_CONCURRENT.pop(key, None)
    else:
        _LOCAL_CONCURRENT[key] = current - 1


def _compute_percentile_position(current_score: float, peer_scores: list[float]) -> dict | None:
    if not peer_scores:
        return None

    n = len(peer_scores)
    lower = sum(1 for s in peer_scores if float(s) < current_score)
    equal = sum(1 for s in peer_scores if float(s) == current_score)
    percentile = ((lower + 0.5 * equal) / n) * 100.0
    ahead = max(0.0, percentile - 50.0)
    avg_peer = sum(float(s) for s in peer_scores) / n
    delta_avg = float(current_score) - avg_peer

    return {
        "peer_count": n,
        "percentile": round(percentile, 1),
        "ahead_percent": round(ahead, 1),
        "average_peer_score": round(avg_peer, 2),
        "delta_vs_average": round(delta_avg, 2),
    }


def _build_analysis_benchmark(db, analysis_record: Analysis) -> dict:
    """Benchmark one analysis against similar analyses by specialization/industry/domain."""
    if not analysis_record:
        return {"available": False, "reason": "analysis_not_found"}

    scope = "global"
    query = db.query(Analysis.similarity_score).filter(Analysis.id != analysis_record.id)

    if analysis_record.specialization_id:
        scope = "specialization"
        query = query.filter(Analysis.specialization_id == analysis_record.specialization_id)
    elif analysis_record.industry_id:
        scope = "industry"
        query = query.filter(Analysis.industry_id == analysis_record.industry_id)
    elif analysis_record.domain_id:
        scope = "domain"
        query = query.filter(Analysis.domain_id == analysis_record.domain_id)

    peer_rows = query.limit(2000).all()
    peer_scores = [float(r[0]) for r in peer_rows if r and r[0] is not None]

    if len(peer_scores) < BENCHMARK_MIN_PEERS:
        return {
            "available": False,
            "scope": scope,
            "peer_count": len(peer_scores),
            "min_peers": BENCHMARK_MIN_PEERS,
            "reason": "not_enough_peers",
        }

    stats = _compute_percentile_position(float(analysis_record.similarity_score), peer_scores)
    if not stats:
        return {
            "available": False,
            "scope": scope,
            "reason": "no_peer_scores",
        }

    ahead = stats["ahead_percent"]
    if ahead >= 1.0:
        summary = f"Bu CV benzer gruptaki adaylardan yaklasik %{ahead} daha onde."
    else:
        summary = "Bu CV benzer grupla benzer seviyede."

    return {
        "available": True,
        "scope": scope,
        **stats,
        "summary": summary,
    }


def _is_premium_plan(plan_type: str | None) -> bool:
    return _normalize_plan(plan_type) in ("pro", "enterprise", "admin")


def _is_admin_user(db_user: User | None) -> bool:
    return bool(db_user and str(getattr(db_user, "role", "") or "").strip().lower() == "admin")


def _resolve_effective_plan(db, db_user: User) -> str:
    if _is_admin_user(db_user):
        return "admin"
    if db_user and db_user.role == "recruiter" and db_user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == db_user.organization_id)
            .first()
        )
        if org and getattr(org, "plan_type", None):
            return _normalize_plan(str(org.plan_type))
    return _normalize_plan(str((db_user.plan_type or "free") if db_user else "free"))


def _build_premium_insights(result: dict) -> dict:
    dimensions = {
        "semantic": float(result.get("semantic_score") or 0),
        "keyword": float(result.get("keyword_score") or 0),
        "skill": float(result.get("skill_score") or 0),
        "experience": float(result.get("experience_score") or 0),
        "ats": float(result.get("ats_score") or 0),
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    gap = round(dimensions[strongest] - dimensions[weakest], 1)

    missing_skills = list(result.get("missing_skills") or [])
    top_skills = [str(s) for s in missing_skills[:3]]

    action_plan = []
    for skill in top_skills:
        action_plan.append(
            {
                "title": f"Mini proje ile {skill} guclendir",
                "detail": f"{skill} iceren olculebilir bir proje ciktisi ekleyin (repo, demo, metrik).",
            }
        )

    interview_questions = [
        f"{skill} kullanarak cozdugunuz bir problemi adim adim anlatir misiniz?"
        for skill in top_skills
    ]

    return {
        "strongest_dimension": strongest,
        "strongest_score": round(dimensions[strongest], 1),
        "weakest_dimension": weakest,
        "weakest_score": round(dimensions[weakest], 1),
        "balance_gap": gap,
        "action_plan": action_plan,
        "interview_questions": interview_questions,
    }


def _apply_plan_based_result_features(result: dict, effective_plan: str) -> dict:
    premium_access = _is_premium_plan(effective_plan)
    result["effective_plan"] = effective_plan
    result["premium_access"] = premium_access

    if premium_access:
        result["premium_insights"] = _build_premium_insights(result)
        return result

    # Free tier: provide a useful preview but keep advanced output for premium.
    recs = result.get("recommendations") or []
    if isinstance(recs, list) and len(recs) > 2:
        result["recommendations"] = recs[:2]
        result["recommendations_truncated"] = True

    missing = result.get("missing_skills") or []
    if isinstance(missing, list) and len(missing) > 6:
        result["missing_skills"] = missing[:6]
        result["missing_skills_truncated"] = True

    result["premium_locked"] = {
        "advanced_breakdown": True,
        "full_recommendations": True,
    }
    return result


# =====================================================
# HELPERS
# =====================================================


def interpret_score(score):
    if score > 75:
        return "High Match"
    elif score > 50:
        return "Moderate Match"
    return "Low Match"


def build_features(
    semantic, keyword, skill, exp, missing_skills, domain_similarity, ats_score,
    ats_details=None, title_match=0.0, seniority_match=0.0,
    cv_text="", job_description="",
):
    # Floor values: prevent 0-scores from bad parse / empty PDF / student CV
    semantic = max(float(semantic), 5.0)
    keyword = max(float(keyword), 5.0)
    skill = max(float(skill), 5.0)
    exp = max(float(exp), 5.0)

    missing_count = len(missing_skills)
    total_required_skills = missing_count + max(1, int(skill / 20))

    missing_ratio = missing_count / total_required_skills

    semantic_skill_interaction = float(semantic * skill / 100)
    keyword_skill_interaction = float(keyword * skill / 100)

    # balance_score approximates how balanced semantic vs skill coverage is
    balance_score = float(max(0.0, 100.0 - abs(float(semantic) - float(skill))))

    # ATS layout features (from ats_details if available)
    layout = (ats_details or {}).get("layout", {})
    content = (ats_details or {}).get("content", {})
    sections_found = layout.get("sections_found", [])

    bullet_score = float(layout.get("bullet_score", 0.0))
    section_count = int(len(sections_found))
    section_presence_score = float(layout.get("section_presence_score", 0.0))
    formatting_score = float(layout.get("formatting_score", 0.0))
    length_score = float(layout.get("length_score", 0.0))
    contact_score = float(layout.get("contact_score", 0.0))

    # ATS content features
    action_verb_score = float(content.get("action_verb_score", 0.0))
    achievement_score = float(content.get("achievement_score", 0.0))

    # Section presence flags
    sections_lower = {s.lower() for s in sections_found}
    has_summary = int(any(s in sections_lower for s in ("summary", "profile", "objective")))
    has_skills = int("skills" in sections_lower)
    has_experience = int("experience" in sections_lower)
    has_education = int("education" in sections_lower)
    has_projects = int("projects" in sections_lower)

    # ── New features (v2.1) ──────────────────────────────────────────────

    # Soft skill detection: leadership, teamwork, communication keywords
    _SOFT_SKILL_PATTERNS = [
        r"\bleadership\b", r"\bteamwork\b", r"\bcommunication\b",
        r"\bcollaboration\b", r"\bproblem.solving\b", r"\btime.management\b",
        r"\bcritical.thinking\b", r"\badaptability\b", r"\bcreativity\b",
        r"\bmentoring\b", r"\bnegotiation\b", r"\bpresentation\b",
        r"\bstakeholder\b", r"\bcross.functional\b", r"\bstrategic\b",
        r"\binitiative\b", r"\bempathy\b", r"\bconflict.resolution\b",
    ]
    _cv_lower = (cv_text or "").lower()
    _soft_hits = sum(1 for p in _SOFT_SKILL_PATTERNS if re.search(p, _cv_lower))
    soft_skill_score = min(100.0, (_soft_hits / max(len(_SOFT_SKILL_PATTERNS), 1)) * 150)

    # Readability: vocabulary richness (unique words / total words)
    _words = re.findall(r"[a-zA-Z]{2,}", _cv_lower)
    _total_words = max(len(_words), 1)
    _unique_words = len(set(_words))
    readability_score = min(100.0, (_unique_words / _total_words) * 130)

    # Keyword density: how well matched keywords spread across the text
    _jd_lower = (job_description or "").lower()
    _jd_words = set(re.findall(r"[a-zA-Z]{3,}", _jd_lower))
    _stop = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
             "was", "one", "our", "out", "with", "that", "this", "have", "from",
             "they", "will", "each", "make", "like", "been", "has", "its", "who",
             "did", "get", "may", "him", "his", "how", "its", "let", "say", "she",
             "too", "use", "way", "about", "would", "there", "their", "what",
             "could", "other", "than", "then", "them", "these", "some", "which"}
    _jd_kw = _jd_words - _stop
    if _jd_kw and _total_words > 0:
        _kw_found = sum(1 for w in _words if w in _jd_kw)
        keyword_density = min(100.0, (_kw_found / _total_words) * 500)
    else:
        keyword_density = 0.0

    # Education quality: degree level detection
    _edu_score = 0.0
    if re.search(r"\b(ph\.?d|doctorate|doktora)\b", _cv_lower):
        _edu_score = 100.0
    elif re.search(r"\b(master|msc|m\.sc|m\.a\.|mba|yüksek\s*lisans)\b", _cv_lower):
        _edu_score = 80.0
    elif re.search(r"\b(bachelor|bsc|b\.sc|b\.a\.|lisans|undergraduate)\b", _cv_lower):
        _edu_score = 60.0
    elif re.search(r"\b(associate|ön\s*lisans|diploma)\b", _cv_lower):
        _edu_score = 40.0
    elif re.search(r"\b(high\s*school|lise|certificate)\b", _cv_lower):
        _edu_score = 20.0

    features = [
        float(semantic),
        float(keyword),
        float(skill),
        float(exp),
        int(missing_count),
        float(missing_ratio),
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score,
        bullet_score,
        section_count,
        section_presence_score,
        formatting_score,
        length_score,
        contact_score,
        action_verb_score,
        achievement_score,
        has_summary,
        has_skills,
        has_experience,
        has_education,
        has_projects,
        float(domain_similarity),
        float(title_match),
        float(seniority_match),
        float(soft_skill_score),
        float(readability_score),
        float(keyword_density),
        float(_edu_score),
    ]
    if len(features) != 29:
        raise ValueError(f"build_features: expected 29 features, got {len(features)}")
    return features


ANALYSIS_CACHE_TTL = int(os.getenv("ANALYSIS_CACHE_TTL", "86400"))
_analysis_mem_cache: dict[str, tuple[float, dict]] = {}


def _stable_hash(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_job_title_from_jd(job_description: str) -> str | None:
    """Extract a compact job title candidate from JD text.

    Uses the first non-empty line and trims common separators.
    """
    if not isinstance(job_description, str):
        return None
    lines = [ln.strip() for ln in job_description.splitlines() if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    for sep in ("|", "-", "("):
        if sep in first:
            first = first.split(sep, 1)[0].strip()
    if not first:
        return None
    return first[:120]


CLAMAV_ENABLED = os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes")
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "localhost")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310") or "3310")


def _scan_upload_for_viruses(contents: bytes) -> None:
    """Scan uploaded file bytes with ClamAV when enabled.

    This uses the clamd network daemon if available. In environments
    without CLAMAV_ENABLED, the function is a no-op.
    """

    if not CLAMAV_ENABLED:
        return

    try:
        import clamd  # type: ignore[import-untyped, import-not-found]
    except Exception:
        raise HTTPException(status_code=500, detail="Virus scanning backend unavailable")

    try:
        client = clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT)
        result = client.instream(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=500, detail="Virus scan failed")

    try:
        _name, (status, signature) = next(iter(result.items()))
    except Exception:
        status, signature = None, None

    if status != "OK":
        detail = "File failed virus scan"
        if signature:
            detail = f"Malware detected: {signature}"
        raise HTTPException(status_code=400, detail=detail)


def _extract_pdf_text(contents: bytes) -> tuple[str, bool]:
    """Extract plain text from PDF bytes using coordinate-based layout analysis.

    Uses pdfplumber word positions to detect and properly reconstruct
    multi-column layouts. Falls back to PyPDF2 if pdfplumber fails.

    Returns (text, truncated) where truncated is True if content was capped.
    """
    from renderers.blocks import fix_decomposed_diacritics

    # ── Primary: pdfplumber with coordinate-based column detection ──
    try:
        import pdfplumber

        left_lines: list[str] = []
        right_lines: list[str] = []
        is_multi_col = False
        col_boundary = 0.0

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            # ── Security: reject PDFs with too many pages ──
            if len(pdf.pages) > _MAX_PDF_PAGES:
                logging.getLogger("app.security").warning(
                    "pdf_pages_limit: %d > %d", len(pdf.pages), _MAX_PDF_PAGES
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)",
                )
            # ── First pass: detect column layout across ALL pages ──
            all_page_gaps: list[float] = []
            total_both = 0
            total_content = 0
            page_widths: list[float] = []

            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue
                page_w = page.width
                page_widths.append(page_w)

                rows: dict[float, list] = {}
                for w in words:
                    row_key = round(w["top"] / 3) * 3
                    rows.setdefault(row_key, []).append(w)

                for row_words in rows.values():
                    sorted_rw = sorted(row_words, key=lambda w: w["x0"])
                    row_span = sorted_rw[-1]["x1"] - sorted_rw[0]["x0"] if len(sorted_rw) > 1 else 0
                    # Skip rows that span less than 30% — likely single-column header rows
                    if row_span < page_w * 0.30:
                        continue
                    total_content += 1
                    max_gap = 0
                    max_gap_pos = page_w / 2
                    for i in range(len(sorted_rw) - 1):
                        gap = sorted_rw[i + 1]["x0"] - sorted_rw[i]["x1"]
                        if gap > max_gap:
                            max_gap = gap
                            max_gap_pos = (sorted_rw[i]["x1"] + sorted_rw[i + 1]["x0"]) / 2
                    if max_gap > 20:
                        all_page_gaps.append(max_gap_pos)
                        total_both += 1

            total_content = max(total_content, 1)
            # Relax thresholds: 2 gap rows and >15% of content rows
            if total_both >= 2 and total_both > total_content * 0.15:
                is_multi_col = True
                all_page_gaps.sort()
                col_boundary = all_page_gaps[len(all_page_gaps) // 2]

            # ── Second pass: extract text using detected layout ──
            for page in pdf.pages:
                words = page.extract_words()

                # If pdfplumber finds no word objects on this page, try a few
                # fallbacks before skipping: (1) page.extract_text() and
                # (2) per-page OCR via Tesseract / remote OCR service.
                if not words:
                    # Quick plain-text fallback
                    try:
                        extracted = page.extract_text() or ""
                    except Exception:
                        extracted = ""

                    if extracted and extracted.strip():
                        if is_multi_col:
                            # treat whole-page extracted text as a left-column block
                            left_lines.append(extracted.strip())
                            left_lines.append("")
                        else:
                            left_lines.extend([ln for ln in extracted.splitlines() if ln.strip()])
                        # page processed via text fallback
                        continue

                    # If configured, attempt OCR on the page image
                    try:
                        # Use pdfplumber's image renderer to get a PIL image
                        pag_img = page.to_image(resolution=150).original
                        buf = io.BytesIO()
                        pag_img.save(buf, format="JPEG")
                        img_bytes = buf.getvalue()
                        ocr_text = _ocr_extract_text(img_bytes)
                        if ocr_text and ocr_text.strip():
                            if is_multi_col:
                                left_lines.append(ocr_text.strip())
                                left_lines.append("")
                            else:
                                left_lines.extend([ln for ln in ocr_text.splitlines() if ln.strip()])
                            continue
                    except Exception:
                        # OCR best-effort: ignore failures and skip page
                        pass

                    # Nothing useful found on this page — skip it
                    continue

                page_w = page.width
                mid = col_boundary if is_multi_col else page_w / 2

                if is_multi_col:
                    # Separate wide-header rows (span both columns) from column rows
                    header_rows_lines: list[str] = []
                    page_left: list[str] = []
                    page_right: list[str] = []

                    rows_by_top: dict[float, list] = {}
                    for w in words:
                        row_key = round(w["top"] / 3) * 3
                        rows_by_top.setdefault(row_key, []).append(w)

                    for row_key in sorted(rows_by_top.keys()):
                        row_words = sorted(rows_by_top[row_key], key=lambda w: w["x0"])
                        # Check if row spans both columns (wide header)
                        has_left = any(w["x0"] < mid - 5 for w in row_words)
                        has_right = any(w["x1"] > mid + 5 for w in row_words)
                        # Measure gap at column boundary
                        max_gap_at_mid = 0
                        for i in range(len(row_words) - 1):
                            gap = row_words[i + 1]["x0"] - row_words[i]["x1"]
                            gap_pos = (row_words[i]["x1"] + row_words[i + 1]["x0"]) / 2
                            if abs(gap_pos - mid) < page_w * 0.15 and gap > max_gap_at_mid:
                                max_gap_at_mid = gap

                        if has_left and has_right and max_gap_at_mid < 15:
                            # Wide row spanning both columns — treat as header/full-width
                            header_rows_lines.append(" ".join(w["text"] for w in row_words))
                        else:
                            # Split into left/right columns
                            left_words = [w for w in row_words if w["x0"] < mid]
                            right_words = [w for w in row_words if w["x0"] >= mid]
                            if left_words:
                                page_left.append(" ".join(w["text"] for w in left_words))
                            if right_words:
                                page_right.append(" ".join(w["text"] for w in right_words))

                    # Prepend wide-header lines (name, contact) before columns
                    if header_rows_lines:
                        left_lines.extend(header_rows_lines)
                        left_lines.append("")  # blank separator

                    # Accumulate column lines per page
                    if page_left:
                        left_lines.extend(page_left)
                    if page_right:
                        right_lines.extend(page_right)

                    # Blank line as page separator
                    left_lines.append("")
                else:
                    # Single column: extract normally
                    all_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
                    cur_top = all_words[0]["top"]
                    cur_line: list[str] = []
                    for w in all_words:
                        if w["top"] - cur_top > 3:
                            if cur_line:
                                left_lines.append(" ".join(cur_line))
                            cur_line = [w["text"]]
                            cur_top = w["top"]
                        else:
                            cur_line.append(w["text"])
                    if cur_line:
                        left_lines.append(" ".join(cur_line))

        if is_multi_col:
            # Determine sidebar vs main: the column with more content is "main" and goes first.
            # This ensures experience/education (main) appear before skills/languages (sidebar).
            left_text = "\n".join(left_lines).strip()
            right_text = "\n".join(right_lines).strip()
            left_len = len(left_text.replace("\n", "").replace(" ", ""))
            right_len = len(right_text.replace("\n", "").replace(" ", ""))

            if left_len >= right_len:
                raw = left_text + "\n\n" + right_text
            else:
                raw = right_text + "\n\n" + left_text
            raw = "multi_col_fixed\n" + raw
        else:
            raw = "\n".join(left_lines)

        raw = raw.strip()
        if raw:
            # Security: cap extracted text length
            truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
            if truncated:
                raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
            return fix_decomposed_diacritics(raw), truncated

    except Exception:
        pass  # Fall through to PyPDF2

    # ── Fallback: PyPDF2 ──
    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Security: cap page count in fallback path
    pages = pdf_reader.pages
    if len(pages) > _MAX_PDF_PAGES:
        pages = pages[:_MAX_PDF_PAGES]

    text_parts = []
    for page in pages:
        extracted = page.extract_text()
        if extracted:
            text_parts.append(extracted)
    raw = "\n".join(text_parts).strip()
    # Security: cap extracted text length
    truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
    if truncated:
        logging.getLogger("app.security").warning(
            "pdf_text_truncated: %d > %d", len(raw), _MAX_PDF_EXTRACTED_CHARS
        )
        raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
    return fix_decomposed_diacritics(raw), truncated


# ── PDF safety constants ──
_MAX_PDF_PAGES = 50
_MAX_PDF_OBJECTS = 5_000
_MAX_PDF_EXTRACTED_CHARS = 100_000


def _validate_pdf_upload(contents: bytes, content_type: str | None) -> None:
    """Apply upload security checks for PDF files."""

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Malicious PDF: too many internal objects
    obj_count = contents.count(b" obj")
    if obj_count > _MAX_PDF_OBJECTS:
        logging.getLogger("app.security").warning(
            "pdf_rejected: too many objects %d > %d", obj_count, _MAX_PDF_OBJECTS
        )
        raise HTTPException(status_code=400, detail="PDF too complex (too many objects)")

    # Malicious PDF: too many pages (quick heuristic via cross-ref)
    page_count = contents.count(b"/Type /Page") - contents.count(b"/Type /Pages")
    if page_count > _MAX_PDF_PAGES:
        logging.getLogger("app.security").warning(
            "pdf_rejected: too many pages %d > %d", page_count, _MAX_PDF_PAGES
        )
        raise HTTPException(
            status_code=400, detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)"
        )

    try:
        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise
    except Exception:
        if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail="Virus scanner error")


async def _resolve_job_description_text(
    job_description: str = "", jd_file: UploadFile | None = None
) -> str:
    """Resolve JD text from direct input or uploaded file (txt/pdf)."""

    direct = (job_description or "").strip()
    if direct:
        return direct

    if jd_file is None:
        raise HTTPException(status_code=400, detail="Job description is required")

    contents = await jd_file.read()
    if len(contents) > 1_000_000:
        raise HTTPException(status_code=400, detail="Job description file too large")

    ctype = (jd_file.content_type or "").lower()
    if ctype == "application/pdf":
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid JD PDF file")
        text, _ = _extract_pdf_text(contents)
        return text

    if ctype in ("text/plain", "application/octet-stream", ""):
        return contents.decode("utf-8", errors="ignore").strip()

    raise HTTPException(
        status_code=400,
        detail="Unsupported JD file type (use text/plain or application/pdf)",
    )


CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "0").lower() in ("1", "true", "yes")
CAPTCHA_PROVIDER = os.getenv("CAPTCHA_PROVIDER", "").strip().lower()
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET", "").strip()


def require_captcha(request: Request):
    """Optional CAPTCHA enforcement for abuse-sensitive endpoints.

    When CAPTCHA_ENABLED is true, expects a CAPTCHA token in the
    X-Captcha-Token header and verifies it against reCAPTCHA or
    hCaptcha depending on CAPTCHA_PROVIDER.
    """

    if not CAPTCHA_ENABLED:
        return None

        
    token = request.headers.get("X-Captcha-Token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing CAPTCHA token")

    if not CAPTCHA_PROVIDER or not CAPTCHA_SECRET:
        raise HTTPException(status_code=500, detail="CAPTCHA misconfigured on server")

    try:
        import requests
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="CAPTCHA verification backend unavailable (install requests)",
        )

    if CAPTCHA_PROVIDER == "recaptcha":
        verify_url = "https://www.google.com/recaptcha/api/siteverify"
        data = {"secret": CAPTCHA_SECRET, "response": token}
    elif CAPTCHA_PROVIDER == "hcaptcha":
        verify_url = "https://hcaptcha.com/siteverify"
        data = {"secret": CAPTCHA_SECRET, "response": token}
    else:
        raise HTTPException(status_code=500, detail="Unsupported CAPTCHA provider")

    try:
        resp = requests.post(verify_url, data=data, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")
        payload = resp.json() if hasattr(resp, "json") else {}
        if not payload or not payload.get("success"):
            raise HTTPException(status_code=400, detail="Invalid CAPTCHA token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="CAPTCHA verification error")

    return None


def _extract_probable_job_title(text: str) -> str:
    source = str(text or "")
    patterns = [
        r"\b(?:hiring|looking for|seeking|position|role)\s+(?:a|an)?\s*([A-Za-z][A-Za-z0-9\-\s]{3,60})",
        r"\b([A-Za-z][A-Za-z0-9\-\s]{3,60})\s+(?:position|role)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.I)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip(" -:;,.\t\n")
            if title:
                return title
    return ""


def _title_match_score(cv_text: str, job_description: str) -> float:
    title = _extract_probable_job_title(job_description)
    if not title:
        return 50.0
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_cv = re.sub(r"[^a-z0-9]+", " ", str(cv_text or "").lower())
    if normalized_title and normalized_title in normalized_cv:
        return 100.0
    title_tokens = {tok for tok in normalized_title.split() if len(tok) > 2}
    if not title_tokens:
        return 50.0
    cv_tokens = set(normalized_cv.split())
    overlap = len(title_tokens & cv_tokens)
    return round((overlap / max(1, len(title_tokens))) * 100.0, 2)


def _detect_seniority(text: str) -> str:
    lowered = str(text or "").lower()
    senior_patterns = {
        "intern": ["intern", "stajyer"],
        "junior": ["junior", "entry level", "associate"],
        "mid": ["mid", "intermediate", "regular"],
        "senior": ["senior", "lead", "principal", "staff"],
        "manager": ["manager", "head", "director", "vp", "chief"],
    }
    for level, patterns in senior_patterns.items():
        for pattern in patterns:
            if re.search(r"\b" + re.escape(pattern) + r"\b", lowered):
                return level
    return "unknown"


def _seniority_match_score(cv_text: str, job_description: str) -> float:
    jd_level = _detect_seniority(job_description)
    cv_level = _detect_seniority(cv_text)
    if jd_level == "unknown" or cv_level == "unknown":
        return 60.0
    if jd_level == cv_level:
        return 100.0

    rank = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "manager": 5}
    distance = abs(rank.get(jd_level, 3) - rank.get(cv_level, 3))
    if distance == 1:
        return 75.0
    if distance == 2:
        return 55.0
    return 35.0


def _build_match_score_v2(result: dict, keyword_gap_v2: dict) -> dict:
    keyword_coverage = float(keyword_gap_v2.get("keyword_coverage_pct", 0.0) or 0.0)
    experience_match = float(result.get("experience_score", 0.0) or 0.0)
    title_match = float(result.get("title_match", 0.0) or 0.0)
    seniority_match = float(result.get("seniority_match", 0.0) or 0.0)

    weighted = (
        keyword_coverage * 0.35
        + experience_match * 0.30
        + title_match * 0.20
        + seniority_match * 0.15
    )
    overall = round(min(100.0, max(0.0, weighted)), 2)

    weak_notes = []
    if keyword_coverage < 50:
        weak_notes.append("Low keyword coverage")
    if seniority_match < 60:
        weak_notes.append("Seniority mismatch")
    if experience_match < 60:
        weak_notes.append("Experience evidence is weak")
    if title_match < 60:
        weak_notes.append("Title alignment is weak")

    return {
        "match_score": overall,
        "keyword_coverage_pct": round(keyword_coverage, 2),
        "experience_match": round(experience_match, 2),
        "title_match": round(title_match, 2),
        "seniority_match": round(seniority_match, 2),
        "missing_skills": result.get("missing_skills") or [],
        "missing_keywords": keyword_gap_v2.get("missing_keywords") or [],
        "extra_skills": result.get("extra_skills") or [],
        "strong_keywords": keyword_gap_v2.get("strong_keywords") or [],
        "weak_keywords": keyword_gap_v2.get("weak_keywords") or [],
        "weak_signals": weak_notes,
    }


def run_pipeline(cv_text: str, job_description: str, lang: str = ""):
    # Basic input guards
    if not isinstance(cv_text, str):
        cv_text = ""
    if not isinstance(job_description, str):
        job_description = ""

    forced_lang = (lang or "").strip().lower()
    lang_detection_fallback = False

    # Detect languages independently and prefer job-description language for output,
    # unless the client explicitly requests a language.
    cv_lang = detect_language(cv_text)
    jd_lang = detect_language(job_description)
    if forced_lang:
        detected_lang = forced_lang
    elif jd_lang and jd_lang != "en":
        detected_lang = jd_lang
    elif cv_lang:
        detected_lang = cv_lang
    else:
        detected_lang = "en"
        lang_detection_fallback = True

    # Truncate extremely large inputs to avoid resource exhaustion
    MAX_CV_LEN = 200_000
    MAX_JOB_LEN = 100_000
    if len(cv_text) > MAX_CV_LEN:
        cv_text = cv_text[:MAX_CV_LEN]
    if len(job_description) > MAX_JOB_LEN:
        job_description = job_description[:MAX_JOB_LEN]

    # Analysis result cache (Redis-backed when available).
    cache_key = None
    try:
        cv_hash = _stable_hash(cv_text)
        job_hash = _stable_hash(job_description)
        # Cache is language-aware to avoid returning English content on non-English UI.
        cache_key = f"analysis:v2:{detected_lang}:{cv_hash}:{job_hash}"
    except Exception:
        cache_key = None

    # 1) Fast in-memory cache (works even when Redis is down)
    if cache_key:
        cached_entry = _analysis_mem_cache.get(cache_key)
        if cached_entry:
            cached_at, cached_result = cached_entry
            if (time.time() - cached_at) <= ANALYSIS_CACHE_TTL:
                return cached_result
            _analysis_mem_cache.pop(cache_key, None)

    # 2) Redis-backed cache
    if cache_key and redis_rate is not None:
        try:
            cached = redis_rate.get(cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                decoded = json.loads(cached)
                _analysis_mem_cache[cache_key] = (time.time(), decoded)
                return decoded
            except Exception:
                # Ignore cache decode errors and continue with fresh pipeline
                pass

    cv_embedding = get_embedding(cv_text)
    job_embedding = get_embedding(job_description)

    # If embeddings fail, fall back to conservative defaults and mark
    warnings: list[str] = []
    embedding_failed = False
    if not cv_embedding or not job_embedding:
        semantic_score = 0.0
        embedding_failed = True
        warnings.append(
            "Semantic analysis unavailable (embedding service offline). "
            "Scores are based on keyword matching only."
        )
    else:
        try:
            semantic_score = calculate_similarity(cv_embedding, job_embedding) * 100
        except Exception:
            semantic_score = 0.0
    keyword_score = keyword_match_score(cv_text, job_description)

    skill_score, missing_skills = skill_coverage_score(cv_text, job_description)

    # Also extract detected skills from the CV for display
    from services.skill_service import extract_skills

    cv_skill_data = extract_skills(cv_text)
    detected_skills = sorted(cv_skill_data.get("found", set()))

    # Instrument skill detection for debugging. This emits a structured log
    # containing detected skills, missing skills and a short CV snippet when
    # either the score is zero or `SKILL_DEBUG` environment flag is enabled.
    try:
        SKILL_DEBUG = os.getenv("SKILL_DEBUG", "").lower() in ("1", "true", "yes")
        if SKILL_DEBUG or float(skill_score) == 0.0:
            snippet = (cv_text or "")[:1000].replace("\n", " ")
            logger.info(
                "skill_debug",
                extra={
                    "skill_score": skill_score,
                    "missing_skills": missing_skills,
                    "detected_skills": detected_skills,
                    "cv_text_snippet": snippet,
                },
            )
    except Exception:
        logger.exception("Failed to emit skill debug log")

    exp_score = experience_score(cv_text, job_description)

    # DOMAIN CREATE / FETCH
    domain_data = detect_or_create_domain(job_description, job_embedding)

    domain_similarity = get_domain_similarity(domain_data["domain_id"], job_embedding)

    # INDUSTRY + SPECIALIZATION
    industry_data = detect_industry_and_specialization(job_description, job_embedding)

    # ATS DETAILS (detailed breakdown)
    ats_details = analyze_cv(cv_text, job_description, lang=detected_lang)
    ats_score = ats_details.get("overall_score", 0)

    # Keyword gap analysis for explainability
    keyword_gap = compute_keyword_gap(cv_text, job_description)
    keyword_gap_v2 = compare(cv_text, job_description)

    jd_skill_data = extract_skills(job_description)
    jd_skills = sorted(jd_skill_data.get("found", set()))
    jd_skill_set = {str(s).strip().lower() for s in jd_skills if str(s).strip()}
    extra_skills = sorted([skill for skill in detected_skills if skill.lower() not in jd_skill_set])[:25]

    title_match = _title_match_score(cv_text, job_description)
    seniority_match = _seniority_match_score(cv_text, job_description)

    # FEATURES
    features = build_features(
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_skills,
        domain_similarity,
        ats_score,
        ats_details=ats_details,
        title_match=title_match,
        seniority_match=seniority_match,
        cv_text=cv_text,
        job_description=job_description,
    )

    try:
        prediction, confidence, risk_level, explanation = predict_match(features)
    except Exception as e:
        # If model runner failed, log and return conservative defaults
        print("Model prediction error:", str(e))
        prediction, confidence, risk_level, explanation = (
            50.0,
            50.0,
            "High Risk",
            {"error": str(e)},
        )

    # Direct ML score from singleton model (fast, no subprocess)
    try:
        ml_score = ml_predict_score(features)
    except Exception:
        ml_score = prediction * 100  # fallback to worker prediction (convert 0-1 to 0-100)

    # Hire classification model
    try:
        hire_decision, hire_probability = predict_hire(features)
    except Exception:
        hire_decision, hire_probability = False, 0.5

    recommendations = generate_recommendations(
        missing_skills, semantic_score, keyword_score, lang=detected_lang
    )

    content_score = float(ats_details.get("content", {}).get("content_score", 0.0))
    layout_score = float(ats_details.get("layout", {}).get("layout_score", 0.0))
    formatting_score_val = float(ats_details.get("layout", {}).get("formatting_score", 0.0))
    contact_score_val = float(ats_details.get("layout", {}).get("contact_score", 0.0))
    section_presence_val = float(ats_details.get("layout", {}).get("section_presence_score", 0.0))

    # Final score: rule-based 70% + ML 30% (real ATS simulation)
    # When no job description is provided, use ATS overall_score directly
    # since keyword/skill/semantic scores are meaningless without a JD target.
    from services.ats_service import compute_final_score
    breakdown = None
    if not job_description or not job_description.strip():
        final_score = round(float(ats_score), 2)
    else:
        # Request a debug breakdown from compute_final_score so we can
        # expose rule vs ML contributions for diagnostics.
        # Pass ML prediction confidence (if available) so ATS can decide
        # whether to trust the ML signal or prefer the rule-based score.
        ml_conf = None
        try:
            ml_conf = float(confidence) / 100.0 if confidence is not None else None
        except Exception:
            ml_conf = None

        breakdown = compute_final_score(
            keyword=keyword_score,
            section=section_presence_val,
            exp=exp_score,
            skills=skill_score,
            layout=formatting_score_val,
            contact=contact_score_val,
            ml_score=ml_score,
            ml_confidence=ml_conf,
            debug=True,
        )
        # `breakdown` is a dict with keys: final, rule_score, ml_score, ats_weight, model_weight
        final_score = round(float(breakdown.get("final", 0.0)), 2)
        # Propagate score confidence & input warnings from safeguard layer
        _sc = breakdown.get("score_confidence", 1.0)
        if _sc < 1.0:
            warnings.append(
                f"Score confidence reduced to {_sc} due to missing inputs: "
                + ", ".join(breakdown.get("input_warnings", []))
            )

    # ── ML Calibrator (optional blend) ────────────────────────────
    ml_calibration = None
    if bool(job_description and job_description.strip()):
        try:
            from services.ml_calibrator import predict_calibrated_score, blend_with_rule_score
            ml_pred = predict_calibrated_score(
                keyword_score=keyword_score,
                skill_score=skill_score,
                ats_score=ats_score,
                content_score=content_score,
                layout_score=layout_score,
                missing_count=len(missing_skills),
                cv_length=len(cv_text or ""),
                jd_length=len(job_description or ""),
            )
            if ml_pred is not None:
                final_score, ml_calibration = blend_with_rule_score(
                    rule_score=final_score,
                    ml_result=ml_pred,
                )
        except Exception:
            pass  # ML calibrator unavailable — use rule-based score

    interpretation = interpret_score_localized(final_score, detected_lang)

    # Localize risk level
    risk_level = localize_risk_level(risk_level, detected_lang)

    # If embeddings failed for this request, optionally apply a conservative
    # cap. Previously this was a hard-coded 40 which caused valid analyses
    # to be lowered unexpectedly when embeddings were unavailable.
    # Make the cap configurable via `EMBEDDING_CAP`. When unset, do NOT
    # artificially lower the final score; instead add a warning for the user.
    if embedding_failed:
        cap_val = os.getenv("EMBEDDING_CAP", "")
        if cap_val:
            try:
                cap_num = float(cap_val)
                capped = min(final_score, cap_num)
                if capped != final_score:
                    final_score = capped
                    interpretation = interpret_score_localized(final_score, detected_lang)
            except Exception:
                # If env var is malformed, skip capping but note warning
                warnings.append("Embedding cap configured but invalid; skipping cap.")
        else:
            # No cap configured: keep final_score as computed, but warn
            warnings.append(
                "Embeddings unavailable; semantic signals disabled for this analysis."
            )

    # ATS config-based composite score
    ats_weights = get_ats_weights()
    score_breakdown = {
        "skills": round(float(skill_score), 2),
        "keywords": round(float(keyword_score), 2),
        "format": float(ats_details["layout"].get("formatting_score", 0.0)),
        "experience": round(float(exp_score), 2),
    }
    total_w = sum(ats_weights.values()) or 1.0
    ats_weighted_score = 0.0
    for key, value in score_breakdown.items():
        w = float(ats_weights.get(key, 0.0))
        ats_weighted_score += value * w
    ats_weighted_score = round(float(ats_weighted_score / total_w), 2)

    # ── Score Decomposition ──────────────────────────────────────────
    # Separate "CV quality" (structural) from "job match" (relevance).
    # This prevents misleading UX where a chef's CV scores 71 against a dev JD
    # because the CV is well-structured, even though relevance is near zero.
    _has_jd = bool(job_description and job_description.strip())
    if _has_jd:
        # Job match: keyword + skill + semantic + seniority (content relevance)
        _job_match = round(min(100.0, max(0.0,
            keyword_score * 0.35
            + skill_score * 0.25
            + semantic_score * 0.25
            + seniority_match * 0.15
        )), 2)
        # ATS quality: structural quality independent of JD
        _ats_quality = round(min(100.0, max(0.0, float(ats_score))), 2)
        # Interpretation text
        if _job_match >= 70:
            _decomp_text = "Strong match for this role"
        elif _job_match >= 40:
            _decomp_text = "Partial match — some skills align"
        else:
            _decomp_text = "CV is well-structured but not aligned with this role"
    else:
        _job_match = 0.0
        _ats_quality = round(min(100.0, max(0.0, float(ats_score))), 2)
        _decomp_text = "No job description provided — showing CV quality only"

    score_decomposition = {
        "overall_score": final_score,
        "ats_quality": _ats_quality,
        "job_match": _job_match,
        "interpretation": _decomp_text,
    }

    result = {
        "semantic_score": round(semantic_score, 2),
        "keyword_score": keyword_score,
        "skill_score": skill_score,
        "experience_score": exp_score,
        "ats_score": ats_score,
        "ml_score": ml_score,
        "soft_skills_score": round(features[25], 2),
        "content_score": round(content_score, 2),
        "layout_score": round(layout_score, 2),
        "ats": ats_details,
        "domain_similarity": round(domain_similarity, 2),
        "detected_skills": detected_skills,
        "job_skills": jd_skills,
        "missing_skills": missing_skills,
        "extra_skills": extra_skills,
        "keyword_gap": keyword_gap,
        "keyword_gap_v2": keyword_gap_v2,
        "title_match": title_match,
        "seniority_match": seniority_match,
        "final_score": final_score,
        "interpretation": interpretation,
        "confidence": float(confidence),
        "risk_level": risk_level,
        "hire_decision": hire_decision,
        "hire_probability": hire_probability,
        "detected_language": detected_lang,
        "explanation": explanation,
        "recommendations": recommendations,
        "domain": domain_data,
        "industry": industry_data,
        "specialization": {
            "id": industry_data["specialization_id"],
            "name": industry_data["specialization_name"],
        },
        "score_breakdown": score_breakdown,
        "final_score_breakdown": breakdown,
        "ats_weights": ats_weights,
        "ats_weighted_score": ats_weighted_score,
        "embedding_available": not embedding_failed,
        "score_decomposition": score_decomposition,
        "ml_calibration": ml_calibration,
    }

    # ── Score Suggestions (actionable improvement tips) ────────────
    if _has_jd:
        from services.ats_service import generate_score_suggestions
        result["score_suggestions"] = generate_score_suggestions(
            missing_skills=missing_skills,
            keyword_gap=keyword_gap,
            keyword_score=keyword_score,
            skill_score=skill_score,
            final_score=final_score,
            total_jd_skills=len(jd_skills),
            lang=detected_lang,
        )
    else:
        result["score_suggestions"] = []

    # Language detection fallback warning
    if lang_detection_fallback:
        warnings.append(
            "Language could not be confidently detected; defaulting to English. "
            "You can set the 'lang' parameter explicitly for better results."
        )

    # Job description quality warning
    jd_stripped = (job_description or "").strip()
    if jd_stripped and len(jd_stripped.split()) < 15:
        warnings.append(
            "Job description is very short (fewer than 15 words). "
            "A detailed job description improves matching accuracy."
        )

    if warnings:
        result["warnings"] = warnings

    result["match_score_v2"] = _build_match_score_v2(result, keyword_gap_v2)

    # Store analysis result in Redis cache for subsequent identical requests.
    if cache_key:
        _analysis_mem_cache[cache_key] = (time.time(), result)

    if cache_key and redis_rate is not None:
        try:
            redis_rate.setex(cache_key, ANALYSIS_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result

# =====================================================
# TEXT ANALYZE
# =====================================================


@app.post("/api/v1/analyze")
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
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        mock_plan = _resolve_effective_plan(db, mock_db_user)
        mock_is_admin = _is_admin_user(mock_db_user)

        user_throttle = _consume_user_rate_limit(
            str(mock_user_id), RATE_LIMIT_USER_ANALYZE_PER_MIN, "analyze"
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(
                user_throttle["remaining"]
            )
            if not user_throttle["allowed"]:
                _metric_quota_hit("analyze", "user_per_minute")
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"User rate limit exceeded ({user_throttle['limit']}/minute)"
                    ),
                )

        if not mock_is_admin and not _is_premium_plan(mock_plan):
            redis_quota = _consume_daily_quota(
                str(mock_user_id), limit=_resolve_daily_limit_for_plan(mock_plan)
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

        try:
            result = run_pipeline(body.cv_text, body.job_description, body.lang)
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
                    mock_db, float(result.get("ats_score") or 0), _bm_prof,
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
        RATE_LIMIT_USER_ANALYZE_PER_MIN,
        "analyze",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(
            user_throttle["remaining"]
        )
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(
                    f"User rate limit exceeded ({user_throttle['limit']}/minute)"
                ),
            )

    # reset daily/monthly counters if a new quota day/month has started
    quota_today = _quota_today_date()
    now_utc = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < quota_today:
        db_user.daily_usage = 0
        db_user.last_reset = now_utc
    if db_user.updated_at is None or (db_user.updated_at.year, db_user.updated_at.month) != (quota_today.year, quota_today.month):
        db_user.monthly_usage = 0
        db_user.updated_at = now_utc

    # enforce limits: individual users use their own quota; recruiters use org quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = (
                db.query(Organization)
                .filter(Organization.id == db_user.organization_id)
                .first()
            )
        # organization daily/monthly quota based on org.plan_type
        if org:
            org_daily_limit = ORG_PLAN_LIMITS_DAILY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_DAILY["free"]
            )
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_MONTHLY["free"]
            )
            if (org.daily_usage or 0) >= org_daily_limit:
                _metric_quota_hit("analyze", "org_daily")
                raise HTTPException(
                    status_code=403, detail="Organization daily limit reached"
                )
            if (org.monthly_usage or 0) >= org_monthly_limit:
                _metric_quota_hit("analyze", "org_monthly")
                raise HTTPException(
                    status_code=403, detail="Organization monthly limit reached"
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
        result = run_pipeline(body.cv_text, body.job_description, body.lang)
        # Add AI recommendations
        score = result.get("final_score", 0)
        if score > 0.8:
            result["recommendations"] = [
                "Strong match! Prepare for behavioral and technical interviews.",
                "Highlight relevant projects and achievements in your CV.",
                "Practice common interview questions for this role."
            ]
        elif score > 0.6:
            result["recommendations"] = [
                "Good potential. Tailor your CV to emphasize matching skills.",
                "Consider gaining more experience in key areas.",
                "Network with professionals in this field."
            ]
        else:
            result["recommendations"] = [
                "Consider upskilling in required technologies.",
                "Seek entry-level positions or internships to build experience.",
                "Get feedback on your CV from mentors."
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
            "missing_skills": result.get("missing_skills", []),
            "recommendations": result.get("recommendations", []),
        },
    )

    try:
        # increment counters now that the request is allowed
        if db_user.role == "recruiter" and db_user.organization_id:
            org = (
                db.query(Organization)
                .filter(Organization.id == db_user.organization_id)
                .first()
            )
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
        try:
            cv_embedding = get_embedding(body.cv_text)
        except Exception:
            cv_embedding = None
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
            db, float(result.get("ats_score") or 0), _bm_prof,
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


@app.post("/api/v1/analyze-async")
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
        RATE_LIMIT_USER_ANALYZE_PER_MIN,
        "analyze-async",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(
            user_throttle["remaining"]
        )
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze-async", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(
                    f"User rate limit exceeded ({user_throttle['limit']}/minute)"
                ),
            )

    # Daily/monthly quota checks (reuse logic from analyze).
    quota_today = _quota_today_date()
    now_utc = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < quota_today:
        db_user.daily_usage = 0
        db_user.last_reset = now_utc
    if db_user.updated_at is None or (db_user.updated_at.year, db_user.updated_at.month) != (quota_today.year, quota_today.month):
        db_user.monthly_usage = 0
        db_user.updated_at = now_utc

    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = (
                db.query(Organization)
                .filter(Organization.id == db_user.organization_id)
                .first()
            )
        if org:
            org_daily_limit = ORG_PLAN_LIMITS_DAILY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_DAILY["free"]
            )
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                _normalize_plan(org.plan_type), ORG_PLAN_LIMITS_MONTHLY["free"]
            )
            if (org.daily_usage or 0) >= org_daily_limit:
                _metric_quota_hit("analyze-async", "org_daily")
                raise HTTPException(
                    status_code=403, detail="Organization daily limit reached"
                )
            if (org.monthly_usage or 0) >= org_monthly_limit:
                _metric_quota_hit("analyze-async", "org_monthly")
                raise HTTPException(
                    status_code=403, detail="Organization monthly limit reached"
                )
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
        result = run_pipeline(body.cv_text, body.job_description, body.lang)
        return {"job_id": "local-sync", "status": "completed", "result": result}

    task = analyze_text_task.delay(body.cv_text, body.job_description, body.lang)
    return {"job_id": task.id, "status": "queued"}


# =====================================================
# PDF ANALYZE
# =====================================================


@app.post("/api/v1/analyze-pdf")
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
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        mock_plan = _resolve_effective_plan(db, mock_db_user)
        mock_is_admin = _is_admin_user(mock_db_user)

        user_throttle = _consume_user_rate_limit(
            str(mock_user_id), RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN, "analyze-pdf"
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(
                user_throttle["remaining"]
            )
            if not user_throttle["allowed"]:
                _metric_quota_hit("analyze-pdf", "user_per_minute")
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"User rate limit exceeded ({user_throttle['limit']}/minute)"
                    ),
                )

        if not mock_is_admin and not _is_premium_plan(mock_plan):
            redis_quota = _consume_daily_quota(
                str(mock_user_id), limit=_resolve_daily_limit_for_plan(mock_plan)
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

        contents = await file.read()
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        if len(contents) > 5_000_000:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        # Optional virus scan in mock mode as well, when enabled
        try:
            _scan_upload_for_viruses(contents)
        except HTTPException:
            raise
        except Exception:
            # Fail closed on scanner errors when explicitly enabled
            if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
                raise HTTPException(status_code=500, detail="Virus scanner error")
        try:
            text, _pdf_truncated = _extract_pdf_text(contents)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PDF file")

        # ── CV detection: reject non-CV documents early ──
        from security.validators import is_probably_cv
        if not is_probably_cv(text):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not appear to be a CV/resume. Please upload a valid CV.",
            )

        autofix = auto_fix_cv_text(
            cv_text=text,
            job_description=job_description,
            lang=lang,
            use_ai=False,
            mode="safe",
        )
        normalized_text = autofix.get("optimized_cv_text") or text
        payload = structured_text_to_builder_payload(
            normalized_text,
            job_description=job_description,
            lang=lang,
        ).model_dump()
        result = run_pipeline(normalized_text, job_description, lang)
        result["builder_payload"] = payload
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
                    mock_db, float(result.get("ats_score") or 0), _bm_prof,
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
        RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN,
        "analyze-pdf",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(
            user_throttle["remaining"]
        )
        if not user_throttle["allowed"]:
            _metric_quota_hit("analyze-pdf", "user_per_minute")
            raise HTTPException(
                status_code=429,
                detail=(
                    f"User rate limit exceeded ({user_throttle['limit']}/minute)"
                ),
            )

    # reset daily counter if a new day has started
    if (
        db_user.last_reset is None
        or db_user.last_reset.date() < _quota_today_date()
    ):
        db_user.daily_usage = 0
        db_user.last_reset = datetime.utcnow()

    # enforce limits: individual users use personal quota; recruiters use org monthly quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = (
                db.query(Organization)
                .filter(Organization.id == db_user.organization_id)
                .first()
            )
        if (
            org
            and org.plan_type == "free"
            and org.monthly_usage >= ORG_PLAN_LIMITS_MONTHLY["free"]
        ):
            _metric_quota_hit("analyze-pdf", "org_monthly")
            raise HTTPException(
                status_code=429, detail="Organization monthly limit reached"
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
    contents = await file.read()
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    # Optional virus scan for uploaded PDFs
    try:
        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise
    except Exception:
        if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail="Virus scanner error")
    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    from renderers.blocks import fix_decomposed_diacritics
    _pdf_truncated = len(text) > _MAX_PDF_EXTRACTED_CHARS
    if _pdf_truncated:
        text = text[:_MAX_PDF_EXTRACTED_CHARS]
    text = fix_decomposed_diacritics(text)

    # Force extract → normalize pipeline before analysis task enqueue.
    autofix = auto_fix_cv_text(
        cv_text=text,
        job_description=job_description,
        lang=lang,
        use_ai=False,
        mode="safe",
    )
    normalized_text = autofix.get("optimized_cv_text") or text

    # Queue the analysis job (or run synchronously in LocalTask fallback)
    task = analyze_pdf_task.delay(normalized_text, job_description, lang)

    # If the task ran synchronously (LocalTask), the wrapper returns a
    # DummyResult with `.status` and `.result` attributes — return the
    # actual analysis result immediately in that case for a better UX.
    try:
        if getattr(task, "status", None) == "SUCCESS" and hasattr(task, "result"):
            result = dict(task.result) if task.result else {}
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
                        "missing_skills": result.get("missing_skills", []),
                        "recommendations": result.get("recommendations", []),
                    },
                )
                db.add(analysis_record)
                db.commit()
                db.refresh(analysis_record)

                try:
                    cv_embedding = get_embedding(text)
                except Exception:
                    cv_embedding = None
                cand = Candidate(
                    organization_id=db_user.organization_id,
                    cv_text=text,
                )
                db.add(cand)
                db.commit()
                db.refresh(cand)
                if cv_embedding:
                    save_candidate_embedding(db, cand.id, cv_embedding)

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
                        db, float(result.get("ats_score") or 0), _bm_prof,
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


@app.get("/api/v1/analysis/{job_id}")
def get_analysis_result(job_id: str, user=Depends(verify_supabase_jwt)):
    """Poll the status/result of an async analysis job.

    For LocalTask fallback, the original analyze-async endpoint will already
    have returned the result inline, but this endpoint remains useful when
    Celery/Redis are enabled.
    """
    _ensure_not_expired(user)

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


@app.get("/api/v1/history")
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
        base_query = base_query.filter(
            Analysis.interpretation.ilike(f"%{q}%") | Analysis.job_title.ilike(f"%{q}%")
        )
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
    records = (
        base_query
        .order_by(Analysis.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {"items": records, "total": total, "limit": limit, "offset": offset}


# ── Analytics Dashboard ────────────────────────────────────────


@app.get("/api/v1/analytics")
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


@app.get("/api/v1/export/analysis/{analysis_id}")
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
    pdf.cell(200, 10, txt=f"CV Analysis Report", ln=True, align='C')
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

    pdf_output = pdf.output(dest='S')
    return StreamingResponse(
        iter([pdf_output]),
        media_type='application/pdf',
        headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.pdf"}
    )


# ── Integration Options ────────────────────────────────────────


@app.post("/api/v1/integrations/import-jobs")
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
        response = requests.get(url, timeout=10)
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


@app.post("/api/v1/share-legacy/{analysis_id}")
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


@app.get("/api/v1/shared-legacy/{token}")
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


@app.get("/api/v1/usage-history")
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

    return {
        "days": [
            {"date": r.date.strftime("%Y-%m-%d"), "count": r.count}
            for r in rows
        ]
    }


# ── Favorites CRUD ──────────────────────────────────────────────


class FavoriteToggleRequest(BaseModel):
    analysis_id: int
    note: str = ""


@app.get("/api/v1/favorites")
def list_favorites(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
):
    """List user's favorite/bookmarked analyses."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    favs = (
        db.query(Favorite)
        .filter(Favorite.user_id == db_user.id)
        .order_by(Favorite.created_at.desc())
        .limit(limit)
        .all()
    )

    # Also fetch associated analysis data
    analysis_ids = [f.analysis_id for f in favs]
    analyses = {}
    if analysis_ids:
        records = db.query(Analysis).filter(Analysis.id.in_(analysis_ids)).all()
        analyses = {a.id: a for a in records}

    return {
        "favorites": [
            {
                "id": f.id,
                "analysis_id": f.analysis_id,
                "note": f.note or "",
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "analysis": {
                    "similarity_score": a.similarity_score,
                    "interpretation": a.interpretation,
                    "job_title": a.job_title,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                } if (a := analyses.get(f.analysis_id)) else None,
            }
            for f in favs
        ]
    }


@app.post("/api/v1/favorites/toggle")
def toggle_favorite(
    body: FavoriteToggleRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Toggle favorite status for an analysis. Returns { favorited: bool }."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Check plan limit for free users
    if db_user.plan_type == "free":
        fav_count = db.query(Favorite).filter(Favorite.user_id == db_user.id).count()
        if fav_count >= 5:
            # Check if we're removing (toggling off) — allow that
            existing = (
                db.query(Favorite)
                .filter(Favorite.user_id == db_user.id, Favorite.analysis_id == body.analysis_id)
                .first()
            )
            if not existing:
                raise HTTPException(
                    status_code=403,
                    detail="Free plan limited to 5 favorites. Upgrade for unlimited.",
                )

    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == db_user.id, Favorite.analysis_id == body.analysis_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "analysis_id": body.analysis_id}
    else:
        fav = Favorite(
            user_id=db_user.id,
            analysis_id=body.analysis_id,
            note=body.note[:200] if body.note else "",
        )
        db.add(fav)
        db.commit()
        return {"favorited": True, "analysis_id": body.analysis_id, "id": fav.id}


@app.get("/api/v1/favorites/ids")
def get_favorite_ids(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Quick lookup: returns list of analysis_ids that are favorited."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    ids = (
        db.query(Favorite.analysis_id)
        .filter(Favorite.user_id == db_user.id)
        .all()
    )
    return {"ids": [r[0] for r in ids]}


# ── Job Description Templates CRUD ──────────────────────────────


class JDTemplateCreate(BaseModel):
    title: str
    description: str


@app.get("/api/v1/jd-templates")
def list_jd_templates(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """List user's saved job description templates."""
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    templates = (
        db.query(JobTemplate)
        .filter(JobTemplate.user_id == db_user.id)
        .order_by(JobTemplate.created_at.desc())
        .all()
    )
    return {
        "templates": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ]
    }


@app.post("/api/v1/jd-templates")
def create_jd_template(
    body: JDTemplateCreate,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Create a saved JD template. Free: max 3, Pro: unlimited."""
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    if not body.title.strip() or not body.description.strip():
        raise HTTPException(status_code=400, detail="Title and description required")

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        count = db.query(JobTemplate).filter(JobTemplate.user_id == db_user.id).count()
        if count >= 3:
            raise HTTPException(
                status_code=403,
                detail="Free plan limited to 3 templates. Upgrade for unlimited.",
            )

    tmpl = JobTemplate(
        user_id=db_user.id,
        title=body.title.strip()[:120],
        description=body.description.strip()[:5000],
    )
    db.add(tmpl)
    db.commit()
    return {"id": tmpl.id, "title": tmpl.title}


@app.delete("/api/v1/jd-templates/{template_id}")
def delete_jd_template(
    template_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    tmpl = (
        db.query(JobTemplate)
        .filter(JobTemplate.id == template_id, JobTemplate.user_id == db_user.id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tmpl)
    db.commit()
    return {"deleted": True}


# ── Analysis Sharing (public link) ──────────────────────────────


class ShareRequest(BaseModel):
    analysis_id: int


@app.post("/api/v1/share")
def create_share_link(
    body: ShareRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Create a public share link for an analysis (Pro feature)."""
    from models import AnalysisShare
    import secrets

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        raise HTTPException(
            status_code=403,
            detail="Sharing is a Pro feature. Upgrade to share analyses.",
        )

    # Check if share already exists
    existing = (
        db.query(AnalysisShare)
        .filter(
            AnalysisShare.user_id == db_user.id,
            AnalysisShare.analysis_id == body.analysis_id,
            AnalysisShare.is_active == True,
        )
        .first()
    )
    if existing:
        return {"share_token": existing.share_token, "already_exists": True}

    token = secrets.token_urlsafe(32)
    share = AnalysisShare(
        user_id=db_user.id,
        analysis_id=body.analysis_id,
        share_token=token,
    )
    db.add(share)
    db.commit()
    return {"share_token": token, "already_exists": False}


@app.delete("/api/v1/share/{share_token}")
def revoke_share_link(
    share_token: str,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisShare

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    share = (
        db.query(AnalysisShare)
        .filter(AnalysisShare.share_token == share_token, AnalysisShare.user_id == db_user.id)
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    share.is_active = False
    db.commit()
    return {"revoked": True}


@app.get("/api/v1/shared/{share_token}")
def view_shared_analysis(
    share_token: str,
    db=Depends(get_db),
):
    """Public endpoint — no auth required. View shared analysis result."""
    from models import AnalysisShare

    share = (
        db.query(AnalysisShare)
        .filter(AnalysisShare.share_token == share_token, AnalysisShare.is_active == True)
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    analysis = db.query(Analysis).filter(Analysis.id == share.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    share.views = (share.views or 0) + 1
    db.commit()

    return {
        "score": analysis.similarity_score,
        "interpretation": analysis.interpretation,
        "job_title": analysis.job_title,
        "result": analysis.result if isinstance(analysis.result, dict) else {},
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "views": share.views,
    }


# ── History CSV Export ──────────────────────────────────────────


@app.get("/api/v1/history/export")
def export_history_csv(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Export user's analysis history as CSV (Pro feature)."""
    import csv
    import io

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        raise HTTPException(
            status_code=403,
            detail="CSV export is a Pro feature. Upgrade to export history.",
        )

    records = (
        db.query(Analysis)
        .filter(Analysis.user_id == db_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(500)
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Job Title", "Score", "Interpretation", "ATS Score", "Semantic", "Keyword", "Skill", "Experience"])
    for r in records:
        res = r.result if isinstance(r.result, dict) else {}
        writer.writerow([
            r.created_at.isoformat() if r.created_at else "",
            r.job_title or "",
            r.similarity_score or 0,
            r.interpretation or "",
            res.get("ats_score", ""),
            res.get("semantic_score", ""),
            res.get("keyword_score", ""),
            res.get("skill_score", ""),
            res.get("experience_score", ""),
        ])

    from starlette.responses import StreamingResponse
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cv_analysis_history.csv"},
    )


# ── Analysis Notes CRUD ─────────────────────────────────────────


class NoteRequest(BaseModel):
    analysis_id: int
    content: str


@app.post("/api/v1/notes")
def save_analysis_note(
    body: NoteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Save or update a note on an analysis."""
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Note content required")

    existing = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == body.analysis_id)
        .first()
    )

    if existing:
        existing.content = body.content.strip()[:2000]
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"id": existing.id, "updated": True}
    else:
        note = AnalysisNote(
            user_id=db_user.id,
            analysis_id=body.analysis_id,
            content=body.content.strip()[:2000],
        )
        db.add(note)
        db.commit()
        return {"id": note.id, "updated": False}


@app.get("/api/v1/notes/{analysis_id}")
def get_analysis_note(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    note = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == analysis_id)
        .first()
    )
    if not note:
        return {"content": "", "exists": False}
    return {
        "id": note.id,
        "content": note.content,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "exists": True,
    }


@app.delete("/api/v1/notes/{analysis_id}")
def delete_analysis_note(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    note = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == analysis_id)
        .first()
    )
    if note:
        db.delete(note)
        db.commit()
    return {"deleted": True}


# ── Usage Streak ────────────────────────────────────────────────


@app.get("/api/v1/usage-streak")
def get_usage_streak(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Return current and longest usage streaks for gamification."""
    from models import UsageDaily
    from datetime import timedelta

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    rows = (
        db.query(UsageDaily.date)
        .filter(UsageDaily.user_id == db_user.id, UsageDaily.count > 0)
        .order_by(UsageDaily.date.desc())
        .limit(365)
        .all()
    )

    if not rows:
        return {"current_streak": 0, "longest_streak": 0, "total_active_days": 0}

    dates = sorted(set(r[0].date() if hasattr(r[0], 'date') else r[0] for r in rows), reverse=True)
    today = datetime.utcnow().date()

    # Current streak
    current = 0
    for i, d in enumerate(dates):
        expected = today - timedelta(days=i)
        if d == expected:
            current += 1
        else:
            break

    # Longest streak
    longest = 1
    streak = 1
    sorted_asc = sorted(dates)
    for i in range(1, len(sorted_asc)):
        if (sorted_asc[i] - sorted_asc[i - 1]).days == 1:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 1

    return {
        "current_streak": current,
        "longest_streak": max(longest, current),
        "total_active_days": len(dates),
    }


# ── Dashboard Insights ──────────────────────────────────────────


@app.get("/api/v1/insights")
def get_dashboard_insights(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Return AI-powered insights and tips based on user's analysis history."""
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    records = (
        db.query(Analysis)
        .filter(Analysis.user_id == db_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
        .all()
    )

    if not records:
        return {"insights": [], "stats": {}}

    scores = [r.similarity_score for r in records if r.similarity_score]
    avg_score = sum(scores) / len(scores) if scores else 0
    best_score = max(scores) if scores else 0
    worst_score = min(scores) if scores else 0
    total = len(records)

    # Trend: compare last 5 vs previous 5
    recent_5 = scores[:5] if len(scores) >= 5 else scores
    prev_5 = scores[5:10] if len(scores) >= 10 else []
    trend = "improving" if prev_5 and (sum(recent_5)/len(recent_5)) > (sum(prev_5)/len(prev_5)) else "stable"
    if prev_5 and (sum(recent_5)/len(recent_5)) < (sum(prev_5)/len(prev_5)) - 5:
        trend = "declining"

    # Find weakest dimensions
    dim_totals = {"semantic": [], "keyword": [], "skill": [], "experience": [], "ats": []}
    for r in records:
        res = r.result if isinstance(r.result, dict) else {}
        for dim in dim_totals:
            val = res.get(f"{dim}_score")
            if val is not None:
                dim_totals[dim].append(val)

    dim_avgs = {k: sum(v)/len(v) if v else 0 for k, v in dim_totals.items()}
    weakest = sorted(dim_avgs.items(), key=lambda x: x[1])[:2]

    insights = []

    if trend == "improving":
        insights.append({
            "type": "positive",
            "icon": "📈",
            "text": f"Skorlarınız yükseliyor! Son analizlerde ortalama {sum(recent_5)/len(recent_5):.0f}%",
        })
    elif trend == "declining":
        insights.append({
            "type": "warning",
            "icon": "📉",
            "text": "Son analizlerde skorlarınız düşüş eğiliminde. Önerilere dikkat edin.",
        })

    if weakest and weakest[0][1] < 60:
        dim_name = {"semantic": "Semantik uyum", "keyword": "Anahtar kelime", "skill": "Yetenek eşleşme", "experience": "Deneyim", "ats": "ATS uyumluluk"}.get(weakest[0][0], weakest[0][0])
        insights.append({
            "type": "tip",
            "icon": "💡",
            "text": f"En zayıf alanınız: {dim_name} (ort. {weakest[0][1]:.0f}%). Bu boyutu iyileştirmeye odaklanın.",
        })

    if total >= 5 and avg_score >= 70:
        insights.append({
            "type": "achievement",
            "icon": "🏆",
            "text": f"{total} analiz tamamlandı, ortalama {avg_score:.0f}%. Harika gidiyorsunuz!",
        })

    if best_score >= 90:
        insights.append({
            "type": "positive",
            "icon": "⭐",
            "text": f"En iyi skorunuz {best_score:.0f}%! Mükemmel CV-iş uyumu.",
        })

    if total < 3:
        insights.append({
            "type": "tip",
            "icon": "🚀",
            "text": "Daha fazla analiz yaparak trend verilerinizi zenginleştirin.",
        })

    return {
        "insights": insights[:4],
        "stats": {
            "avg_score": round(avg_score, 1),
            "best_score": round(best_score, 1),
            "worst_score": round(worst_score, 1),
            "total": total,
            "trend": trend,
            "weakest_dim": weakest[0][0] if weakest else None,
        },
    }


# ── Global ATS Benchmark Endpoints (before catch-all {analysis_id}) ──


# ── Blog Feed: trending tech articles from Dev.to ───────────────────
_blog_feed_cache: dict = {"data": [], "ts": 0}

@app.get("/api/v1/blog/feed")
@rate_limit("10/minute")
async def get_blog_feed(request: Request):
    """Return trending tech/career articles from Dev.to (cached 4h)."""
    import time as _time
    import httpx

    now = _time.time()
    if _blog_feed_cache["data"] and (now - _blog_feed_cache["ts"]) < 14400:
        return {"articles": _blog_feed_cache["data"]}

    tags = ["career", "webdev", "programming", "ai", "python", "javascript"]
    articles = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for tag in tags[:3]:
                resp = await client.get(
                    "https://dev.to/api/articles",
                    params={"tag": tag, "top": 1, "per_page": 3},
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    for item in resp.json():
                        # Sanitize URLs - only allow https
                        raw_url = str(item.get("url") or "")
                        raw_image = str(item.get("cover_image") or item.get("social_image") or "")
                        raw_avatar = str(item.get("user", {}).get("profile_image_90") or "")
                        articles.append({
                            "id": item.get("id"),
                            "title": str(item.get("title") or "")[:200],
                            "summary": str(item.get("description") or "")[:500],
                            "url": raw_url if raw_url.startswith("https://") else "",
                            "image": raw_image if raw_image.startswith("https://") else "",
                            "author": str(item.get("user", {}).get("name") or "")[:100],
                            "author_avatar": raw_avatar if raw_avatar.startswith("https://") else "",
                            "published_at": item.get("published_at", ""),
                            "reading_time": item.get("reading_time_minutes", 3),
                            "tags": item.get("tag_list", [])[:10],
                            "reactions": item.get("positive_reactions_count", 0),
                            "comments": item.get("comments_count", 0),
                            "source": "dev.to",
                        })
    except Exception as exc:
        logger.warning("blog_feed: dev.to fetch failed: %s", exc)
        if _blog_feed_cache["data"]:
            return {"articles": _blog_feed_cache["data"]}
        return {"articles": []}

    seen_ids = set()
    unique = []
    for a in articles:
        if a["id"] not in seen_ids:
            seen_ids.add(a["id"])
            unique.append(a)
    unique.sort(key=lambda x: x.get("reactions", 0), reverse=True)
    unique = unique[:8]

    _blog_feed_cache["data"] = unique
    _blog_feed_cache["ts"] = now
    return {"articles": unique}


@app.get("/api/v1/benchmark/global")
@rate_limit("20/minute")
def get_global_benchmark_stats(request: Request, db=Depends(get_db)):
    """Return global ATS benchmark statistics (public, aggregated only)."""
    from services.benchmark_service import get_global_stats as _bm_global
    return _bm_global(db)


@app.get("/api/v1/benchmark/professions")
@rate_limit("20/minute")
def get_profession_benchmarks(request: Request, db=Depends(get_db)):
    """Return ATS benchmark statistics per profession group."""
    from services.benchmark_service import get_profession_stats as _bm_profs
    return {"professions": _bm_profs(db)}


@app.get("/api/v1/benchmark/{analysis_id:int}")
def get_benchmark(analysis_id: int, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return peer-group benchmark for a user's own analysis."""
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if not _is_premium_plan(effective_plan):
        raise HTTPException(status_code=403, detail="Premium plan required")

    analysis_record = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id)
        .first()
    )
    if not analysis_record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    benchmark = _build_analysis_benchmark(db, analysis_record)
    return {
        "analysis_id": analysis_id,
        "score": float(analysis_record.similarity_score or 0),
        "effective_plan": effective_plan,
        "benchmark": benchmark,
    }


@app.get("/api/v1/usage")
def get_usage(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return usage counters for UI usage widgets."""
    _ensure_not_expired(user)

    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        effective_plan = _resolve_effective_plan(db, db_user)
        is_admin = _is_admin_user(db_user)
        daily_limit = (10**12) if is_admin else _resolve_daily_limit_for_plan(effective_plan)
        redis_quota = _get_daily_quota_status(str(mock_user_id), limit=daily_limit)
        if redis_quota is None:
            return {
                "plan_type": effective_plan,
                "role": db_user.role or "individual",
                "source": "mock",
                "daily": {
                    "used": int(db_user.daily_usage or 0),
                    "limit": daily_limit,
                    "remaining": (10**12) if is_admin else max(0, int(daily_limit - int(db_user.daily_usage or 0))),
                },
                "monthly": {
                    "used": int(db_user.monthly_usage or 0),
                    "limit": (10**12) if is_admin else int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                    "remaining": (10**12) if is_admin else max(
                        0,
                        int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])) - int(db_user.monthly_usage or 0),
                    ),
                },
            }
        return {
            "plan_type": effective_plan,
            "role": db_user.role or "individual",
            "source": "redis",
            "daily": {
                "used": redis_quota["used"],
                "limit": (10**12) if is_admin else redis_quota["limit"],
                "remaining": (10**12) if is_admin else redis_quota["remaining"],
            },
            "monthly": {
                "used": int(db_user.monthly_usage or 0),
                "limit": (10**12) if is_admin else int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                "remaining": (10**12) if is_admin else max(
                    0,
                    int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])) - int(db_user.monthly_usage or 0),
                ),
            },
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    plan_type = _resolve_effective_plan(db, db_user)
    is_admin = _is_admin_user(db_user)
    user_daily_limit = USER_PLAN_LIMITS_DAILY.get(plan_type, USER_PLAN_LIMITS_DAILY["free"])
    user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
        plan_type, USER_PLAN_LIMITS_MONTHLY["free"]
    )

    redis_quota = _get_daily_quota_status(
        db_user.supabase_id or str(db_user.id),
        limit=_resolve_daily_limit_for_plan(plan_type),
    )

    if redis_quota is not None:
        daily_used = redis_quota["used"]
        daily_limit = (10**12) if is_admin else redis_quota["limit"]
        daily_remaining = (10**12) if is_admin else redis_quota["remaining"]
        source = "redis"
    else:
        daily_used = int(db_user.daily_usage or 0)
        daily_limit = (10**12) if is_admin else int(user_daily_limit)
        daily_remaining = (10**12) if is_admin else max(0, daily_limit - daily_used)
        source = "db"

    monthly_used = int(db_user.monthly_usage or 0)
    monthly_limit = (10**12) if is_admin else int(user_monthly_limit)

    return {
        "plan_type": plan_type,
        "role": db_user.role or "individual",
        "source": source,
        "daily": {
            "used": daily_used,
            "limit": daily_limit,
            "remaining": daily_remaining,
        },
        "monthly": {
            "used": monthly_used,
            "limit": monthly_limit,
            "remaining": (10**12) if is_admin else max(0, monthly_limit - monthly_used),
        },
    }


@app.get("/api/v1/me")
def get_me(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return authenticated user's profile: role, plan, email."""
    _ensure_not_expired(user)
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        db_user = get_or_create_user(db, str(mock_user_id or "mock-user"), mock_email or "dev@example.com")
    else:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
    return {
        "role": db_user.role or "individual",
        "plan_type": _normalize_plan(db_user.plan_type),
        "email": db_user.email,
        "organization_id": db_user.organization_id,
    }


@app.get("/api/v1/benchmark/specializations")
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


class SemanticSearchRequest(BaseModel):
    job_text: str | None = None
    job_id: int | None = None
    k: int = 10
    persist_job: bool = False


@app.post("/api/v1/semantic-search")
@rate_limit("20/minute")
def semantic_search(
    body: SemanticSearchRequest, user=Depends(verify_supabase_jwt), db=Depends(get_db)
):
    _ensure_not_expired(user)

    # Require either job_text or job_id
    if not body.job_text and not body.job_id:
        raise HTTPException(status_code=400, detail="Provide job_text or job_id")

    # Resolve job embedding
    job_vec = None
    if body.job_id:
        job = db.query(Job).filter(Job.id == body.job_id).one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_vec = job.job_embedding
        if not job_vec:
            job_vec = get_embedding(job.raw_text or "")
            if job_vec:
                try:
                    save_job_embedding(db, job.id, job_vec)
                except Exception:
                    pass
    else:
        # job_text provided
        job_vec = get_embedding(body.job_text or "")
        if body.persist_job and job_vec:
            try:
                new_job = Job(raw_text=body.job_text, job_embedding=job_vec)
                db.add(new_job)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

    if not job_vec:
        raise HTTPException(status_code=500, detail="Failed to compute job embedding")

    # Find top-k similar candidates (returns list of (id, score))
    matches = find_similar_candidates(db, job_vec, k=body.k)
    candidate_ids = [m[0] for m in matches]

    # Fetch candidate rows preserving order
    candidates = []
    if candidate_ids:
        rows = db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).all()
        rows_map = {r.id: r for r in rows}
        for cid, score in matches:
            r = rows_map.get(cid)
            if r:
                candidates.append(
                    {
                        "id": r.id,
                        "cv_text": (
                            (r.cv_text[:200] + "...")
                            if r.cv_text and len(r.cv_text) > 200
                            else r.cv_text
                        ),
                        "organization_id": r.organization_id,
                        "score": float(score),
                    }
                )

    return {"matches": candidates}


# =====================================================
# AI REWRITE ENDPOINTS
# =====================================================


@app.post("/api/v1/cv/auto-fix")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN}/minute")
async def auto_fix_cv_pdf(
    file: UploadFile = File(...),
    job_description: str = Form(""),
    lang: str = Form("en"),
    use_ai: bool = Form(True),
    mode: str = Form("safe"),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Extract a CV from PDF and rewrite it into a cleaner ATS-friendly format."""
    if not _get_flag("auto_fix"):
        raise HTTPException(status_code=503, detail="auto-fix feature is disabled")
    if _cb_is_open("s3"):
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    _ensure_not_expired(user)
    _metric_request("cv-auto-fix")
    try:
        OPTIMIZES_TOTAL.inc()
    except Exception:
        pass
    _check_cost_guard("optimize", COST_OPTIMIZE_PER_DAY)

    db_user = None
    supabase_id = None
    if not MOCK_SERVICES_ON:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)

    # Per-user + global optimize concurrency guard
    from security.runtime_guard import OptimizeConcurrencyGuard
    try:
        guard = OptimizeConcurrencyGuard(supabase_id or "anon")
        guard.__enter__()
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        contents = await file.read()
        _validate_pdf_upload(contents, file.content_type)
        cv_text, _cv_truncated = _extract_pdf_text(contents)

        try:
            result = await run_in_threadpool(
                auto_fix_cv_text,
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
                use_ai=use_ai,
                mode=mode,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.exception("auto_fix_cv_text unexpected error")
            raise HTTPException(status_code=500, detail=f"Auto-fix error: {e}")
    finally:
        guard.__exit__(None, None, None)

    try:
        audit_payload = {
            "source": "pdf",
            "used_ai": bool(result.get("used_ai")),
            "score_delta": float(result.get("score_delta", 0.0)),
        }
        if db_user is not None:
            audit_payload["user_id"] = db_user.id
            audit_payload["organization_id"] = db_user.organization_id
        audit_log("cv_auto_fix", **audit_payload)
    except Exception:
        pass

    if _cv_truncated:
        result["truncated"] = True
        result["truncation_warning"] = (
            f"CV content exceeded {_MAX_PDF_EXTRACTED_CHARS:,} characters and was truncated. "
            "Analysis may be incomplete for very long documents."
        )

    return result


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = "en"
    tone: str = "professional"
    mode: str = "senior"


class CVAutoFixExportRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = "en"
    font_family: str = ""


class CVAutoFixParseRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    lang: str = "en"


class BulletRewriteRequest(BaseModel):
    bullets: list[str]
    job_description: str | None = ""
    lang: str = "en"
    tone: str = "professional"


class CoverLetterRewriteRequest(BaseModel):
    cv_text: str
    job_description: str
    company_name: str | None = ""
    lang: str = "en"
    tone: str = "professional"
    mode: str = "senior"


class LinkedInOptimizeRequest(BaseModel):
    cv_text: str
    target_role: str | None = ""
    lang: str = "en"
    mode: str = "senior"
    headline: str | None = ""


class JobMatchScoreRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = "en"
    mode: str = "senior"  # junior | senior | manager | tech | academic


class SaveCVVersionRequest(BaseModel):
    cv_text: str
    optimized_cv_text: str | None = ""
    job_description: str | None = ""
    version_label: str | None = ""
    source: str = "manual"
    lang: str = "en"
    notes: str | None = ""


class KeywordGapRequest(BaseModel):
    cv_text: str
    job_description: str


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    lang: str = "en"


class KeywordOptimizeRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = "en"


class RecruiterAdvancedSearchRequest(BaseModel):
    skills: list[str] = []
    min_score: float = 0.0
    min_experience: int = 0
    limit: int = 20
    use_semantic: bool = False
    job_text: str = ""


class FeedbackRequest(BaseModel):
    category: str = "bug"
    message: str
    page: str | None = ""
    lang: str | None = ""
    score: int | None = None
    context: dict | None = None


def _ensure_ai_rewrite_allowed(db, db_user: User):
    plan = _resolve_effective_plan(db, db_user)
    if not is_feature_enabled(plan, "ai_rewrite"):
        raise HTTPException(status_code=403, detail="AI rewrite not enabled for plan")
    return plan


def _next_cv_version_label(db, user_id: int) -> str:
    try:
        total = db.query(CVVersion).filter(CVVersion.user_id == user_id).count()
        return f"v{total + 1}"
    except Exception:
        return "v1"


@app.post("/api/v1/rewrite/cv")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_cv_endpoint(
    body: CVRewriteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    from security.runtime_guard import OptimizeConcurrencyGuard
    try:
        with OptimizeConcurrencyGuard(supabase_id):
            try:
                text = rewrite_service.ai_rewrite_cv(
                    cv_text=body.cv_text,
                    job_description=body.job_description or "",
                    lang=body.lang,
                    tone=body.tone,
                    mode=body.mode,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except RuntimeError as e:
                raise HTTPException(status_code=503, detail=str(e))
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        audit_log(
            "ai_rewrite_cv",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"result": text, "plan": plan}


@app.post("/api/v1/cv/auto-fix/export")
@rate_limit(f"{RATE_LIMIT_IP_RENDER_PER_MIN}/minute")
def export_auto_fixed_cv(
    body: CVAutoFixExportRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from fastapi.responses import StreamingResponse

    _ensure_not_expired(user)

    if body.output_format not in ("docx", "pdf", "html"):
        raise HTTPException(status_code=400, detail="output_format must be 'docx', 'pdf' or 'html'")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    effective_plan = _resolve_effective_plan(db, db_user)

    cv_model = structured_text_to_builder_payload(
        body.optimized_cv_text,
        job_description=body.job_description or "",
        lang=body.lang,
    )
    cv_data = cv_model.model_dump()
    cv_data["template"] = body.template
    cv_data["output_format"] = body.output_format

    try:
        _t0 = time.time()
        # Font selection: only premium plans can override font
        _font = body.font_family if _is_premium_plan(effective_plan) else ""
        result = build_cv(
            cv_data=cv_data,
            job_description=body.job_description or "",
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=effective_plan,
            font_family=_font,
        )
        _metric_parse_latency("build_cv", time.time() - _t0)
    except Exception as exc:
        if "overloaded" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc))
        logger.exception("build_cv failed in auto-fix export")
        raise HTTPException(status_code=500, detail="CV generation failed")

    try:
        audit_log(
            "cv_auto_fix_export",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            output_format=body.output_format,
            template=body.template,
        )
    except Exception:
        pass

    buf = result["buffer"]
    if hasattr(buf, "getbuffer") and buf.getbuffer().nbytes > _MAX_RESPONSE_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Generated file too large")

    return StreamingResponse(
        buf,
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@app.post("/api/v1/cv/auto-fix/parse")
def parse_auto_fixed_cv(
    body: CVAutoFixParseRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        builder_payload = structured_text_to_builder_payload(
            body.optimized_cv_text,
            job_description=body.job_description or "",
            lang=body.lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        audit_log(
            "cv_auto_fix_parse",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            lang=body.lang,
        )
    except Exception:
        pass

    return {"builder_payload": builder_payload.model_dump()}


@app.post("/api/v1/feedback")
def submit_feedback(
    body: FeedbackRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    message = str(body.message or "").strip()
    if len(message) < 5:
        raise HTTPException(status_code=400, detail="Feedback message is too short")
    if len(message) > 3000:
        raise HTTPException(status_code=400, detail="Feedback message is too long")

    category = str(body.category or "bug").strip().lower()
    allowed_categories = {"bug", "feature", "ux", "other"}
    if category not in allowed_categories:
        category = "other"

    score = body.score
    if score is not None and (score < 1 or score > 5):
        raise HTTPException(status_code=400, detail="score must be between 1 and 5")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": str(db_user.id) if getattr(db_user, "id", None) is not None else None,
        "supabase_id": supabase_id,
        "email": email,
        "category": category,
        "page": str(body.page or "").strip()[:120],
        "lang": str(body.lang or "").strip()[:12],
        "score": score,
        "message": message,
        "context": body.context if isinstance(body.context, dict) else {},
    }

    _append_feedback_record(payload)
    emailed = _send_feedback_email(payload)

    try:
        audit_log(
            "user_feedback",
            user_id=payload.get("user_id"),
            organization_id=getattr(db_user, "organization_id", None),
            category=category,
            page=payload.get("page"),
            score=score,
        )
    except Exception:
        pass

    return {"ok": True, "message": "Feedback received", "emailed": emailed}


@app.get("/api/v1/feedback")
def list_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    role = (getattr(db_user, "role", "individual") or "individual").lower()

    include_all = role == "recruiter"
    items = _read_feedback_records(
        limit=limit,
        supabase_id=str(supabase_id) if supabase_id else None,
        include_all=include_all,
    )

    # Hide sensitive fields from API consumers.
    cleaned = []
    for row in items:
        cleaned.append(
            {
                "timestamp": row.get("timestamp"),
                "category": row.get("category"),
                "page": row.get("page"),
                "lang": row.get("lang"),
                "score": row.get("score"),
                "message": row.get("message"),
                "context": row.get("context") or {},
                "submitter": row.get("email") if include_all else None,
            }
        )

    return {"items": cleaned, "count": len(cleaned), "scope": "all" if include_all else "self"}


@app.post("/api/v1/rewrite/bullets")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_bullets_endpoint(
    body: BulletRewriteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    try:
        bullets = rewrite_service.rewrite_bullets(
            bullets=body.bullets,
            job_description=body.job_description or "",
            lang=body.lang,
            tone=body.tone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_rewrite_bullets",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            bullet_count=len(body.bullets or []),
        )
    except Exception:
        pass

    return {"results": bullets, "plan": plan}


@app.post("/api/v1/rewrite/cover-letter")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_cover_letter_endpoint(
    body: CoverLetterRewriteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    try:
        builder_payload = structured_text_to_builder_payload(
            body.cv_text,
            job_description=body.job_description,
            lang=body.lang,
        )
        letter = rewrite_service.rewrite_cover_letter_from_builder_payload(
            builder_payload=builder_payload.model_dump(),
            job_description=body.job_description,
            company_name=body.company_name or "",
            lang=body.lang,
            tone=body.tone,
            mode=body.mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_rewrite_cover_letter",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"result": letter, "plan": plan, "builder_payload": builder_payload.model_dump()}


class InterviewQuestionsRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = "en"
    mode: str = "senior"
    count: int = 5


class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str
    cv_text: str | None = ""
    job_description: str | None = ""
    lang: str = "en"


@app.post("/api/v1/interview/questions")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def interview_questions_endpoint(
    body: InterviewQuestionsRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    try:
        questions = rewrite_service.generate_interview_questions(
            cv_text=body.cv_text,
            job_description=body.job_description or "",
            lang=body.lang,
            mode=body.mode,
            count=body.count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "interview_questions_generated",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            count=len(questions),
        )
    except Exception:
        pass

    return {"questions": questions, "plan": plan}


@app.post("/api/v1/interview/evaluate")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def interview_evaluate_endpoint(
    body: InterviewEvaluateRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    try:
        evaluation = rewrite_service.evaluate_interview_answer(
            question=body.question,
            answer=body.answer,
            cv_text=body.cv_text or "",
            job_description=body.job_description or "",
            lang=body.lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "interview_answer_evaluated",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"evaluation": evaluation, "plan": plan}


@app.post("/api/v1/linkedin/optimize")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def optimize_linkedin_endpoint(
    body: LinkedInOptimizeRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = _ensure_ai_rewrite_allowed(db, db_user)

    try:
        result = rewrite_service.optimize_linkedin_profile(
            cv_text=body.cv_text,
            target_role=body.target_role or "",
            lang=body.lang,
            mode=body.mode,
            current_headline=body.headline or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_optimize_linkedin",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            mode=result.get("mode"),
        )
    except Exception:
        pass

    return {"result": result, "plan": plan}


@app.post("/api/v1/job/match-score")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def job_match_score_endpoint(
    body: JobMatchScoreRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        result = run_pipeline(
            cv_text=body.cv_text,
            job_description=body.job_description,
            lang=body.lang,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job match scoring failed: {e}")

    # ── Mode-specific score adjustment ───────────────────────────────
    # Each career mode has different weight expectations so the same CV
    # gets evaluated differently for junior vs senior vs manager roles.
    mode = (body.mode or "senior").lower().strip()
    raw_score = float(result.get("score", result.get("final_score", 0)) or 0)
    exp_match = float((result.get("match_score_v2") or {}).get("experience_match", 0) or 0)
    title_match_val = float((result.get("match_score_v2") or {}).get("title_match", 0) or 0)
    seniority_match_val = float((result.get("match_score_v2") or {}).get("seniority_match", 0) or 0)
    kw_coverage = float((result.get("match_score_v2") or {}).get("keyword_coverage_pct", 0) or 0)
    skill_score_val = float(result.get("skill_score", 0) or 0)

    # Mode weights: (keyword, experience, title, seniority, skill)
    _MODE_WEIGHTS = {
        "junior":   {"keyword": 0.35, "experience": 0.10, "title": 0.15, "seniority": 0.10, "skill": 0.30},
        "senior":   {"keyword": 0.25, "experience": 0.25, "title": 0.15, "seniority": 0.15, "skill": 0.20},
        "manager":  {"keyword": 0.20, "experience": 0.30, "title": 0.20, "seniority": 0.15, "skill": 0.15},
        "tech":     {"keyword": 0.30, "experience": 0.15, "title": 0.10, "seniority": 0.10, "skill": 0.35},
        "academic": {"keyword": 0.25, "experience": 0.20, "title": 0.20, "seniority": 0.10, "skill": 0.25},
    }
    w = _MODE_WEIGHTS.get(mode, _MODE_WEIGHTS["senior"])
    mode_score = round(
        kw_coverage * w["keyword"]
        + exp_match * w["experience"]
        + title_match_val * w["title"]
        + seniority_match_val * w["seniority"]
        + skill_score_val * w["skill"],
        2,
    )
    mode_score = max(0.0, min(100.0, mode_score))
    mode_interpretation = interpret_score_localized(mode_score, body.lang)

    try:
        audit_log(
            "job_match_score",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            lang=body.lang,
            score=result.get("score"),
        )
    except Exception:
        pass

    return {
        "score": mode_score,
        "raw_score": raw_score,
        "mode": mode,
        "confidence": result.get("confidence"),
        "risk_level": result.get("risk_level"),
        "interpretation": mode_interpretation,
        "keyword_gap": result.get("keyword_gap"),
        "keyword_gap_v2": result.get("keyword_gap_v2") or {},
        "match_score_v2": result.get("match_score_v2") or {},
        "keyword_coverage_pct": kw_coverage,
        "experience_match": exp_match,
        "title_match": title_match_val,
        "seniority_match": seniority_match_val,
        "skill_match": skill_score_val,
        "mode_weights": w,
        "missing_keywords": ((result.get("keyword_gap_v2") or {}).get("missing_keywords") or []),
        "weak_keywords": ((result.get("keyword_gap_v2") or {}).get("weak_keywords") or []),
        "strong_keywords": ((result.get("keyword_gap_v2") or {}).get("strong_keywords") or []),
        "suggested_keywords": ((result.get("keyword_gap_v2") or {}).get("suggested_keywords") or []),
        "missing_skills": result.get("missing_skills", []),
        "extra_skills": result.get("extra_skills", []),
        "recommendations": result.get("recommendations", []),
    }


@app.post("/api/v1/job/keyword-gap")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def keyword_gap_detector_endpoint(
    body: KeywordGapRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        result = compare(body.cv_text, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Keyword gap detection failed: {e}")

    try:
        audit_log(
            "keyword_gap_detector",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            keyword_coverage_pct=result.get("keyword_coverage_pct"),
        )
    except Exception:
        pass

    return {
        "missing_keywords": result.get("missing_keywords", []),
        "weak_keywords": result.get("weak_keywords", []),
        "strong_keywords": result.get("strong_keywords", []),
        "suggested_keywords": result.get("suggested_keywords", []),
        "extra_keywords": result.get("extra_keywords", []),
        "keyword_coverage_pct": result.get("keyword_coverage_pct", 0.0),
        "message": "Add these to increase ATS score",
    }


@app.post("/api/v1/cv/versions")
def save_cv_version(
    body: SaveCVVersionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    cv_text = str(body.cv_text or "").strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="cv_text cannot be empty")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    version_label = (body.version_label or "").strip() or _next_cv_version_label(db, db_user.id)

    match_score = None
    if body.job_description and str(body.job_description).strip():
        try:
            pipeline = run_pipeline(cv_text, body.job_description, lang=body.lang)
            match_score = float((pipeline.get("match_score_v2") or {}).get("match_score") or pipeline.get("final_score") or 0.0)
        except Exception:
            match_score = None

    row = CVVersion(
        user_id=db_user.id,
        organization_id=getattr(db_user, "organization_id", None),
        version_label=version_label[:40],
        source=str(body.source or "manual")[:40],
        lang=str(body.lang or "en")[:10],
        cv_text=cv_text,
        optimized_cv_text=str(body.optimized_cv_text or "") or None,
        job_description=str(body.job_description or "") or None,
        match_score=match_score,
        notes=str(body.notes or "") or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        audit_log(
            "cv_version_saved",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            version_label=row.version_label,
            source=row.source,
        )
    except Exception:
        pass

    return {
        "id": row.id,
        "version_label": row.version_label,
        "source": row.source,
        "lang": row.lang,
        "match_score": row.match_score,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@app.get("/api/v1/cv/versions")
def list_cv_versions(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    rows = (
        db.query(CVVersion)
        .filter(CVVersion.user_id == db_user.id)
        .order_by(CVVersion.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": row.id,
                "version_label": row.version_label,
                "source": row.source,
                "lang": row.lang,
                "match_score": row.match_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@app.get("/api/v1/cv/versions/{version_id}")
def get_cv_version(
    version_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    row = (
        db.query(CVVersion)
        .filter(CVVersion.id == version_id, CVVersion.user_id == db_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="CV version not found")

    return {
        "id": row.id,
        "version_label": row.version_label,
        "source": row.source,
        "lang": row.lang,
        "cv_text": row.cv_text,
        "optimized_cv_text": row.optimized_cv_text,
        "job_description": row.job_description,
        "match_score": row.match_score,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# =====================================================
# BILLING ENDPOINTS (STRIPE)
# =====================================================


class CreateCheckoutSessionRequest(BaseModel):
    plan_type: str | None = "pro"
    price_id: str | None = None
    success_url: str | None = None
    cancel_url: str | None = None
    billing_period: str | None = None
    price: float | None = None
    currency: str | None = None
    coupon_code: str | None = None
    source: str | None = None


class CreatePortalSessionRequest(BaseModel):
    return_url: str | None = None


class ContactSalesRequest(BaseModel):
    plan_type: str | None = "enterprise"
    company_name: str | None = None
    message: str | None = None
    contact_email: str | None = None
    source: str | None = None


class ActivatePremiumTrialRequest(BaseModel):
    plan_type: str | None = "pro"


class AdminSetUserPlanRequest(BaseModel):
    supabase_id: str | None = None
    email: str | None = None
    plan_type: str | None = None
    billing_status: str | None = None
    role: str | None = None
    update_organization: bool = False


def _stripe_price_map() -> dict[str, str]:
    return {
        "free": os.getenv("STRIPE_PRICE_ID_FREE", "").strip(),
        "pro": os.getenv("STRIPE_PRICE_ID_PRO", "").strip(),
        "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE", "").strip(),
    }


def _normalize_plan_type(plan_type: str | None) -> str:
    normalized = _normalize_plan(plan_type)
    if normalized not in User.PLAN_TYPES:
        return "free"
    return normalized


def _parse_plan_type_or_400(plan_type: str | None) -> str:
    value = (plan_type or "").strip().lower()
    if value not in User.PLAN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan_type. Allowed: {', '.join(User.PLAN_TYPES)}",
        )
    return value


def _parse_billing_status_or_400(billing_status: str | None) -> str:
    if billing_status is None:
        return "active"
    value = billing_status.strip().lower()
    if value not in User.BILLING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid billing_status. Allowed: "
                f"{', '.join(User.BILLING_STATUSES)}"
            ),
        )
    return value


def _parse_user_role_or_400(role: str | None) -> str:
    value = str(role or "").strip().lower()
    allowed_roles = {"individual", "recruiter", "admin"}
    if value not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid role. Allowed: "
                f"{', '.join(sorted(allowed_roles))}"
            ),
        )
    return value


def _require_billing_admin_token(x_billing_admin_token: str | None):
    expected = os.getenv("BILLING_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Billing admin endpoint is not configured",
        )
    provided = (x_billing_admin_token or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid billing admin token")


def _parse_billing_admin_allowed_emails() -> set[str]:
    raw = str(os.getenv("BILLING_ADMIN_ALLOWED_EMAILS", "")).strip()
    if not raw:
        return set()
    return {
        item.strip().lower()
        for item in raw.split(",")
        if item and item.strip()
    }


def _require_billing_admin_access(user_payload: dict, x_billing_admin_token: str | None):
    _require_billing_admin_token(x_billing_admin_token)

    allowed_emails = _parse_billing_admin_allowed_emails()
    if not allowed_emails:
        raise HTTPException(
            status_code=503,
            detail="Billing admin allow-list is not configured",
        )

    email = str((user_payload or {}).get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    if email not in allowed_emails:
        raise HTTPException(status_code=403, detail="Billing admin access denied")


@app.get("/api/v1/billing/admin/me")
def billing_admin_me(
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token)
    return {
        "status": "ok",
        "email": str((user or {}).get("email") or ""),
    }


@app.get("/api/v1/billing/admin/users")
def billing_admin_list_users(
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    email: str | None = Query(default=None),
    plan_type: str | None = Query(default=None),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token)

    query = db.query(User)
    if email:
        query = query.filter(User.email.ilike(f"%{email.strip()}%"))
    if plan_type:
        normalized_plan = _parse_plan_type_or_400(plan_type)
        query = query.filter(User.plan_type == normalized_plan)

    total = int(query.count())
    rows = (
        query.order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": row.id,
            "supabase_id": row.supabase_id,
            "email": row.email,
            "plan_type": row.plan_type,
            "billing_status": row.billing_status,
            "role": row.role,
            "organization_id": row.organization_id,
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
            "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@app.get("/api/v1/billing/admin/feedback")
def billing_admin_list_feedback(
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token)

    items = _read_feedback_records(limit=limit, include_all=True)

    cleaned = []
    for row in items:
        cleaned.append(
            {
                "timestamp": row.get("timestamp"),
                "category": row.get("category"),
                "page": row.get("page"),
                "lang": row.get("lang"),
                "score": row.get("score"),
                "message": row.get("message"),
                "context": row.get("context") or {},
                "submitter": row.get("email"),
                "supabase_id": row.get("supabase_id"),
            }
        )

    return {"status": "ok", "items": cleaned, "count": len(cleaned)}


def _resolve_checkout_price_and_plan(
    requested_plan: str | None,
    explicit_price_id: str | None,
) -> tuple[str, str]:
    prices = _stripe_price_map()
    plan = _normalize_plan_type(requested_plan)

    if explicit_price_id and explicit_price_id.strip():
        price_id = explicit_price_id.strip()
        for mapped_plan, mapped_price in prices.items():
            if mapped_price and mapped_price == price_id:
                return price_id, mapped_plan
        return price_id, plan

    mapped_price = prices.get(plan) or ""
    if not mapped_price:
        raise HTTPException(
            status_code=400,
            detail=f"No Stripe price configured for plan '{plan}'",
        )
    return mapped_price, plan


def _stripe_api_post(path: str, form_data: dict[str, str]) -> dict:
    def _get_secret_or_file(env_name: str, file_env_name: str) -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    secret_key = _get_secret_or_file("STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_FILE")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    encoded = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.stripe.com{path}",
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            payload = json.loads(body)
            message = payload.get("error", {}).get("message")
            if message:
                raise HTTPException(status_code=502, detail=f"Stripe error: {message}")
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Stripe request failed")
    except Exception:
        raise HTTPException(status_code=502, detail="Stripe connection failed")


def _stripe_api_get(
    path: str,
    query_params: dict[str, str] | list[tuple[str, str]] | None = None,
) -> dict:
    def _get_secret_or_file(env_name: str, file_env_name: str) -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    secret_key = _get_secret_or_file("STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_FILE")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    query = ""
    if query_params:
        query = "?" + urllib.parse.urlencode(query_params)

    req = urllib.request.Request(
        f"https://api.stripe.com{path}{query}",
        method="GET",
        headers={
            "Authorization": f"Bearer {secret_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            payload = json.loads(body)
            message = payload.get("error", {}).get("message")
            if message:
                raise HTTPException(status_code=502, detail=f"Stripe error: {message}")
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Stripe request failed")
    except Exception:
        raise HTTPException(status_code=502, detail="Stripe connection failed")


def _get_billing_owner(db, db_user: User):
    """Return (owner_type, owner_model) for billing operations."""
    if db_user.role == "recruiter" and db_user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == db_user.organization_id)
            .first()
        )
        if org:
            return "organization", org
    return "user", db_user


def _ensure_stripe_customer(db, owner_type: str, owner, email: str | None, supabase_id: str):
    existing = getattr(owner, "stripe_customer_id", None)
    if existing:
        return existing

    customer_payload = {
        "email": email or "",
        "metadata[supabase_id]": supabase_id,
        "metadata[owner_type]": owner_type,
    }
    if owner_type == "organization":
        customer_payload["metadata[organization_id]"] = str(getattr(owner, "id", ""))
        customer_payload["name"] = getattr(owner, "name", "") or "CV Analyzer Organization"
    else:
        customer_payload["metadata[user_id]"] = str(getattr(owner, "id", ""))

    customer = _stripe_api_post("/v1/customers", customer_payload)
    customer_id = str(customer.get("id", "")).strip()
    if not customer_id:
        raise HTTPException(status_code=502, detail="Stripe customer creation failed")

    owner.stripe_customer_id = customer_id
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return customer_id


def _build_contact_sales_mailto_url(
    plan_type: str,
    user_email: str,
    company_name: str,
    owner_type: str,
    message: str,
) -> str:
    sales_email = os.getenv("CONTACT_SALES_EMAIL", "sales@cvanalyzer.local").strip()
    subject = f"Enterprise plan inquiry ({plan_type})"
    body = (
        f"Email: {user_email}\n"
        f"Company: {company_name}\n"
        f"Owner Type: {owner_type}\n"
        f"Plan: {plan_type}\n\n"
        f"Message:\n{message}\n"
    )
    encoded_email = urllib.parse.quote(sales_email, safe="@")
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    return f"mailto:{encoded_email}?subject={encoded_subject}&body={encoded_body}"


@app.post("/api/v1/billing/checkout-session")
def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    # Development shortcut for local UI testing without external Stripe calls.
    if MOCK_SERVICES_ON:
        desired_plan = _normalize_plan_type(body.plan_type)
        if desired_plan == "free":
            desired_plan = "pro"

        db_user.plan_type = desired_plan
        db_user.billing_status = "active"
        db.add(db_user)

        if owner_type == "organization" and owner is not None:
            owner.plan_type = desired_plan
            owner.billing_status = "active"
            db.add(owner)

        db.commit()
        db.refresh(db_user)

        event_context = {
            "user_id": db_user.id,
            "owner_type": owner_type,
            "plan_type": desired_plan,
            "billing_period": body.billing_period or "monthly",
            "price": body.price,
            "currency": (body.currency or "USD").upper(),
            "coupon_code": body.coupon_code,
            "source": body.source or "web_pricing_page",
            "stripe_customer_id": str(getattr(owner, "stripe_customer_id", "") or "mock_customer"),
            "stripe_price_id": body.price_id or f"price_mock_{desired_plan}",
        }

        track_event("purchase_intent", **event_context)
        track_event("checkout_started", **event_context, session_id="cs_test_mock_123")
        track_event(
            "checkout_completed",
            **event_context,
            session_id="cs_test_mock_123",
            stripe_subscription_id=f"sub_mock_{desired_plan}",
        )

        return {
            "session_id": "cs_test_mock_123",
            "url": "",
            "plan_type": desired_plan,
            "mode": "mock",
        }

    price_id, desired_plan = _resolve_checkout_price_and_plan(
        body.plan_type,
        body.price_id,
    )

    success_url = (
        body.success_url
        or os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", "http://localhost:5173/billing/success")
    )
    cancel_url = (
        body.cancel_url
        or os.getenv("STRIPE_CHECKOUT_CANCEL_URL", "http://localhost:5173/billing/cancel")
    )

    customer_id = _ensure_stripe_customer(db, owner_type, owner, email, supabase_id)

    event_context = {
        "user_id": db_user.id,
        "owner_type": owner_type,
        "plan_type": desired_plan,
        "billing_period": body.billing_period or "monthly",
        "price": body.price,
        "currency": (body.currency or "USD").upper(),
        "coupon_code": body.coupon_code,
        "source": body.source or "web_pricing_page",
        "stripe_customer_id": customer_id,
        "stripe_price_id": price_id,
    }

    track_event("purchase_intent", **event_context)

    payload = {
        "mode": "subscription",
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[plan_type]": desired_plan,
        "metadata[owner_type]": owner_type,
        "metadata[billing_period]": body.billing_period or "monthly",
        "metadata[currency]": (body.currency or "USD").upper(),
        "metadata[source]": body.source or "web_pricing_page",
    }
    if body.price is not None:
        payload["metadata[price]"] = str(body.price)
    if body.coupon_code:
        payload["metadata[coupon_code]"] = str(body.coupon_code)

    try:
        session = _stripe_api_post("/v1/checkout/sessions", payload)
    except HTTPException as exc:
        track_event(
            "checkout_failed",
            **event_context,
            error_code=str(exc.status_code),
            error_message=str(exc.detail),
        )
        raise

    session_id = str(session.get("id", ""))
    checkout_url = str(session.get("url", ""))
    if not session_id or not checkout_url:
        track_event(
            "checkout_failed",
            **event_context,
            error_code="502",
            error_message="missing_session_or_url",
        )
        raise HTTPException(status_code=502, detail="Stripe checkout session failed")

    track_event("checkout_started", **event_context, session_id=session_id)

    result = {
        "session_id": session_id,
        "url": checkout_url,
        "customer_id": customer_id,
        "plan_type": desired_plan,
        "owner_type": owner_type,
    }

    # Audit payment event
    try:
        audit_log(
            "billing_checkout_session_created",
            user_id=db_user.id,
            owner_type=owner_type,
            plan_type=desired_plan,
            stripe_customer_id=customer_id,
            session_id=session_id,
        )
    except Exception:
        pass

    return result


@app.post("/api/v1/billing/portal-session")
def create_billing_portal_session(
    body: CreatePortalSessionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    if MOCK_SERVICES_ON:
        mock_return_url = body.return_url or os.getenv(
            "STRIPE_BILLING_PORTAL_RETURN_URL", "http://localhost:5173/dashboard"
        )
        return {
            "url": mock_return_url,
            "mode": "mock",
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    customer_id = _ensure_stripe_customer(db, owner_type, owner, email, supabase_id)
    return_url = body.return_url or os.getenv(
        "STRIPE_BILLING_PORTAL_RETURN_URL", "http://localhost:5173/dashboard"
    )

    session = _stripe_api_post(
        "/v1/billing_portal/sessions",
        {
            "customer": customer_id,
            "return_url": return_url,
        },
    )
    portal_url = str(session.get("url", ""))
    if not portal_url:
        raise HTTPException(status_code=502, detail="Stripe billing portal session failed")

    result = {
        "url": portal_url,
        "customer_id": customer_id,
        "owner_type": owner_type,
    }

    try:
        audit_log(
            "billing_portal_session_created",
            user_id=db_user.id,
            owner_type=owner_type,
            stripe_customer_id=customer_id,
        )
    except Exception:
        pass

    return result


@app.post("/api/v1/billing/contact-sales")
def create_contact_sales_request(
    body: ContactSalesRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    plan_type = _normalize_plan_type(body.plan_type or "enterprise")
    if plan_type == "free":
        plan_type = "enterprise"

    # Development shortcut for local testing.
    if MOCK_SERVICES_ON:
        contact_url = _build_contact_sales_mailto_url(
            plan_type=plan_type,
            user_email=str((user or {}).get("email") or "dev@example.com"),
            company_name=str(body.company_name or ""),
            owner_type="mock",
            message=str(body.message or ""),
        )
        return {
            "status": "accepted",
            "mode": "mock",
            "contact_url": contact_url,
            "plan_type": plan_type,
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    company_name = str(body.company_name or getattr(owner, "name", "") or "")
    owner_plan = str(getattr(owner, "plan_type", "") or "")
    message = str(body.message or "")
    contact_email = str(body.contact_email or email or "")

    track_event(
        "purchase_intent",
        user_id=db_user.id,
        owner_type=owner_type,
        plan_type=plan_type,
        billing_period="custom",
        price=None,
        currency="USD",
        coupon_code=None,
        source=body.source or "web_pricing_page",
    )

    crm_webhook_url = os.getenv("CRM_WEBHOOK_URL", "").strip()
    if crm_webhook_url:
        payload = {
            "event": "contact_sales",
            "supabase_id": supabase_id,
            "email": contact_email,
            "owner_type": owner_type,
            "owner_plan": owner_plan,
            "requested_plan": plan_type,
            "company_name": company_name,
            "message": message,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        req = urllib.request.Request(
            crm_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                return {
                    "status": "accepted",
                    "mode": "crm_webhook",
                    "plan_type": plan_type,
                }
        except Exception:
            # Fall through to mailto fallback so the user can still reach sales.
            pass

    contact_url = _build_contact_sales_mailto_url(
        plan_type=plan_type,
        user_email=contact_email,
        company_name=company_name,
        owner_type=owner_type,
        message=message,
    )
    result = {
        "status": "accepted",
        "mode": "mailto",
        "contact_url": contact_url,
        "plan_type": plan_type,
    }

    try:
        audit_log(
            "billing_contact_sales",
            user_id=db_user.id,
            owner_type=owner_type,
            requested_plan=plan_type,
            company_name=company_name,
        )
    except Exception:
        pass

    return result


@app.post("/api/v1/billing/activate-trial")
def activate_premium_trial(
    body: ActivatePremiumTrialRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Developer convenience endpoint: upgrade current account to pro/enterprise trial.

    Controlled by `DEV_ALLOW_SELF_PREMIUM` (default enabled in local/dev setups).
    """
    _ensure_not_expired(user)

    allow_self_premium = os.getenv("DEV_ALLOW_SELF_PREMIUM", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    if not allow_self_premium:
        raise HTTPException(status_code=403, detail="Self premium activation disabled")

    requested = _normalize_plan_type(body.plan_type or "pro")
    if requested == "free":
        requested = "pro"

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    db_user.plan_type = requested
    db_user.billing_status = "trialing"
    db.add(db_user)

    org_updated = False
    if db_user.role == "recruiter" and db_user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == db_user.organization_id)
            .first()
        )
        if org:
            org.plan_type = requested
            org.billing_status = "trialing"
            db.add(org)
            org_updated = True

    db.commit()
    db.refresh(db_user)

    result = {
        "status": "ok",
        "user_id": db_user.supabase_id,
        "plan_type": db_user.plan_type,
        "billing_status": db_user.billing_status,
        "organization_updated": org_updated,
    }

    try:
        audit_log(
            "billing_trial_activated",
            user_id=db_user.id,
            plan_type=db_user.plan_type,
            billing_status=db_user.billing_status,
            organization_updated=org_updated,
        )
    except Exception:
        pass

    return result


@app.post("/api/v1/billing/admin/set-user-plan")
def admin_set_user_plan(
    body: AdminSetUserPlanRequest,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    db=Depends(get_db),
):
    """Admin-only override for user membership stored in DB.

    Intended for support/manual recovery scenarios (payment provider bugs,
    one-off grants, rollback of incorrect upgrades).
    """
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token)

    supabase_id = str(body.supabase_id or "").strip()
    email = str(body.email or "").strip().lower()
    if not supabase_id and not email:
        raise HTTPException(status_code=400, detail="supabase_id or email is required")

    has_plan_update = body.plan_type is not None
    has_status_update = body.billing_status is not None
    has_role_update = body.role is not None
    if not (has_plan_update or has_status_update or has_role_update):
        raise HTTPException(
            status_code=400,
            detail="At least one of plan_type, billing_status, or role is required",
        )

    desired_plan = _parse_plan_type_or_400(body.plan_type) if has_plan_update else None
    desired_status = _parse_billing_status_or_400(body.billing_status) if has_status_update else None
    desired_role = _parse_user_role_or_400(body.role) if has_role_update else None

    query = db.query(User)
    if supabase_id:
        query = query.filter(User.supabase_id == supabase_id)
    else:
        query = query.filter(User.email == email)

    db_user = query.first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if desired_plan is not None:
        db_user.plan_type = desired_plan
    if desired_status is not None:
        db_user.billing_status = desired_status
    if desired_role is not None:
        db_user.role = desired_role
    db.add(db_user)

    organization_updated = False
    organization_id = getattr(db_user, "organization_id", None)
    if body.update_organization and organization_id and (
        desired_plan is not None or desired_status is not None
    ):
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if org:
            if desired_plan is not None:
                org.plan_type = desired_plan
            if desired_status is not None:
                org.billing_status = desired_status
            db.add(org)
            organization_updated = True

    db.commit()
    db.refresh(db_user)

    try:
        audit_log(
            "billing_admin_plan_override",
            user_id=db_user.id,
            supabase_id=db_user.supabase_id,
            email=db_user.email,
            plan_type=db_user.plan_type,
            billing_status=db_user.billing_status,
            role=db_user.role,
            organization_updated=organization_updated,
            source="admin_endpoint",
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "user_id": db_user.supabase_id,
        "email": db_user.email,
        "plan_type": db_user.plan_type,
        "billing_status": db_user.billing_status,
        "role": db_user.role,
        "organization_updated": organization_updated,
    }


# =====================================================
# STRIPE WEBHOOK ENDPOINT
# =====================================================


@app.post("/stripe/webhook")
@rate_limit("30/minute")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    """
    Stripe webhook endpoint for billing events.
    Verifies Stripe signature and processes event.
    In development (MOCK_SERVICES=true), signature validation is skipped for testing.
    """
    def _get_secret_or_file(env_name: str, file_env_name: str, default: str = "") -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return default
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip() or default
        except Exception:
            return default

    STRIPE_WEBHOOK_SECRET = _get_secret_or_file(
        "STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_FILE", ""
    )
    IS_TEST_MODE = MOCK_SERVICES_ON

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = json.loads(payload)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Invalid payload"})

    # Signature verification (skip ONLY in non-production test mode)
    if not IS_TEST_MODE or _ENV_MODE in ("production", "prod"):
        if not STRIPE_WEBHOOK_SECRET:
            logger.error("stripe_webhook: STRIPE_WEBHOOK_SECRET not configured")
            return JSONResponse(status_code=500, content={"error": "Webhook not configured"})
        if not sig_header:
            return JSONResponse(status_code=401, content={"error": "Missing Stripe-Signature"})
        try:
            # Parse timestamp and signatures from Stripe header
            sig_parts = {}
            for part in sig_header.split(","):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    sig_parts.setdefault(k.strip(), []).append(v.strip())

            timestamp = sig_parts.get("t", [None])[0]
            signatures = sig_parts.get("v1", [])

            if not timestamp or not signatures:
                return JSONResponse(status_code=401, content={"error": "Invalid signature header"})

            # Reject if timestamp is too old (5 minute tolerance)
            try:
                ts_int = int(timestamp)
                if abs(time.time() - ts_int) > 300:
                    return JSONResponse(status_code=401, content={"error": "Timestamp too old"})
            except (ValueError, TypeError):
                return JSONResponse(status_code=401, content={"error": "Invalid timestamp"})

            # Compute expected signature per Stripe's scheme
            signed_payload = f"{timestamp}.".encode() + payload
            expected_sig = hmac.new(
                STRIPE_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256
            ).hexdigest()

            if not any(hmac.compare_digest(expected_sig, s) for s in signatures):
                return JSONResponse(status_code=401, content={"error": "Invalid signature"})
        except Exception as e:
            logger.warning("stripe_webhook: signature verification error: %s", e)
            return JSONResponse(status_code=400, content={"error": "Signature verification failed"})

    # Process event type
    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "checkout.session.completed":
        obj = data.get("object", {})
        metadata = obj.get("metadata", {}) if isinstance(obj.get("metadata"), dict) else {}
        amount_total = obj.get("amount_total")
        price_value = None
        if isinstance(amount_total, (int, float)):
            price_value = round(float(amount_total) / 100.0, 2)

        billing_period_value = str(metadata.get("billing_period") or "monthly")
        currency_value = str(obj.get("currency") or metadata.get("currency") or "usd").upper()
        stripe_price_id = None
        coupon_code_value = str(metadata.get("coupon_code") or "") or None

        session_id = str(obj.get("id") or "").strip()
        if session_id:
            try:
                session_details = _stripe_api_get(
                    f"/v1/checkout/sessions/{urllib.parse.quote(session_id, safe='')}",
                    [
                        ("expand[]", "line_items.data.price"),
                        ("expand[]", "total_details.breakdown.discounts.discount.coupon"),
                    ],
                )
                line_items_obj = session_details.get("line_items", {})
                line_items = (
                    line_items_obj.get("data", [])
                    if isinstance(line_items_obj, dict)
                    else []
                )
                first_item = line_items[0] if isinstance(line_items, list) and line_items else {}
                price_obj = (
                    first_item.get("price", {})
                    if isinstance(first_item, dict)
                    else {}
                )
                if isinstance(price_obj, dict):
                    stripe_price_id = str(price_obj.get("id") or "") or None
                    recurring = price_obj.get("recurring", {})
                    if isinstance(recurring, dict):
                        interval = str(recurring.get("interval") or "").lower()
                        if interval == "year":
                            billing_period_value = "yearly"
                        elif interval in ("month", "week", "day"):
                            billing_period_value = interval

                    unit_amount = price_obj.get("unit_amount")
                    if isinstance(unit_amount, (int, float)):
                        price_value = round(float(unit_amount) / 100.0, 2)

                    price_currency = str(price_obj.get("currency") or "").strip()
                    if price_currency:
                        currency_value = price_currency.upper()

                total_details = session_details.get("total_details", {})
                if isinstance(total_details, dict):
                    breakdown = total_details.get("breakdown", {})
                    if isinstance(breakdown, dict):
                        discounts = breakdown.get("discounts", [])
                        first_discount = (
                            discounts[0]
                            if isinstance(discounts, list) and discounts
                            else {}
                        )
                        discount_obj = (
                            first_discount.get("discount", {})
                            if isinstance(first_discount, dict)
                            else {}
                        )
                        coupon_obj = (
                            discount_obj.get("coupon", {})
                            if isinstance(discount_obj, dict)
                            else {}
                        )
                        if isinstance(coupon_obj, dict):
                            code = str(coupon_obj.get("id") or coupon_obj.get("name") or "").strip()
                            if code:
                                coupon_code_value = code
            except Exception:
                # Keep webhook resilient; fallback to event payload values.
                pass

        track_event(
            "checkout_completed",
            owner_type=str(metadata.get("owner_type") or "unknown"),
            plan_type=str(metadata.get("plan_type") or "free"),
            billing_period=billing_period_value,
            price=price_value,
            currency=currency_value,
            coupon_code=coupon_code_value,
            source=str(metadata.get("source") or "stripe_webhook"),
            stripe_customer_id=str(obj.get("customer") or ""),
            session_id=session_id,
            stripe_subscription_id=str(obj.get("subscription") or ""),
            stripe_price_id=stripe_price_id,
        )

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        # Extract Stripe customer ID and subscription details
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        status = obj.get("status")  # active, past_due, canceled, trialing
        metadata = obj.get("metadata", {}) if isinstance(obj.get("metadata"), dict) else {}
        plan_hint = str(metadata.get("plan_type", "")).strip().lower()
        if plan_hint not in User.PLAN_TYPES:
            plan_hint = None

        if customer_id:
            # Update user or organization billing_status and stripe_customer_id
            try:
                owner_type = "unknown"
                tracked_user_id = None
                user = (
                    db.query(User)
                    .filter(User.stripe_customer_id == customer_id)
                    .first()
                )
                if user:
                    owner_type = "user"
                    tracked_user_id = user.id
                    user.billing_status = status or "active"
                    if plan_hint:
                        user.plan_type = plan_hint
                    db.add(user)
                    db.commit()
                else:
                    org = (
                        db.query(Organization)
                        .filter(Organization.stripe_customer_id == customer_id)
                        .first()
                    )
                    if org:
                        owner_type = "organization"
                        org.billing_status = status or "active"
                        if plan_hint:
                            org.plan_type = plan_hint
                        db.add(org)
                        db.commit()

                if event_type == "customer.subscription.updated" and (status or "").lower() == "active":
                    track_event(
                        "subscription_renewed",
                        user_id=tracked_user_id,
                        owner_type=owner_type,
                        plan_type=plan_hint,
                        billing_period=str(metadata.get("billing_period") or "monthly"),
                        price=None,
                        currency=str(metadata.get("currency") or "USD").upper(),
                        coupon_code=str(metadata.get("coupon_code") or "") or None,
                        source=str(metadata.get("source") or "stripe_webhook"),
                        stripe_customer_id=str(customer_id),
                        stripe_subscription_id=str(obj.get("id") or ""),
                        subscription_status=status,
                    )
            except Exception as e:
                print(f"Error updating billing status: {str(e)}")
                db.rollback()

    elif event_type == "customer.subscription.deleted":
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        if customer_id:
            try:
                owner_type = "unknown"
                tracked_user_id = None
                user = (
                    db.query(User)
                    .filter(User.stripe_customer_id == customer_id)
                    .first()
                )
                if user:
                    owner_type = "user"
                    tracked_user_id = user.id
                    user.billing_status = "canceled"
                    db.add(user)
                    db.commit()
                else:
                    org = (
                        db.query(Organization)
                        .filter(Organization.stripe_customer_id == customer_id)
                        .first()
                    )
                    if org:
                        owner_type = "organization"
                        org.billing_status = "canceled"
                        db.add(org)
                        db.commit()

                track_event(
                    "subscription_canceled",
                    user_id=tracked_user_id,
                    owner_type=owner_type,
                    plan_type=None,
                    billing_period=None,
                    price=None,
                    currency="USD",
                    coupon_code=None,
                    source="stripe_webhook",
                    stripe_customer_id=str(customer_id),
                    stripe_subscription_id=str(obj.get("id") or ""),
                    subscription_status="canceled",
                )
            except Exception as e:
                print(f"Error canceling subscription: {str(e)}")
                db.rollback()

    try:
        audit_log("billing_webhook_event", event_type=event_type)
    except Exception:
        pass

    return {"status": "success", "event_type": event_type}


# =====================================================
# RECRUITER DASHBOARD ENDPOINTS
# =====================================================


# Recruiter routes moved to routes/recruiter.py
# ================================================

def _is_postgres_engine() -> bool:
    try:
        url = getattr(engine, "url", None)
        if not url:
            return False
        return str(url.get_backend_name()).startswith("postgres")
    except Exception:
        return False


def _do_send_email(to_email: str, subject: str, body: str, recruiter_email: str = "") -> bool:
    """Send email via SMTP or SendGrid.

    *recruiter_email* is the recruiter's personal address.  It is always
    set as ``Reply-To`` so candidates reply to the recruiter — not the
    platform.  When the platform From address differs from recruiter_email
    the display name is set to include the recruiter address for
    transparency.
    """
    import os
    import logging
    from email.utils import formataddr

    _logger = logging.getLogger("app.recruiter.email")

    # Try SendGrid first
    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    if sendgrid_key:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content, Header

            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
            platform_from = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@cvanalyzer.com")
            # Use recruiter name in display, platform address for deliverability
            if recruiter_email and recruiter_email != platform_from:
                from_email = Email(platform_from, name=recruiter_email)
            else:
                from_email = Email(platform_from)
            mail = Mail(
                from_email=from_email,
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", body),
            )
            # Reply-To → recruiter's inbox
            if recruiter_email:
                mail.reply_to = Email(recruiter_email)
            response = sg.client.mail.send.post(request_body=mail.get())
            _logger.info("sendgrid_sent to=%s reply_to=%s status=%s", to_email, recruiter_email, response.status_code)
            return response.status_code in (200, 201, 202)
        except Exception as e:
            _logger.error("sendgrid_failed to=%s error=%s", to_email, e)

    # Fallback to SMTP
    smtp_host = os.environ.get("SMTP_HOST", "")
    if smtp_host:
        try:
            import smtplib
            from email.mime.text import MIMEText

            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")
            platform_from = os.environ.get("SMTP_FROM", "noreply@cvanalyzer.com")

            # Build From with recruiter display-name
            if recruiter_email and recruiter_email != platform_from:
                from_display = formataddr((recruiter_email, platform_from))
            else:
                from_display = platform_from

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = from_display
            msg["To"] = to_email
            if recruiter_email:
                msg["Reply-To"] = recruiter_email

            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(platform_from, [to_email], msg.as_string())

            _logger.info("smtp_sent to=%s reply_to=%s", to_email, recruiter_email)
            return True
        except Exception as e:
            _logger.error("smtp_failed to=%s error=%s", to_email, e)

    _logger.warning("no_email_backend configured, email not sent to=%s", to_email)
    return False


def _validate_reminder_email(email: str) -> str:
    candidate_email = (email or "").strip()
    if "@" not in candidate_email or "." not in candidate_email:
        raise HTTPException(status_code=400, detail="target_email must be a valid email address")
    return candidate_email


def _render_reminder_subject(reminder: Reminder, days_left: int) -> str:
    label = reminder.reminder_type or "Hatırlatma"
    return f"[{label.capitalize()}] {reminder.title} - {days_left} gün kaldı"


def _render_reminder_body(reminder: Reminder, days_left: int) -> str:
    event_date = reminder.event_date.strftime("%Y-%m-%d %H:%M")
    body_lines = [
        f"Merhaba,",
        "",
        f"{reminder.title} için planlanmış tarih: {event_date}",
        f"Kalan süre: {days_left} gün.",
    ]
    if reminder.description:
        body_lines.extend(["", "Açıklama:", reminder.description.strip()])
    body_lines.extend([
        "",
        "Lütfen hazırlanmayı unutmayın.",
        "",
        "Bu hatırlatma otomatik olarak gönderildi."
    ])
    return "\n".join(body_lines)


def _send_reminder_email(reminder: Reminder, days_left: int, recipient: str) -> bool:
    subject = _render_reminder_subject(reminder, days_left)
    body = _render_reminder_body(reminder, days_left)
    return _do_send_email(
        to_email=recipient,
        subject=subject,
        body=body,
        recruiter_email="",
    )


def _process_due_reminders(db):
    now = datetime.utcnow()
    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.is_active == True,
            Reminder.event_date > now,
            Reminder.event_date <= now + timedelta(days=3),
            or_(Reminder.notified_3d_at.is_(None), Reminder.notified_1d_at.is_(None)),
        )
        .all()
    )
    for reminder in reminders:
        if reminder.event_date <= now:
            continue
        delta = reminder.event_date - now
        recipient = reminder.target_email or ""
        if not recipient:
            continue
        if reminder.notified_1d_at is None and delta <= timedelta(days=1):
            if _send_reminder_email(reminder, 1, recipient):
                reminder.notified_1d_at = now
                db.add(reminder)
                db.commit()
            continue
        if (
            reminder.notified_3d_at is None
            and reminder.notified_1d_at is None
            and timedelta(days=1) < delta
            and delta <= timedelta(days=3)
        ):
            if _send_reminder_email(reminder, 3, recipient):
                reminder.notified_3d_at = now
                db.add(reminder)
                db.commit()


def _start_reminder_worker():
    interval = int(os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "3600"))

    def _loop():
        while True:
            try:
                db = SessionLocal()
                _process_due_reminders(db)
            except Exception as exc:
                logger.exception("reminder_worker: failed to process due reminders: %s", exc)
            finally:
                try:
                    db.close()
                except Exception:
                    pass
            time.sleep(interval)

    thread = _threading.Thread(target=_loop, daemon=True, name="reminder-worker")
    thread.start()


# ═══════════════════════════════════════════════════════════════════════════
# CAMERA CV SCAN — OCR + ATS Analysis + PDF Generation
# ═══════════════════════════════════════════════════════════════════════════

_SCAN_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
_SCAN_MAX_FILE_SIZE = 10_000_000  # 10 MB per image
_SCAN_MAX_FILES = 10


# ISO 639-1 → Tesseract language code mapping (all supported languages)
_LANG_TO_TESSERACT: dict[str, str] = {
    "en": "eng",
    "tr": "tur",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "ar": "ara",
    "pt": "por",
    "it": "ita",
    "nl": "nld",
    "ru": "rus",
    "ja": "jpn",
    "ko": "kor",
    "zh": "chi_sim",
}


def _is_tesseract_available() -> bool:
    try:
        import os
        import pytesseract

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            if not os.path.exists(TESSERACT_CMD):
                return False

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_extract_text_remote(image_bytes: bytes, lang: str = "en") -> str:
    if not OCR_SERVICE_URL:
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR service not configured. Set OCR_SERVICE_URL or install "
                "Tesseract-OCR on the server."
            ),
        )

    import requests

    headers = {}
    if OCR_SERVICE_KEY:
        headers["Authorization"] = f"Bearer {OCR_SERVICE_KEY}"

    files = {
        "file": ("scan.jpg", image_bytes, "application/octet-stream"),
    }
    data = {"lang": lang}

    try:
        response = requests.post(OCR_SERVICE_URL, headers=headers, files=files, data=data, timeout=30)
        response.raise_for_status()
        payload = response.json()
        text = payload.get("text") or payload.get("ocr_text") or ""
        if not text:
            raise ValueError("OCR service returned empty text")
        return text.strip()
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Remote OCR service unavailable: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Remote OCR service error: {exc}",
        )


def _build_tesseract_lang(lang: str) -> str:
    """Build Tesseract lang string: always include eng + requested lang."""
    parts: list[str] = ["eng"]
    tess = _LANG_TO_TESSERACT.get(lang)
    if tess and tess != "eng":
        parts.append(tess)
    return "+".join(parts)


def _ocr_extract_text(image_bytes: bytes, lang: str = "en") -> str:
    """Extract text from image bytes using Tesseract OCR.

    Falls back to a descriptive error when Tesseract is not installed.
    Supports all app languages via Tesseract language packs.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA/palette to RGB for OCR compatibility
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Pre-processing: resize if very small (improves OCR accuracy)
    w, h = img.size
    if max(w, h) < 600:
        scale = 1200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    tess_lang = _build_tesseract_lang(lang)

    # If the server is configured to use remote OCR or local Tesseract is unavailable,
    # fallback to a remote OCR endpoint when possible.
    tesseract_ready = _is_tesseract_available()
    if OCR_PROVIDER == "remote" or (OCR_PROVIDER == "auto" and not tesseract_ready):
        return _ocr_extract_text_remote(image_bytes, lang)
    if OCR_PROVIDER == "local" and not tesseract_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR service not available. Install pytesseract and Tesseract-OCR "
                "on the server, or set OCR_PROVIDER=remote with OCR_SERVICE_URL."
            ),
        )

    try:
        import pytesseract

        if TESSERACT_CMD:
            try:
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            except Exception:
                pass

        text = pytesseract.image_to_string(img, lang=tess_lang, config="--psm 6")
        return text.strip()
    except ImportError:
        if OCR_PROVIDER in ("auto", "remote"):
            return _ocr_extract_text_remote(image_bytes, lang)
        raise HTTPException(
            status_code=503,
            detail="OCR service not available. Install pytesseract and Tesseract-OCR.",
        )
    except Exception as e:
        _log = logging.getLogger("app.scan")
        # If requested lang pack is missing, fall back to eng-only
        if "Failed loading language" in str(e) and tess_lang != "eng":
            _log.warning("tesseract_lang_fallback requested=%s falling_back=eng", tess_lang)
            try:
                text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
                return text.strip()
            except Exception as e2:
                _log.error("ocr_fallback_failed error=%s", e2)
                raise HTTPException(status_code=500, detail=f"OCR processing failed: {e2}")
        _log.error("ocr_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")


def _reflow_ocr_lines(text: str) -> str:
    lines = text.split("\n")
    merged: list[str] = []
    prev: str | None = None

    def is_bullet_line(line: str) -> bool:
        return bool(re.match(r"^\s*[-*•\u2022\u2023\u25aa\u25a0\u25cf\u25cb\u25e6]\s+", line))

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if prev is not None:
                merged.append(prev)
                prev = None
            merged.append("")
            continue

        if prev is None:
            prev = stripped
            continue

        if is_bullet_line(stripped) or is_bullet_line(prev):
            merged.append(prev)
            prev = stripped
            continue

        if prev.rstrip().endswith("-"):
            prev = prev.rstrip()[:-1] + stripped
            continue

        if re.search(r"[a-z0-9]$", prev) and re.match(r"^[a-z]", stripped):
            prev = prev + " " + stripped
            continue

        merged.append(prev)
        prev = stripped

    if prev is not None:
        merged.append(prev)

    return "\n".join(merged)


def _normalize_ocr_text_for_cv_processing(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(
        r"(?m)^[ \t]*([•\u2022\u2023\u25aa\u25a0\u25cf\u25cb\u25e6\*\-·])\s*",
        "- ",
        text,
    )
    text = re.sub(r"(?m)^([ \t]*[-*])(?=\S)", r"- ", text)
    text = re.sub(r"(?m)-\n([a-z])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _reflow_ocr_lines(text)

    try:
        from agents.extract_agent import extract_structured
        from agents.normalize_agent import normalize
        from services.cv_autofix_service import _pipeline_to_structured_text

        extracted = extract_structured(text)
        normalized = normalize(extracted)
        repaired_text, _, _, _ = _pipeline_to_structured_text(
            normalized,
            job_description="",
            mode="balanced",
        )
        if repaired_text:
            text = repaired_text
    except Exception:
        pass

    return text.strip()


def _generate_scanned_pdf_from_text(text: str, source_images: list[bytes] | None = None) -> bytes:
    """Generate a PDF from scanned text with optional source images."""
    from fpdf import FPDF
    import textwrap

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Try to load DejaVuSans for full Unicode support
    _font_loaded = False
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                pdf.add_font("ScanFont", "", fpath, uni=True)
                pdf.set_font("ScanFont", size=10)
                _font_loaded = True
                break
            except Exception:
                continue
    if not _font_loaded:
        pdf.set_font("Helvetica", size=10)

    # Page 1: Extracted text
    pdf.add_page()
    pdf.set_font_size(14)
    pdf.cell(0, 10, "CV - Camera Scan", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font_size(10)

    for line in text.split("\n"):
        if not line.strip():
            pdf.ln(3)
            continue
        # Wrap long lines
        wrapped = textwrap.wrap(line, width=95) or [""]
        for wl in wrapped:
            pdf.cell(0, 5, wl, ln=True)

    # Append source images as additional pages if provided
    if source_images:
        from PIL import Image
        import tempfile
        for idx, img_bytes in enumerate(source_images):
            try:
                img = Image.open(io.BytesIO(img_bytes))
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    img.save(tmp, format="JPEG", quality=85)
                    tmp_path = tmp.name
                pdf.add_page()
                pdf.set_font_size(10)
                pdf.cell(0, 8, f"Original Scan - Page {idx + 1}", ln=True, align="C")
                pdf.ln(3)
                # Fit image within page margins
                page_w = pdf.w - 2 * pdf.l_margin
                page_h = pdf.h - pdf.t_margin - 30
                iw, ih = img.size
                ratio = min(page_w / iw, page_h / ih)
                pdf.image(tmp_path, x=pdf.l_margin, w=iw * ratio, h=ih * ratio)
                os.unlink(tmp_path)
            except Exception:
                continue

    return pdf.output()


def _generate_scanned_pdf(
    builder_payload: dict | None,
    job_description: str,
    lang: str,
    fallback_text: str,
    source_images: list[bytes] | None = None,
) -> bytes:
    """Generate a formatted CV PDF from structured payload or fallback to raw OCR text."""
    if builder_payload:
        try:
            cv_document = build_cv(
                builder_payload,
                job_description=job_description,
                template="classic",
                output_format="pdf",
                lang=lang,
                plan="free",
            )
            buf = cv_document.get("buffer")
            if buf is not None:
                if hasattr(buf, "getvalue"):
                    return buf.getvalue()
                if isinstance(buf, (bytes, bytearray)):
                    return bytes(buf)
        except Exception as exc:
            logging.getLogger("app.scan").warning(
                "build_cv_pdf_failed error=%s",
                exc,
                exc_info=True,
            )
    return _generate_scanned_pdf_from_text(fallback_text, source_images)


# recruiter scan-cv moved to routes/recruiter.py


# ═══════════════════════════════════════════════════════════════════════════
# SCORE BREAKDOWN — ATS + Job Match + Recruiter Score
# ═══════════════════════════════════════════════════════════════════════════


def _text_to_cvmodel(cv_text: str, lang: str = "en"):
    """Parse raw CV text into a CVModel via the autofix pipeline."""
    from schemas.cv_model import CVModel
    from services.cv_autofix_service import structured_text_to_builder_payload

    payload = structured_text_to_builder_payload(cv_text, job_description="", lang=lang)
    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    elif isinstance(payload, dict):
        data = payload
    else:
        data = dict(payload or {})
    data.setdefault("language", lang)
    return CVModel.from_mapping(data)


@app.post("/api/v1/score/breakdown")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PER_MIN}/minute")
def score_breakdown_endpoint(
    request: Request,
    response: Response,
    body: JobMatchScoreRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Full score breakdown: ATS scores + job match + recruiter score + feedback."""
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    from services.ats_scoring import score_cv
    from services.job_match_service import match_cv_to_job, generate_feedback, recruiter_score

    try:
        model = _text_to_cvmodel(body.cv_text, body.lang)

        ats = score_cv(model)
        match = match_cv_to_job(model, body.job_description)
        feedback = generate_feedback(model, body.job_description, match)
        rec = recruiter_score(model, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Score breakdown failed: {e}")

    return {
        "ats_scores": {
            "overall": ats.overall,
            "structure": ats.structure,
            "keywords": ats.keywords,
            "experience": ats.experience,
            "education": ats.education,
            "languages": ats.languages,
            "ats": ats.ats,
            "length": ats.length,
        },
        "job_match": {
            "match_score": match.match_score,
            "keyword_score": match.keyword_score,
            "semantic_score": match.semantic_score,
            "keyword_coverage_pct": match.keyword_coverage_pct,
            "missing_keywords": match.missing_keywords[:15],
            "weak_keywords": match.weak_keywords[:10],
            "strong_keywords": match.strong_keywords[:10],
            "suggested_keywords": match.suggested_keywords[:15],
        },
        "recruiter": {
            "interest": rec.recruiter_interest,
            "hireability": rec.hireability,
            "shortlist_probability": rec.shortlist_probability,
            "strengths": rec.strengths,
            "concerns": rec.concerns,
        },
        "feedback": {
            "score_before": feedback.score_before,
            "potential_score": feedback.potential_score,
            "items": [
                {"category": f.category, "priority": f.priority, "message": f.message}
                for f in feedback.items
            ],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# S3 STORAGE — Upload / Download / Delete CVs
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/v1/cv/upload")
@rate_limit(f"{RATE_LIMIT_IP_UPLOAD_PER_MIN}/minute")
async def upload_cv(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    _: None = Depends(require_abuse_check),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Upload original CV (PDF/DOCX) to S3.  Returns the S3 key only."""
    from services.storage_service import upload_original_cv
    from security.file_guard import validate_file_upload
    from security.s3_guard import enforce_user_cv_limit
    from security.rate_limit import check_upload_rate

    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Per-user upload rate guard
    try:
        check_upload_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    # Per-user CV count limit
    try:
        enforce_user_cv_limit(db, db_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    content_type = file.content_type or "application/pdf"
    contents = await file.read()

    # Full file validation (size, extension, mime, magic bytes, PDF complexity)
    try:
        validate_file_upload(contents, file.filename, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        key = upload_original_cv(contents, supabase_id, content_type, file.filename)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    except Exception:
        logger.exception("s3:upload_route_error user=%s", supabase_id)
        raise HTTPException(status_code=500, detail="Upload failed")

    return {"key": key, "filename": file.filename, "size": len(contents)}


@app.post("/api/v1/cv/upload-optimized")
@rate_limit(f"{RATE_LIMIT_IP_UPLOAD_PER_MIN}/minute")
async def upload_optimized_cv_route(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    _: None = Depends(require_abuse_check),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Upload an optimized/generated CV to S3."""
    from services.storage_service import upload_optimized_cv
    from security.file_guard import validate_file_upload
    from security.s3_guard import enforce_user_cv_limit
    from security.rate_limit import check_upload_rate

    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        check_upload_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        enforce_user_cv_limit(db, db_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    content_type = file.content_type or "application/pdf"
    contents = await file.read()

    try:
        validate_file_upload(contents, file.filename, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        key = upload_optimized_cv(contents, supabase_id, content_type, file.filename)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    except Exception:
        logger.exception("s3:upload_optimized_error user=%s", supabase_id)
        raise HTTPException(status_code=500, detail="Upload failed")

    return {"key": key, "filename": file.filename, "size": len(contents)}


@app.get("/api/v1/cv/download")
def download_cv(
    request: Request,
    key: str = Query(..., min_length=10, max_length=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Get a presigned download URL for a stored CV.

    Only allows downloading files that belong to the requesting user.
    Presigned URLs expire in 60 seconds.
    """
    from services.storage_service import get_download_url, exists
    from security.s3_guard import validate_s3_key, enforce_ownership
    from security.runtime_guard import check_download_rate, check_signed_url_rate

    _ensure_not_expired(user)
    supabase_id = user.get("user_id")
    try:
        DOWNLOADS_TOTAL.inc()
    except Exception:
        pass

    # Per-user download + signed URL rate guards
    try:
        check_download_rate(supabase_id)
        check_signed_url_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        validate_s3_key(key)
        enforce_ownership(key, supabase_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if not exists(key):
            raise HTTPException(status_code=404, detail="File not found")
        url_or_path = get_download_url(key, supabase_id)
        
        from services.storage_service import STORAGE_BACKEND
        if STORAGE_BACKEND == "local":
            return FileResponse(url_or_path, filename=os.path.basename(key))
            
        audit_log("cv_download", user_id=supabase_id, key=key[:80])
        return {"url": url_or_path}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key format")
    except HTTPException:
        raise
    except Exception:
        logger.exception("s3:download_error user=%s key=%s", supabase_id, key)
        raise HTTPException(status_code=500, detail="Download failed")


@app.delete("/api/v1/cv/file")
def delete_cv_file(
    request: Request,
    key: str = Query(..., min_length=10, max_length=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Delete a CV file from S3.  Only the owner can delete."""
    from services.storage_service import delete_cv
    from security.s3_guard import validate_s3_key, enforce_ownership

    _ensure_not_expired(user)
    supabase_id = user.get("user_id")

    try:
        validate_s3_key(key)
        enforce_ownership(key, supabase_id)
    except (ValueError, PermissionError):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        delete_cv(key, supabase_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key format")
    except Exception:
        logger.exception("s3:delete_error user=%s key=%s", supabase_id, key)
        raise HTTPException(status_code=500, detail="Delete failed")

    return {"deleted": key}
