from fastapi.testclient import TestClient

from main import app


def test_trace_method_disallowed():
    client = TestClient(app)
    resp = client.request("TRACE", "/api/v1/analyze")
    assert resp.status_code in (405, 404)
