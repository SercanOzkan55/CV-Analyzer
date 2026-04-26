from __future__ import annotations

import os
import re
import unicodedata
from io import BytesIO
from pathlib import Path

from fpdf import FPDF

from renderers.blocks import (
    _clean,
    render_education,
    render_experience,
    render_header,
    render_project,
    render_skills,
)
from renderers.page_break import check_height, new_page
from renderers.theme import load_theme
from schemas.cv_model import CVModel

from agents.normalize_agent import get_section_order

_FONTS_DIR = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"

_TTF_MAP: dict[str, tuple[str, str]] = {
    "arial":           ("arial.ttf",    "arialbd.ttf"),
    "calibri":         ("calibri.ttf",  "calibrib.ttf"),
    "times new roman": ("times.ttf",    "timesbd.ttf"),
    "georgia":         ("georgia.ttf",  "georgiab.ttf"),
    "cambria":         ("cambria.ttc",  "cambriab.ttf"),
    "tahoma":          ("tahoma.ttf",   "tahomabd.ttf"),
    "segoe ui":        ("segoeui.ttf",  "segoeuib.ttf"),
    "consolas":        ("consola.ttf",  "consolab.ttf"),
    "garamond":        ("GARA.TTF",     "GARABD.TTF"),
}

_FALLBACK_REGULAR = "arial.ttf"
_FALLBACK_BOLD = "arialbd.ttf"

# DejaVuSans font paths for unicode support (Turkish, German, French, etc.)
_DEJAVU_PATHS = [
    # Linux
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    # Windows bundled or user-installed
    _FONTS_DIR,
]


def _register_font(pdf: FPDF, font_name: str) -> str:
    # Try DejaVuSans first for full unicode support
    for djv_dir in _DEJAVU_PATHS:
        reg = djv_dir / "DejaVuSans.ttf"
        bold = djv_dir / "DejaVuSans-Bold.ttf"
        if reg.exists() and bold.exists():
            family = "DejaVu"
            pdf.add_font(family, "", str(reg))
            pdf.add_font(family, "B", str(bold))
            return family

    # Fallback to Windows TTF fonts
    key = font_name.strip().lower()
    regular, bold = _TTF_MAP.get(key, (_FALLBACK_REGULAR, _FALLBACK_BOLD))
    reg_path = _FONTS_DIR / regular
    bold_path = _FONTS_DIR / bold
    if not reg_path.exists():
        reg_path = _FONTS_DIR / _FALLBACK_REGULAR
        bold_path = _FONTS_DIR / _FALLBACK_BOLD
    family = f"cv_{key.replace(' ', '_')}"
    pdf.add_font(family, "", str(reg_path))
    if bold_path.exists():
        pdf.add_font(family, "B", str(bold_path))
    else:
        pdf.add_font(family, "B", str(reg_path))
    return family


class _PDF(FPDF):
    pass


def render_pdf(cv_model: CVModel, template: str = "classic", font_override: str = "") -> BytesIO:
    theme = load_theme(template, font_override=font_override)
    font_name = theme.get("font", "Arial")
    body_size = 10.0
    header_size = 16.0
    section_size = 12.0
    spacing = float(theme.get("spacing", 3))
    margin_mm = float(theme.get("margin_cm", 1.5)) * 10
    lh = 5.0  # tighter line height
    bullet_indent = 10.0
    bullet_text_offset = 20.0

    # ── Section headers: prefer original CV headers, fallback to localized ──
    _titles = getattr(cv_model, "section_titles", None) or {}
    lang = getattr(cv_model, "language", "en") or "en"

    _FALLBACK = {
        "summary": {
            "en": "PROFESSIONAL SUMMARY", "tr": "PROFESYONEL \u00D6ZET",
            "de": "ZUSAMMENFASSUNG", "fr": "R\u00C9SUM\u00C9 PROFESSIONNEL",
            "es": "RESUMEN PROFESIONAL", "pt": "RESUMO PROFISSIONAL",
            "it": "PROFILO PROFESSIONALE", "nl": "SAMENVATTING",
            "ru": "\u0420\u0415\u0417\u042E\u041C\u0415", "pl": "PODSUMOWANIE ZAWODOWE",
            "sv": "SAMMANFATTNING", "no": "SAMMENDRAG", "da": "RESUM\u00C9",
            "fi": "YHTEENVETO", "cs": "SHRNUT\u00CD", "hu": "\u00D6SSZEFOGLAL\u00D3",
            "ro": "REZUMAT", "ar": "\u0627\u0644\u0645\u0644\u062E\u0635",
            "zh": "\u4E2A\u4EBA\u7B80\u4ECB", "ja": "\u8077\u52D9\u8981\u7D04",
            "ko": "\uC694\uC57D", "hi": "\u0938\u093E\u0930\u093E\u0902\u0936",
            "id": "RINGKASAN", "vi": "T\u00D3M T\u1EAET", "th": "\u0E2A\u0E23\u0E38\u0E1B",
        },
        "experience": {
            "en": "EXPERIENCE", "tr": "DENEY\u0130M",
            "de": "ERFAHRUNG", "fr": "EXP\u00C9RIENCE",
            "es": "EXPERIENCIA", "pt": "EXPERI\u00CANCIA",
            "it": "ESPERIENZA", "nl": "ERVARING",
            "ru": "\u041E\u041F\u042B\u0422 \u0420\u0410\u0411\u041E\u0422\u042B",
            "pl": "DO\u015AWIADCZENIE",
            "sv": "ERFARENHET", "no": "ERFARING", "da": "ERFARING",
            "fi": "TY\u00D6KOKEMUS", "cs": "ZKU\u0160ENOSTI", "hu": "TAPASZTALAT",
            "ro": "EXPERIEN\u021A\u0102", "ar": "\u0627\u0644\u062E\u0628\u0631\u0629",
            "zh": "\u5DE5\u4F5C\u7ECF\u9A8C", "ja": "\u8077\u6B74",
            "ko": "\uACBD\uB825", "hi": "\u0905\u0928\u0941\u092D\u0935",
            "id": "PENGALAMAN", "vi": "KINH NGHI\u1EC6M", "th": "\u0E1B\u0E23\u0E30\u0E2A\u0E1A\u0E01\u0E32\u0E23\u0E13\u0E4C",
        },
        "education": {
            "en": "EDUCATION", "tr": "E\u011E\u0130T\u0130M",
            "de": "AUSBILDUNG", "fr": "FORMATION",
            "es": "EDUCACI\u00D3N", "pt": "EDUCA\u00C7\u00C3O",
            "it": "ISTRUZIONE", "nl": "OPLEIDING",
            "ru": "\u041E\u0411\u0420\u0410\u0417\u041E\u0412\u0410\u041D\u0418\u0415",
            "pl": "WYKSZTA\u0141CENIE",
            "sv": "UTBILDNING", "no": "UTDANNING", "da": "UDDANNELSE",
            "fi": "KOULUTUS", "cs": "VZD\u011AL\u00C1N\u00CD", "hu": "V\u00C9GZETTS\u00C9G",
            "ro": "EDUCA\u021AIE", "ar": "\u0627\u0644\u062A\u0639\u0644\u064A\u0645",
            "zh": "\u6559\u80B2", "ja": "\u5B66\u6B74",
            "ko": "\uD559\uB825", "hi": "\u0936\u093F\u0915\u094D\u0937\u093E",
            "id": "PENDIDIKAN", "vi": "H\u1ECCC V\u1EA4N", "th": "\u0E01\u0E32\u0E23\u0E28\u0E36\u0E01\u0E29\u0E32",
        },
        "skills": {
            "en": "SKILLS", "tr": "YETENEKLER",
            "de": "F\u00C4HIGKEITEN", "fr": "COMP\u00C9TENCES",
            "es": "HABILIDADES", "pt": "HABILIDADES",
            "it": "COMPETENZE", "nl": "VAARDIGHEDEN",
            "ru": "\u041D\u0410\u0412\u042B\u041A\u0418", "pl": "UMIEJ\u0118TNO\u015ACI",
            "sv": "F\u00C4RDIGHETER", "no": "FERDIGHETER", "da": "F\u00C6RDIGHEDER",
            "fi": "TAIDOT", "cs": "DOVEDNOSTI", "hu": "K\u00C9SZS\u00C9GEK",
            "ro": "COMPETEN\u021AE", "ar": "\u0627\u0644\u0645\u0647\u0627\u0631\u0627\u062A",
            "zh": "\u6280\u80FD", "ja": "\u30B9\u30AD\u30EB",
            "ko": "\uAE30\uC220", "hi": "\u0915\u094C\u0936\u0932",
            "id": "KEAHLIAN", "vi": "K\u1EF8 N\u0102NG", "th": "\u0E17\u0E31\u0E01\u0E29\u0E30",
        },
        "projects": {
            "en": "PROJECTS", "tr": "PROJELER",
            "de": "PROJEKTE", "fr": "PROJETS",
            "es": "PROYECTOS", "pt": "PROJETOS",
            "it": "PROGETTI", "nl": "PROJECTEN",
            "ru": "\u041F\u0420\u041E\u0415\u041A\u0422\u042B", "pl": "PROJEKTY",
            "sv": "PROJEKT", "no": "PROSJEKTER", "da": "PROJEKTER",
            "fi": "PROJEKTIT", "cs": "PROJEKTY", "hu": "PROJEKTEK",
            "ro": "PROIECTE", "ar": "\u0627\u0644\u0645\u0634\u0627\u0631\u064A\u0639",
            "zh": "\u9879\u76EE", "ja": "\u30D7\u30ED\u30B8\u30A7\u30AF\u30C8",
            "ko": "\uD504\uB85C\uC81D\uD2B8", "hi": "\u092A\u0930\u093F\u092F\u094B\u091C\u0928\u093E\u090F\u0902",
            "id": "PROYEK", "vi": "D\u1EF0 \u00C1N", "th": "\u0E42\u0E04\u0E23\u0E07\u0E01\u0E32\u0E23",
        },
        "certifications": {
            "en": "CERTIFICATIONS", "tr": "SERT\u0130F\u0130KALAR",
            "de": "ZERTIFIZIERUNGEN", "fr": "CERTIFICATIONS",
            "es": "CERTIFICACIONES", "pt": "CERTIFICA\u00C7\u00D5ES",
            "it": "CERTIFICAZIONI", "nl": "CERTIFICERINGEN",
            "ru": "\u0421\u0415\u0420\u0422\u0418\u0424\u0418\u041A\u0410\u0422\u042B",
            "pl": "CERTYFIKATY",
            "sv": "CERTIFIERINGAR", "no": "SERTIFISERINGER", "da": "CERTIFICERINGER",
            "fi": "SERTIFIKAATIT", "cs": "CERTIFIK\u00C1TY", "hu": "TAN\u00DAS\u00CDTV\u00C1NYOK",
            "ro": "CERTIFIC\u0102RI", "ar": "\u0627\u0644\u0634\u0647\u0627\u062F\u0627\u062A",
            "zh": "\u8BC1\u4E66", "ja": "\u8CC7\u683C",
            "ko": "\uC790\uACA9\uC99D", "hi": "\u092A\u094D\u0930\u092E\u093E\u0923\u092A\u0924\u094D\u0930",
            "id": "SERTIFIKASI", "vi": "CH\u1EE8NG CH\u1EC8", "th": "\u0E43\u0E1A\u0E23\u0E31\u0E1A\u0E23\u0E2D\u0E07",
        },
        "languages": {
            "en": "LANGUAGES", "tr": "D\u0130LLER",
            "de": "SPRACHEN", "fr": "LANGUES",
            "es": "IDIOMAS", "pt": "IDIOMAS",
            "it": "LINGUE", "nl": "TALEN",
            "ru": "\u042F\u0417\u042B\u041A\u0418", "pl": "J\u0118ZYKI",
            "sv": "SPR\u00C5K", "no": "SPR\u00C5K", "da": "SPROG",
            "fi": "KIELET", "cs": "JAZYKY", "hu": "NYELVEK",
            "ro": "LIMBI", "ar": "\u0627\u0644\u0644\u063A\u0627\u062A",
            "zh": "\u8BED\u8A00", "ja": "\u8A00\u8A9E",
            "ko": "\uC5B8\uC5B4", "hi": "\u092D\u093E\u0937\u093E\u090F\u0902",
            "id": "BAHASA", "vi": "NG\u00D4N NG\u1EEE", "th": "\u0E20\u0E32\u0E29\u0E32",
        },
        "interests": {
            "en": "INTERESTS", "tr": "\u0130LG\u0130 ALANLARI",
            "de": "INTERESSEN", "fr": "CENTRES D'INT\u00C9R\u00CAT",
            "es": "INTERESES", "pt": "INTERESSES",
            "it": "INTERESSI", "nl": "INTERESSES",
            "ru": "\u0418\u041D\u0422\u0415\u0420\u0415\u0421\u042B", "pl": "ZAINTERESOWANIA",
            "sv": "INTRESSEN", "no": "INTERESSER", "da": "INTERESSER",
            "fi": "KIINNOSTUKSET", "cs": "Z\u00C1JMY", "hu": "\u00C9RDEKL\u0150D\u00C9S",
            "ro": "INTERESE", "ar": "\u0627\u0644\u0627\u0647\u062A\u0645\u0627\u0645\u0627\u062A",
            "zh": "\u5174\u8DA3", "ja": "\u8DA3\u5473",
            "ko": "\uAD00\uC2EC\uC0AC", "hi": "\u0930\u0941\u091A\u093F\u092F\u093E\u0902",
            "id": "MINAT", "vi": "S\u1EDE TH\u00CDCH", "th": "\u0E04\u0E27\u0E32\u0E21\u0E2A\u0E19\u0E43\u0E08",
        },
        "misc": {
            "en": "OTHER", "tr": "D\u0130\u011EER",
            "de": "SONSTIGES", "fr": "AUTRES",
            "es": "OTROS", "pt": "OUTROS",
            "it": "ALTRO", "nl": "OVERIG",
            "ru": "\u041F\u0420\u041E\u0427\u0415\u0415", "pl": "INNE",
            "sv": "\u00D6VRIGT", "no": "ANNET", "da": "ANDET",
            "fi": "MUUT", "cs": "OSTATN\u00CD", "hu": "EGY\u00C9B",
            "ro": "ALTELE", "ar": "\u0623\u062E\u0631\u0649",
            "zh": "\u5176\u4ED6", "ja": "\u305D\u306E\u4ED6",
            "ko": "\uAE30\uD0C0", "hi": "\u0905\u0928\u094D\u092F",
            "id": "LAINNYA", "vi": "KH\u00C1C", "th": "\u0E2D\u0E37\u0E48\u0E19\u0E46",
        },
    }

    # Normalize variant keys to canonical
    _KEY_ALIASES = {
        "experiences": "experience", "exp": "experience",
        "work_experience": "experience", "professional_experience": "experience",
        "edu": "education", "academic": "education",
        "skill": "skills", "competencies": "skills",
        "project": "projects",
        "certification": "certifications", "certificates": "certifications",
        "language": "languages",
        "profile": "summary", "objective": "summary", "about": "summary",
    }

    def _h(section: str) -> str:
        key = section.lower().strip()
        key = _KEY_ALIASES.get(key, key)
        # Use original header from CV if available — preserve original case
        try:
            original = (_titles.get(key) or "").strip()
            # If original is just the canonical key, treat as missing
            if original and original.lower() == key:
                original = ""
            if original:
                return original
        except Exception:
            pass
        # Fallback to language-based translation
        fb = _FALLBACK.get(key, {})
        result = fb.get(lang, fb.get("en", "")) or key.upper()
        return result or key.upper()

    pdf = _PDF()
    font_family = _register_font(pdf, font_name)
    pdf.set_margins(margin_mm, margin_mm, margin_mm)
    pdf.set_auto_page_break(auto=True, margin=margin_mm)
    pdf.add_page()

    usable_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ── helper: word-based text wrapping using actual glyph widths ──
    def _break_long_word(word: str, max_w: float) -> list[str]:
        """Break a single word that exceeds *max_w* into chunks that fit."""
        if max_w <= 0:
            return [word]
        parts: list[str] = []
        buf = ""
        for ch in word:
            test = buf + ch
            if pdf.get_string_width(test) > max_w and buf:
                parts.append(buf)
                buf = ch
            else:
                buf = test
        if buf:
            parts.append(buf)
        return parts or [word]

    def _wrap_text(text: str, max_w: float) -> list[str]:
        """Split *text* into lines that fit within *max_w* mm.

        Breaks on spaces first; if a single word is wider than *max_w*
        it is broken at the character level to prevent overflow.
        """
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for w in words:
            # If this single word is wider than max_w, break it
            if pdf.get_string_width(w) > max_w:
                if current:
                    lines.append(current)
                    current = ""
                lines.extend(_break_long_word(w, max_w))
                continue
            if not current:
                current = w
            else:
                test = current + " " + w
                if pdf.get_string_width(test) <= max_w:
                    current = test
                else:
                    lines.append(current)
                    current = w
        if current:
            lines.append(current)
        return lines or [""]

    # ── helper: write one text block with optional indent ──
    def _cell(text: str, bold: bool = False, indent: float = 0.0,
              fs: float | None = None, align: str = "L"):
        txt = _clean(text)
        if not txt:
            return
        # Force no-bold for bullet-like text
        if txt.startswith(("\u2022", "-", "*", "\u25aa", "\u25a0")):
            bold = False
        sz = fs or (section_size if bold else body_size)
        pdf.set_font(font_family, "B" if bold else "", sz)
        effective_w = usable_w - indent
        wrapped = _wrap_text(txt, effective_w)
        for wl in wrapped:
            if check_height(pdf.get_y(), lh, pdf.h, pdf.b_margin):
                new_page(pdf)
            pdf.set_x(pdf.l_margin + indent)
            pdf.cell(effective_w, lh, wl, ln=True, align=align)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(font_family, "", body_size)

    def _section_header(title: str):
        """Draw section title with underline."""
        pdf.ln(spacing * 0.6)
        if check_height(pdf.get_y(), lh * 2, pdf.h, pdf.b_margin):
            new_page(pdf)
        pdf.set_font(font_family, "B", section_size)
        cleaned = _clean(title)
        wrapped = _wrap_text(cleaned, usable_w)
        for wl in wrapped:
            if check_height(pdf.get_y(), lh, pdf.h, pdf.b_margin):
                new_page(pdf)
            pdf.set_x(pdf.l_margin)
            pdf.cell(usable_w, lh, wl, ln=True)
        # Draw thin underline
        y = pdf.get_y()
        pdf.set_line_width(0.3)
        pdf.set_draw_color(150, 150, 150)
        pdf.line(pdf.l_margin, y, pdf.l_margin + usable_w, y)
        pdf.ln(spacing * 0.3)
        pdf.set_font(font_family, "", body_size)

    def _bullet(text: str):
        """Render a bullet point with fixed alignment."""
        txt = _clean(text)
        if not txt:
            return
        txt = re.sub(r'^[\u2022\u25aa\u25a0\-\*]+\s*', '', txt)
        pdf.set_font(font_family, "", body_size)
        bullet_w = usable_w - bullet_text_offset
        wrapped = _wrap_text(txt, bullet_w)
        for i, wl in enumerate(wrapped):
            if check_height(pdf.get_y(), lh, pdf.h, pdf.b_margin):
                new_page(pdf)
            if i == 0:
                pdf.set_x(pdf.l_margin + bullet_indent)
                pdf.cell(bullet_text_offset - bullet_indent, lh, "\u2022 ", ln=False)
            else:
                pdf.set_x(pdf.l_margin + bullet_text_offset)
            pdf.cell(bullet_w, lh, wl, ln=True, align="L")
        pdf.set_x(pdf.l_margin)

    def _gap(factor: float = 0.5):
        pdf.ln(spacing * factor)

    # ── HEADER — centered name + contacts ──
    header_lines = render_header(cv_model)
    for i, hl in enumerate(header_lines):
        if i == 0:
            _cell(hl, bold=True, fs=header_size, align="C")
        else:
            _cell(hl, fs=body_size, align="C")
    _gap()

    # ── Section rendering helpers ──
    def _render_summary():
        summary = (cv_model.summary or "").strip()
        if not summary:
            return
        _section_header(_h("summary"))
        summary = summary.replace("\r\n", "\n").replace("\r", "\n")
        summary = re.sub(r"\n{2,}", "\n", summary)
        for para in summary.split("\n"):
            para = para.strip()
            if para:
                _cell(para)
        _gap(0.3)

    def _estimate_block_lines(texts: list) -> int:
        """Estimate how many PDF lines a block of text will occupy."""
        total = 0
        for txt in texts:
            cleaned = _clean(txt)
            if not cleaned:
                continue
            ew = usable_w - bullet_text_offset if cleaned.startswith(("-", "\u2022", "\u25aa", "\u25a0")) else usable_w
            total += max(1, len(_wrap_text(cleaned, ew)))
        return total

    def _render_experience():
        if not cv_model.experiences:
            return
        _section_header(_h("experience"))
        for exp in cv_model.experiences:
            lines = render_experience(exp)
            has_title = bool((getattr(exp, "title", "") or "").strip() or
                             (getattr(exp, "company", "") or "").strip())
            block_h = _estimate_block_lines(lines) * lh + spacing
            if check_height(pdf.get_y(), block_h, pdf.h, pdf.b_margin):
                new_page(pdf)
            for i, txt in enumerate(lines):
                if txt.startswith(("- ", "\u2022", "\u25aa", "\u25a0")):
                    _bullet(txt)
                elif i == 0 and has_title:
                    _cell(txt, bold=True)
                else:
                    _cell(txt)
            _gap(0.3)
        pdf.set_font(font_family, "", body_size)

    def _render_education():
        if not cv_model.education:
            return
        _section_header(_h("education"))
        for edu in cv_model.education:
            edu_lines = render_education(edu)
            for i, txt in enumerate(edu_lines):
                _cell(txt, bold=(i == 0))
            _gap(0.2)
        pdf.set_font(font_family, "", body_size)

    def _render_skills():
        skill_lines = render_skills(cv_model)
        if not skill_lines:
            return
        _section_header(_h("skills"))
        # Compute uniform category column width (widest category)
        pdf.set_font(font_family, "B", body_size)
        cat_col_w = 0.0
        for txt in skill_lines:
            cleaned = _clean(txt)
            if ":" in cleaned:
                cat_name = cleaned.partition(":")[0]
                w = pdf.get_string_width(cat_name + ": ") + 1
                if w > cat_col_w:
                    cat_col_w = w
        cat_col_w = min(cat_col_w, usable_w * 0.4)  # cap at 40% of page
        pdf.set_font(font_family, "", body_size)
        vals_col_w = usable_w - cat_col_w

        for txt in skill_lines:
            cleaned = _clean(txt)
            if ":" in cleaned:
                cat, _, vals = cleaned.partition(":")
                wrapped_vals = _wrap_text(vals.strip(), vals_col_w)
                for j, vl in enumerate(wrapped_vals):
                    if check_height(pdf.get_y(), lh, pdf.h, pdf.b_margin):
                        new_page(pdf)
                    if j == 0:
                        pdf.set_font(font_family, "B", body_size)
                        pdf.set_x(pdf.l_margin)
                        pdf.cell(cat_col_w, lh, cat + ":", ln=False)
                        pdf.set_font(font_family, "", body_size)
                        pdf.cell(vals_col_w, lh, vl, ln=True, align="L")
                    else:
                        pdf.set_x(pdf.l_margin + cat_col_w)
                        pdf.cell(vals_col_w, lh, vl, ln=True, align="L")
            else:
                _cell(cleaned)
        _gap(0.3)
        pdf.set_font(font_family, "", body_size)

    def _render_projects():
        if not cv_model.projects:
            return
        _section_header(_h("projects"))
        for proj in cv_model.projects:
            proj_lines = render_project(proj)
            has_name = bool((getattr(proj, "name", "") or "").strip())
            block_h = _estimate_block_lines(proj_lines) * lh + spacing
            if check_height(pdf.get_y(), block_h, pdf.h, pdf.b_margin):
                new_page(pdf)
            for i, txt in enumerate(proj_lines):
                if txt.startswith(("- ", "\u2022", "\u25aa", "\u25a0")):
                    _bullet(txt)
                elif i == 0 and has_name:
                    _cell(txt, bold=True)
                else:
                    _cell(txt)
            _gap(0.2)
        pdf.set_font(font_family, "", body_size)

    def _render_certifications():
        certs = getattr(cv_model, "certifications", None) or []
        if not certs:
            return
        _section_header(_h("certifications"))
        for cert in certs:
            name = _clean(getattr(cert, "name", "") or "")
            issuer = _clean(getattr(cert, "issuer", "") or "")
            date = _clean(getattr(cert, "date", "") or "")
            parts = [p for p in [name, issuer, date] if p]
            _cell(" \u2013 ".join(parts))
        _gap(0.2)

    def _render_languages():
        languages = getattr(cv_model, "languages", None) or []
        if not languages:
            return
        _section_header(_h("languages"))
        lang_parts = [_clean(str(la)) for la in languages if str(la or "").strip()]
        _cell(", ".join(lang_parts))
        _gap(0.2)

    def _render_interests():
        interests_list = getattr(cv_model, "interests", None) or []
        if not interests_list:
            return
        _section_header(_h("interests"))
        parts = [_clean(str(i)) for i in interests_list if str(i or "").strip()]
        _cell(", ".join(parts))
        _gap(0.2)

    def _render_misc():
        misc_list = getattr(cv_model, "misc", None) or []
        if not misc_list:
            return
        _section_header(_h("misc"))
        parts = [_clean(str(i)) for i in misc_list if str(i or "").strip()]
        _cell(", ".join(parts))
        _gap(0.2)

    # ── Render sections in configurable ATS order, misc always last ──
    _section_renderers = {
        "summary": _render_summary,
        "experience": _render_experience,
        "projects": _render_projects,
        "education": _render_education,
        "skills": _render_skills,
        "certifications": _render_certifications,
        "languages": _render_languages,
        "interests": _render_interests,
    }

    for section_name in get_section_order():
        if section_name == "misc":
            continue
        renderer = _section_renderers.get(section_name)
        if renderer:
            renderer()

    # misc always renders last
    _render_misc()

    out = BytesIO()
    pdf.output(out)
    out.seek(0)
    return out
