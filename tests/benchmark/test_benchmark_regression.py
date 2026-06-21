"""Benchmark regression tests for keyword_service and ats_service.

These tests use the benchmark dataset to ensure that scoring changes
don't silently break expected behavior across diverse CV+JD pairs.
"""

import json
import os
import pytest
from pathlib import Path

from services.keyword_service import (
    keyword_match_score,
    compare,
    compute_keyword_gap,
    _extract_meaningful_words,
    _normalize_text,
    _best_fuzzy_match,
)
from services.ats_service import analyze_cv, compute_final_score


# ── Dataset Fixture ──────────────────────────────────────────────

BENCHMARK_PATH = Path(__file__).parent / "benchmark_dataset.json"


@pytest.fixture(scope="module")
def benchmark_entries():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["entries"]


def _get_entry(entries, entry_id: str):
    for e in entries:
        if e["id"] == entry_id:
            return e
    pytest.skip(f"Entry {entry_id} not found in dataset")


# ── Keyword Service: Fuzzy Matching Edge Cases ────────────────────


class TestKeywordFuzzyMatching:
    """Tests for difflib fuzzy matching behavior in keyword_service."""

    def test_close_spelling_variants_match(self):
        """'optimized' in CV should fuzzy-match 'optimize' in JD."""
        cv = "Optimized database queries for better performance"
        jd = "Ability to optimize SQL queries"
        score = keyword_match_score(cv, jd)
        assert score > 20, f"Fuzzy matching should catch 'optimized' ≈ 'optimize', got {score}"

    def test_plural_forms_match(self):
        """'applications' should fuzzy-match 'application'."""
        cv = "Built enterprise applications using Java"
        jd = "Experience with application development"
        score = keyword_match_score(cv, jd)
        assert score > 25, f"Plural forms should fuzzy-match, got {score}"

    def test_completely_unrelated_no_fuzzy_match(self):
        """Completely different words should NOT fuzzy-match."""
        cv = "Expert in ceramic sculpture and watercolor painting"
        jd = "Senior Kubernetes engineer with Docker expertise"
        score = keyword_match_score(cv, jd)
        assert score < 20, f"Unrelated terms should not match, got {score}"

    def test_fuzzy_threshold_env_override(self):
        """Fuzzy threshold can be overridden via environment variable."""
        cv = "Developed machine learning models"
        jd = "Machine learning engineer needed"
        # Default threshold (0.8) — should produce some match
        score_default = keyword_match_score(cv, jd)

        # Very strict threshold — fewer fuzzy matches
        os.environ["FUZZY_MATCH_THRESHOLD"] = "0.99"
        score_strict = keyword_match_score(cv, jd)
        os.environ.pop("FUZZY_MATCH_THRESHOLD", None)

        assert score_default >= score_strict, (
            f"Stricter threshold should not increase score: default={score_default}, strict={score_strict}"
        )

    def test_hyphenated_terms_normalized(self):
        """Hyphenated terms like 'real-time' should normalize properly."""
        words = _extract_meaningful_words("Built real-time systems with low-latency")
        # After normalization, hyphens become spaces, so tokens should be individual words
        assert "real" in words or "time" in words or "real time" in words
        assert "low" in words or "latency" in words or "low latency" in words

    def test_oop_expansion(self):
        """'oop' should expand to 'object-oriented'."""
        words = _extract_meaningful_words("Strong OOP skills")
        assert "object oriented" in words or "object-oriented" in words


class TestKeywordNormalization:
    """Tests for text normalization in keyword_service."""

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        assert keyword_match_score("PYTHON DJANGO", "python django") > 80

    def test_slash_separator(self):
        """Slash separators should be normalized to spaces."""
        text = _normalize_text("HTML/CSS/JavaScript")
        assert "html" in text
        assert "css" in text
        assert "javascript" in text

    def test_underscore_separator(self):
        """Underscores should be normalized to spaces."""
        text = _normalize_text("machine_learning_engineer")
        assert "machine" in text
        assert "learning" in text

    def test_empty_string(self):
        assert _normalize_text("") == ""
        assert _normalize_text(None) == ""


class TestBestFuzzyMatch:
    """Direct tests for _best_fuzzy_match helper."""

    def test_exact_match_always_found(self):
        result = _best_fuzzy_match("python", {"python", "java", "go"}, 0.8)
        assert result == "python"

    def test_close_match_found(self):
        result = _best_fuzzy_match("pythons", {"python", "java", "go"}, 0.7)
        assert result == "python"

    def test_no_match_below_cutoff(self):
        result = _best_fuzzy_match("kubernetes", {"python", "java", "go"}, 0.8)
        assert result is None

    def test_empty_candidates(self):
        result = _best_fuzzy_match("python", set(), 0.8)
        assert result is None


# ── ATS Service: ML Override Edge Cases ──────────────────────────


class TestComputeFinalScoreOverride:
    """Tests for ML-confidence override mechanism in compute_final_score."""

    def test_low_confidence_forces_rule_based(self):
        """When ml_confidence < threshold, ML should be overridden."""
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=20,  # Very different from rule-based
            ml_confidence=0.3,  # Below default 0.6 threshold
            debug=True,
        )
        assert isinstance(result, dict)
        assert result["ml_overridden"] is True
        assert result["ml_override_reason"] == "low_confidence"

    def test_high_confidence_uses_ml_blend(self):
        """When ml_confidence >= threshold and scores close, use ML blend."""
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=75,  # Close to rule-based
            ml_confidence=0.9,
            debug=True,
        )
        assert isinstance(result, dict)
        assert result["ml_overridden"] is False

    def test_large_discrepancy_overrides_ml(self):
        """When ML score is wildly different from rule-based, override."""
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=10,  # Very far from rule score
            ml_confidence=0.9,  # High confidence but wrong
            debug=True,
        )
        assert isinstance(result, dict)
        assert result["ml_overridden"] is True
        assert result["ml_override_reason"] == "large_discrepancy"

    def test_no_confidence_provided_uses_ml(self):
        """When ml_confidence is None, ML blend should be used (if close)."""
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=75,
            ml_confidence=None,
            debug=True,
        )
        assert isinstance(result, dict)
        assert result["ml_overridden"] is False

    def test_non_numeric_ml_score_overrides(self):
        """Non-numeric ml_score should gracefully override to rule-based."""
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score="not_a_number",
            ml_confidence=0.9,
            debug=True,
        )
        assert isinstance(result, dict)
        assert result["ml_overridden"] is True
        assert result["ml_override_reason"] == "ml_not_numeric"

    def test_no_keyword_redistributes_weight(self):
        """When keyword=0 (no JD), weight should be redistributed."""
        with_jd = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=0,
            ml_confidence=0.0,
        )
        without_jd = compute_final_score(
            keyword=0,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=0,
            ml_confidence=0.0,
        )
        # Both should be valid scores
        assert 0 <= with_jd <= 100
        assert 0 <= without_jd <= 100
        # Without JD, score should still be reasonable (not 0)
        assert without_jd > 30, f"No-JD score should be reasonable, got {without_jd}"

    def test_env_threshold_override(self):
        """ML_CONFIDENCE_THRESHOLD env var should control the threshold."""
        os.environ["ML_CONFIDENCE_THRESHOLD"] = "0.95"
        result = compute_final_score(
            keyword=80,
            section=70,
            exp=65,
            skills=75,
            layout=60,
            contact=80,
            ml_score=75,
            ml_confidence=0.8,  # Below 0.95
            debug=True,
        )
        os.environ.pop("ML_CONFIDENCE_THRESHOLD", None)
        assert result["ml_overridden"] is True
        assert result["ml_override_reason"] == "low_confidence"


# ── Benchmark Dataset Regression Tests ────────────────────────────


class TestBenchmarkRegression:
    """Regression tests ensuring benchmark entries stay within expected ranges.

    These tests will fail if a code change causes scores to deviate from
    human-evaluated expected ranges, catching regressions early.
    """

    def test_high_match_keyword_score(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B001")
        score = keyword_match_score(entry["cv_text"], entry["job_description"])
        expected = entry["expected"]["keyword_score"]
        assert expected["min"] <= score <= expected["max"], (
            f"B001 keyword_score={score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_low_match_keyword_score(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B002")
        score = keyword_match_score(entry["cv_text"], entry["job_description"])
        expected = entry["expected"]["keyword_score"]
        assert expected["min"] <= score <= expected["max"], (
            f"B002 keyword_score={score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_spam_cv_ats_score(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B007")
        result = analyze_cv(entry["cv_text"], job_text=entry["job_description"])
        ats_score = result.get("overall_score", 0)
        expected = entry["expected"]["ats_score"]
        assert expected["min"] <= ats_score <= expected["max"], (
            f"B007 ats_score={ats_score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_minimal_cv_low_scores(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B008")
        result = analyze_cv(entry["cv_text"], job_text=entry["job_description"])
        ats_score = result.get("overall_score", 0)
        expected = entry["expected"]["ats_score"]
        assert expected["min"] <= ats_score <= expected["max"], (
            f"B008 ats_score={ats_score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_no_jd_keyword_zero(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B009")
        score = keyword_match_score(entry["cv_text"], entry["job_description"])
        assert score == 0.0, f"B009 with empty JD should have keyword_score=0, got {score}"

    def test_no_jd_ats_still_good(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B009")
        result = analyze_cv(entry["cv_text"], job_text="")
        ats_score = result.get("overall_score", 0)
        expected = entry["expected"]["ats_score"]
        assert expected["min"] <= ats_score <= expected["max"], (
            f"B009 ats_score={ats_score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_turkish_cv_keyword_improved(self, benchmark_entries):
        """Turkish CV with long JD — calibrated from actual benchmark run."""
        entry = _get_entry(benchmark_entries, "B010")
        score = keyword_match_score(entry["cv_text"], entry["job_description"])
        expected = entry["expected"]["keyword_score"]
        assert expected["min"] <= score <= expected["max"], (
            f"B010 keyword_score={score}, expected [{expected['min']}-{expected['max']}]"
        )

    def test_career_changer_medium_match(self, benchmark_entries):
        entry = _get_entry(benchmark_entries, "B006")
        score = keyword_match_score(entry["cv_text"], entry["job_description"])
        expected = entry["expected"]["keyword_score"]
        assert expected["min"] <= score <= expected["max"], (
            f"B006 keyword_score={score}, expected [{expected['min']}-{expected['max']}]"
        )


# ── Compare Function Coverage Tests ──────────────────────────────


class TestCompareKeywordCoverage:
    """Tests for the compare() function's keyword coverage reporting."""

    def test_coverage_100_with_identical_text(self):
        text = "Python Django PostgreSQL Docker Kubernetes"
        result = compare(text, text)
        assert result["keyword_coverage_pct"] >= 80, (
            f"Identical text should have high coverage, got {result['keyword_coverage_pct']}"
        )

    def test_coverage_zero_with_no_overlap(self):
        result = compare("painting sculpture ceramics", "Python Django PostgreSQL")
        assert result["keyword_coverage_pct"] < 20

    def test_fuzzy_boosts_coverage(self):
        """Fuzzy matching should reduce missing_keywords count."""
        cv = "Optimized databases and developed applications"
        jd = "Optimize database and develop application"
        result = compare(cv, jd)
        # Without fuzzy, "optimize" and "database" would be missing
        # With fuzzy, they should be promoted to weak
        assert len(result["missing_keywords"]) < 4, (
            f"Fuzzy should reduce missing keywords, got {len(result['missing_keywords'])} missing"
        )

    def test_extra_keywords_detected(self):
        result = compare("Python Django PostgreSQL React TypeScript", "Python Django")
        assert len(result["extra_keywords"]) > 0
