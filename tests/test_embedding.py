"""Tests for services/embedding_service.py — embedding with mock/safe mode."""
import os
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_SERVICES", "1")


class TestGetEmbeddingMock:
    def test_mock_returns_vector(self):
        from services.embedding_service import get_embedding
        result = get_embedding("test text for embedding")
        assert isinstance(result, list)
        assert len(result) == 1536  # OpenAI ada dimension

    def test_mock_returns_consistent_length(self):
        from services.embedding_service import get_embedding
        r1 = get_embedding("hello")
        r2 = get_embedding("world")
        assert len(r1) == len(r2)


class TestEmbeddingRateLimiting:
    def test_rate_limit_env_defaults(self):
        from services.embedding_service import _EMBED_MAX_CALLS_PER_MIN
        assert _EMBED_MAX_CALLS_PER_MIN > 0


class TestEmbeddingCacheTTL:
    def test_default_ttl(self):
        from services.embedding_service import EMBEDDING_CACHE_TTL
        assert EMBEDDING_CACHE_TTL == 604800  # 7 days
