import pytest


def test_replay_attack(client):
    """Repeated requests with same auth should not crash."""
    for i in range(5):
        resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_description": "bar"})
        assert resp.status_code in (200, 403, 429)
