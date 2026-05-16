from __future__ import annotations

from html import escape as _html_escape
from io import BytesIO

from schemas.cv_model import CVModel

from .blocks import prepare_for_render
from .docx_renderer import render_docx
from .pdf_renderer import render_pdf
from .preview_renderer import render_html_preview
from .typst_renderer import render_typst


def render(cv_model: CVModel, template: str, output_format: str, font_override: str = "") -> dict:
    fmt = (output_format or "docx").lower().strip()

    # Apply render-safety rules on a deep copy — original model is untouched.
    safe_model = prepare_for_render(cv_model)

    if fmt == "html":
        html = render_html_preview(safe_model, template, font_override=font_override)
        standalone = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{_html_escape(safe_model.full_name)} - CV</title>\n"
            "</head>\n<body>\n" + html + "\n</body>\n</html>"
        )
        buf = BytesIO(standalone.encode("utf-8"))
        return {
            "buffer": buf,
            "content_type": "text/html; charset=utf-8",
            "extension": "html",
            "metadata": {},
        }

    if fmt == "pdf":
        buffer = render_pdf(safe_model, template, font_override=font_override)
        return {
            "buffer": buffer,
            "content_type": "application/pdf",
            "extension": "pdf",
            "metadata": {},
        }

    if fmt == "typst":
        buffer, metadata = render_typst(safe_model, template, compile_pdf=False, font_override=font_override)
        return {
            "buffer": buffer,
            "content_type": "text/plain; charset=utf-8",
            "extension": "typ",
            "metadata": metadata,
        }

    if fmt == "typst_pdf":
        buffer, metadata = render_typst(safe_model, template, compile_pdf=True, font_override=font_override)
        ct = "application/pdf" if metadata.get("compiled") else "text/plain; charset=utf-8"
        ext = "pdf" if metadata.get("compiled") else "typ"
        return {
            "buffer": buffer,
            "content_type": ct,
            "extension": ext,
            "metadata": metadata,
        }

    buffer = render_docx(safe_model, template, font_override=font_override)
    return {
        "buffer": buffer,
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extension": "docx",
        "metadata": {},
    }
