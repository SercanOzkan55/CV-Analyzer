import pytest
from fastapi.testclient import TestClient
from main import app

def test_csrf_absent():
    """REST API should not use CSRF tokens."""
    client = TestClient(app)
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_description": "bar"})
    assert "csrf" not in resp.headers
    # 401 (no auth) is also a valid secure response
    assert resp.status_code in (200, 400, 401, 403, 422)
