from fastapi.testclient import TestClient

from main import app


def test_open_redirect():
    """API should not perform open redirects."""
    client = TestClient(app)
    resp = client.get("/api/v1/analyze?next=https://evil.com", follow_redirects=False)
    # GET on a POST-only endpoint returns 405; any non-redirect is acceptable
    assert resp.status_code in (200, 400, 403, 405, 422, 429)
    assert "evil.com" not in resp.headers.get("location", "").lower()
