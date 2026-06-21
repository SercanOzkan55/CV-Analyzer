"""Tests for services/industry_service.py — mock mode industry detection."""

import os
import pytest


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_SERVICES", "1")


class TestDetectIndustryAndSpecialization:
    def test_mock_returns_dict(self):
        from services.industry_service import detect_industry_and_specialization

        result = detect_industry_and_specialization("Python developer at tech company")
        assert isinstance(result, dict)
        assert "industry_id" in result
        assert "industry_name" in result
        assert "specialization_id" in result
        assert "specialization_name" in result

    def test_mock_returns_technology(self):
        from services.industry_service import detect_industry_and_specialization

        result = detect_industry_and_specialization("any text")
        assert result["industry_name"] == "Technology"
        assert result["specialization_name"] == "Software Development"
