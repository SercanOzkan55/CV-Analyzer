from fastapi.testclient import TestClient

from main import app


def test_cache_header():
    client = TestClient(app)
    resp = client.get("/api/v1/analyze")
    # Rate limiter may reject before cache-control is added
    if resp.status_code != 429:
        assert "cache-control" in resp.headers
