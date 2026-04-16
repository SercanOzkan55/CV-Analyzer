from datetime import datetime

import main


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


def test_redis_daily_quota_enforced(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())

    allowed = []
    for _ in range(4):
        quota = main._consume_daily_quota("test-user-123", limit=3)
        allowed.append(quota["allowed"])

    assert allowed == [True, True, True, False]


def test_usage_status_reads_redis_quota(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())

    # Consume two units
    main._consume_daily_quota("test-user-123", limit=3)
    main._consume_daily_quota("test-user-123", limit=3)

    data = main._get_daily_quota_status("test-user-123", limit=3)
    assert data["source"] == "redis"
    assert data["used"] == 2
    assert data["limit"] == 3
    assert data["remaining"] == 1


def test_daily_quota_key_format():
    key = main._daily_quota_key("u-1", now=datetime(2026, 3, 6))
    assert key == "quota:daily:u-1:20260306"


def test_user_rate_limit_enforced(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())

    allowed = []
    for _ in range(4):
        throttle = main._consume_user_rate_limit("test-user-123", 3, "analyze")
        allowed.append(throttle["allowed"])

    assert allowed == [True, True, True, False]


def test_user_rate_limit_key_contains_scope(monkeypatch):
    monkeypatch.setattr(main, "redis_rate", FakeRedis())
    throttle = main._consume_user_rate_limit("test-user-abc", 20, "analyze-pdf")
    assert "throttle:user:analyze-pdf:test-user-abc:" in throttle["key"]


def test_resolve_daily_limit_for_plan_uses_plan_mapping(monkeypatch):
    monkeypatch.setattr(
        main,
        "USER_PLAN_LIMITS_DAILY",
        {"free": 5, "pro": 100, "enterprise": 1000},
    )

    assert main._resolve_daily_limit_for_plan("pro") == 100
    assert main._resolve_daily_limit_for_plan("enterprise") == 1000
    assert main._resolve_daily_limit_for_plan("unknown") == 5


def test_resolve_daily_limit_for_free_prefers_redis_override(monkeypatch):
    monkeypatch.setattr(
        main,
        "USER_PLAN_LIMITS_DAILY",
        {"free": 5, "pro": 100, "enterprise": 1000},
    )
    monkeypatch.setenv("REDIS_FREE_DAILY_LIMIT", "7")

    assert main._resolve_daily_limit_for_plan("free") == 7
