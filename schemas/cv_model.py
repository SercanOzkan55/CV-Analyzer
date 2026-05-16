from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class Experience(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: List[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str = ""
    school: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""
    field: str = ""
    location: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    bullets: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class CVModel(BaseModel):
    full_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""

    summary: str = ""

    experiences: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)

    skills_categorized: Dict[str, List[str]] = Field(default_factory=dict)

    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    social_links: list = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    misc: List[str] = Field(default_factory=list)
    language: str = "en"
    section_titles: Dict[str, str] = Field(default_factory=dict)

    # Backward-compatible helper field used by existing rewrite flow.
    skills: List[str] = Field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict | None) -> "CVModel":
        payload = dict(data or {})
        payload.setdefault("skills", payload.get("skills") or [])

        # Normalize languages: accept list[str] or list[dict] from frontend
        raw_langs = payload.get("languages") or []
        normalized_langs: list[str] = []
        for lang in raw_langs:
            if isinstance(lang, str):
                normalized_langs.append(lang)
            elif isinstance(lang, dict):
                name = lang.get("name") or lang.get("language") or ""
                if not name:
                    continue
                # New CEFR sub-skill format: {name, writing, listening, speaking}
                writing = lang.get("writing") or ""
                listening = lang.get("listening") or ""
                speaking = lang.get("speaking") or ""
                if writing or listening or speaking:
                    parts = []
                    if writing:
                        parts.append(f"W:{writing}")
                    if listening:
                        parts.append(f"L:{listening}")
                    if speaking:
                        parts.append(f"S:{speaking}")
                    normalized_langs.append(f"{name} ({', '.join(parts)})")
                else:
                    # Legacy format: {name, level}
                    level = lang.get("level") or lang.get("proficiency") or ""
                    normalized_langs.append(f"{name} ({level})" if level else name)
        payload["languages"] = normalized_langs

        return cls(**payload)

    def ensure_skills_categorized(self) -> None:
        """Populate skills_categorized from flat skills ONLY if empty.
        Never overwrite existing categorized data."""
        if self.skills_categorized:
            return
        if self.skills:
            self.skills_categorized = {"Technical Skills": list(self.skills)}
