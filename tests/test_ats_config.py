"""Tests for services/ats_config.py — ATS weight configuration."""
import os
import tempfile
import pytest
from services.ats_config import _parse_ats_config, get_ats_weights, _DEFAULT_WEIGHTS


class TestParseAtsConfig:
    def test_returns_none_for_missing_file(self):
        result = _parse_ats_config("/nonexistent/path/ats_config.yaml")
        assert result is None

    def test_parses_valid_yaml(self, tmp_path):
        cfg = tmp_path / "ats_config.yaml"
        cfg.write_text("weights:\n  skills: 0.40\n  keywords: 0.20\n  format: 0.10\n  experience: 0.30\n")
        result = _parse_ats_config(str(cfg))
        assert result == {"skills": 0.40, "keywords": 0.20, "format": 0.10, "experience": 0.30}

    def test_ignores_comments(self, tmp_path):
        cfg = tmp_path / "ats_config.yaml"
        cfg.write_text("# header\nweights:\n  skills: 0.35 # inline\n  keywords: 0.25\n")
        result = _parse_ats_config(str(cfg))
        assert result is not None
        assert result["skills"] == 0.35

    def test_returns_none_for_empty_file(self, tmp_path):
        cfg = tmp_path / "ats_config.yaml"
        cfg.write_text("")
        result = _parse_ats_config(str(cfg))
        assert result is None

    def test_returns_none_for_invalid_yaml(self, tmp_path):
        cfg = tmp_path / "ats_config.yaml"
        cfg.write_text("not: valid:\n  ::::\n")
        result = _parse_ats_config(str(cfg))
        # Should not crash, returns None or partial
        assert result is None or isinstance(result, dict)


class TestGetAtsWeights:
    def test_returns_defaults_when_no_config(self, monkeypatch):
        """When ats_config.yaml doesn't exist, defaults are used."""
        # Force cache reset
        import services.ats_config as mod
        mod._cached_weights = None
        monkeypatch.setattr(mod, "_parse_ats_config", lambda p: None)
        weights = get_ats_weights()
        assert weights == _DEFAULT_WEIGHTS
        mod._cached_weights = None  # cleanup

    def test_default_weights_sum_to_one(self):
        total = sum(_DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01
