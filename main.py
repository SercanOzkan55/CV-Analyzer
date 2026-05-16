import logging

from dotenv import load_dotenv

load_dotenv()
import os

MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
import hashlib
import json
import os
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Query,
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
from sqlalchemy import text

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
from services.billing_service import get_entitlements, is_feature_enabled
from services import upload_service
from services.ats_config import get_ats_weights
from routes.cv_builder import create_router as create_cv_builder_router
from routes.billing import create_router as create_billing_router
from routes.feedback import create_router as create_feedback_router
from routes.rewrite import create_router as create_rewrite_router
from routes.recruiter import create_router as create_recruiter_router
from routes.user_dashboard import create_router as create_user_dashboard_router
from routes.workspace import create_router as create_workspace_router
from schemas.rewrite import ScoreBreakdownRequest

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
_LOCAL_FEATURE_STORE_FILE = os.path.join(os.path.dirname(__file__), ".local_feature_store.json")
_LOCAL_FEATURE_STORE_LOCK = threading.Lock()


def _load_feature_store() -> dict:
    try:
        with open(_LOCAL_FEATURE_STORE_FILE, "r", encoding="utf-8") as f:
            data = json.loads(f.read() or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_LOCAL_FEATURE_STORE = _load_feature_store()


def _save_feature_store() -> None:
    try:
        with open(_LOCAL_FEATURE_STORE_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(_LOCAL_FEATURE_STORE, ensure_ascii=False, indent=2, default=str))
    except Exception:
        pass


def _feature_user_key(db_user: User | None, fallback: str | None = None) -> str:
    value = getattr(db_user, "supabase_id", None) or fallback or getattr(db_user, "email", None)
    return str(value or "anonymous")


def _feature_bucket(user_key: str, bucket_name: str) -> list:
    users = _LOCAL_FEATURE_STORE.setdefault("users", {})
    user_store = users.setdefault(str(user_key), {})
    bucket = user_store.setdefault(bucket_name, [])
    if not isinstance(bucket, list):
        bucket = []
        user_store[bucket_name] = bucket
    return bucket


def _next_feature_id(bucket: list) -> int:
    max_id = 0
    for item in bucket:
        try:
            max_id = max(max_id, int(item.get("id") or 0))
        except Exception:
            pass
    return max_id + 1


def _current_db_user(user: dict, db) -> User:
    _ensure_not_expired(user)
    supabase_id = (user or {}).get("user_id") or "mock-user"
    email = (user or {}).get("email") or "dev@example.com"
    return get_or_create_user(db, str(supabase_id), str(email))


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
_ENV_NAME = os.getenv("ENV", "dev").strip().lower()
_configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "https://yourdomain.com").split(",")
    if origin.strip()
]
_dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://localhost:5173",
    "https://127.0.0.1:5173",
    "https://localhost:5174",
    "https://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=(_configured_origins if _ENV_NAME == "prod" else _dev_origins + _configured_origins),
    allow_origin_regex=None if _ENV_NAME == "prod" else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
CLAMAV_ENABLED = upload_service.CLAMAV_ENABLED
CLAMAV_HOST = upload_service.CLAMAV_HOST
CLAMAV_PORT = upload_service.CLAMAV_PORT


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


def _scan_upload_for_viruses(contents: bytes) -> None:
    return upload_service.scan_upload_for_viruses(contents)


def _extract_pdf_text(contents: bytes) -> str:
    return upload_service.extract_pdf_text(contents)


def _extract_docx_text(contents: bytes) -> str:
    return upload_service.extract_docx_text(contents)


def _extract_plain_text(contents: bytes) -> str:
    return upload_service.extract_plain_text(contents)


def _validate_pdf_upload(contents: bytes, content_type: str | None) -> None:
    return upload_service.validate_pdf_upload(
        contents,
        content_type,
        virus_scanner=_scan_upload_for_viruses,
    )


def _extract_upload_text(
    contents: bytes,
    content_type: str | None = "",
    filename: str | None = "",
    *,
    max_size: int = 5_000_000,
) -> str:
    return upload_service.extract_upload_text(
        contents,
        content_type,
        filename,
        max_size=max_size,
        virus_scanner=_scan_upload_for_viruses,
        pdf_extractor=_extract_pdf_text,
        docx_extractor=_extract_docx_text,
        text_extractor=_extract_plain_text,
    )


async def _resolve_job_description_text(
    job_description: str = "", jd_file: UploadFile | None = None
) -> str:
    return await upload_service.resolve_job_description_text(
        job_description,
        jd_file,
        upload_text_extractor=_extract_upload_text,
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
        logger.exception("model prediction failed")
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
    except Exception:
        db.rollback()
        _metric_error("analyze", "db_insert")
        logger.exception("analysis insert failed")
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
    Analyze a CV upload against job description with JWT authentication.
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
        text = _extract_upload_text(contents, file.content_type, file.filename)
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
    text = _extract_upload_text(contents, file.content_type, file.filename)

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


def _analysis_payload(record: Analysis, include_raw: bool = False) -> dict:
    return {
        "id": getattr(record, "id", None),
        "analysis_id": getattr(record, "id", None),
        "user_id": getattr(record, "user_id", None),
        "organization_id": getattr(record, "organization_id", None),
        "similarity_score": float(getattr(record, "similarity_score", 0) or 0),
        "final_score": float(getattr(record, "similarity_score", 0) or 0),
        "interpretation": getattr(record, "interpretation", "") or "",
        "confidence": float(getattr(record, "confidence", 0) or 0),
        "risk_level": getattr(record, "risk_level", "") or "",
        "domain_id": getattr(record, "domain_id", None),
        "industry_id": getattr(record, "industry_id", None),
        "specialization_id": getattr(record, "specialization_id", None),
        "job_title": getattr(record, "job_title", None),
        "created_at": (
            getattr(record, "created_at", None).isoformat()
            if getattr(record, "created_at", None) is not None
            else None
        ),
    }


@app.get("/api/v1/benchmark/global")
def get_global_benchmark(db=Depends(get_db)):
    """Return lightweight global score stats for public pricing/benchmark UI."""
    from sqlalchemy import func

    try:
        total, avg_score, max_score = (
            db.query(
                func.count(Analysis.id),
                func.avg(Analysis.similarity_score),
                func.max(Analysis.similarity_score),
            ).one()
        )
    except Exception:
        total, avg_score, max_score = 0, 0, 0

    return {
        "total_analyses": int(total or 0),
        "average_score": round(float(avg_score or 0), 2),
        "top_score": round(float(max_score or 0), 2),
        "sample_size": int(total or 0),
    }


@app.get("/api/v1/benchmark/professions")
def get_profession_benchmarks(db=Depends(get_db)):
    """Return job-title grouped benchmark stats when enough history exists."""
    from sqlalchemy import func

    try:
        rows = (
            db.query(
                Analysis.job_title,
                func.count(Analysis.id).label("count"),
                func.avg(Analysis.similarity_score).label("avg_score"),
            )
            .filter(Analysis.job_title.isnot(None))
            .group_by(Analysis.job_title)
            .order_by(func.count(Analysis.id).desc())
            .limit(25)
            .all()
        )
    except Exception:
        rows = []

    return {
        "professions": [
            {
                "name": row.job_title or "General",
                "count": int(row.count or 0),
                "average_score": round(float(row.avg_score or 0), 2),
            }
            for row in rows
        ]
    }


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


app.include_router(
    create_user_dashboard_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        ensure_not_expired=_ensure_not_expired,
        get_or_create_user=get_or_create_user,
        current_db_user=_current_db_user,
        resolve_effective_plan=_resolve_effective_plan,
        resolve_daily_limit_for_plan=_resolve_daily_limit_for_plan,
        get_daily_quota_status=_get_daily_quota_status,
        mock_services_on=MOCK_SERVICES_ON,
        user_plan_limits_monthly=USER_PLAN_LIMITS_MONTHLY,
    )
)


app.include_router(
    create_workspace_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        current_db_user=_current_db_user,
        resolve_effective_plan=_resolve_effective_plan,
        analysis_payload=_analysis_payload,
        feature_user_key=_feature_user_key,
        feature_bucket=_feature_bucket,
        next_feature_id=_next_feature_id,
        save_feature_store=_save_feature_store,
        feature_store_lock=_LOCAL_FEATURE_STORE_LOCK,
        feature_store=_LOCAL_FEATURE_STORE,
    )
)


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


def _ensure_ai_rewrite_allowed(db, db_user: User):
    plan = _resolve_effective_plan(db, db_user)
    if not is_feature_enabled(plan, "ai_rewrite"):
        raise HTTPException(status_code=403, detail="AI rewrite not enabled for plan")
    return plan


app.include_router(
    create_feedback_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        ensure_not_expired=_ensure_not_expired,
        get_or_create_user=get_or_create_user,
        append_feedback_record=_append_feedback_record,
        read_feedback_records=_read_feedback_records,
        send_feedback_email=_send_feedback_email,
        audit_log=audit_log,
    )
)


app.include_router(
    create_rewrite_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        ensure_not_expired=_ensure_not_expired,
        get_or_create_user=get_or_create_user,
        resolve_effective_plan=_resolve_effective_plan,
        ensure_ai_rewrite_allowed=_ensure_ai_rewrite_allowed,
        current_db_user=_current_db_user,
        audit_log=audit_log,
        run_pipeline=run_pipeline,
        rate_limit=rate_limit,
        analyze_pdf_rate_limit_per_min=RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN,
        extract_upload_text=_extract_upload_text,
        metric_request=_metric_request,
        mock_services_on=MOCK_SERVICES_ON,
        logger=logger,
    )
)


app.include_router(
    create_billing_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        ensure_not_expired=_ensure_not_expired,
        get_or_create_user=get_or_create_user,
        read_feedback_records=_read_feedback_records,
        audit_log=audit_log,
        track_event=track_event,
        mock_services_on=MOCK_SERVICES_ON,
        logger=logger,
    )
)

app.include_router(
    create_recruiter_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        get_or_create_user=get_or_create_user,
        require_abuse_check=require_abuse_check,
        feature_user_key=_feature_user_key,
        feature_bucket=_feature_bucket,
        next_feature_id=_next_feature_id,
        save_feature_store=_save_feature_store,
        feature_store_lock=_LOCAL_FEATURE_STORE_LOCK,
        resolve_job_description_text=_resolve_job_description_text,
        extract_upload_text=_extract_upload_text,
        run_pipeline=run_pipeline,
        audit_log=audit_log,
        env_name=_ENV_NAME,
    )
)


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


app.include_router(
    create_cv_builder_router(
        verify_supabase_jwt=verify_supabase_jwt,
        get_db=get_db,
        rate_limit=rate_limit,
        require_captcha=require_captcha,
        require_abuse_check=require_abuse_check,
        current_db_user=_current_db_user,
        ensure_not_expired=_ensure_not_expired,
        metric_request=_metric_request,
        get_or_create_user=get_or_create_user,
        resolve_effective_plan=_resolve_effective_plan,
        consume_user_rate_limit=_consume_user_rate_limit,
        consume_daily_quota=_consume_daily_quota,
        resolve_daily_limit_for_plan=_resolve_daily_limit_for_plan,
        is_premium_plan=_is_premium_plan,
        audit_log=audit_log,
        mock_services_on=MOCK_SERVICES_ON,
        user_plan_limits_daily=USER_PLAN_LIMITS_DAILY,
    )
)
