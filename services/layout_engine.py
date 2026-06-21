from __future__ import annotations

import re
from typing import Any, Dict, List

ATS_DEFAULT_TEMPLATE = "classic"

ATS_SECTION_ORDER = [
    "summary",
    "experience",
    "projects",
    "education",
    "skills",
    "languages",
]


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _wrap_line(value: str, width: int = 0) -> str:
    """Clean text without character-based wrapping (renderers handle wrapping)."""
    return _clean_text(value)


# =====================================================================
#  NEW schema-based layout engine
# =====================================================================


def build_layout(schema, section_order: List[str] | None = None) -> Dict[str, Any]:
    """Convert a CVSchema into ordered layout blocks for renderers.

    Returns::

        {
            "header": { name, title, contacts[] },
            "blocks": [
                { "type": "summary", "content": str },
                { "type": "experience", "items": [...] },
                { "type": "projects", "items": [...] },
                { "type": "education", "items": [...] },
                { "type": "skills", "items": [...] },
                { "type": "languages", "items": [...] },
            ],
            "section_order": [...],
            "format_hints": {...},
        }
    """
    order = section_order or ATS_SECTION_ORDER

    # ── Header (always first, not in section order) ──
    contacts = [v for v in [schema.email, schema.phone, schema.location, schema.linkedin] if v]
    header = {
        "name": schema.full_name,
        "title": schema.title,
        "contacts": contacts,
    }

    # ── Build section blocks ──
    section_builders = {
        "summary": lambda: _build_summary_block(schema),
        "experience": lambda: _build_experience_block(schema),
        "projects": lambda: _build_projects_block(schema),
        "education": lambda: _build_education_block(schema),
        "skills": lambda: _build_skills_block(schema),
        "languages": lambda: _build_languages_block(schema),
    }

    blocks: List[Dict[str, Any]] = []
    for section in order:
        builder = section_builders.get(section)
        if builder:
            block = builder()
            if block:
                blocks.append(block)

    return {
        "header": header,
        "blocks": blocks,
        "section_order": order,
        "format_hints": {
            "bold": ["header.name", "section.title", "experience.role", "education.degree"],
            "line_break_between_sections": True,
        },
    }


def _build_summary_block(schema) -> Dict[str, Any] | None:
    summary = (schema.summary or "").strip()
    if not summary:
        return None
    return {"type": "summary", "content": summary}


def _build_experience_block(schema) -> Dict[str, Any] | None:
    if not schema.experiences:
        return None
    items = []
    for exp in schema.experiences:
        date = " – ".join([p for p in [exp.start_date, exp.end_date] if p])
        items.append(
            {
                "role": exp.title,
                "company": exp.company,
                "location": exp.location,
                "date": date,
                "bullets": [b for b in exp.bullets if b],
            }
        )
    return {"type": "experience", "items": items}


def _build_projects_block(schema) -> Dict[str, Any] | None:
    if not schema.projects:
        return None
    items = []
    for proj in schema.projects:
        items.append(
            {
                "name": proj.name,
                "description": proj.description,
                "bullets": [b for b in proj.bullets if b],
            }
        )
    return {"type": "projects", "items": items}


def _build_education_block(schema) -> Dict[str, Any] | None:
    if not schema.education:
        return None
    items = []
    for edu in schema.education:
        date = " – ".join([p for p in [edu.start_date, edu.end_date] if p])
        items.append(
            {
                "degree": edu.degree,
                "field": edu.field,
                "school": edu.school,
                "location": edu.location,
                "date": date,
                "gpa": edu.gpa,
            }
        )
    return {"type": "education", "items": items}


def _build_skills_block(schema) -> Dict[str, Any] | None:
    items: List[str] = []
    if schema.skills_categorized:
        for category, values in schema.skills_categorized.items():
            cleaned = [v for v in values if v]
            if cleaned:
                items.append(f"{category}: {', '.join(cleaned)}")
    elif schema.skills:
        items = [v for v in schema.skills if v]
    if not items:
        return None
    return {"type": "skills", "items": items}


def _build_languages_block(schema) -> Dict[str, Any] | None:
    langs = [v for v in schema.languages if v]
    if not langs:
        return None
    return {"type": "languages", "items": langs}


# =====================================================================
#  LEGACY functions — kept for backward compatibility
# =====================================================================


def build_layout_schema(cv_data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(cv_data or {})

    header = {
        "name": _clean_text(data.get("full_name", "")),
        "title": _clean_text(data.get("title", "")),
        "contacts": [
            v
            for v in [
                _clean_text(data.get("email", "")),
                _clean_text(data.get("phone", "")),
                _clean_text(data.get("location", "")),
                _clean_text(data.get("linkedin", "")),
            ]
            if v
        ],
    }

    summary = _wrap_line(data.get("summary", ""))

    experiences: List[Dict[str, Any]] = []
    for exp in data.get("experiences", []) or []:
        role = _clean_text(exp.get("title", ""))
        company = _clean_text(exp.get("company", ""))
        start = _clean_text(exp.get("start_date", ""))
        end = _clean_text(exp.get("end_date", ""))
        date = " – ".join([p for p in [start, end] if p])
        bullets = []
        for bullet in exp.get("bullets", []) or []:
            text = _clean_text(bullet)
            if text:
                bullets.append(_wrap_line(text))
        experiences.append(
            {
                "company": company,
                "role": role,
                "date": date,
                "bullets": bullets,
            }
        )

    projects: List[Dict[str, Any]] = []
    for proj in data.get("projects", []) or []:
        name = _clean_text(proj.get("name", ""))
        description = _wrap_line(proj.get("description", ""))
        bullets = []
        for bullet in proj.get("bullets", []) or []:
            text = _clean_text(bullet)
            if text:
                bullets.append(_wrap_line(text))
        projects.append({"name": name, "description": description, "bullets": bullets})

    education: List[Dict[str, Any]] = []
    for edu in data.get("education", []) or []:
        degree = _clean_text(edu.get("degree", ""))
        school = _clean_text(edu.get("school", ""))
        start = _clean_text(edu.get("start_date", ""))
        end = _clean_text(edu.get("end_date", ""))
        date = " – ".join([p for p in [start, end] if p])
        gpa = _clean_text(edu.get("gpa", ""))
        education.append(
            {
                "degree": degree,
                "school": school,
                "date": date,
                "gpa": gpa,
            }
        )

    skills: List[str] = []
    skills_categorized = data.get("skills_categorized") or {}
    if isinstance(skills_categorized, dict) and skills_categorized:
        for category, values in skills_categorized.items():
            cleaned_values = [_clean_text(v) for v in (values or []) if _clean_text(v)]
            if cleaned_values:
                skills.append(f"{_clean_text(category)}: {', '.join(cleaned_values)}")
    else:
        skills = [_clean_text(v) for v in (data.get("skills") or []) if _clean_text(v)]

    languages: List[str] = []
    for lang in data.get("languages", []) or []:
        if isinstance(lang, dict):
            name = _clean_text(lang.get("name", ""))
            level = _clean_text(lang.get("level", ""))
            label = " – ".join([p for p in [name, level] if p])
            if label:
                languages.append(label)
        else:
            cleaned = _clean_text(lang)
            if cleaned:
                languages.append(cleaned)

    return {
        "header": header,
        "summary": summary,
        "experience": experiences,
        "projects": projects,
        "education": education,
        "skills": skills,
        "languages": languages,
        "section_order": ATS_SECTION_ORDER,
        "format_hints": {
            "bold": ["header.name", "section.title", "experience.company", "education.degree"],
            "line_break_between_sections": True,
        },
    }


def layout_to_cv_data(layout: Dict[str, Any], base_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = dict(base_data or {})
    header = layout.get("header") or {}

    data["full_name"] = _clean_text(header.get("name", ""))
    data["title"] = _clean_text(header.get("title", ""))

    contacts = header.get("contacts") or []
    contact_text = " | ".join([_clean_text(c) for c in contacts if _clean_text(c)])

    # Preserve explicit fields when available, otherwise derive from contacts.
    data["email"] = _clean_text(data.get("email", ""))
    data["phone"] = _clean_text(data.get("phone", ""))
    data["location"] = _clean_text(data.get("location", ""))
    data["linkedin"] = _clean_text(data.get("linkedin", ""))
    if not data["email"] and contact_text:
        m = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", contact_text, re.I)
        if m:
            data["email"] = m.group(0)

    data["summary"] = _clean_text(layout.get("summary", ""))

    experiences = []
    for exp in layout.get("experience", []) or []:
        company = _clean_text(exp.get("company", ""))
        role = _clean_text(exp.get("role", ""))
        date = _clean_text(exp.get("date", ""))
        start_date, end_date = "", ""
        if " – " in date:
            start_date, end_date = [p.strip() for p in date.split(" – ", 1)]
        elif " - " in date:
            start_date, end_date = [p.strip() for p in date.split(" - ", 1)]
        elif date:
            start_date = date
        experiences.append(
            {
                "title": role,
                "company": company,
                "start_date": start_date,
                "end_date": end_date,
                "location": _clean_text(exp.get("location", "")),
                "bullets": [_clean_text(b) for b in (exp.get("bullets") or []) if _clean_text(b)],
            }
        )
    data["experiences"] = experiences

    projects = []
    for proj in layout.get("projects", []) or []:
        projects.append(
            {
                "name": _clean_text(proj.get("name", "")),
                "description": _clean_text(proj.get("description", "")),
                "bullets": [_clean_text(b) for b in (proj.get("bullets") or []) if _clean_text(b)],
            }
        )
    data["projects"] = projects

    education = []
    for edu in layout.get("education", []) or []:
        date = _clean_text(edu.get("date", ""))
        start_date, end_date = "", ""
        if " – " in date:
            start_date, end_date = [p.strip() for p in date.split(" – ", 1)]
        elif " - " in date:
            start_date, end_date = [p.strip() for p in date.split(" - ", 1)]
        elif date:
            start_date = date
        education.append(
            {
                "degree": _clean_text(edu.get("degree", "")),
                "school": _clean_text(edu.get("school", "")),
                "start_date": start_date,
                "end_date": end_date,
                "gpa": _clean_text(edu.get("gpa", "")),
                "field": _clean_text(edu.get("field", "")),
                "location": _clean_text(edu.get("location", "")),
            }
        )
    data["education"] = education

    skills = [_clean_text(v) for v in (layout.get("skills") or []) if _clean_text(v)]
    data["skills"] = skills

    # keep categorized skills if present on original payload, otherwise derive simple bucket
    if not isinstance(data.get("skills_categorized"), dict) or not data.get("skills_categorized"):
        if skills:
            data["skills_categorized"] = {"Technical Skills": skills}
        else:
            data["skills_categorized"] = {}

    data["languages"] = [_clean_text(v) for v in (layout.get("languages") or []) if _clean_text(v)]

    return data
