"""Tests for services/model_worker.py — worker process management."""
import pytest
from unittest.mock import patch, MagicMock
from services.model_worker import stop, predict_sync


class TestStop:
    def test_stop_when_not_started(self):
        """stop() should not raise when worker was never started."""
        stop()


class TestPredictSync:
    @patch("services.model_worker._ensure_worker_alive", return_value=False)
    def test_raises_when_worker_not_alive(self, mock_ensure):
        with pytest.raises(RuntimeError, match="model worker not running"):
            predict_sync([50, 60, 70])
