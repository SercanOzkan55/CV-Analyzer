"""Spending controls must block providers and fail closed without shared quotas."""

import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from core import quota
from core.cost_policy import paid_ai_enabled
from services import ai_client_factory, blog_moderation_service


@pytest.mark.parametrize("value", ["0", "false", "off", "", "invalid"])
def test_disabled_policy_blocks_both_factories_even_with_keys(monkeypatch, value):
    monkeypatch.setenv("PAID_AI_ENABLED", value)
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "unused-test-key")
    assert not paid_ai_enabled()
    assert ai_client_factory.get_ai_client_and_model() == (None, None)
    assert ai_client_factory.get_embedding_client_and_model() == (None, None)


def test_mock_embeddings_do_not_fall_back_to_paid_key(monkeypatch):
    monkeypatch.setenv("PAID_AI_ENABLED", "1")
    monkeypatch.setenv("REWRITE_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-key")
    assert ai_client_factory.get_embedding_client_and_model() == (None, None)


def test_disabled_ai_blocks_even_admin_before_plan_resolution(monkeypatch):
    from services.ai_feature_service import ensure_ai_rewrite_allowed

    monkeypatch.setenv("PAID_AI_ENABLED", "0")
    with pytest.raises(HTTPException) as exc:
        ensure_ai_rewrite_allowed(None, SimpleNamespace(role="admin"))
    assert exc.value.status_code == 503


def test_disabled_rewrite_does_not_return_fake_ai_result(monkeypatch):
    from services.rewrite_service import _generate

    monkeypatch.setenv("PAID_AI_ENABLED", "0")
    with pytest.raises(HTTPException) as exc:
        _generate("Rewrite this CV")
    assert exc.value.status_code == 503


def test_embedding_switch_blocks_existing_client(monkeypatch):
    # conftest stubs this service; load the real source under a separate name.
    spec = importlib.util.spec_from_file_location(
        "spending_policy_embedding", Path(__file__).parents[1] / "services/embedding_service.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setenv("PAID_AI_ENABLED", "0")
    spec.loader.exec_module(module)
    client = Mock()
    monkeypatch.setattr(module, "client", client)
    assert module.get_embedding("A CV") is None
    client.embeddings.create.assert_not_called()


@pytest.mark.parametrize("required,allowed", [("0", True), ("1", False)])
def test_disabled_moderation_preserves_required_policy(monkeypatch, required, allowed):
    import openai

    provider = Mock(side_effect=AssertionError("Provider must not be created"))
    monkeypatch.setattr(openai, "OpenAI", provider)
    monkeypatch.setenv("PAID_AI_ENABLED", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-key")
    monkeypatch.setenv("BLOG_REQUIRE_AI_MODERATION", required)
    assert blog_moderation_service.moderate_text("Useful CV writing advice.").allowed is allowed
    provider.assert_not_called()


@pytest.mark.parametrize("redis_client", [None, Mock(incr=Mock(side_effect=ConnectionError))])
def test_cost_guard_fails_closed_when_shared_store_unavailable(monkeypatch, redis_client):
    monkeypatch.setenv("COST_GUARD_REQUIRE_REDIS", "1")
    monkeypatch.setattr(quota, "_get_redis_rate", lambda: redis_client)
    with pytest.raises(HTTPException) as exc:
        quota._check_cost_guard("test", 100)
    assert exc.value.status_code == 503


def test_cost_guard_blocks_at_cap_and_uses_istanbul_midnight(monkeypatch):
    redis_client = Mock()
    redis_client.incr.side_effect = [1, 2]
    monkeypatch.setenv("COST_GUARD_REQUIRE_REDIS", "1")
    monkeypatch.setattr(quota, "_get_redis_rate", lambda: redis_client)
    monkeypatch.setattr(quota, "_quota_now", lambda: datetime(2026, 10, 13, 23, 59, tzinfo=ZoneInfo("Europe/Istanbul")))
    quota._check_cost_guard("test", 1)
    redis_client.expire.assert_called_once_with("cost:test:20261013", 60)
    with pytest.raises(HTTPException) as exc:
        quota._check_cost_guard("test", 1)
    assert exc.value.status_code == 429


def test_zero_cost_cap_disables_operation(monkeypatch):
    redis_client = Mock()
    redis_client.incr.return_value = 1
    monkeypatch.setattr(quota, "_get_redis_rate", lambda: redis_client)
    with pytest.raises(HTTPException) as exc:
        quota._check_cost_guard("test", 0)
    assert exc.value.status_code == 429
