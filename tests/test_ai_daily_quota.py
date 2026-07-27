"""AI-feature daily quota: separate budget, enforced per plan."""

import pytest
from fastapi import HTTPException

import main
from core.quota import (
    _ai_daily_quota_key,
    _consume_ai_daily_quota,
    _daily_quota_key,
    _resolve_ai_daily_limit_for_plan,
)
from services.ai_feature_service import _enforce_ai_daily_limit
from services.billing_service import is_feature_enabled


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.expiry = {}

    def get(self, key):
        return self.store.get(key)

    def incr(self, key):
        current = int(self.store.get(key) or 0) + 1
        self.store[key] = str(current)
        return current

    def ttl(self, key):
        return self.expiry.get(key, -1)

    def expire(self, key, seconds):
        self.expiry[key] = int(seconds)
        return True


class FakeUser:
    def __init__(self, supabase_id="user-abc"):
        self.supabase_id = supabase_id
        self.id = 1


def test_free_plan_can_use_ai_tools():
    # Arrange / Act / Assert — beta opens AI tools to everyone.
    assert is_feature_enabled("free", "ai_rewrite") is True


def test_free_plan_ai_limit_is_two():
    assert _resolve_ai_daily_limit_for_plan("free") == 2


def test_ai_quota_stops_after_plan_limit(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())

    allowed = [_consume_ai_daily_quota("u1", limit=2)["allowed"] for _ in range(4)]

    assert allowed == [True, True, False, False]


def test_ai_quota_uses_a_separate_key_from_cv_quota():
    assert _ai_daily_quota_key("u1") != _daily_quota_key("u1")
    assert _ai_daily_quota_key("u1").startswith("quota:ai:")


def test_enforce_raises_429_once_exhausted(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())
    user = FakeUser()

    _enforce_ai_daily_limit(user, "free")
    _enforce_ai_daily_limit(user, "free")

    with pytest.raises(HTTPException) as exc:
        _enforce_ai_daily_limit(user, "free")

    assert exc.value.status_code == 429
    assert "Daily AI limit" in str(exc.value.detail)


def test_admin_is_not_rate_limited(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())
    user = FakeUser("admin-user")

    for _ in range(20):
        _enforce_ai_daily_limit(user, "admin")
