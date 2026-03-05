

def test_path_traversal_upload(client):
    """Path traversal in filenames should not cause server errors."""
    files = {"file": ("../etc/passwd", b"%PDF-fakepdf", "application/pdf")}
    resp = client.post("/api/v1/analyze-pdf", files=files)
    # Endpoint ignores filename (reads stream only) → 200 is acceptable
    assert resp.status_code in (200, 400, 403, 422)
