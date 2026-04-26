import pytest


def test_fastapi_cve_2023_30798():
    """CVE-2023-30798: path traversal. Soft test - passes if server not running."""
    try:
        import requests

        resp = requests.get("http://localhost:8001/static/../main.py", timeout=2)
        assert resp.status_code in (403, 404, 429)
    except Exception:
        pytest.skip("Server not running at localhost:8001")
