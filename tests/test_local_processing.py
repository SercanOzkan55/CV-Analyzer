"""
Integration tests for local processing mode - zero data retention.
Tests API key validation, quota management, and processing without DB saves.
"""

import pytest
import json
from io import BytesIO
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def mock_cv_processing():
    """Mock CV processing to avoid ProcessPoolExecutor spawn issue on Windows."""
    async def mock_ultra_fast(files, job_description, job_id, use_cache=True, workers=None):
        results = []
        for f in files:
            results.append({
                "filename": f["filename"],
                "status": "success",
                "final_score": 85.0,
                "ats_score": 90.0,
                "skills_match": ["Python"],
                "experience_match": 5,
                "education_match": 4,
                "processed_at": "2026-05-17T12:00:00"
            })
        return results

    with patch("utils.cv_processor.process_cv_batch_ultra_fast", new=mock_ultra_fast):
        yield


@pytest.fixture
def recruiter_user(db_session):
    """Create a test recruiter user with organization."""
    from models import User, Organization

    # Create organization
    org = Organization(
        name="Test Organization",
        domain="testcompany.com",
        plan_type="pro",
        billing_status="active"
    )
    db_session.add(org)
    db_session.commit()

    # Create user
    user = User(
        supabase_id="test-user-123",
        email="testuser@example.com",
        organization_id=org.id,
        role="recruiter",
        plan_type="pro",
        billing_status="active",
    )
    db_session.add(user)
    db_session.commit()

    return {
        "user_id": user.id,
        "supabase_id": user.supabase_id,
        "email": user.email,
        "organization_id": user.organization_id,
        "token": "mock-jwt-token"
    }


@pytest.fixture
def test_job(db_session, recruiter_user):
    """Create a test job for the recruiter."""
    from models import RecruiterJob

    job = RecruiterJob(
        title="Senior Python Developer",
        description="Looking for experienced Python developer with FastAPI experience",
        organization_id=recruiter_user["organization_id"],
        created_by=recruiter_user["user_id"],
    )
    db_session.add(job)
    db_session.commit()

    return job


@pytest.fixture
def sample_pdf_file():
    """Create a minimal PDF-like file for testing."""
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
(Sample CV Test) Tj
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


def test_generate_api_key_success(client, recruiter_user):
    """Test successful API key generation."""
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("cv_")
    assert "monthly_limit" in data
    assert "expires_at" in data


def test_generate_api_key_existing(client, recruiter_user, db):
    """Test generating key when one already exists."""
    # First create a key
    response1 = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    assert response1.status_code == 200
    api_key = response1.json()["api_key"]

    # Try to generate again
    response2 = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    assert response2.status_code == 200
    assert response2.json()["api_key"] == api_key
    assert "Existing active subscription" in response2.json()["message"]


def test_get_subscription_usage_valid_key(client, recruiter_user):
    """Test getting usage with valid API key."""
    # First generate a key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Get usage
    response = client.get(
        "/api/v1/recruiter/subscriptions/usage",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "monthly_limit" in data
    assert "monthly_usage" in data
    assert "remaining" in data
    assert data["is_active"] is True


def test_get_subscription_usage_invalid_key(client):
    """Test getting usage with invalid API key."""
    response = client.get(
        "/api/v1/recruiter/subscriptions/usage",
        headers={"X-API-Key": "invalid_key"},
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_process_local_success(client, recruiter_user, test_job, sample_pdf_file):
    """Test successful local processing."""
    # Generate API key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Process CV
    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={"files": ("sample.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "summary" in data
    assert "downloads" in data
    assert "usage" in data
    assert len(data["results"]) == 1
    assert data["summary"]["total_cvs"] == 1


def test_process_local_multiple_files(client, recruiter_user, test_job, sample_pdf_file, sample_txt_file):
    """Test processing multiple files locally."""
    # Generate API key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Process multiple CVs
    files = [
        ("files", ("cv1.pdf", sample_pdf_file, "application/pdf")),
        ("files", ("cv2.txt", sample_txt_file, "text/plain")),
    ]

    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files=files,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["summary"]["total_cvs"] == 2


def test_process_local_quota_exceeded(client, recruiter_user, test_job, sample_pdf_file, db):
    """Test processing fails when quota exceeded."""
    # Generate API key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Set usage to exceed limit
    from models import APISubscription
    subscription = db.query(APISubscription).filter(
        APISubscription.api_key == api_key
    ).first()
    subscription.monthly_usage = subscription.monthly_limit
    db.commit()

    # Try to process
    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 429
    assert "Monthly quota exceeded" in response.json()["detail"]


def test_process_local_invalid_job(client, recruiter_user, sample_pdf_file):
    """Test processing fails with invalid job ID."""
    # Generate API key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Try with invalid job ID
    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": 99999},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


def test_process_local_no_files(client, recruiter_user, test_job):
    """Test processing fails with no files."""
    # Generate API key
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Try with no files
    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={},
    )

    assert response.status_code == 400
    assert "At least one file" in response.json()["detail"]


def test_process_local_invalid_api_key(client, test_job, sample_pdf_file):
    """Test processing fails with invalid API key."""
    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": "invalid_key"},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_download_csv_success(client, recruiter_user, test_job, sample_pdf_file):
    """Test CSV download after processing."""
    # Generate API key and process
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )
    download_url = response.json()["downloads"]["csv"]

    # Extract download ID from URL
    download_id = download_url.split("/")[-1]

    # Download CSV
    response = client.get(f"/api/v1/downloads/{download_id}", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert b"name" in response.content  # CSV headers


def test_download_requires_owner_api_key(client, recruiter_user, test_job, sample_pdf_file):
    """Test local-processing downloads require the owning API key."""
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )
    download_url = response.json()["downloads"]["csv"]
    download_id = download_url.split("/")[-1]

    response = client.get(f"/api/v1/downloads/{download_id}")

    assert response.status_code == 401


def test_download_json_success(client, recruiter_user, test_job, sample_pdf_file):
    """Test JSON download after processing."""
    # Generate API key and process
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    response = client.post(
        "/api/v1/recruiter/process-local",
        headers={"X-API-Key": api_key},
        data={"job_id": test_job.id},
        files={"files": ("cv.pdf", sample_pdf_file, "application/pdf")},
    )
    download_url = response.json()["downloads"]["json"]

    # Extract download ID from URL
    download_id = download_url.split("/")[-1]

    # Download JSON
    response = client.get(f"/api/v1/downloads/{download_id}", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "results" in data
    assert "metadata" in data


def test_download_expired(client):
    """Test download fails when expired."""
    # Try to download non-existent/expired file
    response = client.get("/api/v1/downloads/expired_id")

    assert response.status_code == 404
    assert "not found or expired" in response.json()["detail"]


def test_reset_usage_admin(client, recruiter_user, db):
    """Test admin usage reset."""
    # Generate API key and use some quota
    response = client.post(
        "/api/v1/recruiter/subscriptions/generate-key",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )
    api_key = response.json()["api_key"]

    # Manually set usage
    from models import APISubscription
    subscription = db.query(APISubscription).filter(
        APISubscription.api_key == api_key
    ).first()
    subscription.monthly_usage = 100
    db.commit()

    # Reset usage
    response = client.post(
        "/api/v1/recruiter/subscriptions/reset-usage",
        headers={"Authorization": f"Bearer {recruiter_user['token']}"},
    )

    assert response.status_code == 200
    assert "Reset usage" in response.json()["message"]

    # Verify reset
    db.refresh(subscription)
    assert subscription.monthly_usage == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
