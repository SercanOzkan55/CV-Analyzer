from fastapi.testclient import TestClient

import main as main_module
from main import app


def test_content_length_limit():
    main_module._LOCAL_ABUSE_COUNTERS.clear()
    main_module._LOCAL_ABUSE_BANS.clear()
    main_module._LOCAL_USER_THROTTLE.clear()

    client = TestClient(app)
    big_text = "A" * 2_000_000  # 2MB
    payload = {"cv_text": big_text, "job_text": "bar"}
    resp = client.post("/api/v1/analyze", json=payload)

    # Large requests should be rejected before normal processing.
    assert resp.status_code in (413, 400, 422, 401, 403)
