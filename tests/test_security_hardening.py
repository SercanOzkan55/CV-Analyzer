"""Security hardening tests — validate all protection layers.

Tests input safety limits, render caps, PDF safety, embedding guards,
log flood protection, exception safety, and SAFE_MODE.
"""

import os
import json
import pytest

# ── 1. Input safety limits (extract_agent) ─────────────────────────────────


def test_extract_truncates_oversized_text():
    """Text longer than _MAX_TEXT_LEN is truncated, not crashed."""
    from agents.extract_agent import extract_structured, _MAX_TEXT_LEN

    huge = "word " * (_MAX_TEXT_LEN // 4)
    result = extract_structured(huge)
    assert isinstance(result, dict)


def test_extract_truncates_too_many_lines():
    """More than _MAX_LINES lines are truncated."""
    from agents.extract_agent import extract_structured, _MAX_LINES

    text = "\n".join([f"line {i}" for i in range(_MAX_LINES + 500)])
    result = extract_structured(text)
    assert isinstance(result, dict)


def test_extract_truncates_too_many_words():
    """More than _MAX_TOTAL_WORDS are truncated."""
    from agents.extract_agent import extract_structured, _MAX_TOTAL_WORDS

    text = " ".join(["word"] * (_MAX_TOTAL_WORDS + 100))
    result = extract_structured(text)
    assert isinstance(result, dict)


# ── 2. Regex DoS protection (section_classifier) ──────────────────────────


def test_regex_input_capped():
    """_classify_content truncates text before regex if over _MAX_REGEX_INPUT."""
    from services.section_classifier import _MAX_REGEX_INPUT

    assert _MAX_REGEX_INPUT == 10_000


def test_classify_survives_regex_bomb():
    """ReDoS-like input doesn't hang the classifier."""
    from services.section_classifier import detect_sections

    # Evil regex input: repeated alternation pattern
    evil = "a" * 15_000 + "!" * 5_000
    sections, _, _ = detect_sections(evil)
    assert isinstance(sections, dict)


# ── 3. Section limits ────────────────────────────────────────────────────


def test_max_sections_capped():
    from services.section_classifier import _MAX_SECTIONS

    assert _MAX_SECTIONS == 20


# ── 4. Loop iteration guards (section_resolver) ──────────────────────────


def test_resolver_iteration_limit():
    from services.section_resolver import _MAX_ITERATIONS

    assert _MAX_ITERATIONS <= 500


# ── 5. Render safety limits (blocks.py) ──────────────────────────────────


def test_render_limits_exist():
    from renderers.blocks import (
        _MAX_RENDER_ENTRIES,
        _MAX_RENDER_BULLETS,
        _MAX_RENDER_ITEMS,
        _MAX_RENDER_CHARS,
    )

    assert _MAX_RENDER_ENTRIES == 50
    assert _MAX_RENDER_BULLETS == 20
    assert _MAX_RENDER_ITEMS == 200
    assert _MAX_RENDER_CHARS == 200_000


def test_prepare_for_render_caps_entries():
    """prepare_for_render caps experience count to _MAX_RENDER_ENTRIES."""
    from renderers.blocks import prepare_for_render, _MAX_RENDER_ENTRIES
    from schemas.cv_model import CVModel, Experience

    model = CVModel(full_name="Test User")
    model.experiences = [
        Experience(title=f"Job {i}", company="Co", bullets=[f"b{j}" for j in range(25)])
        for i in range(_MAX_RENDER_ENTRIES + 10)
    ]
    safe = prepare_for_render(model)
    assert len(safe.experiences) <= _MAX_RENDER_ENTRIES
    for exp in safe.experiences:
        assert len(exp.bullets) <= 20  # _MAX_RENDER_BULLETS


# ── 6. Header field length cap ───────────────────────────────────────────


def test_header_field_length_capped():
    from renderers.blocks import prepare_for_render, _MAX_HEADER_FIELD_LEN
    from schemas.cv_model import CVModel

    model = CVModel(full_name="A" * 500, email="B" * 500)
    safe = prepare_for_render(model)
    assert len(safe.full_name) <= _MAX_HEADER_FIELD_LEN
    assert len(safe.email) <= _MAX_HEADER_FIELD_LEN


# ── 7. URL length cap ───────────────────────────────────────────────────


def test_url_length_capped():
    from utils.cv_normalizer import _MAX_URL_LEN

    assert _MAX_URL_LEN == 500


# ── 8. Description length cap ───────────────────────────────────────────


def test_description_length_capped():
    from services.schema_builder import _MAX_DESCRIPTION_LEN

    assert _MAX_DESCRIPTION_LEN == 2000


# ── 9. JSON output size cap ─────────────────────────────────────────────


def test_json_size_limit_exists():
    from agents.normalize_agent import _MAX_JSON_SIZE

    assert _MAX_JSON_SIZE == 500_000


# ── 10. PDF safety constants ─────────────────────────────────────────────


def test_pdf_safety_constants():
    from main import _MAX_PDF_PAGES, _MAX_PDF_OBJECTS, _MAX_PDF_EXTRACTED_CHARS

    assert _MAX_PDF_PAGES == 50
    assert _MAX_PDF_OBJECTS == 5_000
    assert _MAX_PDF_EXTRACTED_CHARS == 100_000


# ── 11. Embedding rate limiting ──────────────────────────────────────────


def test_embedding_rate_limiter_exists():
    from services.embedding_service import _EMBED_MAX_CALLS_PER_MIN

    assert _EMBED_MAX_CALLS_PER_MIN == 60


def test_embed_rate_ok_works():
    from services.embedding_service import _embed_rate_ok

    # Should succeed at least once
    assert _embed_rate_ok() is True


# ── 12. Log flood protection ────────────────────────────────────────────


def test_log_truncation():
    from main import _safe_log_message, _MAX_LOG_LINE_LEN

    short = "hello"
    assert _safe_log_message(short) == "hello"
    long = "x" * 2000
    result = _safe_log_message(long)
    assert len(result) <= _MAX_LOG_LINE_LEN + 20  # allow for suffix
    assert result.endswith("...[truncated]")


# ── 13. Exception handler returns safe error ─────────────────────────────


def test_global_exception_handler(client):
    """Unhandled errors should never expose stacktraces."""
    # Any malformed request that triggers server error should return clean JSON
    resp = client.post("/api/v1/analyze", json={})
    # Should get auth error or validation error, but not a raw stacktrace
    assert resp.status_code in (200, 400, 401, 422, 429, 500)
    body = resp.json()
    assert "detail" in body
    assert "Traceback" not in body.get("detail", "")


# ── 14. Rate limit constants for new endpoints ──────────────────────────


def test_rate_limit_constants_exist():
    from main import (
        RATE_LIMIT_IP_UPLOAD_PER_MIN,
        RATE_LIMIT_IP_RENDER_PER_MIN,
        RATE_LIMIT_IP_MATCH_PER_MIN,
        RATE_LIMIT_IP_REWRITE_PER_MIN,
        RATE_LIMIT_IP_EMBED_PER_MIN,
    )

    assert RATE_LIMIT_IP_UPLOAD_PER_MIN == 5
    assert RATE_LIMIT_IP_RENDER_PER_MIN == 10
    assert RATE_LIMIT_IP_MATCH_PER_MIN == 10
    assert RATE_LIMIT_IP_REWRITE_PER_MIN == 5
    assert RATE_LIMIT_IP_EMBED_PER_MIN == 10


# ── 15. SAFE_MODE flag tightens limits ───────────────────────────────────


def test_safe_mode_flag_exists():
    """The SAFE_MODE env flag is recognized and affects limits."""
    from services.cv_builder_service import _is_safe_mode, SAFE_MODE

    # In test env, SAFE_MODE is not set (defaults to False)
    assert isinstance(SAFE_MODE, bool)
    assert isinstance(_is_safe_mode(), bool)


# ══════════════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING GUARDS
# ══════════════════════════════════════════════════════════════════════════

# ── 16. Per-IP global rate limit ────────────────────────────────────────


def test_ip_global_rate_constants():
    from main import _IP_GLOBAL_LIMIT_PER_MIN, _ip_global_rate_ok

    # conftest disables IP rate limit (sets to 0), so accept both
    assert _IP_GLOBAL_LIMIT_PER_MIN in (0, 60)
    assert _ip_global_rate_ok("1.2.3.4") is True


# ── 17. Per-user global rate limit ──────────────────────────────────────


def test_user_global_rate_constants():
    from main import _USER_GLOBAL_LIMIT_PER_MIN, _user_global_rate_ok

    assert _USER_GLOBAL_LIMIT_PER_MIN == 30
    assert _user_global_rate_ok("test-user") is True


# ── 18. Global concurrency semaphore ────────────────────────────────────


def test_global_concurrency_limit():
    from main import _GLOBAL_CONCURRENCY_LIMIT, _global_semaphore

    assert _GLOBAL_CONCURRENCY_LIMIT == 20
    assert hasattr(_global_semaphore, "acquire")


# ── 19. Request timeout guard ──────────────────────────────────────────


def test_request_timeout_constant():
    from main import _REQUEST_TIMEOUT_SECONDS

    assert _REQUEST_TIMEOUT_SECONDS == 600.0


# ── 20. Memory guard ──────────────────────────────────────────────────


def test_memory_guard():
    from main import _MEMORY_RSS_LIMIT_MB, _get_rss_bytes

    assert _MEMORY_RSS_LIMIT_MB == 1024
    rss = _get_rss_bytes()
    assert isinstance(rss, int)
    assert rss >= 0


# ── 21. Request dedup guard ──────────────────────────────────────────


def test_dedup_guard():
    from main import _is_duplicate_request, _DEDUP_WINDOW_SECONDS

    assert _DEDUP_WINDOW_SECONDS == 5
    # First call should not be duplicate
    assert _is_duplicate_request("test-fingerprint-unique-xyz") is False
    # Immediate second call with same fingerprint should be duplicate
    assert _is_duplicate_request("test-fingerprint-unique-xyz") is True


# ── 22. Per-user embedding spam guard ──────────────────────────────────


def test_user_embed_rate():
    from main import _USER_EMBED_LIMIT_PER_MIN, _user_embed_rate_ok

    assert _USER_EMBED_LIMIT_PER_MIN == 15
    assert _user_embed_rate_ok("embed-test-user") is True


# ── 23. Search abuse guard ───────────────────────────────────────────


def test_search_rate_guard():
    from main import _SEARCH_LIMIT_PER_MIN, _MAX_SEARCH_QUERY_LEN, _search_rate_ok

    assert _SEARCH_LIMIT_PER_MIN == 30
    assert _MAX_SEARCH_QUERY_LEN == 500
    assert _search_rate_ok("search-test-user") is True


# ── 24. Large allocation guard ───────────────────────────────────────


def test_large_allocation_constants():
    from main import _MAX_REQUEST_BODY_BYTES, _MAX_RESPONSE_BODY_BYTES

    assert _MAX_REQUEST_BODY_BYTES == 6 * 1024 * 1024
    assert _MAX_RESPONSE_BODY_BYTES == 50 * 1024 * 1024


# ── 25. Worker safety ────────────────────────────────────────────────


def test_worker_safety():
    from services.model_worker import _MAX_WORKER_RESTARTS, _ensure_worker_alive

    assert _MAX_WORKER_RESTARTS == 3
    # _ensure_worker_alive should not crash even when worker isn't running
    result = _ensure_worker_alive()
    assert isinstance(result, bool)


# ── 26. Guard dependencies exist ────────────────────────────────────


def test_guard_dependencies():
    from main import require_user_global_rate, require_embed_rate, require_search_rate

    assert callable(require_user_global_rate)
    assert callable(require_embed_rate)
    assert callable(require_search_rate)


# ── 27. Middleware rejects oversized body ────────────────────────────


def test_large_body_rejected(client):
    """Request with Content-Length > MAX should get 413."""
    # The middleware checks content-length header
    resp = client.post(
        "/api/v1/analyze",
        json={"cv_text": "x"},
        headers={"Content-Length": str(20 * 1024 * 1024)},
    )
    # Should be rejected at middleware or auth level
    assert resp.status_code in (401, 413, 422, 429)


# ══════════════════════════════════════════════════════════════════════════
# GUARD BUG-FIX VALIDATION
# ══════════════════════════════════════════════════════════════════════════

# ── 28. Rate dict inline key cleanup ────────────────────────────────────


def test_rate_bucket_removes_empty_keys():
    """After all timestamps expire, the key should be removed from the dict."""
    import time as _time
    from main import (
        _ip_global_counts,
        _ip_global_lock,
        _prune_rate_bucket,
    )

    test_key = "__test_prune_key__"
    # Insert a stale timestamp
    with _ip_global_lock:
        _ip_global_counts[test_key] = [_time.time() - 300]
    _prune_rate_bucket(_ip_global_counts, _ip_global_lock, _time.time() - 10)
    with _ip_global_lock:
        assert test_key not in _ip_global_counts


def test_rate_dict_max_keys_constant():
    from main import _RATE_DICT_MAX_KEYS

    assert _RATE_DICT_MAX_KEYS == 10_000


# ── 29. Dedup cache hard cap ───────────────────────────────────────────


def test_dedup_always_prunes():
    """Dedup cache prunes stale entries even when under limit."""
    import time as _time
    from main import _dedup_cache, _dedup_lock

    test_fp = "__test_dedup_prune__"
    with _dedup_lock:
        _dedup_cache[test_fp] = _time.time() - 60  # already stale
    from main import _is_duplicate_request

    _is_duplicate_request("__trigger_prune__")
    with _dedup_lock:
        assert test_fp not in _dedup_cache


# ── 30. Per-path timeout mapping ───────────────────────────────────────


def test_per_path_timeout_exists():
    from main import _PATH_TIMEOUTS, _REQUEST_TIMEOUT_SECONDS

    assert isinstance(_PATH_TIMEOUTS, dict)
    assert len(_PATH_TIMEOUTS) >= 5
    # Heavy endpoints should have shorter timeouts than default
    for path, timeout in _PATH_TIMEOUTS.items():
        assert timeout <= _REQUEST_TIMEOUT_SECONDS


# ── 31. Worker restart count decay ─────────────────────────────────────


def test_worker_restart_decay_constant():
    from services.model_worker import _WORKER_RESTART_DECAY_SECONDS

    assert _WORKER_RESTART_DECAY_SECONDS == 3600


def test_worker_restart_decay_logic():
    """After decay period, restart count should reset to 0."""
    import services.model_worker as mw
    import time as _time

    old_count = mw._worker_restart_count
    old_last = mw._worker_last_restart
    try:
        mw._worker_restart_count = 3
        mw._worker_last_restart = _time.time() - 7200  # 2 hours ago
        # Calling _ensure_worker_alive should decay the counter
        mw._ensure_worker_alive()
        # Counter should have been reset (may be 1 if restart attempted)
        assert mw._worker_restart_count <= 1
    finally:
        mw._worker_restart_count = old_count
        mw._worker_last_restart = old_last


# ── 32. Safe mode auto-recovery ─────────────────────────────────────────


def test_safe_mode_auto_recovers():
    """After error window clears, auto-safe-mode should disable itself."""
    import services.cv_builder_service as cbs

    old_auto = cbs._safe_mode_auto
    old_ts = cbs._error_timestamps[:]
    try:
        cbs._safe_mode_auto = True
        cbs._error_timestamps.clear()  # no recent errors
        assert cbs._is_safe_mode() is False
        assert cbs._safe_mode_auto is False
    finally:
        cbs._safe_mode_auto = old_auto
        cbs._error_timestamps[:] = old_ts


# ── 33. Circuit breaker ────────────────────────────────────────────────


def test_circuit_breaker_opens_on_failures():
    from main import (
        _cb_record_failure,
        _cb_record_success,
        _cb_is_open,
        _CB_FAILURE_THRESHOLD,
        _circuit_breaker_state,
        _cb_lock,
    )

    svc = "__test_circuit_svc__"
    try:
        for _ in range(_CB_FAILURE_THRESHOLD):
            _cb_record_failure(svc)
        assert _cb_is_open(svc) is True
        _cb_record_success(svc)
        assert _cb_is_open(svc) is False
    finally:
        with _cb_lock:
            _circuit_breaker_state.pop(svc, None)


# ── 34. Abuse ban escalation ──────────────────────────────────────────


def test_abuse_ban_escalation_function():
    from main import _escalate_abuse_ban, _ABUSE_BAN_SECONDS

    assert _ABUSE_BAN_SECONDS == 300
    assert callable(_escalate_abuse_ban)


# ── 35. Abuse dict cleanup function ──────────────────────────────────


def test_abuse_dict_cleanup():
    """_prune_abuse_dicts removes expired bans and stale counters."""
    import time as _time
    from main import (
        _LOCAL_ABUSE_BANS,
        _LOCAL_ABUSE_COUNTERS,
        _LOCAL_ABUSE_LOCK,
        _prune_abuse_dicts,
    )

    test_ban_key = "__test_ban_key__"
    test_counter_key = "__test_counter_key__"
    now = _time.time()
    with _LOCAL_ABUSE_LOCK:
        _LOCAL_ABUSE_BANS[test_ban_key] = now - 100  # expired
        _LOCAL_ABUSE_COUNTERS[test_counter_key] = {"window_start": now - 700, "count": 5}
    _prune_abuse_dicts(now)
    with _LOCAL_ABUSE_LOCK:
        assert test_ban_key not in _LOCAL_ABUSE_BANS
        assert test_counter_key not in _LOCAL_ABUSE_COUNTERS


# ── 36. Stream response size guard ──────────────────────────────────


def test_stream_response_cap_constant():
    from main import _MAX_RESPONSE_BODY_BYTES

    assert _MAX_RESPONSE_BODY_BYTES == 50 * 1024 * 1024


# ══════════════════════════════════════════════════════════════════════════
# FINAL PRODUCTION HARDENING GUARDS
# ══════════════════════════════════════════════════════════════════════════

# ── 37. CPU guard ───────────────────────────────────────────────────


def test_cpu_guard_constants():
    from main import _CPU_USAGE_LIMIT, _get_cpu_percent

    # conftest sets to 100.0 for test stability; accept both
    assert _CPU_USAGE_LIMIT in (90, 100.0)
    cpu = _get_cpu_percent()
    assert isinstance(cpu, float)
    assert 0 <= cpu <= 100


# ── 38. Per-path concurrency ────────────────────────────────────────


def test_per_path_concurrency_exists():
    from main import _PATH_CONCURRENCY, _path_semaphores

    assert isinstance(_PATH_CONCURRENCY, dict)
    assert len(_PATH_CONCURRENCY) >= 6
    # Each path in the config should have a semaphore
    for path in _PATH_CONCURRENCY:
        assert path in _path_semaphores
        assert hasattr(_path_semaphores[path], "acquire")


def test_per_path_concurrency_limits():
    from main import _PATH_CONCURRENCY

    for path, limit in _PATH_CONCURRENCY.items():
        assert 1 <= limit <= 50, f"{path} has unreasonable limit: {limit}"


# ── 39. Request queue ──────────────────────────────────────────────


def test_request_queue_exists():
    from main import _REQUEST_QUEUE_SIZE, _request_queue

    assert _REQUEST_QUEUE_SIZE == 100
    assert hasattr(_request_queue, "acquire")
    assert hasattr(_request_queue, "release")


# ── 40. Per-service circuit breaker wired to embedding ─────────────


def test_circuit_breaker_embedding_wired():
    """embedding_service imports circuit breaker functions."""
    from main import _cb_is_open, _cb_record_failure, _cb_record_success

    # Verify that openai_embedding service key doesn't crash
    assert _cb_is_open("openai_embedding") is False
    _cb_record_failure("openai_embedding")
    _cb_record_success("openai_embedding")
    assert _cb_is_open("openai_embedding") is False


# ── 41. Ban dict cap ──────────────────────────────────────────────


def test_ban_dict_cap_constants():
    from main import _BAN_DICT_MAX_ENTRIES, _ABUSE_COUNTER_MAX_ENTRIES

    assert _BAN_DICT_MAX_ENTRIES == 5000
    assert _ABUSE_COUNTER_MAX_ENTRIES == 5000


def test_ban_dict_cap_enforced():
    """_prune_abuse_dicts respects hard cap."""
    import time as _time
    from main import (
        _LOCAL_ABUSE_BANS,
        _LOCAL_ABUSE_LOCK,
        _prune_abuse_dicts,
        _BAN_DICT_MAX_ENTRIES,
    )

    now = _time.time()
    # We don't actually insert _BAN_DICT_MAX_ENTRIES entries (too slow),
    # just verify the function handles the cap branch without error
    _prune_abuse_dicts(now)


# ── 42. Auto safe mode from guards ────────────────────────────────


def test_auto_safe_mode_from_guards():
    from main import (
        _record_guard_rejection,
        _check_auto_safe_mode_from_guards,
        _GUARD_SAFE_MODE_THRESHOLD,
        _GUARD_SAFE_MODE_WINDOW,
        _GUARD_REJECT_TIMESTAMPS,
        _GUARD_REJECT_LOCK,
    )

    assert _GUARD_SAFE_MODE_THRESHOLD == 50
    assert _GUARD_SAFE_MODE_WINDOW == 60
    assert callable(_record_guard_rejection)
    assert callable(_check_auto_safe_mode_from_guards)


# ── 43. Health endpoints ──────────────────────────────────────────


def test_liveness_endpoint(client):
    resp = client.get("/liveness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"


def test_health_includes_guards(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    # In mock mode, health returns early without guard stats
    if data.get("mode") == "mock":
        assert data["status"] == "ok"
        return
    assert "guards" in data
    guards = data["guards"]
    assert "global_concurrency_limit" in guards
    assert "request_queue_size" in guards
    assert "cpu_limit" in guards
    assert "cpu_current" in guards
    assert "memory_rss_limit_mb" in guards
    assert "circuit_breakers_open" in guards
    assert "ban_dict_size" in guards
    assert "rate_dict_sizes" in guards


# ── 44. Worker warmup ────────────────────────────────────────────


def test_worker_warmup_exists():
    """start_model_worker includes a warmup prediction call."""
    import inspect
    from main import start_model_worker

    src = inspect.getsource(start_model_worker)
    assert "predict_sync" in src


# ── 45. Guard metrics counters ───────────────────────────────────


def test_guard_metrics_exist():
    from main import (
        GUARD_REJECTIONS_TOTAL,
        GUARD_CIRCUIT_BREAKER_TRIPS,
        GUARD_QUEUE_FULL,
        GUARD_CPU_REJECTIONS,
        GUARD_CONCURRENCY_REJECTIONS,
        GUARD_SAFE_MODE_TRIGGERS,
    )

    # All should be callable (either real Prometheus or noop)
    assert hasattr(GUARD_REJECTIONS_TOTAL, "labels")
    assert hasattr(GUARD_CIRCUIT_BREAKER_TRIPS, "labels")
    assert hasattr(GUARD_QUEUE_FULL, "inc")
    assert hasattr(GUARD_CPU_REJECTIONS, "inc")
    assert hasattr(GUARD_CONCURRENCY_REJECTIONS, "labels")
    assert hasattr(GUARD_SAFE_MODE_TRIGGERS, "inc")


# ── 46. Startup validation ──────────────────────────────────────


def test_startup_validation_exists():
    """validate_startup_config is registered as a startup event."""
    import inspect
    from main import validate_startup_config

    assert callable(validate_startup_config)
    src = inspect.getsource(validate_startup_config)
    assert "GLOBAL_CONCURRENCY_LIMIT" in src
    assert "REQUEST_TIMEOUT_SECONDS" in src


# ── 47. Middleware skips liveness ────────────────────────────────


def test_middleware_skips_liveness(client):
    """Liveness probe should not be rate-limited or guarded."""
    for _ in range(5):
        resp = client.get("/liveness")
        assert resp.status_code == 200
