from fastapi.testclient import TestClient

from main import app


def test_api_versioning():
    client = TestClient(app)
    resp = client.post("/api/v0/analyze", json={"cv_text": "foo", "job_text": "bar"})
    assert resp.status_code in (403, 404, 405, 429)
