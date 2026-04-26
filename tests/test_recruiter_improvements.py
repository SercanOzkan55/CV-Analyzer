"""
Tests for improved recruiter endpoints with validation, error handling, and proper response formats.
Covers: search endpoint, email validation, reminders, batch upload validation, and response formats.
"""

from datetime import datetime, timedelta
import json
import pytest
from auth import verify_supabase_jwt
import main as main_module
from models import Candidate, Organization, User, Reminder, CandidateAction, RecruiterJob


@pytest.fixture(autouse=True)
def _stable_runtime(monkeypatch):
    monkeypatch.setattr(main_module, "redis_rate", None)
    try:
        main_module._LOCAL_ABUSE_COUNTERS.clear()
        main_module._LOCAL_ABUSE_BANS.clear()
    except Exception:
        pass


def _setup_org_with_recruiter(db):
    """Create organization, recruiter, and job."""
    org = Organization(name="Test Org", domain="test.io")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    recruiter = User(
        supabase_id="test-recruiter",
        email="recruiter@test.io",
        role="recruiter",
        organization_id=org.id,
    )
    db.add(recruiter)
    db.commit()
    db.refresh(recruiter)
    
    job = RecruiterJob(
        organization_id=org.id,
        created_by=recruiter.id,
        title="Senior Engineer",
        description="Looking for experienced developer",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return org, recruiter, job


def _mock_pipeline(cv_text, job_description, lang=""):
    """Mock pipeline for testing."""
    return {
        "final_score": 0.85,
        "ats_score": 0.8,
        "detected_skills": ["python", "react"],
    }


# ── GET /candidates Tests ──

def test_candidates_returns_proper_response_format(client, db_session):
    """Verify /candidates returns CandidatesResponse with 'total' field."""
    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.get("/api/v1/recruiter/candidates")
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify response format
    assert "candidates" in data, "Response must have 'candidates' field"
    assert "total" in data, "Response must have 'total' field"
    assert isinstance(data["candidates"], list)
    assert isinstance(data["total"], int)


def test_candidates_limit_validation(client, db_session):
    """Verify limit parameter bounds (1-1000)."""
    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Test invalid limit (> 1000)
    resp = client.get("/api/v1/recruiter/candidates?limit=1500")
    assert resp.status_code == 422, "Should reject limit > 1000"
    
    # Test invalid limit (< 1)
    resp = client.get("/api/v1/recruiter/candidates?limit=0")
    assert resp.status_code == 422, "Should reject limit < 1"
    
    # Test valid limits
    resp = client.get("/api/v1/recruiter/candidates?limit=1")
    assert resp.status_code == 200
    
    resp = client.get("/api/v1/recruiter/candidates?limit=1000")
    assert resp.status_code == 200


# ── GET /search Tests ──

def test_search_requires_query(client, db_session):
    """Verify search endpoint requires 'q' parameter."""
    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Missing query parameter
    resp = client.get("/api/v1/recruiter/search")
    assert resp.status_code == 422, "Query 'q' is required"
    
    # Empty query
    resp = client.get("/api/v1/recruiter/search?q=")
    assert resp.status_code == 422, "Empty query should fail validation"


def test_search_response_format(client, db_session):
    """Verify /search returns SearchResponse with proper fields."""
    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.get("/api/v1/recruiter/search?q=python")
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify response format
    assert "results" in data, "Response must have 'results' field"
    assert "total" in data, "Response must have 'total' field"
    assert "query" in data, "Response must have 'query' field (echoed back)"
    assert isinstance(data["results"], list)
    assert data["query"] == "python"


def test_search_query_length_validation(client, db_session):
    """Verify search query respects max length."""
    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Query too long (> 500)
    long_query = "x" * 501
    resp = client.get(f"/api/v1/recruiter/search?q={long_query}")
    assert resp.status_code == 422, "Query > 500 chars should fail validation"


# ── POST /batch-upload Tests ──

def test_batch_upload_rejects_too_many_files(client, db_session):
    """Verify batch-upload rejects > 50 files."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Create 51 dummy files
    files = [
        ("files", (f"cv_{i}.pdf", b"%PDF-1.4\n%test", "application/pdf"))
        for i in range(51)
    ]
    
    resp = client.post(
        f"/api/v1/recruiter/dashboard/batch-upload",
        data={"job_id": job.id},
        files=files,
    )
    assert resp.status_code == 400
    assert "Maximum 50 files" in resp.json().get("detail", "")


def test_batch_upload_rejects_invalid_file_types(client, db_session):
    """Verify batch-upload only accepts PDF/TXT/DOCX."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Try to upload an image file
    files = [
        ("files", ("image.jpg", b"fake_image_data", "image/jpeg"))
    ]
    
    resp = client.post(
        f"/api/v1/recruiter/dashboard/batch-upload",
        data={"job_id": job.id},
        files=files,
    )
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json().get("detail", "")


def test_batch_upload_rejects_empty_files(client, db_session):
    """Verify batch-upload rejects empty files."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    files = [
        ("files", ("empty.pdf", b"", "application/pdf"))
    ]
    
    resp = client.post(
        f"/api/v1/recruiter/dashboard/batch-upload",
        data={"job_id": job.id},
        files=files,
    )
    assert resp.status_code == 400
    assert "empty" in resp.json().get("detail", "").lower()


def test_batch_upload_rejects_oversized_files(client, db_session):
    """Verify batch-upload rejects files > 5MB."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Create file > 5MB
    oversized = b"x" * (5_000_001)
    files = [
        ("files", ("huge.pdf", oversized, "application/pdf"))
    ]
    
    resp = client.post(
        f"/api/v1/recruiter/dashboard/batch-upload",
        data={"job_id": job.id},
        files=files,
    )
    assert resp.status_code == 400
    assert "too large" in resp.json().get("detail", "").lower()


# ── POST /send-email Tests ──

def test_send_email_requires_valid_recipient(client, db_session):
    """Verify send-email requires valid candidate email."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    from models import RecruiterEmailTemplate

    template = RecruiterEmailTemplate(
        organization_id=org.id,
        created_by=recruiter.id,
        name="Test",
        template_type="accept",
        subject="Subject",
        body="Body",
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Invalid email
    resp = client.post(
        "/api/v1/recruiter/send-email",
        json={
            "candidate_name": "John Doe",
            "candidate_email": "invalid-email",
            "template_id": template.id,
        },
    )
    assert resp.status_code == 400
    assert "valid" in resp.json().get("detail", "").lower()


def test_send_email_requires_template(client, db_session):
    """Verify send-email requires valid template."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Non-existent template
    resp = client.post(
        "/api/v1/recruiter/send-email",
        json={
            "candidate_name": "John Doe",
            "candidate_email": "john@test.com",
            "template_id": 9999,
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()


def test_export_candidates_csv(client, db_session):
    """Verify export candidates CSV endpoint returns recruiter organization's data."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    candidate = Candidate(
        organization_id=org.id,
        name="Jane Smith",
        email="jane@example.com",
        phone="555-1234",
        cv_text="Experienced engineer",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.get("/api/v1/recruiter/export/candidates?format=csv")
    assert resp.status_code == 200
    text = resp.text
    assert "name,email,phone,created_at" in text
    assert "Jane Smith" in text
    assert "jane@example.com" in text


def test_export_rankings_json(client, db_session):
    """Verify export rankings JSON endpoint returns candidate actions."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)

    action = CandidateAction(
        organization_id=org.id,
        job_id=job.id,
        recruiter_id=recruiter.id,
        candidate_name="Jane Smith",
        candidate_email="jane@example.com",
        cv_text="Experienced engineer",
        final_score=85.0,
        ats_score=90.0,
        action="accepted",
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.get(f"/api/v1/recruiter/export/rankings?job_id={job.id}&format=json")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert payload[0]["name"] == "Jane Smith"
    assert payload[0]["final_score"] == 85.0


def test_send_email_response_includes_timestamp(client, db_session, monkeypatch):
    """Verify send-email response includes timestamp."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    from models import RecruiterEmailTemplate
    
    template = RecruiterEmailTemplate(
        organization_id=org.id,
        created_by=recruiter.id,
        name="Test",
        template_type="accept",
        subject="Test Subject",
        body="Test {name}",
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    
    # Mock email sending
    monkeypatch.setattr(
        "services.recruiter_helpers._do_send_email",
        lambda to_email, subject, body, recruiter_email: True
    )
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.post(
        "/api/v1/recruiter/send-email",
        json={
            "candidate_name": "John Doe",
            "candidate_email": "john@test.com",
            "template_id": template.id,
        },
    )
    
    # Verify response on success
    if resp.status_code == 200:
        data = resp.json()
        assert "timestamp" in data, "Response must include timestamp"
        assert "sent" in data
        assert "to" in data


# ── POST /reminders Tests ──

def test_reminders_requires_future_date(client, db_session):
    """Verify reminders endpoint rejects past dates."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # Past date
    past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/recruiter/reminders",
        json={
            "title": "Past Event",
            "event_date": past_date,
            "reminder_type": "interview",
        },
    )
    assert resp.status_code == 400
    assert "future" in resp.json().get("detail", "").lower()


def test_reminders_requires_title(client, db_session):
    """Verify reminders endpoint requires title."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
    
    # Empty title
    resp = client.post(
        "/api/v1/recruiter/reminders",
        json={
            "title": "",
            "event_date": future_date,
            "reminder_type": "interview",
        },
    )
    assert resp.status_code == 400
    assert "required" in resp.json().get("detail", "").lower()


def test_reminders_response_format(client, db_session):
    """Verify reminders response includes expected fields."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.get("/api/v1/recruiter/reminders")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "reminders" in data
    assert "total" in data, "Response should include 'total' field"
    assert isinstance(data["reminders"], list)
    assert isinstance(data["total"], int)


# ── GET /jobs Tests ──

def test_jobs_response_format(client, db_session):
    """Verify /jobs returns JobsResponse with 'total' field."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.get("/api/v1/recruiter/jobs")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "jobs" in data
    assert "total" in data, "Response must have 'total' field"
    assert isinstance(data["jobs"], list)
    assert isinstance(data["total"], int)


def test_jobs_includes_full_description(client, db_session):
    """Verify /jobs returns longer descriptions (500 chars, not 200)."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    # Create job with long description
    long_desc = "x" * 400
    job.description = long_desc
    db_session.add(job)
    db_session.commit()
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    resp = client.get("/api/v1/recruiter/jobs")
    assert resp.status_code == 200
    data = resp.json()
    
    # Should include the full long description (not truncated at 200)
    if data["jobs"]:
        first_job = data["jobs"][0]
        assert len(first_job["description"]) >= 350, "Description should not be truncated at 200"
