"""Strict CV Schema — jsonresume-inspired canonical representation.

This is the single source of truth after normalize.  No text parsing
ever happens after data enters this schema.  The layout engine and
every renderer consume this schema directly.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field, PrivateAttr


class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: List[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    degree: str = ""
    field: str = ""
    school: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class ProjectEntry(BaseModel):
    name: str = ""
    description: str = ""
    bullets: List[str] = Field(default_factory=list)


class CertificationEntry(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class CVSchema(BaseModel):
    """Strict CV schema.  All downstream code consumes this model."""

    full_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""

    summary: str = ""

    experiences: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    skills_categorized: Dict[str, List[str]] = Field(default_factory=dict)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    social_links: list = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    misc: List[str] = Field(default_factory=list)
    language: str = "en"
    section_titles: Dict[str, str] = Field(default_factory=dict)

    _frozen: bool = PrivateAttr(default=False)

    def __setattr__(self, name: str, value: object) -> None:
        if name != "_frozen" and self._frozen:
            import logging

            logging.getLogger("app.parser.schema").warning(
                "frozen_schema_mutation: attempted to set %s after freeze",
                name,
            )
            return
        super().__setattr__(name, value)

    def freeze(self) -> None:
        """Mark schema as read-only.  Mutations after this log a warning and are ignored."""
        object.__setattr__(self, "_frozen", True)

    def unfreeze(self) -> None:
        """Temporarily re-enable mutations (used internally by fallback paths)."""
        object.__setattr__(self, "_frozen", False)

    # ── helpers ──────────────────────────────────────────────────────

    def ensure_skills_categorized(self) -> None:
        """Promote flat skills list into categorized dict if empty."""
        if self.skills_categorized:
            return
        if self.skills:
            self.skills_categorized = {"Technical Skills": list(self.skills)}

    def to_cv_model(self):
        """Convert to legacy CVModel for backward compatibility."""
        from schemas.cv_model import CVModel

        return CVModel.from_mapping(self.model_dump())
