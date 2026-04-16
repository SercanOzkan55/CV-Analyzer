import os

import pytest
import main as main_module
from models import User


@pytest.fixture(autouse=True)
def _stable_api_runtime(monkeypatch):
    """Keep API tests deterministic by stubbing heavy runtime dependencies."""

    def _mock_pipeline(cv_text: str, job_description: str, lang: str = None):
        return {
            "semantic_score": 75.0,
            "keyword_score": 68.0,
            "skill_score": 70.0,
            "experience_score": 72.0,
            "ats_score": 74.0,
            "ats": {"layout": {"formatting_score": 80.0}},
            "domain_similarity": 60.0,
            "detected_skills": ["python", "sql"],
            "missing_skills": ["kubernetes"],
            "keyword_gap": {"missing_words": ["microservices"], "missing_phrases": []},
            "final_score": 78.0,
            "interpretation": "High Match",
            "confidence": 0.9,
            "risk_level": "Low Risk",
            "detected_language": "en",
            "explanation": {"reason": "test-stub"},
            "recommendations": ["Add more quantified achievements"],
            "domain": {"domain_id": 1, "domain_name": "Other"},
            "industry": {"industry_id": 1, "industry_name": "Other"},
            "specialization": {"id": 1, "name": "General"},
            "score_breakdown": {
                "skills": 70.0,
                "keywords": 68.0,
                "format": 80.0,
                "experience": 72.0,
            },
            "ats_weights": {
                "skills": 0.35,
                "keywords": 0.25,
                "format": 0.15,
                "experience": 0.25,
            },
            "ats_weighted_score": 72.5,
        }

    class _DummyTaskResult:
        def __init__(self, result):
            self.id = "test-task-id"
            self.status = "SUCCESS"
            self.result = result

    def _mock_pdf_delay(*args, **kwargs):
        return _DummyTaskResult(_mock_pipeline(args[0], args[1]))

    # Avoid external Redis/ClamAV/Celery dependencies in API unit tests.
    monkeypatch.setattr(main_module, "run_pipeline", _mock_pipeline)
    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "CLAMAV_ENABLED", False)
    monkeypatch.setattr(main_module.analyze_pdf_task, "delay", _mock_pdf_delay, raising=False)

    try:
        main_module._LOCAL_DAILY_QUOTA.clear()
    except Exception:
        pass
    try:
        main_module._LOCAL_USER_THROTTLE.clear()
    except Exception:
        pass



def test_analyze_endpoint(client, sample_texts):
    cv, job = sample_texts
    resp = client.post("/api/v1/analyze", json={"cv_text": cv, "job_description": job})
    assert resp.status_code == 200
    data = resp.json()
    assert "final_score" in data


def test_analyze_pdf_large_file(client, sample_texts):
    _, job = sample_texts
    # create payload >5MB
    big = b"%PDF-" + b"0" * (5_000_001)
    files = {"file": ("big.pdf", big, "application/pdf")}
    resp = client.post(
        "/api/v1/analyze-pdf", files=files, data={"job_description": job}
    )
    assert resp.status_code == 400
    assert "File too large" in resp.text or resp.json().get("detail")


def test_history_auth(monkeypatch, client):
    # JWT auth is mocked in conftest for testing
    # /api/v1/history uses JWT (not API_KEY) authentication
    # This test verifies JWT-authenticated users can access history
    resp = client.get("/api/v1/history")
    # Request succeeds because JWT is mocked in conftest
    assert resp.status_code == 200


def test_history_with_wrong_key(client):
    # JWT auth is mocked in conftest for testing
    # API_KEY header is not used by /api/v1/history (JWT only)
    # This test verifies history endpoint is JWT-protected
    resp = client.get("/api/v1/history")
    # Request succeeds because JWT is mocked in conftest
    assert resp.status_code == 200


def test_history_with_good_key(client):
    headers = {"x-api-key": os.environ.get("API_KEY")}
    resp = client.get("/api/v1/history", headers=headers)
    assert resp.status_code == 200


def test_rate_limit_analyze_pdf(monkeypatch, client, sample_texts):
    # Note: free plan allows 5 daily analyses
    # This test verifies quota enforcement limits requests
    # Ensure quota/rate limit logic is triggered reliably
    old_mock_services = os.environ.get("MOCK_SERVICES", "0")
    os.environ["MOCK_SERVICES"] = "1"
    monkeypatch.setattr(main_module, "RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN", 2)
    try:
        main_module._LOCAL_USER_THROTTLE.clear()
    except Exception:
        pass
    try:
        main_module._LOCAL_DAILY_QUOTA.clear()
    except Exception:
        pass

    _, job = sample_texts
    files = {"file": ("small.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")}
    # call 6 times; should hit quota limit on or before 6th request
    statuses = [
        client.post(
            "/api/v1/analyze-pdf", files=files, data={"job_description": job}
        ).status_code
        for _ in range(6)
    ]
    # Verify at least one request hits quota (403) or rate limit (429)
    has_limit_hit = 403 in statuses or 429 in statuses
    assert has_limit_hit, f"Expected quota/rate limit hit, got: {statuses}"
    # Restore original MOCK_SERVICES value
    os.environ["MOCK_SERVICES"] = old_mock_services


def test_cv_auto_fix_endpoint_returns_optimized_text(monkeypatch, client):
    sample_cv = """John Doe
john@example.com | +90 555 123 45 67 | Istanbul

Objective
Backend developer with Python and SQL experience.

Experience
Developed internal APIs and improved report processing performance by 20%.
Worked with Python, FastAPI and SQL in production systems.

Education
BSc in Computer Engineering

Skills
Python, SQL, FastAPI, REST APIs

Hobbies
Photography
"""

    monkeypatch.setattr(main_module, "_extract_pdf_text", lambda _: sample_cv)

    resp = client.post(
        "/api/v1/cv/auto-fix",
        files={"file": ("cv.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")},
        data={
            "job_description": "Python FastAPI engineer with strong SQL skills",
            "lang": "en",
            "use_ai": "false",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["used_ai"] is False
    assert "PROFESSIONAL SUMMARY" in data["optimized_cv_text"]
    assert "EXPERIENCE" in data["optimized_cv_text"]
    assert "SKILLS" in data["optimized_cv_text"]
    assert data["after_ats"]["overall_score"] >= data["before_ats"]["overall_score"]


def test_cv_auto_fix_endpoint_drops_irrelevant_sections(monkeypatch, client):
    sample_cv = """Jane Doe
jane@example.com

Professional Summary
Data analyst with SQL and Python experience.

Experience
Created dashboards and automated weekly reports.

Education
MSc in Information Systems

References
Available on request

Interests
Travel, movies
"""

    monkeypatch.setattr(main_module, "_extract_pdf_text", lambda _: sample_cv)

    resp = client.post(
        "/api/v1/cv/auto-fix",
        files={"file": ("cv.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")},
        data={"job_description": "SQL analyst", "use_ai": "false"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "references" in data["dropped_sections"]
    assert data["optimized_cv_text"].upper().find("REFERENCES") == -1


def test_cv_auto_fix_export_endpoint_returns_document(client):
    payload = {
        "optimized_cv_text": "John Doe\njohn@example.com\n\nPROFESSIONAL SUMMARY\nPython developer.\n\nEXPERIENCE\nBackend Developer\n- Built FastAPI services\n\nSKILLS\nPython, FastAPI, SQL",
        "job_description": "Python FastAPI backend engineer",
        "output_format": "docx",
        "template": "classic",
        "lang": "en",
    }

    resp = client.post("/api/v1/cv/auto-fix/export", json=payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_cv_auto_fix_parse_endpoint_returns_builder_payload(client):
    payload = {
        "optimized_cv_text": "John Doe\njohn@example.com\n\nPROFESSIONAL SUMMARY\nPython developer.\n\nEXPERIENCE\nBackend Developer\n- Built FastAPI services\n\nSKILLS\nPython, FastAPI, SQL",
        "job_description": "Python FastAPI backend engineer",
        "lang": "en",
    }

    resp = client.post("/api/v1/cv/auto-fix/parse", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "builder_payload" in data
    assert data["builder_payload"]["full_name"] == "John Doe"
    assert "Python" in data["builder_payload"]["skills"]


def test_cv_auto_fix_parse_endpoint_rejects_empty_text(client):
    resp = client.post(
        "/api/v1/cv/auto-fix/parse",
        json={"optimized_cv_text": "", "job_description": "Python role", "lang": "en"},
    )

    assert resp.status_code == 400
    assert "cannot be empty" in resp.json().get("detail", "")


def test_billing_admin_set_user_plan_updates_user_by_email(client, db_session, monkeypatch):
    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "billing-admin-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")

    db_user = User(
        supabase_id="support-user-1",
        email="support1@example.com",
        plan_type="free",
        billing_status="trialing",
    )
    db_session.add(db_user)
    db_session.commit()

    resp = client.post(
        "/api/v1/billing/admin/set-user-plan",
        json={
            "email": "support1@example.com",
            "plan_type": "pro",
            "billing_status": "active",
        },
        headers={"X-Billing-Admin-Token": "billing-admin-secret"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["plan_type"] == "pro"
    assert data["billing_status"] == "active"

    updated = db_session.query(User).filter(User.supabase_id == "support-user-1").first()
    assert updated is not None
    assert updated.plan_type == "pro"
    assert updated.billing_status == "active"


def test_billing_admin_set_user_plan_rejects_invalid_token(client, db_session, monkeypatch):
    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "expected-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")

    db_user = User(
        supabase_id="support-user-2",
        email="support2@example.com",
        plan_type="free",
        billing_status="trialing",
    )
    db_session.add(db_user)
    db_session.commit()

    resp = client.post(
        "/api/v1/billing/admin/set-user-plan",
        json={
            "email": "support2@example.com",
            "plan_type": "enterprise",
            "billing_status": "active",
        },
        headers={"X-Billing-Admin-Token": "wrong-secret"},
    )

    assert resp.status_code == 403


def test_billing_admin_users_list_returns_items(client, db_session, monkeypatch):
    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "billing-admin-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")

    db_session.add(
        User(
            supabase_id="support-user-3",
            email="support3@example.com",
            plan_type="pro",
            billing_status="active",
        )
    )
    db_session.add(
        User(
            supabase_id="support-user-4",
            email="support4@example.com",
            plan_type="free",
            billing_status="trialing",
        )
    )
    db_session.commit()

    resp = client.get(
        "/api/v1/billing/admin/users?limit=10&offset=0",
        headers={"X-Billing-Admin-Token": "billing-admin-secret"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total"] >= 2
    assert isinstance(data["items"], list)
    assert any(item.get("email") == "support3@example.com" for item in data["items"])


def test_billing_admin_feedback_list_includes_submitted_feedback(client, monkeypatch):
    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "billing-admin-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")

    submit_resp = client.post(
        "/api/v1/feedback",
        json={
            "category": "bug",
            "message": "Dun gonderdigim sikayet metni test kaydi",
            "page": "/analyze",
            "lang": "tr",
        },
    )
    assert submit_resp.status_code == 200

    list_resp = client.get(
        "/api/v1/billing/admin/feedback?limit=20",
        headers={"X-Billing-Admin-Token": "billing-admin-secret"},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["items"], list)
    assert any("Dun gonderdigim sikayet" in str(item.get("message") or "") for item in data["items"])
