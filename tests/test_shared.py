"""Tests for shared.py — metrics, alerts, circuit breaker."""
import time
import pytest
from shared import (
    _NoopMetric,
    _get_or_create_counter,
    _get_or_create_gauge,
    _cb_record_failure,
    _cb_record_success,
    _cb_is_open,
    _alert,
    S3_ERRORS_TOTAL,
    WORKER_RESTARTS_TOTAL,
    _circuit_breaker_state,
    _alert_cooldowns,
)


class TestNoopMetric:
    def test_inc(self):
        m = _NoopMetric()
        assert m.inc() is None

    def test_dec(self):
        assert _NoopMetric().dec() is None

    def test_set(self):
        assert _NoopMetric().set(42) is None

    def test_observe(self):
        assert _NoopMetric().observe(1.5) is None

    def test_labels(self):
        m = _NoopMetric()
        labeled = m.labels(service="test")
        assert labeled is m  # returns self


class TestMetricsCreation:
    def test_counter_created(self):
        c = _get_or_create_counter("test_shared_counter_xyz", "test counter")
        assert c is not None

    def test_gauge_created(self):
        g = _get_or_create_gauge("test_shared_gauge_xyz", "test gauge")
        assert g is not None

    def test_s3_errors_metric(self):
        # Should not raise
        S3_ERRORS_TOTAL.inc()

    def test_worker_restarts_metric(self):
        WORKER_RESTARTS_TOTAL.inc()


class TestCircuitBreaker:
    def setup_method(self):
        _circuit_breaker_state.clear()

    def test_initially_closed(self):
        assert _cb_is_open("test_svc") is False

    def test_opens_after_threshold(self):
        for _ in range(5):
            _cb_record_failure("test_svc")
        assert _cb_is_open("test_svc") is True

    def test_success_resets(self):
        for _ in range(3):
            _cb_record_failure("test_svc")
        _cb_record_success("test_svc")
        assert _cb_is_open("test_svc") is False

    def test_different_services_isolated(self):
        for _ in range(5):
            _cb_record_failure("svc_a")
        assert _cb_is_open("svc_a") is True
        assert _cb_is_open("svc_b") is False


class TestAlert:
    def setup_method(self):
        _alert_cooldowns.clear()

    def test_alert_does_not_raise(self):
        _alert("test_alert", "something happened", level="warning")

    def test_alert_cooldown(self):
        _alert("cooldown_test", "first")
        # Second call within cooldown should be silently suppressed
        _alert("cooldown_test", "second")
        # No crash = success
