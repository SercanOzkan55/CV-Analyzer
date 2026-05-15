"""Centralized Prometheus metrics definitions.

All metric objects and their helper wrappers live here so ``main.py`` only
needs a single import line for the full observability surface.
"""
from __future__ import annotations

import time

try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
except Exception:
    Counter = None
    Gauge = None
    Histogram = None
    REGISTRY = None


# ── Noop fallback ─────────────────────────────────────────────────────────

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


# ── Factory helpers ───────────────────────────────────────────────────────

def _get_or_create_counter(name: str, description: str, labelnames=()):
    if not Counter:
        return _NoopMetric()
    try:
        return Counter(name, description, labelnames=labelnames)
    except ValueError:
        if REGISTRY is not None:
            existing = REGISTRY._names_to_collectors.get(name)
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


# ── Analysis metrics ──────────────────────────────────────────────────────

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

# ── Process metrics ───────────────────────────────────────────────────────

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

# ── Worker metrics ────────────────────────────────────────────────────────

WORKER_ACTIVE_TASKS = _get_or_create_gauge(
    "cv_worker_active_tasks", "Active worker tasks",
)
WORKER_QUEUE_SIZE = _get_or_create_gauge(
    "cv_worker_queue_size", "Worker task queue size",
)

# ── Circuit breaker gauge ─────────────────────────────────────────────────

BREAKER_OPEN = _get_or_create_gauge(
    "cv_circuit_breaker_open", "Circuit breaker state (1=open, 0=closed)",
    labelnames=("service",),
)

# ── Feature flag gauge ────────────────────────────────────────────────────

FLAG_ENABLED = _get_or_create_gauge(
    "cv_feature_flag_enabled", "Feature flag state (1=enabled, 0=disabled)",
    labelnames=("flag",),
)

# ── Panic metrics ─────────────────────────────────────────────────────────

PANIC_TRIGGERS_TOTAL = _get_or_create_counter(
    "cv_panic_triggers_total", "Times panic mode was triggered",
)
PANIC_ACTIVE = _get_or_create_gauge(
    "cv_panic_active", "Panic mode active (1=yes, 0=no)",
)

# ── Admin action counter ──────────────────────────────────────────────────

ADMIN_ACTIONS_TOTAL = _get_or_create_counter(
    "cv_admin_actions_total", "Admin control-plane actions",
    labelnames=("action",),
)

# ── SRE metrics ───────────────────────────────────────────────────────────

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

# ── Dependency latency ────────────────────────────────────────────────────

DEP_LATENCY = _get_or_create_histogram(
    "cv_dependency_latency_seconds",
    "Latency of dependency calls (db, redis, s3, worker)",
    labelnames=("dependency",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ── Guard-level metrics ──────────────────────────────────────────────────

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


# ── Metric helper functions ───────────────────────────────────────────────

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


def _observe_dep(dep: str, start: float) -> None:
    """Record dependency call latency."""
    try:
        DEP_LATENCY.labels(dependency=dep).observe(time.time() - start)
    except Exception:
        pass


# ── Guard rejection tracking (used by auto-safe-mode) ─────────────────────
# The actual tracking list and check function are here to avoid circular deps.
import threading as _threading

_GUARD_REJECT_TIMESTAMPS: list[float] = []
_GUARD_REJECT_LOCK = _threading.Lock()


def _record_guard_rejection() -> None:
    """Track guard-level rejection timestamps for auto safe mode."""
    import os
    now = time.time()
    window = float(os.getenv("GUARD_SAFE_MODE_WINDOW", "60"))
    with _GUARD_REJECT_LOCK:
        _GUARD_REJECT_TIMESTAMPS.append(now)
        cutoff = now - window
        while _GUARD_REJECT_TIMESTAMPS and _GUARD_REJECT_TIMESTAMPS[0] < cutoff:
            _GUARD_REJECT_TIMESTAMPS.pop(0)
