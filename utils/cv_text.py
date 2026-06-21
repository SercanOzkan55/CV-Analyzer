"""Shared utility — flatten CVModel to plain text."""

from __future__ import annotations

from schemas.cv_model import CVModel


def build_cv_text(model: CVModel) -> str:
    """Flatten *model* into a single newline-separated string.

    Used by keyword matching, embedding extraction, ATS scoring, etc.
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


def extract_structured_data(text: str) -> dict:
    """
    Extract structured data from CV text.
    Returns basic structured information for scoring.
    """
    import re

    # Basic skill extraction
    skills = []
    skill_keywords = [
        "python",
        "javascript",
        "java",
        "c++",
        "c#",
        "php",
        "ruby",
        "go",
        "rust",
        "react",
        "angular",
        "vue",
        "node.js",
        "django",
        "flask",
        "spring",
        "sql",
        "mysql",
        "postgresql",
        "mongodb",
        "redis",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "git",
        "machine learning",
        "ai",
        "data science",
        "tensorflow",
        "pytorch",
    ]

    text_lower = text.lower()
    for skill in skill_keywords:
        if skill in text_lower:
            skills.append(skill.title())

    # Experience years estimation
    experience_years = 0
    year_patterns = [
        r"(\d+)\s*(?:year|yr|yrs?)",
        r"(\d+)\+?\s*(?:year|yr|yrs?)",
        r"(\d{4})\s*-\s*(?:\d{4}|present|current)",
    ]

    for pattern in year_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            try:
                if "-" in str(match):
                    # Date range
                    years = str(match).split("-")
                    if len(years) == 2:
                        start_year = int(years[0])
                        end_year = int(years[1]) if years[1].isdigit() else 2024
                        experience_years = max(experience_years, end_year - start_year)
                else:
                    # Direct year count
                    experience_years = max(experience_years, int(match))
            except:
                continue

    # Education level detection
    education_level = 0
    if "phd" in text_lower or "doctorate" in text_lower or "doktora" in text_lower:
        education_level = 5
    elif "master" in text_lower or "msc" in text_lower or "ms" in text_lower or "yüksek lisans" in text_lower:
        education_level = 4
    elif "bachelor" in text_lower or "bsc" in text_lower or "bs" in text_lower or "lisans" in text_lower:
        education_level = 3
    elif "associate" in text_lower or "ön lisans" in text_lower:
        education_level = 2

    return {
        "skills": skills,
        "experience_years": min(experience_years, 20),  # Cap at 20 years
        "education_level": education_level,
        "word_count": len(text.split()),
        "has_email": bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)),
        "has_phone": bool(re.search(r"[\+]?[1-9][\d]{0,15}", text)),
    }
