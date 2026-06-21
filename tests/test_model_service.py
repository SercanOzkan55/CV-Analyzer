"""Tests for services/model_service.py — model predictions with mocking."""

import os
import pytest
from services.model_service import is_mock, predict_hire, predict_match


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_SERVICES", "1")


class TestIsMock:
    def test_returns_true_in_mock_mode(self):
        assert is_mock() is True

    def test_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.setenv("MOCK_SERVICES", "0")
        assert is_mock() is False


class TestPredictHire:
    def test_mock_returns_tuple(self):
        decision, prob = predict_hire([50, 60, 70, 80])
        assert isinstance(decision, bool)
        assert isinstance(prob, float)

    def test_mock_returns_default_values(self):
        decision, prob = predict_hire([])
        assert decision is False
        assert prob == 0.5


class TestPredictMatch:
    def test_mock_returns_four_tuple(self):
        result = predict_match([50, 60, 70, 80])
        assert len(result) == 4
        score, confidence, risk, explanation = result
        assert score == 50.0
        assert confidence == 50.0
        assert risk == "High Risk"
        assert isinstance(explanation, dict)

    def test_mock_includes_feature_count(self):
        features = [1, 2, 3, 4, 5]
        _, _, _, explanation = predict_match(features)
        assert explanation.get("features_count") == 5
