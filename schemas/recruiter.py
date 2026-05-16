from __future__ import annotations

from pydantic import BaseModel


class RecruiterJobRequest(BaseModel):
    title: str
    description: str | None = ""
    company: str | None = ""
    location: str | None = ""


class RecruiterDashboardActionRequest(BaseModel):
    job_id: int | str | None = None
    candidate_name: str | None = ""
    candidate_email: str | None = ""
    cv_text: str | None = ""
    final_score: float | None = None
    ats_score: float | None = None
    action: str | None = "review"
    stage: str | None = None
    feedback: str | None = ""


class RecruiterTemplateRequest(BaseModel):
    name: str
    template_type: str | None = "accept"
    subject: str | None = ""
    body: str


class RecruiterTemplatePreviewRequest(BaseModel):
    template_id: int | str | None = None
    candidate_name: str | None = "Candidate"
    candidate_email: str | None = ""
    job_description: str | None = ""
    position: str | None = ""
    company: str | None = ""
    score: float | None = None
    top_skills: list[str] | None = None
