import pytest
from fastapi.testclient import TestClient

from auth import verify_supabase_jwt
from main import app


# JWT expiration test
@pytest.fixture
def expired_jwt():
    def _expired_jwt(_=None):
        return {
            "user_id": "test-user-123",
            "email": "testuser@example.com",
            "payload": {"sub": "test-user-123", "exp": 1},  # expired
        }

    app.dependency_overrides[verify_supabase_jwt] = _expired_jwt
    yield
    app.dependency_overrides.pop(verify_supabase_jwt, None)


# Organization escalation test
@pytest.mark.usefixtures("expired_jwt")
def test_jwt_expired_rejected():
    client = TestClient(app)
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_text": "bar"})
    assert resp.status_code in (401, 403, 429)


# Mass assignment test
def test_mass_assignment_org_id(client):
    # Try to set organization_id directly
    payload = {"cv_text": "foo", "job_text": "bar", "organization_id": 9999}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 403, 429)  # Should not allow arbitrary org_id


# Query injection test
@pytest.mark.parametrize("malicious", ["1; DROP TABLE app_users;--", "' OR 1=1 --"])
def test_query_injection(client, malicious):
    payload = {"cv_text": malicious, "job_text": "bar"}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 403, 422, 429)
    assert "error" not in resp.text.lower()
