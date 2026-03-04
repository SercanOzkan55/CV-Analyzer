import pytest
from fastapi.testclient import TestClient
from main import app


def test_referrer_policy_header():
    """Referrer-Policy should be set on all responses."""
    client = TestClient(app)
    resp = client.get("/api/v1/analyze")
    rp = resp.headers.get("referrer-policy") or resp.headers.get("Referrer-Policy")
    assert rp is not None
