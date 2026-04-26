"""Unit tests for services/skill_service.py"""
import pytest
from unittest.mock import patch
from services.skill_service import extract_skills, skill_coverage_score


# ── extract_skills ───────────────────────────────────────────

class TestExtractSkills:
    def test_extracts_programming_languages(self):
        text = "Experienced in Python, Java, and JavaScript development"
        result = extract_skills(text)
        assert "python" in result["found"]
        assert "java" in result["found"]
        assert "javascript" in result["found"]

    def test_extracts_frameworks(self):
        text = "Built APIs with Django and FastAPI, frontend with React"
        result = extract_skills(text)
        assert "django" in result["found"]
        assert "fastapi" in result["found"]
        assert "react" in result["found"]

    def test_by_category_structure(self):
        text = "Python developer using Docker and Kubernetes"
        result = extract_skills(text)
        assert "languages" in result["by_category"]
        assert "python" in result["by_category"]["languages"]
        assert "devops_cloud" in result["by_category"]

    def test_abbreviation_expansion(self):
        text = "Expert in JS, TS, and K8s deployments"
        result = extract_skills(text)
        assert "javascript" in result["found"]
        assert "typescript" in result["found"]
        assert "kubernetes" in result["found"]

    def test_empty_text(self):
        result = extract_skills("")
        assert result["found"] == set()
        assert result["by_category"] == {}

    def test_case_insensitive(self):
        result1 = extract_skills("PYTHON DJANGO")
        result2 = extract_skills("python django")
        assert result1["found"] == result2["found"]

    def test_database_skills(self):
        text = "PostgreSQL, MongoDB, Redis for caching"
        result = extract_skills(text)
        assert "postgresql" in result["found"]
        assert "mongodb" in result["found"]
        assert "redis" in result["found"]

    def test_cloud_skills(self):
        text = "Deployed on AWS using Docker and Terraform"
        result = extract_skills(text)
        assert "aws" in result["found"]
        assert "docker" in result["found"]
        assert "terraform" in result["found"]


# ── skill_coverage_score ─────────────────────────────────────

class TestSkillCoverageScore:
    def test_full_coverage(self):
        text = "Python Django PostgreSQL Docker"
        score, missing = skill_coverage_score(text, text)
        assert score == 100.0
        assert missing == []

    def test_partial_coverage(self):
        cv = "Python Django"
        jd = "Python Django PostgreSQL Docker Kubernetes"
        score, missing = skill_coverage_score(cv, jd)
        assert 0 < score < 100
        assert "postgresql" in missing or "docker" in missing

    def test_no_job_skills_returns_zero(self):
        score, missing = skill_coverage_score("Python", "no tech skills here aaa bbb")
        assert score == 0.0
        assert missing == []

    def test_missing_skills_are_sorted(self):
        cv = "Python"
        jd = "Python Django PostgreSQL React Docker"
        _, missing = skill_coverage_score(cv, jd)
        assert missing == sorted(missing)
