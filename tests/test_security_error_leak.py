def test_error_leak(client):
    """Endpoint should never leak internal error details."""
    resp = client.post("/api/v1/analyze", json={"cv_text": "' OR 1=1;--", "job_description": "bar"})
    leak_keywords = ["traceback", "sqlalchemy", "select * from", "syntax error"]
    for kw in leak_keywords:
        assert kw not in resp.text.lower()
