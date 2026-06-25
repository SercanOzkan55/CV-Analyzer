"""Operational runtime controls: feature flags, kill switch, drain, panic, audit.

Extracted from ``main.py`` to reduce monolith size while preserving
backward-compatible attribute access via ``getattr(main, ...)``.
"""

from __future__ import annotations
from core.timeutils import utcnow

import gc as _gc
import ipaddress
import json
import logging
import os
import threading as _threading
import time

from core.metrics import (
    _GUARD_REJECT_LOCK,
    _GUARD_REJECT_TIMESTAMPS,
    ADMIN_ACTIONS_TOTAL,
    BREAKER_OPEN,
    FLAG_ENABLED,
    GC_COLLECTIONS_TOTAL,
    GUARD_SAFE_MODE_TRIGGERS,
    PANIC_ACTIVE,
    PANIC_TRIGGERS_TOTAL,
    PROCESS_CPU_PERCENT,
    PROCESS_RSS_BYTES,
    PROCESS_VMS_BYTES,
    WORKER_ACTIVE_TASKS,
    WORKER_QUEUE_SIZE,
)
from security.redaction import redact_for_log, redact_mapping

# ── Ops: Feature flags (env-driven) ──────────────────────────────────────
FEATURE_OPTIMIZE = os.getenv("FEATURE_OPTIMIZE", "1").lower() not in ("0", "false", "no")
FEATURE_AUTO_FIX = os.getenv("FEATURE_AUTO_FIX", "1").lower() not in ("0", "false", "no")
FEATURE_SEMANTIC_SEARCH = os.getenv("FEATURE_SEMANTIC_SEARCH", "1").lower() not in ("0", "false", "no")
FEATURE_HTML_EXPORT = os.getenv("FEATURE_HTML_EXPORT", "1").lower() not in ("0", "false", "no")

# ── Ops: Maintenance mode ────────────────────────────────────────────────
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "").lower() in ("1", "true", "yes")

# ── Runtime: Live feature toggle store ───────────────────────────────────
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
        with open(_LIVE_FLAGS_FILE, encoding="utf-8") as f:
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

# Import circuit breaker from shared
from shared import _cb_record_failure


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
    safe_kwargs = {key: redact_for_log(value, key=key) for key, value in kwargs.items()}
    _audit_rt_logger.warning("AUDIT:%s %s", event, " ".join(f"{k}={v}" for k, v in safe_kwargs.items()))


# ── Event stores ─────────────────────────────────────────────────────────
_OPS_EVENT_LIMIT = int(os.getenv("OPS_EVENT_LIMIT", "500"))
_ops_events: list[dict] = []
_security_events: list[dict] = []
_ai_usage_events: list[dict] = []
_ops_events_lock = _threading.Lock()
_security_events_lock = _threading.Lock()
_ai_usage_events_lock = _threading.Lock()


def _push_limited_event(bucket: list[dict], lock, event: dict) -> None:
    try:
        with lock:
            bucket.append(event)
            overflow = len(bucket) - max(50, _OPS_EVENT_LIMIT)
            if overflow > 0:
                del bucket[:overflow]
    except Exception:
        pass


def _recent_events(bucket: list[dict], limit: int = 50) -> list[dict]:
    try:
        safe_limit = max(1, min(int(limit or 50), 200))
        return list(reversed(bucket[-safe_limit:]))
    except Exception:
        return []


def _record_ops_event(kind: str, status: str = "info", **fields) -> None:
    event = {
        "kind": str(kind or "event"),
        "status": str(status or "info"),
        "timestamp": utcnow().isoformat() + "Z",
        **redact_mapping(fields),
    }
    _push_limited_event(_ops_events, _ops_events_lock, event)


def _record_security_event(
    kind: str,
    severity: str = "medium",
    request=None,
    **fields,
) -> None:
    event = {
        "kind": str(kind or "security_event"),
        "severity": str(severity or "medium"),
        "timestamp": utcnow().isoformat() + "Z",
        "path": getattr(getattr(request, "url", None), "path", fields.pop("path", "")),
        "client_ip": _safe_request_ip(request),
        **redact_mapping(fields),
    }
    _push_limited_event(_security_events, _security_events_lock, event)


def _record_ai_usage(
    endpoint: str,
    user_id: int | None = None,
    input_chars: int = 0,
    output_chars: int = 0,
    used_ai: bool | None = None,
    billable_units: int = 0,
) -> None:
    total_chars = max(0, int(input_chars or 0)) + max(0, int(output_chars or 0))
    tokens = max(0, int((total_chars + 3) / 4))
    per_1k = float(os.getenv("AI_COST_PER_1K_TOKENS_USD", "0.002") or "0.002")
    event = {
        "endpoint": str(endpoint or "unknown"),
        "user_id": user_id,
        "used_ai": bool(used_ai) if used_ai is not None else None,
        "billable_units": int(billable_units or 0),
        "input_chars": int(input_chars or 0),
        "output_chars": int(output_chars or 0),
        "estimated_tokens": tokens,
        "estimated_cost_usd": round((tokens / 1000.0) * per_1k, 6),
        "timestamp": utcnow().isoformat() + "Z",
    }
    _push_limited_event(_ai_usage_events, _ai_usage_events_lock, event)


def _safe_request_ip(request) -> str:
    try:
        return _extract_client_ip(request) or ""
    except Exception:
        try:
            return request.client.host if request and request.client else ""
        except Exception:
            return ""


def _extract_client_ip(request) -> str | None:
    """Best-effort client IP extraction, aware of proxies."""
    if request is None:
        return None
    trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "0") or "0")
    xff = getattr(request, "headers", {}).get("X-Forwarded-For") if hasattr(request, "headers") else None
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        if trusted_proxy_count > 0 and xff and _is_trusted_proxy_peer(client.host):
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                index = max(0, len(parts) - trusted_proxy_count)
                return parts[index]
        return client.host
    return None


def _is_trusted_proxy_peer(peer_host: str | None) -> bool:
    if not peer_host:
        return False
    try:
        peer_ip = ipaddress.ip_address(str(peer_host))
    except ValueError:
        return False

    raw = os.getenv("TRUSTED_PROXY_IPS", "").strip()
    if not raw:
        return peer_ip.is_loopback

    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            if "/" in value:
                if peer_ip in ipaddress.ip_network(value, strict=False):
                    return True
            elif peer_ip == ipaddress.ip_address(value):
                return True
        except ValueError:
            continue
    return False


# ── Runtime: Request sampling (1%) ───────────────────────────────────────
_SAMPLE_RATE = float(os.getenv("REQUEST_SAMPLE_RATE", "0.01"))
_sample_logger = logging.getLogger("app.sample")

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


# ── Ops: Blue/Green readiness gate ───────────────────────────────────────
_app_ready = False
_app_ready_lock = _threading.Lock()


def _set_app_ready(val: bool = True) -> None:
    global _app_ready
    with _app_ready_lock:
        _app_ready = val


def _is_app_ready() -> bool:
    with _app_ready_lock:
        return _app_ready


# ── CPU / Memory helpers ─────────────────────────────────────────────────
_CPU_USAGE_LIMIT = float(os.getenv("CPU_USAGE_LIMIT", "90"))
_cpu_last_check: float = 0.0
_cpu_last_value: float = 0.0
_CPU_CHECK_INTERVAL = 5.0


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


_MEMORY_RSS_LIMIT_MB = int(os.getenv("MEMORY_RSS_LIMIT_MB", "1024"))
_MEMORY_RSS_LIMIT_BYTES = _MEMORY_RSS_LIMIT_MB * 1024 * 1024


def _get_rss_bytes() -> int:
    """Return process RSS in bytes (best-effort, 0 on failure)."""
    try:
        import psutil

        return psutil.Process().memory_info().rss
    except Exception:
        pass
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


# ── Disk safety ──────────────────────────────────────────────────────────
_DISK_WARN_PERCENT = float(os.getenv("DISK_WARN_PERCENT", "80"))
_DISK_BLOCK_PERCENT = float(os.getenv("DISK_BLOCK_PERCENT", "95"))
_disk_logger = logging.getLogger("app.disk")


def _get_disk_usage() -> float:
    """Return disk usage percentage for the app partition."""
    if os.getenv("ENV") == "test" or os.getenv("TESTING") == "1":
        return 0.0
    import shutil

    total, used, free = shutil.disk_usage(os.path.dirname(os.path.dirname(__file__)) or "/")
    return round(used / total * 100, 1) if total > 0 else 0.0


def _check_disk_safety() -> None:
    """Warn >80%, block >95% disk usage. Raises HTTPException(503)."""
    from fastapi import HTTPException

    from shared import _alert

    try:
        pct = _get_disk_usage()
    except Exception:
        return
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


# ── Background metrics collector ─────────────────────────────────────────
_METRICS_COLLECT_INTERVAL = 15


def _metrics_collector_loop():
    """Background thread: update process, worker, breaker, flag gauges."""
    from shared import _cb_lock, _circuit_breaker_state

    while True:
        time.sleep(_METRICS_COLLECT_INTERVAL)
        try:
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

            counts = _gc.get_stats() if hasattr(_gc, "get_stats") else []
            for i, gen in enumerate(counts):
                GC_COLLECTIONS_TOTAL.labels(generation=str(i)).set(gen.get("collections", 0))

            cpu = _get_cpu_percent()
            PROCESS_CPU_PERCENT.set(cpu)

            try:
                from services.model_worker import _proc as _mw_proc
                from services.model_worker import _request_queue as _mw_q

                WORKER_ACTIVE_TASKS.set(1 if (_mw_proc and _mw_proc.is_alive()) else 0)
                WORKER_QUEUE_SIZE.set(_mw_q.qsize() if _mw_q else 0)
            except Exception:
                pass

            now = time.time()
            with _cb_lock:
                for svc, st in _circuit_breaker_state.items():
                    BREAKER_OPEN.labels(service=svc).set(1 if st.get("open_until", 0) > now else 0)

            with _live_flags_lock:
                for k, v in _live_flags.items():
                    FLAG_ENABLED.labels(flag=k).set(1 if v else 0)

            PANIC_ACTIVE.set(1 if _is_panic() else 0)

        except Exception:
            pass


# ── Guard cleanup loop ───────────────────────────────────────────────────
_GUARD_CLEANUP_INTERVAL = 300
_GUARD_SAFE_MODE_THRESHOLD = int(os.getenv("GUARD_SAFE_MODE_THRESHOLD", "50"))
_GUARD_SAFE_MODE_WINDOW = float(os.getenv("GUARD_SAFE_MODE_WINDOW", "60"))
_guard_logger = logging.getLogger("app.guard")


def _check_auto_safe_mode_from_guards(now: float) -> None:
    """If too many guard rejections in window, trigger safe mode."""
    with _GUARD_REJECT_LOCK:
        cutoff = now - _GUARD_SAFE_MODE_WINDOW
        while _GUARD_REJECT_TIMESTAMPS and _GUARD_REJECT_TIMESTAMPS[0] < cutoff:
            _GUARD_REJECT_TIMESTAMPS.pop(0)
        count = len(_GUARD_REJECT_TIMESTAMPS)
    if count >= _GUARD_SAFE_MODE_THRESHOLD:
        try:
            import services.cv_builder_service as _cbs
            from services.cv_builder_service import _safe_mode_lock

            with _safe_mode_lock:
                if not _cbs._safe_mode_auto:
                    _cbs._safe_mode_auto = True
                    _guard_logger.warning(
                        "guard:auto_safe_mode_triggered rejections=%d window=%.0fs",
                        count,
                        _GUARD_SAFE_MODE_WINDOW,
                    )
                    try:
                        GUARD_SAFE_MODE_TRIGGERS.inc()
                    except Exception:
                        pass
        except Exception:
            pass


def start_background_threads():
    """Start the metrics collector and guard cleanup background threads."""
    _threading.Thread(target=_metrics_collector_loop, daemon=True, name="metrics-collector").start()
    # guard cleanup is started via start_guard_cleanup_thread()


def start_guard_cleanup_thread(
    prune_rate_bucket,
    ip_global_lock,
    ip_global_counts,
    user_global_lock,
    user_global_counts,
    user_embed_lock,
    user_embed_counts,
    search_lock,
    search_counts,
    dedup_lock,
    dedup_cache,
    prune_abuse_dicts,
):
    """Start the guard cleanup background thread with references to rate dicts."""

    def _guard_cleanup_loop():
        while True:
            time.sleep(_GUARD_CLEANUP_INTERVAL)
            now = time.time()
            cutoff = now - 120
            for lock, bucket in [
                (ip_global_lock, ip_global_counts),
                (user_global_lock, user_global_counts),
                (user_embed_lock, user_embed_counts),
                (search_lock, search_counts),
            ]:
                prune_rate_bucket(bucket, lock, cutoff)
            with dedup_lock:
                stale = [k for k, v in dedup_cache.items() if v < cutoff]
                for k in stale:
                    del dedup_cache[k]
            prune_abuse_dicts(now)
            _check_auto_safe_mode_from_guards(now)

    _threading.Thread(target=_guard_cleanup_loop, daemon=True, name="guard-cleanup").start()
