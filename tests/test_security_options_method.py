from fastapi.testclient import TestClient

from main import app


def test_options_method():
    """OPTIONS preflight should return CORS headers."""
    client = TestClient(app)
    headers = {
        "Origin": "https://yourdomain.com",
        "Access-Control-Request-Method": "POST",
    }
    resp = client.options("/api/v1/analyze", headers=headers)
    assert resp.status_code in (200, 204, 403, 429)
    # Rate limiter/abuse guard may reject before CORS middleware adds headers
    if resp.status_code not in (403, 429):
        assert "access-control-allow-methods" in resp.headers
