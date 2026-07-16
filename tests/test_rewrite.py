"""Tests for services/rewrite_service.py — text rewriting (mock provider)."""

import os
import pytest
from services.rewrite_service import (
    _guard_text,
    _select_provider,
    _normalize_mode,
    _normalize_rewrite_mode,
    _extract_keywords,
    _mock_generate,
    ai_rewrite_available,
    ai_rewrite_cv,
    rewrite_cv_for_ats,
    rewrite_bullets,
)


@pytest.fixture(autouse=True)
def mock_provider(monkeypatch):
    monkeypatch.setenv("REWRITE_PROVIDER", "mock")


class TestGuardText:
    def test_strips_whitespace(self):
        assert _guard_text("  hello  ", 100, "test") == "hello"

    def test_truncates_long_text(self):
        result = _guard_text("a" * 200, 100, "test")
        assert len(result) == 100

    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _guard_text("", 100, "test_field")

    def test_converts_none(self):
        with pytest.raises(ValueError):
            _guard_text(None, 100, "test")


class TestSelectProvider:
    def test_mock_by_default(self):
        assert _select_provider() == "mock"


class TestNormalizeMode:
    def test_valid_mode(self):
        assert _normalize_mode("junior") == "junior"

    def test_invalid_falls_to_senior(self):
        assert _normalize_mode("invalid") == "senior"

    def test_none_defaults_senior(self):
        assert _normalize_mode(None) == "senior"


class TestNormalizeRewriteMode:
    def test_valid_modes(self):
        assert _normalize_rewrite_mode("ats_strict") == "ats_strict"
        assert _normalize_rewrite_mode("one_page") == "one_page"

    def test_invalid_defaults_senior(self):
        assert _normalize_rewrite_mode("xyz") == "senior"


class TestExtractKeywords:
    def test_extracts_tokens(self):
        result = _extract_keywords("Python developer with React and Docker experience")
        assert "python" in result
        assert "react" in result
        assert "docker" in result

    def test_removes_stopwords(self):
        result = _extract_keywords("and the for work using")
        assert "and" not in result
        assert "the" not in result

    def test_max_items(self):
        text = " ".join(f"skill{i}" for i in range(50))
        result = _extract_keywords(text, max_items=5)
        assert len(result) <= 5

    def test_deduplicates(self):
        result = _extract_keywords("python python python")
        assert result.count("python") == 1


class TestMockGenerate:
    def test_returns_mock_prefix(self):
        result = _mock_generate("Rewrite this text")
        assert result.startswith("[mock-rewrite]")


class TestAiRewriteAvailable:
    def test_mock_not_available(self):
        assert ai_rewrite_available() is False


class TestAiRewriteCv:
    def test_returns_string(self):
        result = ai_rewrite_cv("Experienced engineer with Python skills")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_prefix(self):
        result = ai_rewrite_cv("Some CV text")
        assert "[mock-rewrite]" in result

    def test_requested_language_translation_preserves_factual_names(self, monkeypatch):
        captured = {}

        def fake_generate(prompt, **_kwargs):
            captured["prompt"] = prompt
            return "Translated CV"

        monkeypatch.setattr("services.rewrite_service._generate", fake_generate)

        result = rewrite_cv_for_ats("Sercan Ozkan\nDasal Havacilik", lang="en")

        assert result == "Translated CV"
        assert "Write the complete CV in the requested language" in captured["prompt"]
        assert "Never translate or alter personal names" in captured["prompt"]


class TestRewriteBullets:
    def test_returns_list(self):
        result = rewrite_bullets(["Led team of 5", "Built API"])
        assert isinstance(result, list)
        assert len(result) > 0
