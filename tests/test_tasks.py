"""Tests for services/tasks.py — Celery task fallback."""
import pytest
from services.tasks import analyze_pdf_task, analyze_text_task


class TestLocalTaskFallback:
    """When Redis/Celery is unavailable, tasks fall back to LocalTask."""

    def test_analyze_pdf_task_callable(self):
        assert callable(analyze_pdf_task)

    def test_analyze_text_task_callable(self):
        assert callable(analyze_text_task)

    def test_analyze_pdf_has_delay(self):
        assert hasattr(analyze_pdf_task, "delay")

    def test_analyze_text_has_delay(self):
        assert hasattr(analyze_text_task, "delay")
