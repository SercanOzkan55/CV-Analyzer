from fastapi.testclient import TestClient

from main import app


def test_brute_force_rate_limit():
    client = TestClient(app)
    for i in range(100):
        resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_text": "bar"})
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_text": "bar"})
    assert resp.status_code in (429, 403, 401)
