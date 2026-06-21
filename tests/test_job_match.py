"""Tests for services/job_match_service.py — CV-job matching."""

import pytest
from unittest.mock import patch
from schemas.cv_model import CVModel
from services.job_match_service import (
    match_cv_to_job,
    _cosine_similarity,
    MatchResult,
)


def _sample_model():
    return CVModel(
        candidate_name="John Doe",
        detected_skills=["python", "javascript", "docker", "aws"],
        cv_text="Experienced software engineer with Python and Docker skills. "
        "Built REST APIs and microservices. Led team of 5 engineers.",
    )


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 0.01

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1, 0], [0, 1])) < 0.01

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.0


class TestMatchCvToJob:
    def test_empty_job_text(self):
        model = _sample_model()
        result = match_cv_to_job(model, "")
        assert isinstance(result, MatchResult)
        assert result.match_score == 0.0

    def test_matching_job(self):
        model = _sample_model()
        result = match_cv_to_job(model, "Looking for a Python developer with Docker experience")
        assert isinstance(result, MatchResult)
        assert result.keyword_score >= 0

    def test_returns_missing_keywords(self):
        model = _sample_model()
        result = match_cv_to_job(model, "Kubernetes Terraform CI/CD pipeline expert")
        assert isinstance(result.missing_keywords, list)

    def test_returns_strong_keywords(self):
        model = _sample_model()
        result = match_cv_to_job(model, "Python Docker AWS developer")
        assert isinstance(result.strong_keywords, list)

    @patch("services.job_match_service._semantic_match", return_value=0.0)
    def test_keyword_only_matching(self, mock_semantic):
        model = _sample_model()
        result = match_cv_to_job(model, "Python developer")
        assert result.semantic_score == 0.0
        assert result.keyword_score >= 0
