

def test_unsupported_upload_content_type(client):
    """Unsupported executable-like content type should be rejected."""
    with open(__file__, "rb") as f:
        resp = client.post(
            "/api/v1/analyze-pdf",
            files={"file": ("test.exe", f, "application/x-msdownload")},
        )
    assert resp.status_code in (400, 415, 422)
