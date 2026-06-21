def test_file_type_enforcement(client):
    """Non-PDF file uploads should be rejected."""
    files = {"file": ("test.exe", b"MZ...", "application/octet-stream")}
    resp = client.post("/api/v1/analyze-pdf", files=files)
    assert resp.status_code in (400, 403, 415, 422, 429)
