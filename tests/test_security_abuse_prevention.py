"""Abuse prevention tests (fingerprint + risk scoring + temporary ban)."""

import main as main_module


def _reset_abuse_state():
    try:
        main_module._LOCAL_ABUSE_COUNTERS.clear()
    except Exception:
        pass
    try:
        main_module._LOCAL_ABUSE_BANS.clear()
    except Exception:
        pass


def test_abuse_blocks_suspicious_request(monkeypatch, client, sample_texts):
    cv, job = sample_texts

    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "ABUSE_PROTECTION_ENABLED", True)
    monkeypatch.setattr(main_module, "ABUSE_SCORE_BLOCK_THRESHOLD", 30)
    monkeypatch.setattr(main_module, "ABUSE_BAN_SECONDS", 60)
    _reset_abuse_state()

    resp = client.post(
        "/api/v1/analyze",
        json={"cv_text": cv, "job_description": job},
        headers={"User-Agent": "security-scanner/1.0"},
    )
    assert resp.status_code == 429
    assert "abuse protection" in resp.json().get("detail", "").lower()


def test_abuse_temporary_ban_applies_followup_request(monkeypatch, client, sample_texts):
    cv, job = sample_texts

    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "ABUSE_PROTECTION_ENABLED", True)
    monkeypatch.setattr(main_module, "ABUSE_SCORE_BLOCK_THRESHOLD", 30)
    monkeypatch.setattr(main_module, "ABUSE_BAN_SECONDS", 60)
    _reset_abuse_state()

    first = client.post(
        "/api/v1/analyze",
        json={"cv_text": cv, "job_description": job},
        headers={"User-Agent": "fuzzer-bot/2.0"},
    )
    assert first.status_code == 429

    # Second request uses a cleaner UA but same client IP should still be banned.
    second = client.post(
        "/api/v1/analyze",
        json={"cv_text": cv, "job_description": job},
        headers={"User-Agent": "Mozilla/5.0"},
    )
    assert second.status_code == 429
