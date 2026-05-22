"""
Integration tests for recruiter batch upload and WebSocket endpoints.
Tests cover file upload, progress tracking, and error handling.
"""

import pytest
import asyncio
import json
from io import BytesIO
from unittest.mock import patch, MagicMock
import websockets
from fastapi.testclient import TestClient


@pytest.fixture
def sample_pdf_file():
    """Create a minimal PDF-like file for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< >>
stream
BT
/F1 12 Tf
50 750 Td
(Sample CV Test with Python FastAPI PostgreSQL Docker AWS leadership and backend development experience) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF
"""
    return BytesIO(pdf_content)


@pytest.fixture
def sample_txt_file():
    """Create a sample text file."""
    content = """
JOHN DOE
john@example.com
+1-234-567-8900

OBJECTIVE:
Seeking a position in software development.

EXPERIENCE:
Software Engineer - ABC Company (2020-Present)
- Developed Python backend services
- Managed databases with PostgreSQL
- Led team of 3 developers

EDUCATION:
BS Computer Science - University (2020)

SKILLS:
Python, FastAPI, PostgreSQL, Docker, AWS
"""
    return BytesIO(content.encode())


def test_batch_upload_success(client, recruiter_user, test_job, sample_pdf_file):
    """Test successful batch upload of CVs."""
    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files={"files": ("sample.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["count"] == 1
    assert "message" in data
    task_id = data.get("task_id")
    assert task_id
    
    return task_id


def test_batch_upload_multiple_files(
    client, recruiter_user, test_job, sample_pdf_file, sample_txt_file
):
    """Test batch upload with multiple files."""
    files = [
        ("files", ("cv1.pdf", sample_pdf_file, "application/pdf")),
        ("files", ("cv2.txt", sample_txt_file, "text/plain")),
    ]

    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files=files,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


def test_batch_upload_exceeds_max_files(client, recruiter_user, test_job):
    """Test batch upload fails when exceeding 50 file limit."""
    files = [
        ("files", (f"cv{i}.pdf", BytesIO(b"%PDF dummy content"), "application/pdf"))
        for i in range(51)
    ]

    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files=files,
    )

    assert response.status_code == 400
    data = response.json()
    assert "Maximum 50 files" in data.get("detail", "")


def test_batch_upload_invalid_format(client, recruiter_user, test_job):
    """Test batch upload fails with unsupported file format."""
    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files={"files": ("document.xlsx", BytesIO(b"fake excel"), "application/excel")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data.get("detail", "")


def test_batch_upload_empty_file(client, recruiter_user, test_job):
    """Test batch upload fails with empty file."""
    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files={"files": ("empty.pdf", BytesIO(b""), "application/pdf")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "File is empty" in data.get("detail", "")


def test_batch_upload_insufficient_credits(
    client, recruiter_user, test_job, sample_pdf_file, db
):
    """Test batch upload fails when organization lacks credits."""
    # Set org credits to 0
    org = recruiter_user["org"]
    org.monthly_usage = org.cv_credit_limit
    db.add(org)
    db.commit()

    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 429
    data = response.json()
    assert "Insufficient credits" in data.get("detail", "")


def test_batch_upload_job_not_found(client, recruiter_user, sample_pdf_file):
    """Test batch upload fails when job doesn't exist."""
    response = client.post(
        "/api/v1/recruiter/dashboard/batch-upload",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
        data={"job_id": 99999},  # Non-existent job
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 404
    data = response.json()
    assert "Job not found" in data.get("detail", "")


def test_batch_upload_requires_auth(client, sample_pdf_file, test_job):
    """Test batch upload requires authentication."""
    from auth import verify_supabase_jwt
    from main import app

    original_override = app.dependency_overrides.pop(verify_supabase_jwt, None)
    try:
        response = client.post(
            "/api/v1/recruiter/dashboard/batch-upload",
            data={"job_id": test_job.id},
            files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
        )
    finally:
        if original_override is not None:
            app.dependency_overrides[verify_supabase_jwt] = original_override

    assert response.status_code == 401


def test_websocket_batch_upload_progress(client, recruiter_user, test_job):
    """Test WebSocket batch upload progress tracking."""
    pytest.skip("WebSocket progress requires a running ASGI server and async client")


def test_websocket_invalid_task_id(client):
    """Test WebSocket connection with invalid task ID."""
    # This would require WebSocket testing - skip for now
    pytest.skip("WebSocket connection test requires async test client")


def test_export_candidates_csv(client, recruiter_user):
    """Test export candidates as CSV."""
    response = client.get(
        "/api/v1/recruiter/export/candidates?format=csv",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert b"name" in response.content  # CSV headers


def test_export_candidates_json(client, recruiter_user):
    """Test export candidates as JSON."""
    response = client.get(
        "/api/v1/recruiter/export/candidates?format=json",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert isinstance(data, list)


def test_export_rankings_csv(client, recruiter_user, test_job):
    """Test export rankings as CSV."""
    response = client.get(
        f"/api/v1/recruiter/export/rankings?format=csv&job_id={test_job.id}",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert b"final_score" in response.content


def test_export_rankings_json(client, recruiter_user, test_job):
    """Test export rankings as JSON."""
    response = client.get(
        f"/api/v1/recruiter/export/rankings?format=json&job_id={test_job.id}",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.skip(reason="Rate limiting test requires rate limiter configuration")
def test_rate_limiting_batch_upload():
    """Test rate limiting on batch upload endpoint."""
    # This would need rate limiter configured.


def test_pagination_with_batch_upload(client, recruiter_user):
    """Test pagination works on candidates list after batch upload."""
    response = client.get(
        "/api/v1/recruiter/candidates?limit=10&offset=0",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data
    assert data["pagination"]["limit"] == 10
    assert data["pagination"]["offset"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
