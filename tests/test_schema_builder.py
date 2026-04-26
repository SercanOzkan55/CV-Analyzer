"""Tests for services/schema_builder.py — mapping normalized data to CVSchema."""
import pytest
from services.schema_builder import (
    build_schema,
    _clean,
    _clean_list,
    _clean_bullets,
    _is_language_item,
    _enforce_summary_rules,
)


class TestClean:
    def test_normalizes_whitespace(self):
        assert _clean("  hello   world  ") == "hello world"

    def test_handles_none(self):
        assert _clean(None) == ""

    def test_unicode_normalization(self):
        # NFC normalization
        result = _clean("café")
        assert "café" in result or "cafe" in result


class TestCleanList:
    def test_filters_empty(self):
        assert _clean_list(["hello", "", " ", "world"]) == ["hello", "world"]

    def test_none_input(self):
        assert _clean_list(None) == []


class TestCleanBullets:
    def test_strips_bullet_markers(self):
        result = _clean_bullets(["- Led team", "• Built API", "* Deployed"])
        assert result[0] == "Led team"
        assert result[1] == "Built API"

    def test_filters_empty(self):
        result = _clean_bullets(["- ", "", "Valid bullet"])
        assert len(result) == 1


class TestIsLanguageItem:
    def test_english_native(self):
        assert _is_language_item("English - Native") is True

    def test_cefr_level(self):
        assert _is_language_item("German B2") is True

    def test_not_language(self):
        assert _is_language_item("Python") is False

    def test_empty(self):
        assert _is_language_item("") is False


class TestEnforceSummaryRules:
    def test_prose_passes(self):
        text = "Experienced software engineer with 10 years of Python development."
        result = _enforce_summary_rules(text)
        assert "Experienced" in result

    def test_empty_returns_empty(self):
        assert _enforce_summary_rules("") == ""

    def test_skill_list_rejected(self):
        text = "Python, Java, Docker, Kubernetes, AWS, React, Node.js"
        result = _enforce_summary_rules(text)
        assert result == ""

    def test_strips_emails(self):
        text = "Great engineer. Contact: john@example.com for details."
        result = _enforce_summary_rules(text)
        assert "john@example.com" not in result


class TestBuildSchema:
    def test_basic_mapping(self):
        normalized = {
            "full_name": "John Doe",
            "title": "Software Engineer",
            "email": "john@example.com",
            "phone": "+1234567890",
            "summary": "Experienced developer.",
            "experience": [
                {
                    "title": "Senior Dev",
                    "company": "Acme Inc",
                    "start_date": "2020",
                    "end_date": "Present",
                    "bullets": ["Led team of 5"],
                },
            ],
            "education": [
                {
                    "degree": "BS",
                    "field": "CS",
                    "school": "MIT",
                    "start_date": "2016",
                    "end_date": "2020",
                },
            ],
            "skills": ["Python", "Docker"],
            "languages": ["English"],
        }
        schema = build_schema(normalized)
        assert schema.full_name == "John Doe"
        assert len(schema.experiences) >= 1
        assert len(schema.education) >= 1

    def test_empty_normalized(self):
        schema = build_schema({})
        assert schema.full_name == ""
        assert schema.experiences == []
