"""Tests for services/domain_service.py — mock mode domain detection."""
import os
import pytest


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_SERVICES", "1")


class TestDetectOrCreateDomain:
    def test_mock_returns_dict(self):
        from services.domain_service import detect_or_create_domain
        result = detect_or_create_domain("Software engineer job description")
        assert isinstance(result, dict)
        assert "domain_id" in result
        assert "domain_name" in result

    def test_mock_returns_other(self):
        from services.domain_service import detect_or_create_domain
        result = detect_or_create_domain("any text")
        assert result["domain_name"] == "Other"

    def test_allowed_domains_list(self):
        from services.domain_service import ALLOWED_DOMAINS
        assert len(ALLOWED_DOMAINS) > 5
        assert "Other" in ALLOWED_DOMAINS
