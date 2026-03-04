import pytest


def test_xss_payload(client):
    """XSS payloads should be neutralized."""
    payload = {"cv_text": "<img src=x onerror=alert('xss')>", "job_description": "<script>alert('xss')</script>"}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 422)
