from fastapi.testclient import TestClient

from main import app


def test_cache_header():
    client = TestClient(app)
    resp = client.get("/api/v1/analyze")
    assert "cache-control" in resp.headers
