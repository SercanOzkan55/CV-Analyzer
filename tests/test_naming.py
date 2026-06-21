"""Tests for services/naming_service.py — mock mode name generation."""

import os
import pytest
from services.naming_service import generate_primary_name, generate_specialization_name


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_SERVICES", "1")


class TestGeneratePrimaryName:
    def test_returns_string(self):
        result = generate_primary_name("Software engineer with Python")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_returns_default(self):
        result = generate_primary_name("test text")
        # In mock mode returns "Engineering & Technology" or similar
        assert isinstance(result, str)


class TestGenerateSpecializationName:
    def test_returns_string(self):
        result = generate_specialization_name("Data analyst role")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_returns_default(self):
        result = generate_specialization_name("test")
        assert isinstance(result, str)
