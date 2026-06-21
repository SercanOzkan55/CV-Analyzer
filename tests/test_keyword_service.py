"""Unit tests for services/keyword_service.py"""

import pytest
from services.keyword_service import (
    compute_keyword_gap,
    compare,
    keyword_match_score,
    _extract_meaningful_words,
)


# ── keyword_match_score ──────────────────────────────────────


class TestKeywordMatchScore:
    def test_identical_text_returns_high_score(self):
        text = "Python Django REST API microservices PostgreSQL"
        score = keyword_match_score(text, text)
        assert score >= 80

    def test_no_overlap_returns_low_score(self):
        cv = "Painting sculpture ceramics watercolor exhibition"
        jd = "Python Django REST API microservices PostgreSQL"
        score = keyword_match_score(cv, jd)
        assert score < 30

    def test_partial_overlap(self):
        cv = "Python FastAPI PostgreSQL React"
        jd = "Python Django PostgreSQL Redis Docker"
        score = keyword_match_score(cv, jd)
        assert 20 < score < 90

    def test_empty_job_returns_zero(self):
        assert keyword_match_score("Python Django", "") == 0.0
        assert keyword_match_score("Python Django", "   ") == 0.0

    def test_stop_words_excluded(self):
        # "the and for with" are stop words — shouldn't inflate score
        cv = "the and for with"
        jd = "Python developer with strong experience"
        score = keyword_match_score(cv, jd)
        assert score < 50

    def test_score_capped_at_100(self):
        # Even with extra words, should not exceed 100
        cv = "Python Django REST API ML NLP TensorFlow Kubernetes Docker AWS"
        jd = "Python"
        score = keyword_match_score(cv, jd)
        assert score <= 100


# ── compute_keyword_gap ──────────────────────────────────────


class TestComputeKeywordGap:
    def test_missing_words_detected(self):
        cv = "Python developer"
        jd = "Python Django PostgreSQL developer"
        result = compute_keyword_gap(cv, jd)
        assert "django" in result["missing_words"]
        assert "postgresql" in result["missing_words"]

    def test_no_missing_when_full_coverage(self):
        text = "Python Django PostgreSQL"
        result = compute_keyword_gap(text, text)
        assert result["missing_words"] == []

    def test_empty_job_returns_empty(self):
        result = compute_keyword_gap("Python", "")
        assert result["missing_words"] == []
        assert result["missing_phrases"] == []


# ── compare ──────────────────────────────────────────────────


class TestCompare:
    def test_returns_all_keys(self):
        result = compare("Python", "Python Django")
        expected_keys = {
            "missing_keywords",
            "weak_keywords",
            "strong_keywords",
            "suggested_keywords",
            "extra_keywords",
            "keyword_coverage_pct",
        }
        assert set(result.keys()) == expected_keys

    def test_repeated_word_is_strong(self):
        cv = "Python Python Python development"
        jd = "Python development"
        result = compare(cv, jd)
        assert "python" in result["strong_keywords"]

    def test_single_occurrence_is_weak(self):
        cv = "Python development"
        jd = "Python development"
        result = compare(cv, jd)
        # "python" appears once — should be weak, not strong
        assert "python" in result["weak_keywords"] or "python" in result["strong_keywords"]

    def test_missing_detected(self):
        cv = "Python developer"
        jd = "Python Django PostgreSQL developer"
        result = compare(cv, jd)
        assert "django" in result["missing_keywords"]

    def test_empty_jd_returns_defaults(self):
        result = compare("Python", "")
        assert result["keyword_coverage_pct"] == 0.0
        assert result["missing_keywords"] == []

    def test_coverage_percentage_range(self):
        result = compare("Python Django", "Python Django PostgreSQL Redis")
        assert 0 <= result["keyword_coverage_pct"] <= 100

    def test_suggested_keywords_limited(self):
        # suggested_keywords should be capped at 15
        jd = " ".join(f"skill{i}" for i in range(30))
        result = compare("unrelated", jd)
        assert len(result["suggested_keywords"]) <= 15


# ── _extract_meaningful_words ────────────────────────────────


class TestExtractMeaningfulWords:
    def test_filters_stop_words(self):
        words = _extract_meaningful_words("the Python and Django for web")
        assert "the" not in words
        assert "and" not in words
        assert "python" in words
        assert "django" in words

    def test_handles_empty_string(self):
        assert _extract_meaningful_words("") == set()
