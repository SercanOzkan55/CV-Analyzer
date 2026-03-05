from fastapi.testclient import TestClient

from main import app


def test_security_headers_present():
    """Security headers should be present on all responses."""
    client = TestClient(app)
    resp = client.get("/api/v1/analyze")
    assert resp.headers.get("Strict-Transport-Security") is not None
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert resp.headers.get("Cache-Control") == "no-store"
