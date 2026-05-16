from __future__ import annotations

from pydantic import BaseModel

from services.language_service import DEFAULT_LANG


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG
    tone: str = "professional"


class CVAutoFixExportRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = DEFAULT_LANG


class CVAutoFixParseRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG


class BulletRewriteRequest(BaseModel):
    bullets: list[str]
    job_description: str | None = ""
    lang: str = DEFAULT_LANG
    tone: str = "professional"


class CoverLetterRewriteRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = DEFAULT_LANG
    tone: str = "professional"


class InterviewQuestionsRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG
    mode: str | None = "senior"
    count: int = 5


class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str
    cv_text: str | None = ""
    job_description: str | None = ""
    lang: str = DEFAULT_LANG


class SummarySuggestionRequest(BaseModel):
    summary: str
    job_description: str | None = ""
    lang: str = DEFAULT_LANG


class ScoreBreakdownRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    lang: str = DEFAULT_LANG


class KeywordOptimizationRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    lang: str = DEFAULT_LANG


class DiffRequest(BaseModel):
    original_text: str
    optimized_text: str
