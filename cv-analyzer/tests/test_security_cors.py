import pytest
from fastapi.testclient import TestClient
from main import app

def test_cors_headers():
    """CORS preflight with valid Origin should return CORS headers."""
    client = TestClient(app)
    headers = {
        "Origin": "https://yourdomain.com",
        "Access-Control-Request-Method": "POST",
    }
    resp = client.options("/api/v1/analyze", headers=headers)
    assert resp.headers.get("access-control-allow-origin") is not None
    assert resp.headers.get("access-control-allow-methods") is not None
