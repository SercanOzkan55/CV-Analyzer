import logging

from dotenv import load_dotenv

load_dotenv()
import os

MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
import hashlib
import hmac
import io
import json
import os
import smtplib
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import (Depends, FastAPI, File, Form, Header, HTTPException, Query,
                     Request, Response, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except Exception:
    Instrumentator = None

try:
    from prometheus_client import Counter, REGISTRY
except Exception:
    Counter = None
    REGISTRY = None

from alembic.config import Config
from alembic.script import ScriptDirectory
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, text

try:
    from redis import Redis
except Exception:
    Redis = None
from limits.storage import RedisStorage

from auth import verify_supabase_jwt
from database import SessionLocal, get_db
from models import Analysis, Candidate, Job, Organization, User
from services.ats_service import analyze_cv
from services.domain_service import (detect_or_create_domain,
                                     get_domain_similarity)
from services.embedding_service import (find_similar_candidates, get_embedding,
                                        save_candidate_embedding,
                                        save_job_embedding)
from services.experience_service import experience_score
from services.industry_service import detect_industry_and_specialization
from services.keyword_service import keyword_match_score, compute_keyword_gap
from services.language_service import (DEFAULT_LANG,
                                       FALLBACK_LANG,
                                       NEUTRAL_LANG,
                                       detect_language,
                                       interpret_score_localized,
                                       localize_risk_level)
from services.model_service import predict_match
from services.recommendation_service import generate_recommendations
from services.scoring_service import calculate_similarity
from services.skill_service import skill_coverage_score
from services.tasks import analyze_pdf_task, analyze_text_task, celery_app
from services.cv_builder_service import build_cv, get_available_templates
from services.billing_service import get_entitlements, is_feature_enabled
from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload
from services import rewrite_service
from services.ats_config import get_ats_weights
from database import engine

# FastAPI docs hardening for production
if os.getenv("ENV", "dev") == "prod":
    app = FastAPI(docs_url=None, redoc_url=None)
else:
    app = FastAPI()

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

# Fallback stores when Redis is unavailable (local runtime memory).
# Daily quota is persisted to a JSON file so it survives server restarts.
_QUOTA_FILE = os.path.join(os.path.dirname(__file__), ".local_quota.json")


def _load_local_quota() -> dict:
    """Load persisted daily quota from disk."""
    try:
        with open(_QUOTA_FILE, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        # Prune entries older than today based on quota key suffix.
        # Key format: quota:daily:<user_id>:YYYYMMDD
        today_compact = datetime.utcnow().strftime("%Y%m%d")
        today_hyphen = datetime.utcnow().strftime("%Y-%m-%d")

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
_LOCAL_ABUSE_COUNTERS = {}
_LOCAL_ABUSE_BANS = {}


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

# CORS middleware
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
        os.getenv("CORS_ORIGINS", "https://yourdomain.com"),
    ],
    # Accept any localhost/127.0.0.1 dev origin regardless of port.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve only the built frontend assets under /static (never the project root).
_static_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


logger = logging.getLogger("app.access")
audit_logger = logging.getLogger("app.audit")


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
    start = time.time()
    response = await call_next(request)
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
        "request_id": request.headers.get("X-Request-ID"),
        "user_id": user_id,
        "organization_id": organization_id,
        "plan_type": plan_type,
        "endpoint": request.url.path,
        "duration_ms": duration,
        "status_code": response.status_code,
    }
    logger.info("%s", json.dumps(log_payload, ensure_ascii=False))
    return response


# Health check endpoint
@app.get("/health")
def health_check():
    if MOCK_SERVICES_ON:
        return {"status": "ok", "mode": "mock"}

    # Only use database dependency in non-mock mode

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return {"status": "fail"}, 503
    finally:
        db.close()


# Readiness check endpoint
@app.get("/ready")
def readiness_check():
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()
        return {"migration_head": head, "status": "ready"}
    except Exception as e:
        return {"status": "fail", "error": "internal readiness check failed"}


# NOTE: we used to call ``Base.metadata.create_all`` here to ensure the
# schema matched the models. With Alembic migrations in place that is no
# longer desirable (it can lead to drift and won't add/remove columns).
# In development you can still bootstrap the database by running
# ``python setup_db.py`` or ``alembic upgrade head``; this automatic call
# is intentionally disabled.


@app.on_event("startup")
def start_model_worker():
    try:
        # Allow tests to disable the worker without enabling MOCK_SERVICES
        if os.getenv("MODEL_WORKER_DISABLED"):
            return
        from services import model_worker

        model_worker.start()
    except Exception:
        pass


@app.on_event("shutdown")
def stop_model_worker():
    try:
        from services import model_worker

        model_worker.stop()
    except Exception:
        pass


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
    except Exception:
        redis_rate = None
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


MODEL_WEIGHT = float(os.getenv("MODEL_WEIGHT", 0.85))
ATS_WEIGHT = float(os.getenv("ATS_WEIGHT", 0.15))

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


class AnalyzeRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    job_text: str | None = None
    lang: str = DEFAULT_LANG

    def model_post_init(self, __context):
        if (not self.job_description) and self.job_text:
            self.job_description = self.job_text


class CVBuilderRequest(BaseModel):
    full_name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    professional_profile: str = ""
    summary: str = ""
    experiences: list = []
    education: list = []
    skills: list = []
    certifications: list = []
    projects: list = []
    languages: list = []
    job_description: str = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = DEFAULT_LANG


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

    # Domain-based auto role assignment: if user's email domain matches an
    # existing Organization, mark them as a recruiter and attach the org.
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


def _seconds_until_next_utc_day() -> int:
    now = datetime.utcnow()
    tomorrow = datetime(now.year, now.month, now.day) + timedelta(days=1)
    return max(1, int((tomorrow - now).total_seconds()))


def _daily_quota_key(user_id: str, now: datetime | None = None) -> str:
    dt = now or datetime.utcnow()
    return f"quota:daily:{user_id}:{dt.strftime('%Y%m%d')}"


def _resolve_daily_limit_for_plan(plan_type: str | None) -> int:
    """Resolve the effective daily limit for a user's plan.

    For backward compatibility, free users can still override via
    `REDIS_FREE_DAILY_LIMIT`; other plans use USER_PLAN_LIMITS_DAILY.
    """
    normalized = (plan_type or "free").strip().lower()
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
            redis_rate.expire(key, _seconds_until_next_utc_day())

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
    return (plan_type or "free").strip().lower() in ("pro", "enterprise")


def _resolve_effective_plan(db, db_user: User) -> str:
    if db_user and db_user.role == "recruiter" and db_user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == db_user.organization_id)
            .first()
        )
        if org and getattr(org, "plan_type", None):
            return str(org.plan_type)
    return str((db_user.plan_type or "free") if db_user else "free")


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
    semantic, keyword, skill, exp, missing_skills, domain_similarity, ats_score
):
    missing_count = len(missing_skills)
    total_required_skills = missing_count + max(1, int(skill / 20))

    missing_ratio = missing_count / total_required_skills

    semantic_skill_interaction = float(semantic * skill / 100)
    keyword_skill_interaction = float(keyword * skill / 100)

    # balance_score approximates how balanced semantic vs skill coverage is
    balance_score = float(max(0.0, 100.0 - abs(float(semantic) - float(skill))))

    return [
        float(semantic),
        float(keyword),
        float(skill),
        float(exp),
        int(missing_count),
        float(missing_ratio),
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score,
    ]


ANALYSIS_CACHE_TTL = int(os.getenv("ANALYSIS_CACHE_TTL", "86400"))
MAX_ANALYZE_CV_TEXT_CHARS = int(os.getenv("MAX_ANALYZE_CV_TEXT_CHARS", "200000"))
MAX_ANALYZE_JOB_TEXT_CHARS = int(os.getenv("MAX_ANALYZE_JOB_TEXT_CHARS", "100000"))


def _stable_hash(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_analyze_text_payload(cv_text: str, job_description: str) -> None:
    if len(cv_text or "") > MAX_ANALYZE_CV_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="CV text is too large")
    if len(job_description or "") > MAX_ANALYZE_JOB_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="Job description is too large")


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
        import clamd
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


def _extract_pdf_text(contents: bytes) -> str:
    """Extract plain text from PDF bytes with layout-aware fallbacks.

    pdfplumber is used when available because it tends to preserve multi-page
    and multi-column reading order better than basic PyPDF2 extraction. PyPDF2
    remains the dependency-light fallback for test and minimal deployments.
    """

    errors: list[str] = []
    text_parts: list[str] = []

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                extracted = ""
                try:
                    extracted = page.extract_text(layout=True) or ""
                except TypeError:
                    extracted = page.extract_text() or ""
                if extracted.strip():
                    text_parts.append(f"\n--- Page {page_index} ---\n{extracted.strip()}")
    except Exception:
        errors.append("pdfplumber")

    if not text_parts:
        try:
            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
            for page_index, page in enumerate(pdf_reader.pages, start=1):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    text_parts.append(f"\n--- Page {page_index} ---\n{extracted.strip()}")
        except Exception:
            errors.append("PyPDF2")

    if errors and not text_parts:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    text = "\n".join(text_parts).strip()
    if not text:
        raise HTTPException(status_code=400, detail="PDF contains no extractable text")
    return text


def _validate_pdf_upload(contents: bytes, content_type: str | None) -> None:
    """Apply upload security checks for PDF files."""

    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

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
        return _extract_pdf_text(contents)

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


def run_pipeline(cv_text: str, job_description: str, lang: str = DEFAULT_LANG):
    # Basic input guards
    if not isinstance(cv_text, str):
        cv_text = ""
    if not isinstance(job_description, str):
        job_description = ""

    requested_lang = (lang or DEFAULT_LANG).strip().lower()

    # Detect languages independently and prefer job-description language for output
    # unless the client explicitly requests a supported language. Unknown language
    # stays neutral internally and falls back only for localized copy.
    cv_lang = detect_language(cv_text)
    jd_lang = detect_language(job_description)
    if requested_lang not in ("", DEFAULT_LANG, "detect", "default", "browser"):
        detected_lang = requested_lang
    elif jd_lang != NEUTRAL_LANG:
        detected_lang = jd_lang
    elif cv_lang != NEUTRAL_LANG:
        detected_lang = cv_lang
    else:
        detected_lang = FALLBACK_LANG

    # Truncate extremely large inputs to avoid resource exhaustion
    MAX_CV_LEN = 200_000
    MAX_JOB_LEN = 100_000
    if len(cv_text) > MAX_CV_LEN:
        cv_text = cv_text[:MAX_CV_LEN]
    if len(job_description) > MAX_JOB_LEN:
        job_description = job_description[:MAX_JOB_LEN]

    # Analysis result cache (Redis-backed when available).
    cache_key = None
    if redis_rate is not None:
        try:
            cv_hash = _stable_hash(cv_text)
            job_hash = _stable_hash(job_description)
            # Cache is language-aware to avoid returning English content on non-English UI.
            cache_key = f"analysis:v2:{detected_lang}:{cv_hash}:{job_hash}"
            cached = redis_rate.get(cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                # Ignore cache decode errors and continue with fresh pipeline
                pass

    cv_embedding = get_embedding(cv_text)
    job_embedding = get_embedding(job_description)

    # If embeddings fail, fall back to conservative defaults and mark
    embedding_failed = False
    if not cv_embedding or not job_embedding:
        semantic_score = 0.0
        embedding_failed = True
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

    # FEATURES
    features = build_features(
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_skills,
        domain_similarity,
        ats_score,
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

    recommendations = generate_recommendations(
        missing_skills, semantic_score, keyword_score, lang=detected_lang
    )

    final_score = (prediction * MODEL_WEIGHT) + (ats_score * ATS_WEIGHT)
    final_score = round(float(final_score), 2)
    interpretation = interpret_score_localized(final_score, detected_lang)

    # Localize risk level
    risk_level = localize_risk_level(risk_level, detected_lang)

    # If embeddings failed for this request, apply conservative cap to avoid
    # manipulation via embedding failures. Also expose a flag for observability.
    if embedding_failed:
        capped = min(final_score, 40.0)
        if capped != final_score:
            final_score = capped
            interpretation = interpret_score_localized(final_score, detected_lang)

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

    result = {
        "semantic_score": round(semantic_score, 2),
        "keyword_score": keyword_score,
        "skill_score": skill_score,
        "experience_score": exp_score,
        "ats_score": ats_score,
        "ats": ats_details,
        "domain_similarity": round(domain_similarity, 2),
        "detected_skills": detected_skills,
        "missing_skills": missing_skills,
        "keyword_gap": keyword_gap,
        "final_score": final_score,
        "interpretation": interpretation,
        "confidence": float(confidence),
        "risk_level": risk_level,
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
        "ats_weights": ats_weights,
        "ats_weighted_score": ats_weighted_score,
    }

    # Store analysis result in Redis cache for subsequent identical requests.
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
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Analyze CV against job description with JWT authentication.
    User must provide valid Supabase JWT token in Authorization header.
    """
    _ensure_not_expired(user)
    _metric_request("analyze")
    _validate_analyze_text_payload(body.cv_text, body.job_description)

    # In MOCK_SERVICES mode skip DB user creation and quota checks
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"

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

        redis_quota = _consume_daily_quota(
            str(mock_user_id), limit=_resolve_daily_limit_for_plan("free")
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
        result = _apply_plan_based_result_features(result, "free")
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

    # reset daily/monthly counters if a new UTC day/month has started
    now = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < now.date():
        db_user.daily_usage = 0
        db_user.last_reset = now
    if db_user.updated_at is None or db_user.updated_at.month != now.month:
        db_user.monthly_usage = 0
        db_user.updated_at = now

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
                org.plan_type or "free", ORG_PLAN_LIMITS_DAILY["free"]
            )
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                org.plan_type or "free", ORG_PLAN_LIMITS_MONTHLY["free"]
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
    else:
        # individual user quota using plan mapping
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_MONTHLY["free"]
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
        else:
            db_user.daily_usage = (db_user.daily_usage or 0) + 1
            db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
            db.add(db_user)

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

    result = _apply_plan_based_result_features(result, effective_plan)

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
    now = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < now.date():
        db_user.daily_usage = 0
        db_user.last_reset = now
    if db_user.updated_at is None or db_user.updated_at.month != now.month:
        db_user.monthly_usage = 0
        db_user.updated_at = now

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
                org.plan_type or "free", ORG_PLAN_LIMITS_DAILY["free"]
            )
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(
                org.plan_type or "free", ORG_PLAN_LIMITS_MONTHLY["free"]
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
    else:
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_MONTHLY["free"]
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
    lang: str = Form(DEFAULT_LANG),
    _: None = Depends(require_captcha),
    __: None = Depends(require_abuse_check),
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

    # In MOCK_SERVICES mode skip DB user creation and quota checks
    # Use the normalized boolean `MOCK_SERVICES_ON` so values like "0" don't
    # accidentally enable mock behaviour (string "0" is truthy).
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"

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

        redis_quota = _consume_daily_quota(
            str(mock_user_id), limit=_resolve_daily_limit_for_plan("free")
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
        _validate_pdf_upload(contents, file.content_type)
        text = _extract_pdf_text(contents)
        result = run_pipeline(text, job_description, lang)
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
        or db_user.last_reset.date() < datetime.utcnow().date()
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
    else:
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_DAILY["free"]
        )
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_MONTHLY["free"]
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
    _validate_pdf_upload(contents, file.content_type)
    text = _extract_pdf_text(contents)

    # Queue the analysis job (or run synchronously in LocalTask fallback)
    task = analyze_pdf_task.delay(text, job_description, lang)

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
def get_analysis_result(job_id: str):
    """Poll the status/result of an async analysis job.

    For LocalTask fallback, the original analyze-async endpoint will already
    have returned the result inline, but this endpoint remains useful when
    Celery/Redis are enabled.
    """

    if celery_app is None:
        raise HTTPException(status_code=503, detail="Async processing disabled")

    async_result = celery_app.AsyncResult(job_id)
    state = async_result.state
    if state in ("PENDING", "RECEIVED"):
        return {"status": "pending"}
    if state == "STARTED":
        return {"status": "running"}
    if state == "FAILURE":
        return {"status": "failed", "error": str(async_result.result)}

    # SUCCESS
    try:
        result = async_result.result
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    return {"status": "completed", "result": result}


# =====================================================
# HISTORY
# =====================================================


@app.get("/api/v1/history")
def get_history(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """
    Get analysis history for authenticated user with JWT.
    Returns user's own analyses only.
    """
    # Get or create user in database
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Return user's analysis records
    records = (
        db.query(Analysis)
        .filter(Analysis.user_id == db_user.id)
        .order_by(Analysis.id.desc())
        .all()
    )

    return records


@app.get("/api/v1/benchmark/{analysis_id}")
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
        daily_limit = _resolve_daily_limit_for_plan(effective_plan)
        redis_quota = _get_daily_quota_status(str(mock_user_id), limit=daily_limit)
        if redis_quota is None:
            return {
                "plan_type": effective_plan,
                "role": db_user.role or "individual",
                "source": "mock",
                "daily": {
                    "used": int(db_user.daily_usage or 0),
                    "limit": daily_limit,
                    "remaining": max(0, int(daily_limit - int(db_user.daily_usage or 0))),
                },
                "monthly": {
                    "used": int(db_user.monthly_usage or 0),
                    "limit": int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                    "remaining": max(
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
                "limit": redis_quota["limit"],
                "remaining": redis_quota["remaining"],
            },
            "monthly": {
                "used": int(db_user.monthly_usage or 0),
                "limit": int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                "remaining": max(
                    0,
                    int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])) - int(db_user.monthly_usage or 0),
                ),
            },
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    plan_type = db_user.plan_type or "free"
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
        daily_limit = redis_quota["limit"]
        daily_remaining = redis_quota["remaining"]
        source = "redis"
    else:
        daily_used = int(db_user.daily_usage or 0)
        daily_limit = int(user_daily_limit)
        daily_remaining = max(0, daily_limit - daily_used)
        source = "db"

    monthly_used = int(db_user.monthly_usage or 0)
    monthly_limit = int(user_monthly_limit)

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
            "remaining": max(0, monthly_limit - monthly_used),
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
        "plan_type": db_user.plan_type or "free",
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
    if not matches:
        # Portable fallback for local/test databases without vector search.
        rows = db.query(Candidate).limit(max(1, int(body.k or 10))).all()
        matches = [(row.id, 0.0) for row in rows]
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
    lang: str = Form(DEFAULT_LANG),
    use_ai: bool = Form(True),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Extract a CV from PDF and rewrite it into a cleaner ATS-friendly format."""

    _ensure_not_expired(user)
    _metric_request("cv-auto-fix")

    db_user = None
    if not MOCK_SERVICES_ON:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)

    contents = await file.read()
    _validate_pdf_upload(contents, file.content_type)
    cv_text = _extract_pdf_text(contents)

    try:
        result = await run_in_threadpool(
            auto_fix_cv_text,
            cv_text=cv_text,
            job_description=job_description,
            lang=lang,
            use_ai=use_ai,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("auto_fix_cv_text unexpected error")
        raise HTTPException(status_code=500, detail=f"Auto-fix error: {e}")

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

    return result


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG
    tone: str = "professional"


class CVAutoFixExportRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = DEFAULT_LANG


class CVAutoFixParseRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG


class BulletRewriteRequest(BaseModel):
    bullets: list[str]
    job_description: str | None = ""
    lang: str = DEFAULT_LANG
    tone: str = "professional"


class CoverLetterRewriteRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = DEFAULT_LANG
    tone: str = "professional"


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


@app.post("/api/v1/rewrite/cv")
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

    try:
        text = rewrite_service.rewrite_cv(
            cv_text=body.cv_text,
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
            "ai_rewrite_cv",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"result": text, "plan": plan}


@app.post("/api/v1/cv/auto-fix/export")
def export_auto_fixed_cv(
    body: CVAutoFixExportRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from fastapi.responses import StreamingResponse

    _ensure_not_expired(user)

    if body.output_format not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="output_format must be 'docx' or 'pdf'")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    effective_plan = _resolve_effective_plan(db, db_user)

    cv_data = structured_text_to_builder_payload(
        body.optimized_cv_text,
        job_description=body.job_description or "",
        lang=body.lang,
    )
    cv_data["template"] = body.template
    cv_data["output_format"] = body.output_format

    result = build_cv(
        cv_data=cv_data,
        job_description=body.job_description or "",
        template=body.template,
        output_format=body.output_format,
        lang=body.lang,
        plan=effective_plan,
    )

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

    return StreamingResponse(
        result["buffer"],
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

    return {"builder_payload": builder_payload}


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
        letter = rewrite_service.rewrite_cover_letter(
            cv_text=body.cv_text,
            job_description=body.job_description,
            lang=body.lang,
            tone=body.tone,
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

    return {"result": letter, "plan": plan}


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
    value = (plan_type or "free").strip().lower()
    if value not in User.PLAN_TYPES:
        return "free"
    return value


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
            stripe_price_id=body.price_id or f"price_mock_{desired_plan}",
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
        "STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_FILE", "test_secret"
    )
    IS_TEST_MODE = MOCK_SERVICES_ON

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = json.loads(payload)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {str(e)}"})

    # Signature verification (skip in test mode)
    if not IS_TEST_MODE and STRIPE_WEBHOOK_SECRET != "test_secret":
        try:
            expected_sig = hmac.new(
                STRIPE_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
            ).hexdigest()
            provided_sig = ""
            for part in sig_header.split(","):
                part = part.strip()
                if part.startswith("v1="):
                    provided_sig = part.split("=", 1)[1]
                    break
            if not provided_sig or not hmac.compare_digest(expected_sig, provided_sig):
                return JSONResponse(status_code=401, content={"error": "Invalid signature"})
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"error": f"Signature verification failed: {str(e)}"},
            )

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


def recruiter_required(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Dependency: verify caller is a recruiter by checking DB record."""
    supabase_id = user.get("user_id")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")

    db_user = db.query(User).filter(User.supabase_id == supabase_id).first()
    if not db_user or db_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter role required")
    return db_user


@app.get("/api/v1/recruiter/candidates")
def recruiter_candidates(
    limit: int = 20, db=Depends(get_db), recruiter=Depends(recruiter_required)
):
    """Return recent candidate analyses for the recruiter's organization."""
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    # Find analyses belonging to users in the organization
    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
    records = (
        db.query(Analysis)
        .filter(Analysis.user_id.in_(select(users_subq.c.id)))
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )

    result = []
    for r in records:
        result.append(
            {
                "analysis_id": getattr(r, "id", None),
                "user_id": getattr(r, "user_id", None),
                "similarity_score": getattr(r, "similarity_score", None),
                "interpretation": getattr(r, "interpretation", None),
                "confidence": getattr(r, "confidence", None),
                "risk_level": getattr(r, "risk_level", None),
                "domain_id": getattr(r, "domain_id", None),
                "industry_id": getattr(r, "industry_id", None),
                "specialization_id": getattr(r, "specialization_id", None),
                "created_at": getattr(r, "created_at", None),
            }
        )

    return {"candidates": result}


@app.get("/api/v1/recruiter/top_candidates")
def recruiter_top_candidates(
    limit: int = 10,
    min_score: float = 0.0,
    start_date: str | None = None,
    end_date: str | None = None,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """Return top N candidates for recruiter's org ordered by score.

    Optional filters: `min_score`, `start_date` and `end_date` (ISO format).
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()

    query = db.query(Analysis).filter(Analysis.user_id.in_(select(users_subq.c.id)))

    # Apply score filter
    try:
        if min_score is not None:
            query = query.filter(Analysis.similarity_score >= float(min_score))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid min_score")

    # Date filters (expect ISO-8601 strings)
    from datetime import datetime as _dt

    if start_date:
        try:
            sd = _dt.fromisoformat(start_date)
            query = query.filter(Analysis.created_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid start_date format; expected ISO-8601"
            )

    if end_date:
        try:
            ed = _dt.fromisoformat(end_date)
            query = query.filter(Analysis.created_at <= ed)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid end_date format; expected ISO-8601"
            )

    records = query.order_by(Analysis.similarity_score.desc()).limit(limit).all()

    result = []
    for r in records:
        result.append(
            {
                "analysis_id": getattr(r, "id", None),
                "user_id": getattr(r, "user_id", None),
                "final_score": getattr(r, "similarity_score", None),
                "interpretation": getattr(r, "interpretation", None),
                "created_at": getattr(r, "created_at", None),
            }
        )

    return {"top_candidates": result}


@app.get("/api/v1/recruiter/candidate/{analysis_id}")
def recruiter_candidate_detail(
    analysis_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)
):
    """Return full analysis detail for a single candidate (scoped to org)."""
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    # Load analysis and ensure it belongs to a user in the org
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    user = db.query(User).filter(User.id == analysis.user_id).first()
    if not user or user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build response payload
    payload = {
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

    return payload


def _is_postgres_engine() -> bool:
    try:
        url = getattr(engine, "url", None)
        if not url:
            return False
        return str(url.get_backend_name()).startswith("postgres")
    except Exception:
        return False


@app.get("/api/v1/recruiter/search")
def recruiter_search(
    q: str,
    limit: int = 20,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """Full-text search over candidates for a recruiter's organization.

    Uses PostgreSQL tsvector/ts_rank when available; falls back to a
    simple LIKE-based search on other databases so tests and SQLite
    environments continue to work.
    """

    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query q is required")

    results: list[dict] = []

    try:
        if _is_postgres_engine():
            # Use PostgreSQL full-text search with ranking.
            sql = text(
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
                LIMIT :limit
                """
            )
            rows = db.execute(sql, {"q": q, "org_id": org_id, "limit": int(limit)}).fetchall()
            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "organization_id": row[1],
                        "cv_preview": (row[2][:200] + "...") if row[2] and len(row[2]) > 200 else row[2],
                        "rank": float(row[3]),
                    }
                )
        else:
            # Generic LIKE-based search for non-Postgres engines.
            pattern = f"%{q}%"
            from models import Candidate

            rows = (
                db.query(Candidate)
                .filter(Candidate.organization_id == org_id)
                .filter(Candidate.cv_text.ilike(pattern))
                .limit(limit)
                .all()
            )
            for r in rows:
                results.append(
                    {
                        "id": getattr(r, "id", None),
                        "organization_id": getattr(r, "organization_id", None),
                        "cv_preview": (
                            (r.cv_text[:200] + "...")
                            if getattr(r, "cv_text", None) and len(r.cv_text) > 200
                            else getattr(r, "cv_text", None)
                        ),
                    }
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    return {"results": results}


@app.post("/api/v1/recruiter/batch-rank")
async def recruiter_batch_rank(
    request: Request,
    files: list[UploadFile] = File(...),
    job_description: str = Form(""),
    jd_file: UploadFile | None = File(None),
    _: None = Depends(require_abuse_check),
    recruiter=Depends(recruiter_required),
):
    """Batch-rank up to 50 CV PDFs against a job description.

    Input can include JD text (`job_description`) or JD file (`jd_file` as txt/pdf).
    Returns sorted ranking and recruiter analytics summary.
    """

    if not files:
        raise HTTPException(status_code=400, detail="At least one CV file is required")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 CV files allowed")

    jd_text = await _resolve_job_description_text(job_description, jd_file)
    if not jd_text:
        raise HTTPException(status_code=400, detail="Job description is empty")

    ranked = []
    skill_counts: dict[str, int] = {}

    for idx, upload in enumerate(files):
        contents = await upload.read()
        _validate_pdf_upload(contents, upload.content_type)
        cv_text = _extract_pdf_text(contents)
        if not cv_text:
            raise HTTPException(
                status_code=400,
                detail=f"CV contains no extractable text: {upload.filename or (idx + 1)}",
            )

        result = run_pipeline(cv_text, jd_text)
        detected_skills = result.get("detected_skills") or []
        for s in detected_skills:
            key = str(s or "").strip().lower()
            if key:
                skill_counts[key] = skill_counts.get(key, 0) + 1

        ranked.append(
            {
                "candidate_name": (upload.filename or f"candidate_{idx + 1}").replace(
                    ".pdf", ""
                ),
                "file_name": upload.filename or f"candidate_{idx + 1}.pdf",
                "final_score": float(result.get("final_score") or 0.0),
                "ats_score": float(result.get("ats_score") or 0.0),
                "skill_score": float(result.get("skill_score") or 0.0),
                "missing_skills": result.get("missing_skills") or [],
                "keyword_gap": result.get("keyword_gap") or {},
                "score_breakdown": result.get("score_breakdown") or {},
                "recommendations": result.get("recommendations") or [],
            }
        )

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i

    total = len(ranked)
    avg_score = round(sum(r["final_score"] for r in ranked) / max(1, total), 2)
    distribution = {
        "high": sum(1 for r in ranked if r["final_score"] >= 75),
        "medium": sum(1 for r in ranked if 50 <= r["final_score"] < 75),
        "low": sum(1 for r in ranked if r["final_score"] < 50),
    }
    top_skills = sorted(skill_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    try:
        audit_log(
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
        "analytics": {
            "avg_score": avg_score,
            "top_skills": [
                {"skill": skill, "count": count} for skill, count in top_skills
            ],
            "candidate_distribution": distribution,
        },
    }


@app.get("/api/v1/task-status/{task_id}")
def get_task_status(task_id: str):
    # If Celery isn't configured (tests or minimal env), return a safe response
    try:
        from celery.result import AsyncResult
    except Exception:
        return {
            "task_id": task_id,
            "status": "unavailable",
            "note": "Celery not configured",
        }

    if not celery_app:
        return {
            "task_id": task_id,
            "status": "unavailable",
            "note": "Celery backend not configured",
        }

    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    return response


# =====================================================
# CV BUILDER
# =====================================================

RATE_LIMIT_IP_CV_BUILDER_PER_MIN = int(
    os.getenv("RATE_LIMIT_IP_CV_BUILDER_PER_MIN", "10")
)
RATE_LIMIT_USER_CV_BUILDER_PER_MIN = int(
    os.getenv("RATE_LIMIT_USER_CV_BUILDER_PER_MIN", "5")
)


@app.get("/api/v1/cv-builder/templates")
def cv_builder_templates(
    request: Request,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Return available CV templates for the user's plan."""
    _ensure_not_expired(user)

    if MOCK_SERVICES_ON:
        # Even in mock mode, respect actual user plan for templates
        supabase_id = user.get("user_id")
        email = user.get("email") 
        db_user = get_or_create_user(db, supabase_id, email)
        plan = _resolve_effective_plan(db, db_user)
        # Fallback to free if no plan resolved
        if not plan or plan == "unknown":
            plan = "free"
    else:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        plan = _resolve_effective_plan(db, db_user)

    templates = get_available_templates(plan)
    return {
        "templates": templates,
        "plan": plan,
    }


@app.post("/api/v1/cv-builder/generate")
@rate_limit(f"{RATE_LIMIT_IP_CV_BUILDER_PER_MIN}/minute")
async def cv_builder_generate(
    request: Request,
    response: Response,
    body: CVBuilderRequest,
    _: None = Depends(require_captcha),
    __: None = Depends(require_abuse_check),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Generate an ATS-optimized CV document (DOCX or PDF).
    Uses the same daily quota as analyze-pdf.
    """
    from fastapi.responses import StreamingResponse

    _ensure_not_expired(user)
    _metric_request("cv-builder")

    # Validate output format
    if body.output_format not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="output_format must be 'docx' or 'pdf'")

    # Validate name
    if not body.full_name or not body.full_name.strip():
        raise HTTPException(status_code=400, detail="full_name is required")

    # ---- MOCK MODE ----
    if MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        mock_plan = _resolve_effective_plan(db, mock_db_user)

        user_throttle = _consume_user_rate_limit(
            str(mock_user_id), RATE_LIMIT_USER_CV_BUILDER_PER_MIN, "cv-builder"
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(
                user_throttle["remaining"]
            )
            if not user_throttle["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail=f"User rate limit exceeded ({user_throttle['limit']}/minute)",
                )

        # Premium users: unlimited CV generation (skip quota)
        if not _is_premium_plan(mock_plan):
            redis_quota = _consume_daily_quota(
                str(mock_user_id), limit=_resolve_daily_limit_for_plan(mock_plan)
            )
            if redis_quota is not None:
                response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
                response.headers["X-Daily-Used"] = str(redis_quota["used"])
                response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
                if not redis_quota["allowed"]:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                    )

        cv_data = body.model_dump()
        result = build_cv(
            cv_data=cv_data,
            job_description=body.job_description,
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=mock_plan,
        )

        return StreamingResponse(
            result["buffer"],
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            },
        )

    # ---- NORMAL MODE ----
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    effective_plan = _resolve_effective_plan(db, db_user)

    # Per-user throttle
    user_throttle = _consume_user_rate_limit(
        db_user.supabase_id or str(db_user.id),
        RATE_LIMIT_USER_CV_BUILDER_PER_MIN,
        "cv-builder",
    )
    if user_throttle is not None:
        response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
        response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
        response.headers["X-User-RateLimit-Remaining"] = str(
            user_throttle["remaining"]
        )
        if not user_throttle["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"User rate limit exceeded ({user_throttle['limit']}/minute)",
            )

    # Daily quota (shared with analyze)
    if db_user.last_reset is None or db_user.last_reset.date() < datetime.utcnow().date():
        db_user.daily_usage = 0
        db_user.last_reset = datetime.utcnow()

    if db_user.role != "recruiter" and not _is_premium_plan(effective_plan):
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(
            db_user.plan_type or "free", USER_PLAN_LIMITS_DAILY["free"]
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
                raise HTTPException(
                    status_code=403,
                    detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                )
        elif (db_user.daily_usage or 0) >= user_daily_limit:
            raise HTTPException(status_code=403, detail="Daily quota exceeded")

        db_user.daily_usage = (db_user.daily_usage or 0) + 1
        db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
        db.add(db_user)
        db.commit()

    # Build the CV
    cv_data = body.model_dump()
    result = build_cv(
        cv_data=cv_data,
        job_description=body.job_description,
        template=body.template,
        output_format=body.output_format,
        lang=body.lang,
        plan=effective_plan,
    )

    response_stream = StreamingResponse(
        result["buffer"],
        media_type=result["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"'
        },
    )

    try:
        audit_log(
            "cv_builder_generate",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            output_format=body.output_format,
            template=body.template,
            plan=effective_plan,
        )
    except Exception:
        pass

    return response_stream


@app.post("/api/v1/cv-builder/preview")
@rate_limit(f"{RATE_LIMIT_IP_CV_BUILDER_PER_MIN}/minute")
async def cv_builder_preview(
    request: Request,
    response: Response,
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """
    Preview: enhance CV data with AI and return structured JSON
    (no document generation, no quota consumption).
    """
    _ensure_not_expired(user)

    if MOCK_SERVICES_ON:
        plan = "free"
    else:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        plan = _resolve_effective_plan(db, db_user)

    from services.cv_builder_service import _enhance_cv_with_ai, _mock_enhance

    cv_data = body.model_dump()
    if MOCK_SERVICES_ON:
        enhanced = _mock_enhance(cv_data, body.job_description, body.lang)
    else:
        enhanced = _enhance_cv_with_ai(cv_data, body.job_description, body.lang)

    # Remove non-serializable fields
    enhanced.pop("buffer", None)

    return {
        "enhanced_data": enhanced,
        "available_templates": get_available_templates(plan),
        "plan": plan,
    }
