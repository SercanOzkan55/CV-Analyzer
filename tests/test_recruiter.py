"""Tests for services/recruiter_service.py — ranking, strength/weakness, preview."""

import pytest
from services.recruiter_service import (
    rank_candidates,
    analyze_strengths_weaknesses,
    build_preview,
    render_template,
)


class TestRankCandidates:
    def test_ranks_by_score_descending(self):
        analyses = [
            {"final_score": 60, "detected_skills": ["python"]},
            {"final_score": 85, "detected_skills": ["python", "java"]},
            {"final_score": 40, "detected_skills": []},
        ]
        ranked = rank_candidates(analyses)
        assert ranked[0]["rank"] == 1
        assert ranked[0]["final_score"] == 85.0
        assert ranked[-1]["final_score"] == 40.0

    def test_empty_list(self):
        assert rank_candidates([]) == []

    def test_ranked_output_fields(self):
        analyses = [{"final_score": 70, "detected_skills": ["python"]}]
        ranked = rank_candidates(analyses)
        item = ranked[0]
        assert "rank" in item
        assert "final_score" in item
        assert "detected_skills" in item
        assert "missing_skills" in item

    def test_secondary_sort_by_experience(self):
        analyses = [
            {"final_score": 70, "detected_skills": [], "ats": {"experience": {"entry_count": 1}}},
            {"final_score": 70, "detected_skills": [], "ats": {"experience": {"entry_count": 5}}},
        ]
        ranked = rank_candidates(analyses)
        assert ranked[0]["experience_count"] >= ranked[1]["experience_count"]


class TestAnalyzeStrengthsWeaknesses:
    def test_high_score_is_strength(self):
        analysis = {"final_score": 85, "skill_score": 80, "detected_skills": list(range(10))}
        result = analyze_strengths_weaknesses(analysis)
        assert any("High" in s for s in result["strengths"])

    def test_low_score_is_weakness(self):
        analysis = {"final_score": 30, "skill_score": 20, "detected_skills": []}
        result = analyze_strengths_weaknesses(analysis)
        assert len(result["weaknesses"]) > 0

    def test_missing_skills_noted(self):
        analysis = {"final_score": 60, "missing_skills": ["python", "java", "go"]}
        result = analyze_strengths_weaknesses(analysis)
        weakness_text = " ".join(result["weaknesses"])
        assert "Missing" in weakness_text or "missing" in weakness_text.lower()

    def test_returns_both_keys(self):
        result = analyze_strengths_weaknesses({})
        assert "strengths" in result
        assert "weaknesses" in result


class TestBuildPreview:
    def test_basic_preview(self):
        analysis = {
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "final_score": 75.5,
            "ats_score": 70.0,
            "detected_skills": ["python", "java"],
            "missing_skills": ["go"],
        }
        preview = build_preview(analysis)
        assert preview["name"] == "John Doe"
        assert preview["final_score"] == 75.5
        assert "python" in preview["top_skills"]

    def test_empty_analysis(self):
        preview = build_preview({})
        assert preview["name"] == ""
        assert preview["final_score"] == 0.0


class TestRenderTemplate:
    def test_basic_render(self):
        result = render_template(
            "Hello {name}, your score is {score}.",
            "Results for {name}",
            {"name": "John", "score": "85"},
        )
        assert "John" in result["body"]
        assert "85" in result["body"]
        assert "John" in result["subject"]

    def test_missing_variable_kept(self):
        result = render_template("Hi {name} at {company}", "Subject", {"name": "Jane"})
        # Should handle missing vars gracefully
        assert "Jane" in result["body"]
