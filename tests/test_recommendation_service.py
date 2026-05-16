"""Unit tests for services/recommendation_service.py"""
import pytest
from services.recommendation_service import generate_recommendations


class TestGenerateRecommendations:
    def test_low_semantic_triggers_recommendation(self):
        recs = generate_recommendations([], semantic_score=20, keyword_score=80)
        assert len(recs) >= 1
        # Should mention structure/alignment
        assert any("structure" in r.lower() or "align" in r.lower() for r in recs)

    def test_missing_skills_generates_skill_recs(self):
        recs = generate_recommendations(
            ["Docker", "Kubernetes", "AWS"],
            semantic_score=80,
            keyword_score=80,
        )
        assert any("Docker" in r for r in recs)
        assert any("Kubernetes" in r for r in recs)

    def test_low_keyword_triggers_recommendation(self):
        recs = generate_recommendations([], semantic_score=80, keyword_score=30)
        assert len(recs) >= 1

    def test_all_good_when_no_issues(self):
        recs = generate_recommendations([], semantic_score=80, keyword_score=80)
        assert len(recs) == 1
        # Should be positive/encouraging
        assert recs[0]  # non-empty

    def test_capped_at_5(self):
        many_skills = [f"skill{i}" for i in range(20)]
        recs = generate_recommendations(
            many_skills, semantic_score=10, keyword_score=10,
        )
        assert len(recs) <= 5

    def test_turkish_locale(self):
        recs = generate_recommendations(
            ["Python"], semantic_score=20, keyword_score=80, lang="tr",
        )
        assert len(recs) >= 1
        # Should have Turkish content
        assert any(r for r in recs)

    def test_missing_skills_limited_to_3(self):
        skills = ["A", "B", "C", "D", "E"]
        recs = generate_recommendations(
            skills, semantic_score=80, keyword_score=80,
        )
        # Only top 3 skills generate recs
        skill_recs = [r for r in recs if any(s in r for s in skills)]
        assert len(skill_recs) <= 3
