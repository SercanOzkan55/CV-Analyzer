import pytest


def test_sensitive_data_exposure(client):
    """Response should never contain sensitive tokens."""
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_description": "bar"})
    sensitive_keywords = ["password", "secret", "apikey"]
    for kw in sensitive_keywords:
        assert kw not in resp.text.lower()
