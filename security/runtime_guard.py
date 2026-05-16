"""Runtime concurrency and rate guards for public deployment.

Provides per-user optimize concurrency, global optimize concurrency,
per-user download rate, and per-user signed URL rate limits.
Uses Redis when available, falls back to in-memory with thread-safe access.
Auto-reconnects on Redis failure and logs disconnect events.
"""

import logging
import os
import threading
import time
from collections import defaultdict

logger = logging.getLogger("security.runtime_guard")

# ── Redis handle (injected from main.py at startup) ─────────────────
_redis = None
_redis_url: str | None = None
_redis_lock = threading.Lock()
_redis_last_fail: float = 0.0
_REDIS_RECONNECT_INTERVAL = 30  # seconds between reconnect attempts


def set_redis(redis_client, url: str | None = None):
    """Inject the shared Redis client from main.py startup."""
    global _redis, _redis_url
    _redis = redis_client
    if url:
        _redis_url = url


def _get_redis():
    """Return the Redis client, attempting reconnect if previously failed."""
    global _redis, _redis_last_fail
    if _redis is not None:
        return _redis

    now = time.time()
    if now - _redis_last_fail < _REDIS_RECONNECT_INTERVAL:
        return None

    with _redis_lock:
        if _redis is not None:
            return _redis
        if not _redis_url:
            return None
        try:
            from redis import Redis
            client = Redis.from_url(
                _redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
                retry_on_timeout=False,
            )
            client.ping()
            _redis = client
            _redis_last_fail = 0.0
            logger.info("redis:reconnected via runtime_guard")
            try:
                from main import REDIS_CONNECTED
                REDIS_CONNECTED.set(1)
            except Exception:
                pass
            return _redis
        except Exception as exc:
            _redis_last_fail = now
            logger.warning("redis:reconnect_failed error=%s (using local fallback)", exc)
            return None


def _redis_op(fn):
    """Execute a Redis operation with disconnect logging, alerting & fallback."""
    global _redis, _redis_last_fail
    client = _get_redis()
    if client is None:
        return None  # signal caller to use local fallback
    try:
        return fn(client)
    except Exception as exc:
        logger.warning("redis:disconnect error=%s (falling back to local)", exc)
        _redis = None
        _redis_last_fail = time.time()
        # SRE: alert on redis disconnect
        try:
            from main import _alert, REDIS_CONNECTED
            _alert("redis_down", f"Redis disconnected: {exc}")
            REDIS_CONNECTED.set(0)
        except Exception:
            pass
        return None  # signal caller to use local fallback

# ── Per-user optimize concurrency ───────────────────────────────────
_MAX_USER_OPTIMIZE_CONCURRENT = int(os.getenv("MAX_USER_OPTIMIZE_CONCURRENT", "2"))
_user_optimize_counts: dict[str, int] = defaultdict(int)
_user_optimize_lock = threading.Lock()

# ── Global optimize concurrency ─────────────────────────────────────
_GLOBAL_OPTIMIZE_LIMIT = int(os.getenv("GLOBAL_OPTIMIZE_CONCURRENT", "5"))
_global_optimize_sem = threading.Semaphore(_GLOBAL_OPTIMIZE_LIMIT)


class OptimizeConcurrencyGuard:
    """Context manager enforcing per-user + global optimize concurrency.

    Usage::

        with OptimizeConcurrencyGuard(user_id):
            ... # heavy optimize work
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._user_acquired = False
        self._global_acquired = False

    def __enter__(self):
        # Per-user check first
        with _user_optimize_lock:
            if _user_optimize_counts[self.user_id] >= _MAX_USER_OPTIMIZE_CONCURRENT:
                logger.warning(
                    "runtime:user_optimize_concurrency user=%s count=%d limit=%d",
                    self.user_id, _user_optimize_counts[self.user_id],
                    _MAX_USER_OPTIMIZE_CONCURRENT,
                )
                raise ValueError(
                    f"Too many concurrent optimize requests (max {_MAX_USER_OPTIMIZE_CONCURRENT})"
                )
            _user_optimize_counts[self.user_id] += 1
            self._user_acquired = True

        # Global check
        if not _global_optimize_sem.acquire(timeout=0.1):
            # Roll back user counter
            with _user_optimize_lock:
                _user_optimize_counts[self.user_id] -= 1
                if _user_optimize_counts[self.user_id] <= 0:
                    _user_optimize_counts.pop(self.user_id, None)
            self._user_acquired = False
            logger.warning(
                "runtime:global_optimize_concurrency limit=%d",
                _GLOBAL_OPTIMIZE_LIMIT,
            )
            raise ValueError("Server optimize capacity reached, please retry shortly")
        self._global_acquired = True
        return self

    def __exit__(self, *args):
        if self._global_acquired:
            _global_optimize_sem.release()
        if self._user_acquired:
            with _user_optimize_lock:
                _user_optimize_counts[self.user_id] -= 1
                if _user_optimize_counts[self.user_id] <= 0:
                    _user_optimize_counts.pop(self.user_id, None)


# ── Per-user download rate limit ────────────────────────────────────
_DOWNLOAD_LIMIT_PER_MIN = int(os.getenv("DOWNLOAD_LIMIT_PER_MIN", "30"))
_download_counts: dict[str, list[float]] = {}
_download_lock = threading.Lock()


def check_download_rate(user_id: str) -> None:
    """Raise ValueError if user exceeds download rate limit."""
    if _DOWNLOAD_LIMIT_PER_MIN <= 0 or not user_id:
        return

    # ── Try Redis first ──
    def _redis_dl(client):
        key = f"rl:dl:{user_id}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 60)
        if count > _DOWNLOAD_LIMIT_PER_MIN:
            raise ValueError(f"Download rate limit exceeded ({_DOWNLOAD_LIMIT_PER_MIN}/min)")
        return True

    result = _redis_op(_redis_dl)
    if result is not None:
        return  # Redis handled it (or raised ValueError)

    now = time.time()
    cutoff = now - 60
    with _download_lock:
        ts = _download_counts.get(user_id)
        if ts is None:
            ts = []
            _download_counts[user_id] = ts
        while ts and ts[0] < cutoff:
            ts.pop(0)
        if not ts:
            _download_counts.pop(user_id, None)
            ts = []
            _download_counts[user_id] = ts
        if len(ts) >= _DOWNLOAD_LIMIT_PER_MIN:
            logger.warning(
                "runtime:download_rate user=%s count=%d limit=%d",
                user_id, len(ts), _DOWNLOAD_LIMIT_PER_MIN,
            )
            raise ValueError(f"Download rate limit exceeded ({_DOWNLOAD_LIMIT_PER_MIN}/min)")
        ts.append(now)


# ── Per-user signed URL rate limit ──────────────────────────────────
_SIGNED_URL_LIMIT_PER_MIN = int(os.getenv("SIGNED_URL_LIMIT_PER_MIN", "20"))
_signed_url_counts: dict[str, list[float]] = {}
_signed_url_lock = threading.Lock()


def check_signed_url_rate(user_id: str) -> None:
    """Raise ValueError if user exceeds signed URL rate limit."""
    if _SIGNED_URL_LIMIT_PER_MIN <= 0 or not user_id:
        return

    # ── Try Redis first ──
    def _redis_su(client):
        key = f"rl:su:{user_id}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 60)
        if count > _SIGNED_URL_LIMIT_PER_MIN:
            raise ValueError(f"Signed URL rate limit exceeded ({_SIGNED_URL_LIMIT_PER_MIN}/min)")
        return True

    result = _redis_op(_redis_su)
    if result is not None:
        return  # Redis handled it (or raised ValueError)

    now = time.time()
    cutoff = now - 60
    with _signed_url_lock:
        ts = _signed_url_counts.get(user_id)
        if ts is None:
            ts = []
            _signed_url_counts[user_id] = ts
        while ts and ts[0] < cutoff:
            ts.pop(0)
        if not ts:
            _signed_url_counts.pop(user_id, None)
            ts = []
            _signed_url_counts[user_id] = ts
        if len(ts) >= _SIGNED_URL_LIMIT_PER_MIN:
            logger.warning(
                "runtime:signed_url_rate user=%s count=%d limit=%d",
                user_id, len(ts), _SIGNED_URL_LIMIT_PER_MIN,
            )
            raise ValueError(f"Signed URL rate limit exceeded ({_SIGNED_URL_LIMIT_PER_MIN}/min)")
        ts.append(now)
