import pytest
from fastapi.testclient import TestClient
from main import app

def test_method_enforcement():
    client = TestClient(app)
    # GET ile analyze endpointine erişim olmamalı
    resp = client.get("/api/v1/analyze")
    assert resp.status_code in (405, 404)
    # PUT ile de erişim olmamalı
    resp = client.put("/api/v1/analyze", json={"cv_text": "foo", "job_text": "bar"})
    assert resp.status_code in (405, 404)
