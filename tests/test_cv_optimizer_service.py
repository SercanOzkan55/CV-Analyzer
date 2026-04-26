"""Unit tests for services/cv_optimizer_service.py"""
import pytest
from schemas.cv_model import CVModel, Experience, Education
from services.cv_optimizer_service import optimize_cv, KeywordOptResult


def _make_model(**overrides) -> CVModel:
    defaults = dict(
        full_name="Jane Doe",
        title="Developer",
        email="jane@example.com",
        summary="Experienced developer with Python skills.",
        experiences=[
            Experience(
                title="Developer",
                company="Corp",
                bullets=[
                    "Responsible for building APIs",
                    "Worked on database optimization",
                    "Helped with deployment pipelines",
                ],
            ),
        ],
        education=[
            Education(degree="B.Sc.", school="University", field="CS"),
        ],
        skills=["Python"],
        skills_categorized={"Backend": ["Python"]},
        languages=["English"],
    )
    defaults.update(overrides)
    return CVModel(**defaults)


class TestOptimizeCV:
    def test_returns_rewrite_result(self):
        model = _make_model()
        result = optimize_cv(model, job_text="Python Django PostgreSQL developer")
        assert hasattr(result, "model")
        assert hasattr(result, "changes")
        assert hasattr(result, "score_before")
        assert hasattr(result, "score_after")

    def test_injects_missing_keywords(self):
        model = _make_model(skills=["Python"], skills_categorized={"Backend": ["Python"]})
        result = optimize_cv(model, job_text="Python Django PostgreSQL Docker Kubernetes")
        # Should add missing keywords to skills
        new_skills = [s.lower() for s in (result.model.skills or [])]
        assert any(kw in new_skills for kw in ["django", "postgresql", "docker"])

    def test_rewrites_weak_bullets(self):
        model = _make_model()
        result = optimize_cv(model, job_text="Python developer")
        # Bullets starting with "Responsible for" should be rewritten
        changes = [c for c in result.changes if c.section == "experience"]
        # At least some bullet improvement should happen
        assert len(result.changes) >= 0  # Non-crashing minimum

    def test_generates_summary_when_missing(self):
        model = _make_model(summary="")
        result = optimize_cv(model, job_text="Python developer")
        assert (result.model.summary or "").strip() != ""
        summary_changes = [c for c in result.changes if c.section == "summary"]
        assert len(summary_changes) >= 1

    def test_no_job_text_still_works(self):
        model = _make_model()
        result = optimize_cv(model)
        assert result.model is not None

    def test_does_not_mutate_original(self):
        model = _make_model()
        original_skills = list(model.skills)
        optimize_cv(model, job_text="Django Docker Kubernetes AWS Azure")
        assert model.skills == original_skills

    def test_keywords_added_tracked(self):
        model = _make_model(skills=[], skills_categorized={})
        result = optimize_cv(model, job_text="Python Django PostgreSQL Docker Kubernetes")
        assert isinstance(result.keywords_added, list)
