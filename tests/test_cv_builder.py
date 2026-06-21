"""Tests for services/cv_builder_service.py — pure utility functions."""

import pytest
from services.cv_builder_service import (
    _normalize_text,
    _fix_case,
    _dedupe_preserve,
    _sanitize_prompt_text,
    _truncate_text,
    _is_safe_mode,
    _normalize_link_value,
    _estimate_content_size,
    INSTANCE_ID,
)


class TestNormalizeText:
    def test_strips_markdown(self):
        assert _normalize_text("**bold**") == "bold"

    def test_handles_none(self):
        result = _normalize_text(None)
        assert isinstance(result, str)

    def test_normalises_newlines(self):
        result = _normalize_text("line1\r\nline2")
        assert "\r" not in result


class TestFixCase:
    def test_known_acronyms(self):
        assert _fix_case("html") == "HTML"
        assert _fix_case("css") == "CSS"
        assert _fix_case("python") == "Python"

    def test_unknown_preserved(self):
        assert _fix_case("SomeFramework") == "SomeFramework"


class TestDedupePreserve:
    def test_removes_duplicates(self):
        result = _dedupe_preserve(["Python", "python", "Java", "PYTHON"])
        assert len(result) == 2  # Python + Java

    def test_preserves_order(self):
        result = _dedupe_preserve(["C", "B", "A"])
        assert result == ["C", "B", "A"]

    def test_filters_empty(self):
        result = _dedupe_preserve(["Python", "", " ", "Java"])
        assert result == ["Python", "Java"]

    def test_none_input(self):
        assert _dedupe_preserve(None) == []


class TestSanitizePromptText:
    def test_strips_script_tags(self):
        result = _sanitize_prompt_text("<script>alert('x')</script>hello", 1000)
        assert "<script>" not in result

    def test_truncates(self):
        result = _sanitize_prompt_text("a" * 200, 100)
        assert len(result) == 100

    def test_strips_null_bytes(self):
        result = _sanitize_prompt_text("hello\x00world", 100)
        assert "\x00" not in result


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert _truncate_text("hello", 100) == "hello"

    def test_long_text_truncated(self):
        result = _truncate_text("a" * 200, 100)
        assert len(result) <= 100


class TestIsSafeMode:
    def test_returns_bool(self):
        assert isinstance(_is_safe_mode(), bool)


class TestNormalizeLinkValue:
    def test_empty(self):
        result = _normalize_link_value("")
        assert result == ""


class TestEstimateContentSize:
    def test_empty_dict(self):
        result = _estimate_content_size({})
        assert isinstance(result, int)

    def test_with_experience(self):
        cv_data = {"experience": [{"title": "Dev", "bullets": ["Built APIs"]}]}
        result = _estimate_content_size(cv_data)
        assert result > 0


class TestInstanceId:
    def test_is_string(self):
        assert isinstance(INSTANCE_ID, str)
        assert len(INSTANCE_ID) > 0
