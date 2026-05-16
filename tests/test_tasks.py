"""Tests for services/tasks.py — Celery task fallback."""
import pytest
import services.tasks as tasks_module
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

    def test_analyze_pdf_task_uses_original_text(self, monkeypatch):
        captured = {}

        def _fake_pipeline(cv_text, job_description, lang="en"):
            captured["cv_text"] = cv_text
            captured["job_description"] = job_description
            captured["lang"] = lang
            return {"final_score": 1.0}

        original = "Jane Doe\nExperience\nBuilt reporting dashboards."
        monkeypatch.setattr(tasks_module, "_run_pipeline", _fake_pipeline)

        result = analyze_pdf_task(original, "Data analyst", "en")

        assert result == {"final_score": 1.0}
        assert captured["cv_text"] == original
