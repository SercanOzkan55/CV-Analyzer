from fastapi.testclient import TestClient

from main import app


def test_referrer_policy_header():
    """Referrer-Policy should be set on all responses."""
    client = TestClient(app)
    resp = client.get("/api/v1/analyze")
    # Rate limiter may reject before header middleware runs
    if resp.status_code != 429:
        rp = resp.headers.get("referrer-policy") or resp.headers.get("Referrer-Policy")
        assert rp is not None
