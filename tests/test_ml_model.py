"""Tests for services/ml_model.py and services/model_runner.py."""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from services.ml_model import health_check
from services.model_runner import calibrate_confidence, get_risk_level


class TestHealthCheck:
    def test_returns_dict(self):
        result = health_check()
        assert isinstance(result, dict)
        assert "score_model" in result
        assert "hire_model" in result

    def test_models_have_status(self):
        result = health_check()
        for key in ("score_model", "hire_model"):
            assert "status" in result[key]


class TestCalibrateConfidence:
    def test_low_std_high_confidence(self):
        result = calibrate_confidence(0.0)
        assert result == 100.0

    def test_high_std_low_confidence(self):
        result = calibrate_confidence(50.0)
        assert result < 50.0

    def test_moderate_std(self):
        result = calibrate_confidence(10.0)
        assert 30.0 < result < 40.0  # exp(-1) ≈ 0.368


class TestGetRiskLevel:
    def test_high_risk_low_confidence(self):
        assert get_risk_level(80, 50) == "High Risk"

    def test_medium_risk(self):
        assert get_risk_level(40, 70) == "Medium Risk"

    def test_low_risk(self):
        assert get_risk_level(70, 80) == "Low Risk"
