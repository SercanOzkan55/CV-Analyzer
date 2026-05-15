import pytest
from fastapi.testclient import TestClient

from auth import verify_supabase_jwt
from main import app
import main as main_module


# JWT tamper test: invalid signature
@pytest.fixture
def tampered_jwt():
    main_module._LOCAL_USER_THROTTLE.clear()
    main_module._LOCAL_DAILY_QUOTA.clear()
    main_module._LOCAL_ABUSE_COUNTERS.clear()
    main_module._LOCAL_ABUSE_BANS.clear()

    def _tampered_jwt(_=None):
        return {
            "user_id": "test-user-123",
            "email": "testuser@example.com",
            "payload": {"sub": "test-user-123", "exp": 9999999999},
            "signature": "invalidsig",
        }

    app.dependency_overrides[verify_supabase_jwt] = _tampered_jwt
    yield
    app.dependency_overrides.pop(verify_supabase_jwt, None)


@pytest.mark.usefixtures("tampered_jwt")
def test_jwt_tampered_rejected():
    client = TestClient(app)
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_text": "bar"})
    assert resp.status_code in (401, 403)


# Org privilege escalation: recruiter tries to access another org
@pytest.mark.parametrize("org_id", [9999, 1, 2])
def test_org_privilege_escalation(client, org_id):
    payload = {"cv_text": "foo", "job_text": "bar", "organization_id": org_id}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 403)
    # Should not allow recruiter to analyze for arbitrary org_id


# SQL injection in job_text
@pytest.mark.parametrize(
    "malicious", ["Robert'); DROP TABLE organizations;--", "' OR TRUE --"]
)
def test_sql_injection_job_text(client, malicious):
    payload = {"cv_text": "foo", "job_text": malicious}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 403, 422)
    assert "error" not in resp.text.lower()
