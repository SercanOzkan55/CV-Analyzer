"""Tests for billing endpoints: checkout, portal, contact-sales, activate-trial."""

import os
import pytest
import main as main_module


@pytest.fixture(autouse=True)
def _billing_env(monkeypatch):
    """Enable MOCK_SERVICES so billing endpoints don't call real Stripe."""
    monkeypatch.setattr(main_module, "MOCK_SERVICES_ON", True)
    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "CLAMAV_ENABLED", False)
    monkeypatch.setenv("DEV_ALLOW_SELF_PREMIUM", "1")
    monkeypatch.setenv("BILLING_REDIRECT_ALLOWED_ORIGINS", "http://localhost:5173")


# ── Checkout Session ──


class TestCheckoutSession:
    def test_creates_mock_checkout(self, client):
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={"plan_type": "pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "mock"
        assert data["plan_type"] == "pro"
        assert "session_id" in data

    def test_defaults_free_to_pro(self, client):
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={"plan_type": "free"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_type"] == "pro"

    def test_enterprise_plan(self, client):
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={"plan_type": "enterprise"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_type"] == "enterprise"

    def test_rejects_untrusted_success_url(self, client):
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={
                "plan_type": "pro",
                "success_url": "https://example.com/billing/success",
            },
        )
        assert resp.status_code == 400


# ── Portal Session ──


class TestPortalSession:
    def test_returns_mock_portal_url(self, client):
        resp = client.post(
            "/api/v1/billing/portal-session",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "mock"
        assert "url" in data

    def test_custom_return_url(self, client):
        resp = client.post(
            "/api/v1/billing/portal-session",
            json={"return_url": "http://localhost:5173/dashboard"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "http://localhost:5173/dashboard"

    def test_rejects_untrusted_return_url(self, client):
        resp = client.post(
            "/api/v1/billing/portal-session",
            json={"return_url": "https://example.com/dash"},
        )
        assert resp.status_code == 400


# ── Contact Sales ──


class TestContactSales:
    def test_accepted_mock(self, client):
        resp = client.post(
            "/api/v1/billing/contact-sales",
            json={"plan_type": "enterprise", "company_name": "Acme Corp"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["mode"] == "mock"
        assert data["plan_type"] == "enterprise"

    def test_free_plan_upgraded_to_enterprise(self, client):
        resp = client.post(
            "/api/v1/billing/contact-sales",
            json={"plan_type": "free"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_type"] == "enterprise"


# ── Activate Trial ──


class TestActivateTrial:
    def test_activates_pro_trial(self, client):
        resp = client.post(
            "/api/v1/billing/activate-trial",
            json={"plan_type": "pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["plan_type"] == "pro"
        assert data["billing_status"] == "trialing"

    def test_enterprise_trial(self, client):
        resp = client.post(
            "/api/v1/billing/activate-trial",
            json={"plan_type": "enterprise"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_type"] == "enterprise"

    def test_free_defaults_to_pro(self, client):
        resp = client.post(
            "/api/v1/billing/activate-trial",
            json={"plan_type": "free"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_type"] == "pro"

    def test_blocked_when_disabled(self, monkeypatch, client):
        monkeypatch.setenv("DEV_ALLOW_SELF_PREMIUM", "0")
        resp = client.post(
            "/api/v1/billing/activate-trial",
            json={"plan_type": "pro"},
        )
        assert resp.status_code == 403
