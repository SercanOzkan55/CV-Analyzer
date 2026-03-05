import pytest


@pytest.mark.parametrize(
    "payload",
    [
        {"cv_text": "\x00\x01\x02\x03\x04", "job_description": "bar"},
        {"cv_text": "A" * 10000, "job_description": "B" * 10000},
        {"cv_text": "<script>alert('xss')</script>", "job_description": "bar"},
        {"cv_text": "' OR 1=1;--", "job_description": "bar"},
        {"cv_text": "Robert'); DROP TABLE analysis;--", "job_description": "bar"},
        {"cv_text": "\U0001f40d\U0001f680\U0001f4a5", "job_description": "bar"},
        {"cv_text": "", "job_description": ""},
    ],
)
def test_fuzz_analyze_endpoint(client, payload):
    """Fuzz payloads should not crash the endpoint."""
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 400, 422)
