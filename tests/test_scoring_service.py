"""Unit tests for services/scoring_service.py"""

import pytest
from services.scoring_service import calculate_similarity


class TestCalculateSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        sim = calculate_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        sim = calculate_similarity(vec1, vec2)
        assert abs(sim) < 0.001

    def test_opposite_vectors(self):
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        sim = calculate_similarity(vec1, vec2)
        assert abs(sim + 1.0) < 0.001

    def test_similar_vectors_(self):
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.1, 2.1, 3.1]
        sim = calculate_similarity(vec1, vec2)
        assert sim > 0.99

    def test_returns_float(self):
        result = calculate_similarity([1, 0], [0, 1])
        assert isinstance(result, float)

    def test_high_dimensional(self):
        import random

        random.seed(42)
        vec1 = [random.random() for _ in range(1536)]
        sim = calculate_similarity(vec1, vec1)
        assert abs(sim - 1.0) < 0.001
