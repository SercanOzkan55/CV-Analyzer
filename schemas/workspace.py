from __future__ import annotations

from pydantic import BaseModel


class JDTemplateRequest(BaseModel):
    title: str
    description: str
