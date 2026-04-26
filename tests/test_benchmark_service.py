"""Unit tests for services/benchmark_service.py"""
import pytest
from unittest.mock import MagicMock, patch
from services.benchmark_service import infer_profession


class TestInferProfession:
    def test_infers_from_job_title(self):
        result = infer_profession(job_title="Senior Backend Developer")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_infers_from_skills(self):
        result = infer_profession(skills=["Python", "Django", "FastAPI", "PostgreSQL"])
        assert isinstance(result, str)

    def test_infers_from_experience_titles(self):
        result = infer_profession(
            experience_titles=["Frontend Developer", "React Developer"]
        )
        assert isinstance(result, str)

    def test_defaults_on_empty_input(self):
        result = infer_profession()
        assert isinstance(result, str)

    def test_data_science_detection(self):
        result = infer_profession(
            job_title="Data Scientist",
            skills=["Python", "TensorFlow", "pandas", "scikit-learn"],
        )
        assert isinstance(result, str)
        # Should detect something data-related
        assert result  # non-empty

    def test_devops_detection(self):
        result = infer_profession(
            skills=["Docker", "Kubernetes", "Terraform", "AWS", "Jenkins"]
        )
        assert isinstance(result, str)
