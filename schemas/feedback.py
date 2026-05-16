from __future__ import annotations

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    category: str = "bug"
    message: str
    page: str | None = ""
    lang: str | None = ""
    score: int | None = None
    context: dict | None = None
