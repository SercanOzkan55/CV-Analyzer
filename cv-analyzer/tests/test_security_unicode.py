import pytest


def test_unicode_payload(client):
    """Unicode input should not crash the endpoint."""
    payload = {"cv_text": "你好世界 🌍🚀", "job_description": "Привет мир"}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 422)
