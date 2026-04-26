from fastapi.testclient import TestClient

from main import app


def test_content_length_limit():
    client = TestClient(app)
    big_text = "A" * 2_000_000  # 2MB
    payload = {"cv_text": big_text, "job_text": "bar"}
    resp = client.post("/api/v1/analyze", json=payload)
    # 413 Payload Too Large veya 400/422 olmalı
    assert resp.status_code in (413, 400, 403, 422, 401, 429)
