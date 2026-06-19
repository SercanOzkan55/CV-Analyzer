from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading as _threading
import time
import uuid
from datetime import datetime
from time import time as current_time

from fastapi import Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from redis import Redis
except Exception:
    Redis = None

from limits.storage import RedisStorage
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import verify_supabase_jwt
from config.aws import MAX_UPLOAD_BYTES
from core.metrics import REDIS_CONNECTED
from core.ops_runtime import (
    _SAMPLE_RATE,
    _audit_event,
    _extract_client_ip,
    _inflight_dec,
    _inflight_inc,
    _record_security_event,
    _sample_logger,
)
from core.quota import (
    _LOCAL_USER_THROTTLE,
    _THROTTLE_MAX_ENTRIES,
    _extract_minute_bucket,
)
from core.request_utils import LimitUploadSizeMiddleware
from core.runtime_bridge import is_mock_services_on, main_value
from security.redaction import redact_mapping


logger = logging.getLogger("app.http")
audit_logger = logging.getLogger("app.audit")
_guard_logger = logging.getLogger("app.guard")
_MAX_LOG_LINE_LEN = int(os.getenv("MAX_LOG_LINE_LEN", "1000"))

_ENV_MODE = os.getenv("ENV", "development").lower()
MOCK_SERVICES_ON = is_mock_services_on()

share_tokens: dict[str, int] = {}

_GLOBAL_CONCURRENCY_LIMIT = int(os.getenv("GLOBAL_CONCURRENCY_LIMIT", "20"))
_REQUEST_QUEUE_SIZE = int(os.getenv("REQUEST_QUEUE_SIZE", "100"))
_REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "600"))
_IP_GLOBAL_LIMIT_PER_MIN = int(os.getenv("IP_GLOBAL_LIMIT_PER_MIN", "120"))
_USER_GLOBAL_LIMIT_PER_MIN = int(os.getenv("USER_GLOBAL_LIMIT_PER_MIN", "30"))
_USER_EMBED_LIMIT_PER_MIN = int(os.getenv("USER_EMBED_LIMIT_PER_MIN", "15"))
_SEARCH_LIMIT_PER_MIN = int(os.getenv("SEARCH_LIMIT_PER_MIN", "30"))
_MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(6 * 1024 * 1024)))
_MAX_RESPONSE_BODY_BYTES = int(os.getenv("MAX_RESPONSE_BODY_BYTES", str(50 * 1024 * 1024)))
_MAX_SEARCH_QUERY_LEN = int(os.getenv("MAX_SEARCH_QUERY_LEN", "500"))
_CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
_CB_COOLDOWN_SECONDS = float(os.getenv("CB_COOLDOWN_SECONDS", "30"))
_RATE_DICT_MAX_KEYS = int(os.getenv("RATE_DICT_MAX_KEYS", "10000"))
_DEDUP_WINDOW_SECONDS = float(os.getenv("DEDUP_WINDOW_SECONDS", "5"))

_global_semaphore = _threading.Semaphore(_GLOBAL_CONCURRENCY_LIMIT)
_request_queue = _threading.Semaphore(_REQUEST_QUEUE_SIZE)
_circuit_breaker_state: dict = {}

_HEAVY_ENDPOINTS = {
    "/api/analyze-cv-pdf",
    "/api/analyze-cv",
    "/api/cv-auto-fix",
    "/api/rewrite-cv",
    "/api/optimize-cv",
    "/api/cv-builder/render",
}
_PATH_TIMEOUTS: dict[str, int] = {
    "/api/analyze-cv-pdf": int(os.getenv("PATH_TIMEOUT_ANALYZE_PDF", "120")),
    "/api/analyze-cv": int(os.getenv("PATH_TIMEOUT_ANALYZE", "90")),
    "/api/cv-auto-fix": int(os.getenv("PATH_TIMEOUT_AUTOFIX", "90")),
    "/api/rewrite-cv": int(os.getenv("PATH_TIMEOUT_REWRITE", "90")),
    "/api/v1/recruiter/batch-rank": int(os.getenv("PATH_TIMEOUT_BATCH_RANK", "90")),
}
_PATH_CONCURRENCY: dict[str, int] = {
    "/api/v1/analyze": int(os.getenv("PATH_CONCURRENCY_ANALYZE", "10")),
    "/api/v1/analyze-pdf": int(os.getenv("PATH_CONCURRENCY_ANALYZE_PDF", "6")),
    "/api/v1/analyze-async": int(os.getenv("PATH_CONCURRENCY_ANALYZE_ASYNC", "6")),
    "/api/v1/cv-builder/generate": int(os.getenv("PATH_CONCURRENCY_CV_BUILDER", "5")),
    "/api/v1/rewrite/cover-letter": int(os.getenv("PATH_CONCURRENCY_COVER_LETTER", "5")),
    "/api/v1/recruiter/batch-rank": int(os.getenv("PATH_CONCURRENCY_BATCH_RANK", "3")),
}
_path_semaphores: dict[str, _threading.Semaphore] = {
    path: _threading.Semaphore(limit) for path, limit in _PATH_CONCURRENCY.items()
}
_path_semaphore_lock = _threading.Lock()

_ip_global_counts: dict[str, list[float]] = {}
_ip_global_lock = _threading.Lock()
_user_global_counts: dict[str, list[float]] = {}
_user_global_lock = _threading.Lock()
_user_embed_counts: dict[str, list[float]] = {}
_user_embed_lock = _threading.Lock()
_search_counts: dict[str, list[float]] = {}
_search_lock = _threading.Lock()
_dedup_cache: dict[str, float] = {}
_dedup_lock = _threading.Lock()

_BAN_DICT_MAX_ENTRIES = int(os.getenv("BAN_DICT_MAX_ENTRIES", "5000"))
_ABUSE_COUNTER_MAX_ENTRIES = int(os.getenv("ABUSE_COUNTER_MAX_ENTRIES", "5000"))
_ABUSE_BAN_SECONDS = int(os.getenv("ABUSE_BAN_SECONDS", "300"))
_LOCAL_ABUSE_COUNTERS: dict = {}
_LOCAL_ABUSE_BANS: dict = {}
_LOCAL_ABUSE_LOCK = _threading.Lock()

_BLOCKED_IPS = {ip.strip() for ip in os.getenv("BLOCKED_IPS", "").split(",") if ip.strip()}
ABUSE_PROTECTION_ENABLED = os.getenv("ABUSE_PROTECTION_ENABLED", "1").lower() in ("1", "true", "yes")
ABUSE_SCORE_BLOCK_THRESHOLD = int(os.getenv("ABUSE_SCORE_BLOCK_THRESHOLD", "100"))
ABUSE_SCORE_AUDIT_THRESHOLD = int(os.getenv("ABUSE_SCORE_AUDIT_THRESHOLD", "60"))
ABUSE_BAN_SECONDS = int(os.getenv("ABUSE_BAN_SECONDS", "900"))
ABUSE_FINGERPRINT_WINDOW_SECONDS = int(os.getenv("ABUSE_FINGERPRINT_WINDOW_SECONDS", "600"))
ABUSE_BURST_SOFT_LIMIT = int(os.getenv("ABUSE_BURST_SOFT_LIMIT", "20"))
ABUSE_BURST_HARD_LIMIT = int(os.getenv("ABUSE_BURST_HARD_LIMIT", "40"))
SENSITIVE_ABUSE_PATHS = {
    "/api/v1/analyze",
    "/api/v1/analyze-async",
    "/api/v1/analyze-pdf",
    "/api/v1/cv-builder/generate",
    "/api/v1/recruiter/batch-rank",
}

_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
_ADMIN_IP_ALLOWLIST_RAW = os.getenv("ADMIN_IP_ALLOWLIST", "").strip()
_ADMIN_RATE_LIMIT_PER_MIN = int(os.getenv("ADMIN_RATE_LIMIT_PER_MIN", "20"))
_ADMIN_RATE_WINDOW_SECONDS = 60
_admin_rate_lock = _threading.Lock()
_admin_rate_hits: dict[str, list[float]] = {}

RATE_LIMIT_IP_ANALYZE_PER_MIN = int(os.getenv("RATE_LIMIT_IP_ANALYZE_PER_MIN", "10"))
RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN = int(os.getenv("RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN", "10"))
RATE_LIMIT_USER_ANALYZE_PER_MIN = int(os.getenv("RATE_LIMIT_USER_ANALYZE_PER_MIN", "10"))
RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN = int(os.getenv("RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN", "10"))
RATE_LIMIT_IP_UPLOAD_PER_MIN = int(os.getenv("RATE_LIMIT_IP_UPLOAD_PER_MIN", "5"))
RATE_LIMIT_IP_RENDER_PER_MIN = int(os.getenv("RATE_LIMIT_IP_RENDER_PER_MIN", "10"))
RATE_LIMIT_IP_MATCH_PER_MIN = int(os.getenv("RATE_LIMIT_IP_MATCH_PER_MIN", "10"))
RATE_LIMIT_IP_REWRITE_PER_MIN = int(os.getenv("RATE_LIMIT_IP_REWRITE_PER_MIN", "5"))
RATE_LIMIT_IP_EMBED_PER_MIN = int(os.getenv("RATE_LIMIT_IP_EMBED_PER_MIN", "10"))

_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS")
_cors_origins = [
    origin.strip()
    for origin in (_CORS_ORIGINS_RAW or "http://localhost:5173,https://yourdomain.com").split(",")
    if origin.strip()
]
_APP_ENV = (
    os.getenv("APP_ENV")
    or os.getenv("ENV")
    or os.getenv("ENVIRONMENT")
    or os.getenv("STAGE")
    or "development"
).lower()
_CSRF_PROTECTION_ENABLED = os.getenv("CSRF_PROTECTION_ENABLED", "0").lower() in ("1", "true", "yes")
_UNSAFE_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_COOKIE_NAMES = ("csrf_token", "XSRF-TOKEN")
_CSRF_HEADER_NAMES = ("x-csrf-token", "x-xsrf-token")
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def _csrf_cookie_token(request: Request) -> str:
    for name in _CSRF_COOKIE_NAMES:
        token = request.cookies.get(name)
        if token:
            return token
    return ""


def _csrf_header_token(request: Request) -> str:
    for name in _CSRF_HEADER_NAMES:
        token = request.headers.get(name)
        if token:
            return token
    return ""


def _is_cookie_auth_state_changing_request(request: Request) -> bool:
    if request.method.upper() not in _UNSAFE_CSRF_METHODS:
        return False
    auth_header = (request.headers.get("authorization") or "").strip().lower()
    if auth_header.startswith("bearer "):
        return False
    cookie_header = request.headers.get("cookie") or ""
    if not cookie_header:
        return False
    if bool(main_value("_CSRF_PROTECTION_ENABLED", _CSRF_PROTECTION_ENABLED)):
        return True
    lower_cookie = cookie_header.lower()
    return "csrf_token=" in lower_cookie or "xsrf-token=" in lower_cookie


def _has_valid_csrf_token(request: Request) -> bool:
    cookie_token = _csrf_cookie_token(request)
    header_token = _csrf_header_token(request)
    return bool(cookie_token and header_token and hmac.compare_digest(cookie_token, header_token))


def _apply_security_headers(response):
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def _safe_log_message(message) -> str:
    text = str(message or "")
    if len(text) <= _MAX_LOG_LINE_LEN:
        return text
    return text[:_MAX_LOG_LINE_LEN] + "...[truncated]"


def _get_path_semaphore(path: str) -> _threading.Semaphore:
    with _path_semaphore_lock:
        if path not in _path_semaphores:
            limit = int(os.getenv("PATH_CONCURRENCY_LIMIT", "5"))
            _path_semaphores[path] = _threading.Semaphore(limit)
        return _path_semaphores[path]


def _prune_rate_bucket(bucket: dict, lock: _threading.Lock, cutoff: float):
    with lock:
        stale = [k for k, v in bucket.items() if isinstance(v, list) and (not v or max(v) < cutoff)]
        for key in stale:
            del bucket[key]


def _rate_ok(bucket: dict, lock: _threading.Lock, key: str, limit: int, window: int = 60) -> bool:
    now = time.time()
    cutoff = now - window
    with lock:
        hits = [ts for ts in bucket.get(key, []) if ts >= cutoff]
        if len(hits) >= limit:
            bucket[key] = hits
            return False
        hits.append(now)
        bucket[key] = hits
    return True


def _ip_global_rate_ok(ip: str) -> bool:
    return _rate_ok(_ip_global_counts, _ip_global_lock, ip, _IP_GLOBAL_LIMIT_PER_MIN)


def _user_global_rate_ok(uid: str) -> bool:
    return _rate_ok(_user_global_counts, _user_global_lock, uid, _USER_GLOBAL_LIMIT_PER_MIN)


def _user_embed_rate_ok(uid: str) -> bool:
    return _rate_ok(_user_embed_counts, _user_embed_lock, uid, _USER_EMBED_LIMIT_PER_MIN)


def _search_rate_ok(uid: str) -> bool:
    return _rate_ok(_search_counts, _search_lock, uid, _SEARCH_LIMIT_PER_MIN)


def _is_duplicate_request(key: str, window: float = _DEDUP_WINDOW_SECONDS) -> bool:
    now = time.time()
    with _dedup_lock:
        stale = [cache_key for cache_key, timestamp in _dedup_cache.items() if (now - timestamp) >= window]
        for cache_key in stale:
            del _dedup_cache[cache_key]
        if len(_dedup_cache) > _RATE_DICT_MAX_KEYS:
            oldest = sorted(_dedup_cache, key=_dedup_cache.get)
            for cache_key in oldest[: len(_dedup_cache) - _RATE_DICT_MAX_KEYS]:
                del _dedup_cache[cache_key]
        previous = _dedup_cache.get(key)
        if previous is not None and (now - previous) < window:
            return True
        _dedup_cache[key] = now
    return False


def _make_dedup_key(request: Request, user_id: str | None = None) -> str:
    parts = [request.method, request.url.path]
    if user_id:
        if isinstance(user_id, bytes):
            parts.append(user_id.decode("utf-8", errors="ignore"))
        else:
            parts.append(str(user_id))
    ip = _extract_client_ip(request) or ""
    if ip:
        parts.append(ip)
    return ":".join(parts)


def _parse_ip_allowlist(raw: str):
    import ipaddress

    entries = []
    for item in (raw or "").split(","):
        value = item.strip()
        if not value:
            continue
        try:
            entries.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid ADMIN_IP_ALLOWLIST entry")
    return entries


_ADMIN_IP_ALLOWLIST = _parse_ip_allowlist(_ADMIN_IP_ALLOWLIST_RAW)


def _check_admin_token(request: Request) -> bool:
    token = main_value("_ADMIN_TOKEN", _ADMIN_TOKEN)
    if not token:
        return False
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth[7:].strip(), token)


def _admin_client_host(request: Request) -> str:
    return _extract_client_ip(request) or (request.client.host if request.client else "")


def _admin_ip_allowed(request: Request) -> bool:
    import ipaddress

    allowlist = main_value("_ADMIN_IP_ALLOWLIST", _ADMIN_IP_ALLOWLIST)
    if not allowlist:
        return True
    try:
        ip_obj = ipaddress.ip_address(_admin_client_host(request))
    except ValueError:
        return False
    return any(ip_obj in network for network in allowlist)


def _admin_rate_limited(request: Request) -> bool:
    rate_limit_per_min = int(main_value("_ADMIN_RATE_LIMIT_PER_MIN", _ADMIN_RATE_LIMIT_PER_MIN))
    if rate_limit_per_min <= 0:
        return False
    now = time.time()
    identity = _admin_client_host(request) or "unknown"
    cutoff = now - _ADMIN_RATE_WINDOW_SECONDS
    with _admin_rate_lock:
        hits = [ts for ts in _admin_rate_hits.get(identity, []) if ts >= cutoff]
        if len(hits) >= rate_limit_per_min:
            _admin_rate_hits[identity] = hits
            return True
        hits.append(now)
        _admin_rate_hits[identity] = hits
        if len(_admin_rate_hits) > 1000:
            stale_keys = [key for key, values in _admin_rate_hits.items() if not values or max(values) < cutoff]
            for key in stale_keys[:200]:
                _admin_rate_hits.pop(key, None)
    return False


def _admin_access_error(request: Request):
    if not _check_admin_token(request):
        _audit_event("admin_access_denied", reason="invalid_token", path=request.url.path)
        _record_security_event("admin_access_denied", "high", request, reason="invalid_token")
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not _admin_ip_allowed(request):
        _audit_event("admin_access_denied", reason="ip_not_allowed", path=request.url.path)
        _record_security_event("admin_access_denied", "high", request, reason="ip_not_allowed")
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if _admin_rate_limited(request):
        _audit_event("admin_access_denied", reason="rate_limited", path=request.url.path)
        _record_security_event("admin_access_denied", "medium", request, reason="rate_limited")
        return JSONResponse({"error": "rate_limited"}, status_code=429)
    return None


def _set_abuse_ban(ip: str | None, fp: str | None, seconds: int = 300) -> None:
    now = time.time()
    with _LOCAL_ABUSE_LOCK:
        if ip:
            _LOCAL_ABUSE_BANS[f"ip:{ip}"] = now + seconds
        if fp:
            _LOCAL_ABUSE_BANS[f"fp:{fp}"] = now + seconds


def _is_abuse_banned(ip: str | None, fp: str | None) -> bool:
    now = time.time()
    with _LOCAL_ABUSE_LOCK:
        if ip and _LOCAL_ABUSE_BANS.get(f"ip:{ip}", 0) > now:
            return True
        if fp and _LOCAL_ABUSE_BANS.get(f"fp:{fp}", 0) > now:
            return True
    return False


def _escalate_abuse_ban(request: Request, uid: str, reason: str) -> None:
    client = getattr(request, "client", None)
    client_ip = client.host if client else None
    try:
        _set_abuse_ban(client_ip, uid, int(main_value("_ABUSE_BAN_SECONDS", _ABUSE_BAN_SECONDS)))
    except Exception:
        pass
    _guard_logger.warning("guard:abuse_ban_escalated reason=%s user=%s ip=%s", reason, uid, client_ip)


def require_user_global_rate(request: Request, user=Depends(verify_supabase_jwt)):
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _user_global_rate_ok(uid):
        _guard_logger.warning("guard:user_global_rate user=%s path=%s", uid, request.url.path)
        _escalate_abuse_ban(request, uid, "user_global_rate")
        raise HTTPException(status_code=429, detail="User request budget exceeded")
    return user


def require_embed_rate(request: Request, user=Depends(verify_supabase_jwt)):
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _user_embed_rate_ok(uid):
        _guard_logger.warning("guard:embed_spam user=%s", uid)
        _escalate_abuse_ban(request, uid, "embed_spam")
        raise HTTPException(status_code=429, detail="Embedding rate limit exceeded")
    return user


def require_search_rate(request: Request, user=Depends(verify_supabase_jwt)):
    uid = (user or {}).get("user_id") if isinstance(user, dict) else None
    if uid and not _search_rate_ok(uid):
        _guard_logger.warning("guard:search_abuse user=%s", uid)
        _escalate_abuse_ban(request, uid, "search_abuse")
        raise HTTPException(status_code=429, detail="Search rate limit exceeded")
    return user


def audit_log(event_type: str, **fields):
    try:
        payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **redact_mapping(fields),
        }
        audit_logger.info("%s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


def track_event(event_name: str, **fields):
    try:
        payload = {
            "event_name": event_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **fields,
        }
        audit_log("product_event", **payload)
    except Exception:
        pass


def _prune_abuse_dicts(now: float) -> None:
    with _LOCAL_ABUSE_LOCK:
        expired = [key for key, value in _LOCAL_ABUSE_BANS.items() if isinstance(value, (int, float)) and value < now]
        for key in expired:
            del _LOCAL_ABUSE_BANS[key]
        if len(_LOCAL_ABUSE_BANS) > _BAN_DICT_MAX_ENTRIES:
            by_expiry = sorted(_LOCAL_ABUSE_BANS, key=lambda key: _LOCAL_ABUSE_BANS.get(key, 0))
            for key in by_expiry[: len(by_expiry) - _BAN_DICT_MAX_ENTRIES]:
                del _LOCAL_ABUSE_BANS[key]
        stale = []
        for key, value in _LOCAL_ABUSE_COUNTERS.items():
            if isinstance(value, dict):
                window_start = value.get("window_start", 0)
                if window_start and (now - window_start) > 600:
                    stale.append(key)
        for key in stale:
            del _LOCAL_ABUSE_COUNTERS[key]
        if len(_LOCAL_ABUSE_COUNTERS) > _ABUSE_COUNTER_MAX_ENTRIES:
            by_window = sorted(
                _LOCAL_ABUSE_COUNTERS,
                key=lambda key: (_LOCAL_ABUSE_COUNTERS.get(key) or {}).get("window_start", 0),
            )
            for key in by_window[: len(by_window) - _ABUSE_COUNTER_MAX_ENTRIES]:
                del _LOCAL_ABUSE_COUNTERS[key]
        current_bucket = int(now) // 60
        stale_throttle = [key for key in _LOCAL_USER_THROTTLE if _extract_minute_bucket(key) < current_bucket - 5]
        for key in stale_throttle:
            del _LOCAL_USER_THROTTLE[key]
        if len(_LOCAL_USER_THROTTLE) > _THROTTLE_MAX_ENTRIES:
            sorted_keys = sorted(_LOCAL_USER_THROTTLE, key=_extract_minute_bucket)
            for key in sorted_keys[: len(sorted_keys) - _THROTTLE_MAX_ENTRIES]:
                del _LOCAL_USER_THROTTLE[key]


def _abuse_counter_key(fingerprint: str) -> str:
    window = max(1, int(main_value("ABUSE_FINGERPRINT_WINDOW_SECONDS", ABUSE_FINGERPRINT_WINDOW_SECONDS)))
    bucket = int(time.time()) // window
    return f"abuse:fp:{fingerprint}:{bucket}"


def _abuse_ban_key(kind: str, value: str) -> str:
    return f"abuse:ban:{kind}:{value}"


def _get_request_fingerprint(request: Request, client_ip: str | None = None) -> str:
    ip = client_ip or _extract_client_ip(request) or "unknown"
    ua = (request.headers.get("User-Agent") or "").strip().lower()
    lang = (request.headers.get("Accept-Language") or "").strip().lower()
    raw = "|".join([ip, ua, lang, request.method, request.url.path])
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _consume_abuse_fingerprint(fingerprint: str) -> dict:
    from core.runtime_bridge import redis_rate_client

    key = _abuse_counter_key(fingerprint)
    window = max(1, int(main_value("ABUSE_FINGERPRINT_WINDOW_SECONDS", ABUSE_FINGERPRINT_WINDOW_SECONDS)))
    redis_rate = redis_rate_client()

    if not redis_rate:
        now = time.time()
        current = _LOCAL_ABUSE_COUNTERS.get(key)
        if not current or float(current.get("expires_at", 0)) <= now:
            current = {"count": 0, "expires_at": now + window}
        current["count"] = int(current.get("count", 0)) + 1
        _LOCAL_ABUSE_COUNTERS[key] = current
        return {"key": key, "count": int(current["count"]), "window_seconds": window, "source": "memory"}

    try:
        count = int(redis_rate.incr(key))
        ttl = int(redis_rate.ttl(key))
        if count == 1 or ttl < 0:
            redis_rate.expire(key, window)
        return {"key": key, "count": count, "window_seconds": window, "source": "redis"}
    except Exception:
        now = time.time()
        current = _LOCAL_ABUSE_COUNTERS.get(key)
        if not current or float(current.get("expires_at", 0)) <= now:
            current = {"count": 0, "expires_at": now + window}
        current["count"] = int(current.get("count", 0)) + 1
        _LOCAL_ABUSE_COUNTERS[key] = current
        return {"key": key, "count": int(current["count"]), "window_seconds": window, "source": "memory"}


def _set_abuse_ban_with_redis(client_ip: str | None, fingerprint: str, seconds: int) -> None:
    from core.runtime_bridge import redis_rate_client

    ttl = max(1, int(seconds))
    redis_rate = redis_rate_client()
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


def _is_abuse_banned_with_redis(client_ip: str | None, fingerprint: str | None) -> bool:
    from core.runtime_bridge import redis_rate_client

    keys = []
    if client_ip:
        keys.append(_abuse_ban_key("ip", client_ip))
    if fingerprint:
        keys.append(_abuse_ban_key("fp", fingerprint))
    if not keys:
        return False

    redis_rate = redis_rate_client()
    if redis_rate:
        try:
            for key in keys:
                if redis_rate.get(key):
                    return True
            return False
        except Exception:
            pass

    now = time.time()
    return any(float(_LOCAL_ABUSE_BANS.get(key, 0)) > now for key in keys)


def _compute_abuse_risk_score(request: Request, client_ip: str | None, fingerprint_count: int) -> int:
    score = 0
    ua = (request.headers.get("User-Agent") or "").lower()
    content_length = int(request.headers.get("Content-Length", "0") or "0")

    if not ua:
        score += 20
    if any(token in ua for token in ("sqlmap", "scanner", "nikto", "nmap", "fuzzer", "bot", "crawler")):
        score += 35
    if request.url.path in SENSITIVE_ABUSE_PATHS:
        score += 10
    if request.method not in ("GET", "POST", "OPTIONS"):
        score += 15
    if content_length > MAX_UPLOAD_BYTES:
        score += 25
    if fingerprint_count > int(main_value("ABUSE_BURST_SOFT_LIMIT", ABUSE_BURST_SOFT_LIMIT)):
        score += 20
    if fingerprint_count > int(main_value("ABUSE_BURST_HARD_LIMIT", ABUSE_BURST_HARD_LIMIT)):
        score += 45
    if client_ip and client_ip in _BLOCKED_IPS:
        score += 100
    return int(score)


def require_abuse_check(request: Request):
    if not bool(main_value("ABUSE_PROTECTION_ENABLED", ABUSE_PROTECTION_ENABLED)):
        return None

    client_ip = _extract_client_ip(request)
    fingerprint = _get_request_fingerprint(request, client_ip)

    if _is_abuse_banned_with_redis(client_ip, fingerprint):
        audit_log(
            "abuse_request_rejected",
            client_ip=client_ip,
            endpoint=request.url.path,
            method=request.method,
            reason="temporary_ban_active",
        )
        raise HTTPException(status_code=429, detail="Request blocked by abuse protection")

    fp_usage = _consume_abuse_fingerprint(fingerprint)
    risk_score = _compute_abuse_risk_score(request, client_ip, int(fp_usage.get("count", 0)))
    request.state.abuse_risk_score = risk_score

    block_threshold = int(main_value("ABUSE_SCORE_BLOCK_THRESHOLD", ABUSE_SCORE_BLOCK_THRESHOLD))
    audit_threshold = int(main_value("ABUSE_SCORE_AUDIT_THRESHOLD", ABUSE_SCORE_AUDIT_THRESHOLD))
    ban_seconds = int(main_value("ABUSE_BAN_SECONDS", ABUSE_BAN_SECONDS))

    if risk_score >= block_threshold:
        _set_abuse_ban_with_redis(client_ip, fingerprint, ban_seconds)
        audit_log(
            "abuse_request_blocked",
            client_ip=client_ip,
            endpoint=request.url.path,
            method=request.method,
            risk_score=risk_score,
            fingerprint_count=int(fp_usage.get("count", 0)),
            ban_seconds=ban_seconds,
        )
        raise HTTPException(status_code=429, detail="Request blocked by abuse protection")

    if risk_score >= audit_threshold:
        audit_log(
            "abuse_risk_detected",
            client_ip=client_ip,
            endpoint=request.url.path,
            method=request.method,
            risk_score=risk_score,
            fingerprint_count=int(fp_usage.get("count", 0)),
        )
    return None


def _init_redis_rate():
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
            redis_rate.ping()
            from security.runtime_guard import set_redis as _set_runtime_redis

            _set_runtime_redis(redis_rate, url=redis_url)
            try:
                REDIS_CONNECTED.set(1)
            except Exception:
                pass
            return redis_url, redis_rate
        except Exception:
            try:
                REDIS_CONNECTED.set(0)
            except Exception:
                pass
    return redis_url, None


redis_url, redis_rate = _init_redis_rate()


class NoopLimiter:
    def limit(self, limit_string):
        def decorator(func):
            return func

        return decorator


def _build_limiter():
    try:
        return Limiter(key_func=get_remote_address, storage=RedisStorage(redis_url))
    except Exception:
        return NoopLimiter()


limiter = _build_limiter()


def rate_limit(limit_string):
    if bool(main_value("MOCK_SERVICES_ON", MOCK_SERVICES_ON)):
        def noop_decorator(func):
            return func

        return noop_decorator
    return limiter.limit(limit_string)


def register_http_runtime(app, app_logger):
    cors_origins = list(_cors_origins)
    if _APP_ENV in {"prod", "production"} and not _CORS_ORIGINS_RAW:
        raise RuntimeError("CORS_ORIGINS must be configured explicitly in production")
    if not cors_origins:
        if _APP_ENV in {"prod", "production"}:
            raise RuntimeError("CORS_ORIGINS must be configured explicitly in production")
        cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

    app.state.limiter = limiter
    app.add_middleware(LimitUploadSizeMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next):
        if _is_cookie_auth_state_changing_request(request) and not _has_valid_csrf_token(request):
            return JSONResponse(status_code=403, content={"detail": "CSRF token missing or invalid"})
        return await call_next(request)

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = current_time()
        try:
            response = await call_next(request)
            duration_ms = (current_time() - start_time) * 1000
            app_logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            duration_ms = (current_time() - start_time) * 1000
            app_logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise

    @app.middleware("http")
    async def ip_blocklist_middleware(request: Request, call_next):
        if request.url.path in ("/health", "/readiness", "/liveness"):
            return await call_next(request)
        try:
            client_ip = _extract_client_ip(request)
            if client_ip and client_ip in _BLOCKED_IPS:
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            fingerprint = _get_request_fingerprint(request, client_ip)
            if _is_abuse_banned_with_redis(client_ip, fingerprint):
                return JSONResponse(status_code=429, content={"detail": "Request blocked by abuse protection"})
        except Exception:
            pass
        return await call_next(request)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        _inflight_inc()
        start = time.time()
        try:
            response = await call_next(request)
        finally:
            _inflight_dec()
        duration = int((time.time() - start) * 1000)
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None) if user else None
        if user_id is None and isinstance(user, dict):
            user_id = user.get("user_id")
        organization_id = getattr(user, "organization_id", None) if user else None
        if organization_id is None and isinstance(user, dict):
            organization_id = user.get("organization_id")
        plan_type = getattr(user, "plan_type", None) if user else None
        if plan_type is None and isinstance(user, dict):
            plan_type = user.get("plan_type")
        payload = {
            "request_id": getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID"),
            "user_id": user_id,
            "organization_id": organization_id,
            "plan_type": plan_type,
            "endpoint": request.url.path,
            "duration_ms": duration,
            "status_code": response.status_code,
        }
        app_logger.info("%s", json.dumps(payload, ensure_ascii=False))
        if duration > 1000:
            logging.getLogger("app.slow").warning(
                "slow_request path=%s duration_ms=%d status=%d request_id=%s",
                request.url.path,
                duration,
                response.status_code,
                payload["request_id"] or "-",
            )
        if _SAMPLE_RATE and __import__("random").random() < _SAMPLE_RATE:
            _sample_logger.info(
                "sample path=%s method=%s duration_ms=%d status=%d request_id=%s user_agent=%s",
                request.url.path,
                request.method,
                duration,
                response.status_code,
                payload["request_id"] or "-",
                (request.headers.get("user-agent") or "-")[:200],
            )
        return response

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        return _apply_security_headers(response)
