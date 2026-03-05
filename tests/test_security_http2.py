

def test_http2_not_supported(client):
    """HTTP/1.1 requests should work without hanging."""
    resp = client.post(
        "/api/v1/analyze", json={"cv_text": "foo", "job_description": "bar"}
    )
    assert resp.status_code in (200, 400, 422)
