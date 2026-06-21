import time


def test_analyze_timeout(client):
    """Endpoint should respond within a reasonable time."""
    start = time.time()
    resp = client.post("/api/v1/analyze", json={"cv_text": "foo", "job_description": "bar"}, timeout=10)
    duration = time.time() - start
    assert resp.status_code in (200, 400, 403, 422, 429)
    assert duration < 10
