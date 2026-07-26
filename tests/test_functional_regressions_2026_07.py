import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from core.quota import (
    _reset_api_subscription_usage_if_needed,
    _reset_organization_usage_if_needed,
)
from routes.analysis import _analysis_recommendations
from routes.recruiter import _normalize_recruiter_event_date
from services import rewrite_service
from services.tasks import persist_analysis_result


def test_analysis_recommendations_use_percentage_scale():
    assert _analysis_recommendations(1)[0].startswith("Consider upskilling")
    assert _analysis_recommendations(60)[0].startswith("Good potential")
    assert _analysis_recommendations(80)[0].startswith("Strong match")


def test_organization_usage_resets_at_day_and_month_boundaries():
    organization = SimpleNamespace(
        daily_usage=7,
        monthly_usage=19,
        usage_reset_at=datetime(2026, 6, 30, 12, 0),
    )

    changed = _reset_organization_usage_if_needed(
        organization,
        datetime(2026, 7, 1, 9, 0),
    )

    assert changed is True
    assert organization.daily_usage == 0
    assert organization.monthly_usage == 0


def test_api_subscription_usage_resets_for_new_billing_month():
    subscription = SimpleNamespace(
        monthly_usage=40,
        monthly_reset_day=15,
        usage_reset_at=datetime(2026, 6, 20, 9, 0),
        last_used_at=datetime(2026, 6, 20, 9, 0),
        created_at=datetime(2026, 5, 1, 9, 0),
    )

    changed = _reset_api_subscription_usage_if_needed(
        subscription,
        datetime(2026, 7, 20, 9, 0),
    )

    assert changed is True
    assert subscription.monthly_usage == 0


def test_recruiter_reminder_accepts_timezone_aware_iso_value():
    future = datetime.now(timezone.utc) + timedelta(days=2)

    normalized = _normalize_recruiter_event_date(future.isoformat().replace("+00:00", "Z"))

    assert normalized.tzinfo is None
    assert normalized > datetime.utcnow()


def test_mock_interview_generator_honors_requested_count(monkeypatch):
    monkeypatch.setattr(rewrite_service, "ai_rewrite_available", lambda: False)

    questions = rewrite_service.generate_interview_questions(
        cv_text="Senior Python engineer with distributed systems experience.",
        job_description="Build reliable APIs and mentor engineers.",
        lang="en",
        mode="senior",
        count=10,
    )

    assert len(questions) == 10
    assert len({item["question"] for item in questions}) == 10


def test_processing_status_falls_back_to_in_memory(monkeypatch):
    import redis
    from utils import cv_processor

    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    cv_processor._PROCESSING_STATUS.clear()

    asyncio.run(cv_processor.set_processing_status("session-1", {"status": "queued"}))
    status = asyncio.run(cv_processor.get_processing_status("session-1"))

    assert status["status"] == "queued"


def test_async_result_persistence_creates_history_record(db_session):
    from models import Analysis, User

    user = User(
        supabase_id="async-functional-user",
        email="async-functional@example.com",
        plan_type="free",
        role="individual",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    result = persist_analysis_result(
        {
            "final_score": 72,
            "interpretation": "Good match",
            "confidence": 80,
            "risk_level": "Low Risk",
            "domain": {"domain_id": 1},
            "industry": {"industry_id": 1},
            "specialization": {"id": 1},
            "recommendations": ["Prepare examples"],
        },
        user_id=user.id,
        organization_id=None,
        cv_text="Python engineer",
        job_description="Senior Python engineer",
        db=db_session,
    )

    stored = db_session.query(Analysis).filter(Analysis.id == result["analysis_id"]).one()
    assert stored.user_id == user.id
    assert stored.similarity_score == 72
