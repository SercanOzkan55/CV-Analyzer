

def test_pdf_upload_content_type(client):
    """Non-PDF content type should be rejected."""
    with open(__file__, "rb") as f:
        resp = client.post(
            "/api/v1/analyze-pdf", files={"file": ("test.txt", f, "text/plain")}
        )
    assert resp.status_code in (400, 403, 415, 422, 429)
