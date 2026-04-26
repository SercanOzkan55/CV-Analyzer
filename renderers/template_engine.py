from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

from schemas.cv_model import CVModel
from renderers.theme import load_theme

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"


def _clean_text_line(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([A-Z][A-Za-z0-9]+)-\s+([A-Z][A-Za-z0-9]+)", r"\1-\2", text)
    text = re.sub(r"([a-z0-9])\-\s+([a-z0-9])", r"\1\2", text)
    text = re.sub(r"([A-Za-z])\(", r"\1 (", text)
    return text.strip()


def _normalize_rendered_template(text: str) -> str:
    lines = []
    for raw in str(text or "").splitlines():
        if raw.strip():
            lines.append(_clean_text_line(raw))
        else:
            lines.append("")
    merged = "\n".join(lines)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip() + "\n"


def load_template_file(template: str, filename: str = "template.typ") -> str:
    template_name = (template or "classic").strip().lower() or "classic"
    candidates = [
        TEMPLATES_DIR / f"{template_name}.typ" if filename == "template.typ" else None,
        TEMPLATES_DIR / template_name / filename,
        TEMPLATES_DIR / "classic.typ" if filename == "template.typ" else None,
        TEMPLATES_DIR / "classic" / filename,
    ]

    path = None
    for candidate in candidates:
        if candidate and candidate.exists():
            path = candidate
            break
    if path is None:
        raise FileNotFoundError(f"Template file not found for '{template_name}' ({filename})")
    return path.read_text(encoding="utf-8")


def _replace_simple_placeholders(content: str, model: CVModel) -> str:
    values = {
        "full_name": model.full_name,
        "email": model.email,
        "phone": model.phone,
        "location": model.location,
        "summary": model.summary,
    }
    rendered = content
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", _clean_text_line(value))
    return rendered


def _render_experiences_block(model: CVModel) -> str:
    lines = []
    for exp in model.experiences:
        title = _clean_text_line(exp.title)
        company = _clean_text_line(exp.company)
        header = " - ".join([p for p in [title, company] if p])
        start_date = _clean_text_line(exp.start_date)
        end_date = _clean_text_line(exp.end_date)
        dates = " - ".join([p for p in [start_date, end_date] if p])
        if header:
            lines.append(f"=== {header}")
        if dates:
            lines.append(dates)
        for bullet in exp.bullets:
            if str(bullet or "").strip():
                lines.append(f"- {_clean_text_line(bullet)}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_skills_block(model: CVModel) -> str:
    lines = []
    skills_map = model.skills_categorized or {}
    for category, values in skills_map.items():
        clean_values = [_clean_text_line(v) for v in values or [] if _clean_text_line(v)]
        if clean_values:
            lines.append(f"- *{_clean_text_line(category)}:* {', '.join(clean_values)}")
    return "\n".join(lines)


def _render_education_block(model: CVModel) -> str:
    lines = []
    for edu in model.education:
        degree = _clean_text_line(edu.degree)
        school = _clean_text_line(edu.school)
        parts = [p for p in [degree, school] if p]
        if parts:
            lines.append(f"=== {' - '.join(parts)}")
        start_date = _clean_text_line(edu.start_date)
        end_date = _clean_text_line(edu.end_date)
        date_span = " - ".join([p for p in [start_date, end_date] if p])
        if date_span:
            lines.append(date_span)
        lines.append("")
    return "\n".join(lines).strip()


def _process_conditionals(content: str, model: CVModel) -> str:
    """Process {{#if section}}...{{/if}} blocks."""
    section_checks = {
        "experiences": bool(model.experiences),
        "skills": bool(model.skills_categorized),
        "education": bool(model.education),
        "summary": bool(str(model.summary or "").strip()),
        "email": bool(str(model.email or "").strip()),
        "phone": bool(str(model.phone or "").strip()),
        "location": bool(str(model.location or "").strip()),
    }

    def _replace_if(match: re.Match) -> str:
        section = match.group(1).strip()
        body = match.group(2)
        if section_checks.get(section, False):
            return body
        return ""

    return re.sub(
        r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}",
        _replace_if,
        content,
        flags=re.DOTALL,
    )


def _inject_theme(content: str, theme: dict) -> str:
    """Replace {{theme_*}} placeholders with theme JSON values."""
    for key, value in theme.items():
        content = content.replace(f"{{{{theme_{key}}}}}", str(value))
    return content


def fill_template(template_text: str, model: CVModel, template_name: Optional[str] = None, font_override: str = "") -> str:
    theme = load_theme(template_name or "classic", font_override=font_override)
    rendered = _inject_theme(template_text, theme)

    rendered = _process_conditionals(rendered, model)

    rendered = _replace_simple_placeholders(rendered, model)

    block_map = {
        "experiences": _render_experiences_block(model),
        "skills": _render_skills_block(model),
        "education": _render_education_block(model),
    }

    for key, value in block_map.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)

    return _normalize_rendered_template(rendered)
