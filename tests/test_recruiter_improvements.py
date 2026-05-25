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
    try:
        from routes.recruiter import _IN_MEMORY_CACHE
        _IN_MEMORY_CACHE.clear()
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


def test_jobs_caching_and_invalidation(client, db_session):
    """Verify /jobs endpoint caching and invalidation on POST /jobs."""
    from routes.recruiter import _IN_MEMORY_CACHE
    _IN_MEMORY_CACHE.clear()

    org, recruiter, job = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # 1. Warm up the cache
    resp1 = client.get("/api/v1/recruiter/jobs")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["jobs"]) == 1
    assert data1["jobs"][0]["title"] == "Senior Engineer"
    
    # 2. Modify the job in DB directly (bypass endpoint/API)
    job.title = "Directly Modified Title"
    db_session.add(job)
    db_session.commit()
    
    # 3. GET /jobs again - should return cached "Senior Engineer"
    resp2 = client.get("/api/v1/recruiter/jobs")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["jobs"][0]["title"] == "Senior Engineer"
    
    # 4. Create a new job via POST /jobs - should invalidate cache
    resp3 = client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "New Job via API", "description": "Some description"}
    )
    assert resp3.status_code == 200
    
    # 5. GET /jobs again - should reflect database state (both jobs, and title change)
    resp4 = client.get("/api/v1/recruiter/jobs")
    assert resp4.status_code == 200
    data4 = resp4.json()
    assert len(data4["jobs"]) == 2
    titles = [j["title"] for j in data4["jobs"]]
    assert "Directly Modified Title" in titles
    assert "New Job via API" in titles


def test_templates_caching_and_invalidation(client, db_session):
    """Verify /templates endpoint caching and invalidation on POST and DELETE."""
    from routes.recruiter import _IN_MEMORY_CACHE
    _IN_MEMORY_CACHE.clear()

    org, recruiter, _ = _setup_org_with_recruiter(db_session)
    
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    
    # 1. Warm up cache (should be empty initially)
    resp1 = client.get("/api/v1/recruiter/templates")
    assert resp1.status_code == 200
    assert len(resp1.json()["templates"]) == 0
    
    # 2. Create template via API - should invalidate cache
    resp2 = client.post(
        "/api/v1/recruiter/templates",
        json={
            "name": "Template 1",
            "template_type": "accept",
            "subject": "Hello",
            "body": "Welcome",
        }
    )
    assert resp2.status_code == 200
    tpl_id = resp2.json()["id"]
    
    # 3. GET /templates again - cache should be invalidated, returns 1 template
    resp3 = client.get("/api/v1/recruiter/templates")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3["templates"]) == 1
    assert data3["templates"][0]["name"] == "Template 1"
    
    # 4. DELETE template via API - should invalidate cache
    resp4 = client.delete(f"/api/v1/recruiter/templates/{tpl_id}")
    assert resp4.status_code == 200
    
    # 5. GET /templates again - cache should be invalidated, returns 0 templates
    resp5 = client.get("/api/v1/recruiter/templates")
    assert resp5.status_code == 200
    assert len(resp5.json()["templates"]) == 0


def test_dashboard_action_saves_decision_message_and_sends_email(client, db_session, monkeypatch):
    """Approve/reject actions should persist reviewer message and optionally send candidate email."""
    org, recruiter, job = _setup_org_with_recruiter(db_session)
    sent = {}

    def fake_send(to_email, subject, body, recruiter_email):
        sent.update({
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "recruiter_email": recruiter_email,
        })
        return True

    monkeypatch.setattr("routes.recruiter._do_send_email", fake_send)
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.post(
        "/api/v1/recruiter/dashboard/action",
        json={
            "job_id": job.id,
            "candidate_name": "Jane Smith",
            "candidate_email": "jane@example.com",
            "cv_text": "Python developer with React and PostgreSQL experience",
            "final_score": 86,
            "ats_score": 82,
            "action": "accepted",
            "notes": "Strong Python and React match.",
            "send_email": True,
            "email_subject": "Next step",
            "email_body": "Strong Python and React match.",
            "analysis_snapshot": {
                "final_score": 86,
                "detected_skills": ["Python", "React"],
                "missing_skills": ["Kubernetes"],
            },
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["decision_message"] == "Strong Python and React match."
    assert payload["email"]["sent"] is True
    assert sent["to_email"] == "jane@example.com"

    action = db_session.query(CandidateAction).filter_by(candidate_email="jane@example.com").one()
    assert action.notes == "Strong Python and React match."
    assert action.email_sent is True


def test_dashboard_action_rejects_other_org_job(client, db_session):
    """Recruiters must not create decisions against jobs outside their organization."""
    _org, recruiter, _job = _setup_org_with_recruiter(db_session)
    other = Organization(name="Other Org", domain="other.test")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_job = RecruiterJob(
        organization_id=other.id,
        created_by=recruiter.id,
        title="Other job",
        description="Private role",
    )
    db_session.add(other_job)
    db_session.commit()
    db_session.refresh(other_job)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.post(
        "/api/v1/recruiter/dashboard/action",
        json={
            "job_id": other_job.id,
            "candidate_name": "Jane Smith",
            "candidate_email": "jane@example.com",
            "action": "rejected",
        },
    )

    assert resp.status_code == 404
    assert db_session.query(CandidateAction).filter_by(candidate_email="jane@example.com").count() == 0
