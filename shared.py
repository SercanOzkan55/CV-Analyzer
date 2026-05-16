"""Shared infrastructure utilities used by both main.py and services.

Extracted to break circular imports: services that need metrics, alerts,
or the circuit breaker import from here instead of ``main``.
"""
from __future__ import annotations

import logging
import os
import threading
import time

# ── Prometheus metrics (optional) ─────────────────────────────────────────
try:
    from prometheus_client import Counter, Gauge, CollectorRegistry, REGISTRY
except ImportError:
    Counter = None  # type: ignore[assignment,misc]
    Gauge = None  # type: ignore[assignment,misc]
    REGISTRY = None


class _NoopMetric:
    """Drop-in that silently swallows Prometheus inc/dec/set/observe."""

    def labels(self, **kw):
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


# ── Prometheus counters used by services ──────────────────────────────────
S3_ERRORS_TOTAL = _get_or_create_counter(
    "cv_s3_errors_total_shared", "Total S3 operation errors (shared)",
)
WORKER_RESTARTS_TOTAL = _get_or_create_counter(
    "cv_worker_restarts_total_shared", "Total model worker auto-restarts (shared)",
)
GUARD_CIRCUIT_BREAKER_TRIPS = _get_or_create_counter(
    "cv_guard_circuit_breaker_trips_shared",
    "Circuit breaker trip events (shared)",
    labelnames=("service",),
)
BREAKER_OPEN = _get_or_create_gauge(
    "cv_breaker_open_shared",
    "Whether service circuit breaker is open (shared)",
    labelnames=("service",),
)


# ── Circuit breaker ──────────────────────────────────────────────────────
_CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
_CB_COOLDOWN_SECONDS = float(os.getenv("CB_COOLDOWN_SECONDS", "30"))
_circuit_breaker_state: dict[str, dict] = {}
_cb_lock = threading.Lock()


def _cb_record_failure(service: str) -> None:
    """Record a failure for *service*. Opens circuit if threshold exceeded."""
    now = time.time()
    opened = False
    with _cb_lock:
        state = _circuit_breaker_state.setdefault(
            service, {"failures": 0, "last_failure": 0, "open_until": 0},
        )
        state["failures"] += 1
        state["last_failure"] = now
        if state["failures"] >= _CB_FAILURE_THRESHOLD:
            state["open_until"] = now + _CB_COOLDOWN_SECONDS
            opened = True
            logging.getLogger("app.guard").warning(
                "circuit_breaker:open service=%s failures=%d cooldown=%.0fs",
                service, state["failures"], _CB_COOLDOWN_SECONDS,
            )
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
            _circuit_breaker_state[service] = {
                "failures": 0, "last_failure": 0, "open_until": 0,
            }
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
        if state["failures"] >= _CB_FAILURE_THRESHOLD:
            state["failures"] = _CB_FAILURE_THRESHOLD - 1
        return False


# ── Alerting ─────────────────────────────────────────────────────────────
_alert_logger = logging.getLogger("app.alert")
_alert_cooldowns: dict[str, float] = {}
_alert_lock = threading.Lock()
_ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))


def _alert(name: str, message: str, *, level: str = "critical") -> None:
    """Emit a rate-limited alert log."""
    now = time.time()
    with _alert_lock:
        last = _alert_cooldowns.get(name, 0.0)
        if now - last < _ALERT_COOLDOWN_SECONDS:
            return
        _alert_cooldowns[name] = now
    log_fn = getattr(_alert_logger, level, _alert_logger.critical)
    log_fn("ALERT:%s %s", name, message)
