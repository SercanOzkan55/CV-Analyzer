"""Tests for services/billing_service.py — plan normalization and entitlements."""
import pytest
from services.billing_service import normalize_plan, get_entitlements, is_feature_enabled


class TestNormalizePlan:
    def test_free_default(self):
        assert normalize_plan(None) == "free"
        assert normalize_plan("") == "free"

    def test_known_plans(self):
        assert normalize_plan("pro") == "pro"
        assert normalize_plan("PRO") == "pro"
        assert normalize_plan("enterprise") == "enterprise"
        assert normalize_plan("admin") == "admin"

    def test_unknown_falls_to_free(self):
        assert normalize_plan("platinum") == "free"
        assert normalize_plan("random") == "free"

    def test_whitespace_stripped(self):
        assert normalize_plan("  pro  ") == "pro"


class TestGetEntitlements:
    def test_free_plan(self):
        ent = get_entitlements("free")
        assert ent["plan"] == "free"
        assert ent["ai_rewrite"] is False
        assert ent["daily_cv_limit"] >= 1

    def test_pro_plan(self):
        ent = get_entitlements("pro")
        assert ent["plan"] == "pro"
        assert ent["ai_rewrite"] is True
        assert ent["recruiter_dashboard"] is False

    def test_enterprise_plan(self):
        ent = get_entitlements("enterprise")
        assert ent["recruiter_dashboard"] is True

    def test_admin_plan(self):
        ent = get_entitlements("admin")
        assert ent["daily_cv_limit"] == 999999

    def test_returns_copy(self):
        ent1 = get_entitlements("free")
        ent2 = get_entitlements("free")
        ent1["daily_cv_limit"] = 999
        assert ent2["daily_cv_limit"] != 999


class TestIsFeatureEnabled:
    def test_ai_rewrite_disabled_for_free(self):
        assert is_feature_enabled("free", "ai_rewrite") is False

    def test_ai_rewrite_enabled_for_pro(self):
        assert is_feature_enabled("pro", "ai_rewrite") is True

    def test_recruiter_dashboard_enterprise(self):
        assert is_feature_enabled("enterprise", "recruiter_dashboard") is True

    def test_nonexistent_feature(self):
        assert is_feature_enabled("pro", "nonexistent_feature") is False
