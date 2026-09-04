"""Shared utility — flatten CVModel to plain text.

Ported from utils/cv_text.py (web repo). Only ``build_cv_text`` is ported —
the sibling ``extract_structured_data`` helper in the source file is unused
by anything in this package (it's a standalone raw-text heuristic, not part
of the CVModel pipeline) and was dropped to keep this port minimal.
"""

from __future__ import annotations

from .schema import CVModel


def build_cv_text(model: CVModel) -> str:
    """Flatten *model* into a single newline-separated string.

    Used by ATS scoring and recruiter scoring.
    """
    parts: list[str] = []
    parts.append(model.full_name)
    parts.append(model.title)
    parts.append(model.summary or "")
    for exp in model.experiences:
        parts.append(exp.title)
        parts.append(exp.company)
        parts.extend(exp.bullets)
    for edu in model.education:
        parts.append(edu.degree)
        parts.append(edu.school)
        parts.append(edu.field)
    for proj in model.projects:
        parts.append(proj.name)
        parts.append(proj.description)
        parts.extend(proj.bullets)
    parts.extend(model.skills)
    for cat_skills in model.skills_categorized.values():
        parts.extend(cat_skills)
    parts.extend(model.languages)
    return "\n".join(p for p in parts if p)
