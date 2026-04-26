from __future__ import annotations

from html import escape

from renderers.template_engine import load_template_file
from schemas.cv_model import CVModel


def render_html_preview(cv_model: CVModel, template: str = "classic", font_override: str = "") -> str:
    experiences = "".join(
        f"<li><strong>{escape(exp.title)}</strong> - {escape(exp.company)}<ul>"
        + "".join(f"<li>{escape(b)}</li>" for b in exp.bullets)
        + "</ul></li>"
        for exp in cv_model.experiences
    )

    skills = "".join(
        f"<li><strong>{escape(cat)}:</strong> {escape(', '.join(vals))}</li>"
        for cat, vals in (cv_model.skills_categorized or {}).items()
    )

    tpl = load_template_file(template, "preview.html")
    rendered = tpl
    rendered = rendered.replace("{{full_name}}", escape(cv_model.full_name))
    rendered = rendered.replace("{{email}}", escape(cv_model.email))
    rendered = rendered.replace("{{phone}}", escape(cv_model.phone))
    rendered = rendered.replace("{{location}}", escape(cv_model.location))
    rendered = rendered.replace("{{summary}}", escape(cv_model.summary))
    rendered = rendered.replace("{{experiences_html}}", experiences)
    rendered = rendered.replace("{{skills_html}}", skills)
    return rendered
