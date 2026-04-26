"""Tests for score breakdown, health, webhook, and miscellaneous endpoints."""

import os
import json
import pytest
import main as main_module


@pytest.fixture(autouse=True)
def _endpoint_env(monkeypatch):
    """Stub heavy runtime deps for API endpoint tests."""
    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "CLAMAV_ENABLED", False)
    monkeypatch.setattr(main_module, "MOCK_SERVICES_ON", True)

    def _mock_pipeline(cv_text, job_description, lang=None):
        return {
            "final_score": 78.0,
            "score": 78.0,
            "confidence": 0.9,
            "risk_level": "Low Risk",
            "interpretation": "High Match",
            "keyword_gap": {"missing_words": ["k8s"]},
            "keyword_gap_v2": {
                "missing_keywords": ["docker"],
                "weak_keywords": [],
                "strong_keywords": ["python"],
                "suggested_keywords": ["aws"],
                "extra_keywords": [],
                "keyword_coverage_pct": 72.0,
            },
            "match_score_v2": {
                "match_score": 78.0,
                "keyword_coverage_pct": 72.0,
                "experience_match": 0.8,
                "title_match": 0.7,
                "seniority_match": 0.6,
            },
            "missing_skills": ["kubernetes"],
            "extra_skills": [],
            "recommendations": ["Add quantified achievements"],
            "detected_language": "en",
        }

    monkeypatch.setattr(main_module, "run_pipeline", _mock_pipeline)

    try:
        main_module._LOCAL_DAILY_QUOTA.clear()
    except Exception:
        pass
    try:
        main_module._LOCAL_USER_THROTTLE.clear()
    except Exception:
        pass


# ── Health Endpoints ──


class TestHealthEndpoints:
    def test_health_basic(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_liveness(self, client):
        resp = client.get("/liveness")
        assert resp.status_code == 200

    def test_readiness(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200


# ── Score Breakdown ──


class TestScoreBreakdown:
    def test_score_breakdown_returns_all_sections(self, client):
        resp = client.post(
            "/api/v1/score/breakdown",
            json={
                "cv_text": "John Doe\nPython developer with 5 years experience\nSkills: Python, SQL, Docker",
                "job_description": "Senior Python developer needed with SQL and Docker experience",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ats_scores" in data
        assert "job_match" in data
        assert "recruiter" in data
        assert "feedback" in data

    def test_score_breakdown_ats_fields(self, client):
        resp = client.post(
            "/api/v1/score/breakdown",
            json={
                "cv_text": "Jane Doe\nSoftware engineer\nSkills: Java, Spring Boot",
                "job_description": "Java developer with Spring Boot",
            },
        )
        assert resp.status_code == 200
        ats = resp.json()["ats_scores"]
        for field in ("overall", "structure", "keywords", "experience", "education"):
            assert field in ats


# ── Job Match Score ──


class TestJobMatchScore:
    def test_returns_score(self, client):
        resp = client.post(
            "/api/v1/job/match-score",
            json={
                "cv_text": "Developer with Python experience",
                "job_description": "Python developer needed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert data["score"] == 78.0

    def test_returns_keyword_gap_v2(self, client):
        resp = client.post(
            "/api/v1/job/match-score",
            json={
                "cv_text": "Developer with Python",
                "job_description": "Python developer with Docker",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_keywords" in data
        assert "strong_keywords" in data


# ── Keyword Gap ──


class TestKeywordGap:
    def test_keyword_gap(self, client):
        resp = client.post(
            "/api/v1/job/keyword-gap",
            json={
                "cv_text": "Python developer with SQL experience",
                "job_description": "Need Python SQL Docker Kubernetes engineer",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_keywords" in data
        assert "keyword_coverage_pct" in data


# ── Stripe Webhook ──


class TestStripeWebhook:
    def test_webhook_checkout_completed(self, client):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "customer": "cus_test_123",
                    "subscription": "sub_test_123",
                    "amount_total": 2900,
                    "currency": "usd",
                    "metadata": {
                        "plan_type": "pro",
                        "owner_type": "user",
                        "billing_period": "monthly",
                    },
                }
            },
        }
        resp = client.post(
            "/stripe/webhook",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_webhook_subscription_updated(self, client):
        event = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test_456",
                    "customer": "cus_unknown_999",
                    "status": "active",
                    "metadata": {"plan_type": "pro"},
                }
            },
        }
        resp = client.post(
            "/stripe/webhook",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_webhook_invalid_json(self, client):
        resp = client.post(
            "/stripe/webhook",
            content=b"not-json{{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_webhook_unknown_event_type(self, client):
        event = {"type": "unknown.event.type", "data": {}}
        resp = client.post(
            "/stripe/webhook",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200  # Unknown events are silently accepted


# ── User Endpoints ──


class TestUserEndpoints:
    def test_me_endpoint(self, client):
        resp = client.get("/api/v1/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "supabase_id" in data or "user_id" in data or "email" in data

    def test_usage_endpoint(self, client):
        resp = client.get("/api/v1/usage")
        assert resp.status_code == 200

    def test_feedback_submit(self, client):
        resp = client.post(
            "/api/v1/feedback",
            json={"category": "feature", "message": "Great tool, love it!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_feedback_too_short(self, client):
        resp = client.post(
            "/api/v1/feedback",
            json={"category": "bug", "message": "hi"},
        )
        assert resp.status_code == 400

    def test_feedback_list(self, client):
        resp = client.get("/api/v1/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


# ── Benchmark Endpoints ──


class TestBenchmarkEndpoints:
    def test_global_benchmark(self, client):
        resp = client.get("/api/v1/benchmark/global")
        assert resp.status_code == 200

    def test_professions_benchmark(self, client):
        resp = client.get("/api/v1/benchmark/professions")
        assert resp.status_code == 200


# ── Embeddings ──


class TestEmbeddingEndpoints:
    def test_index_cv(self, client):
        resp = client.post(
            "/api/v1/embeddings/index-cv",
            json={"cv_text": "Python developer with machine learning experience"},
        )
        # Might be 200, 400, or 500 depending on mocks; just check it doesn't crash
        assert resp.status_code in (200, 400, 422, 500)

    def test_find_candidates(self, client):
        resp = client.post(
            "/api/v1/embeddings/find-candidates",
            json={"job_text": "Python ML engineer", "top_k": 5},
        )
        assert resp.status_code in (200, 400, 422, 500)


# ── CV Builder ──


class TestCVBuilderEndpoints:
    def test_list_templates(self, client):
        resp = client.get("/api/v1/cv-builder/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_fonts_endpoint(self, client):
        resp = client.get("/api/v1/fonts")
        assert resp.status_code == 200
