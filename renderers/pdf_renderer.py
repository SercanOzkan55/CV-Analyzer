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
    "arial": ("arial.ttf", "arialbd.ttf"),
    "calibri": ("calibri.ttf", "calibrib.ttf"),
    "times new roman": ("times.ttf", "timesbd.ttf"),
    "georgia": ("georgia.ttf", "georgiab.ttf"),
    "cambria": ("cambria.ttc", "cambriab.ttf"),
    "tahoma": ("tahoma.ttf", "tahomabd.ttf"),
    "segoe ui": ("segoeui.ttf", "segoeuib.ttf"),
    "consolas": ("consola.ttf", "consolab.ttf"),
    "garamond": ("GARA.TTF", "GARABD.TTF"),
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
            "en": "PROFESSIONAL SUMMARY",
            "tr": "PROFESYONEL \u00d6ZET",
            "de": "ZUSAMMENFASSUNG",
            "fr": "R\u00c9SUM\u00c9 PROFESSIONNEL",
            "es": "RESUMEN PROFESIONAL",
            "pt": "RESUMO PROFISSIONAL",
            "it": "PROFILO PROFESSIONALE",
            "nl": "SAMENVATTING",
            "ru": "\u0420\u0415\u0417\u042e\u041c\u0415",
            "pl": "PODSUMOWANIE ZAWODOWE",
            "sv": "SAMMANFATTNING",
            "no": "SAMMENDRAG",
            "da": "RESUM\u00c9",
            "fi": "YHTEENVETO",
            "cs": "SHRNUT\u00cd",
            "hu": "\u00d6SSZEFOGLAL\u00d3",
            "ro": "REZUMAT",
            "ar": "\u0627\u0644\u0645\u0644\u062e\u0635",
            "zh": "\u4e2a\u4eba\u7b80\u4ecb",
            "ja": "\u8077\u52d9\u8981\u7d04",
            "ko": "\uc694\uc57d",
            "hi": "\u0938\u093e\u0930\u093e\u0902\u0936",
            "id": "RINGKASAN",
            "vi": "T\u00d3M T\u1eaeT",
            "th": "\u0e2a\u0e23\u0e38\u0e1b",
        },
        "experience": {
            "en": "EXPERIENCE",
            "tr": "DENEY\u0130M",
            "de": "ERFAHRUNG",
            "fr": "EXP\u00c9RIENCE",
            "es": "EXPERIENCIA",
            "pt": "EXPERI\u00caNCIA",
            "it": "ESPERIENZA",
            "nl": "ERVARING",
            "ru": "\u041e\u041f\u042b\u0422 \u0420\u0410\u0411\u041e\u0422\u042b",
            "pl": "DO\u015aWIADCZENIE",
            "sv": "ERFARENHET",
            "no": "ERFARING",
            "da": "ERFARING",
            "fi": "TY\u00d6KOKEMUS",
            "cs": "ZKU\u0160ENOSTI",
            "hu": "TAPASZTALAT",
            "ro": "EXPERIEN\u021a\u0102",
            "ar": "\u0627\u0644\u062e\u0628\u0631\u0629",
            "zh": "\u5de5\u4f5c\u7ecf\u9a8c",
            "ja": "\u8077\u6b74",
            "ko": "\uacbd\ub825",
            "hi": "\u0905\u0928\u0941\u092d\u0935",
            "id": "PENGALAMAN",
            "vi": "KINH NGHI\u1ec6M",
            "th": "\u0e1b\u0e23\u0e30\u0e2a\u0e1a\u0e01\u0e32\u0e23\u0e13\u0e4c",
        },
        "education": {
            "en": "EDUCATION",
            "tr": "E\u011e\u0130T\u0130M",
            "de": "AUSBILDUNG",
            "fr": "FORMATION",
            "es": "EDUCACI\u00d3N",
            "pt": "EDUCA\u00c7\u00c3O",
            "it": "ISTRUZIONE",
            "nl": "OPLEIDING",
            "ru": "\u041e\u0411\u0420\u0410\u0417\u041e\u0412\u0410\u041d\u0418\u0415",
            "pl": "WYKSZTA\u0141CENIE",
            "sv": "UTBILDNING",
            "no": "UTDANNING",
            "da": "UDDANNELSE",
            "fi": "KOULUTUS",
            "cs": "VZD\u011aL\u00c1N\u00cd",
            "hu": "V\u00c9GZETTS\u00c9G",
            "ro": "EDUCA\u021aIE",
            "ar": "\u0627\u0644\u062a\u0639\u0644\u064a\u0645",
            "zh": "\u6559\u80b2",
            "ja": "\u5b66\u6b74",
            "ko": "\ud559\ub825",
            "hi": "\u0936\u093f\u0915\u094d\u0937\u093e",
            "id": "PENDIDIKAN",
            "vi": "H\u1eccC V\u1ea4N",
            "th": "\u0e01\u0e32\u0e23\u0e28\u0e36\u0e01\u0e29\u0e32",
        },
        "skills": {
            "en": "SKILLS",
            "tr": "YETENEKLER",
            "de": "F\u00c4HIGKEITEN",
            "fr": "COMP\u00c9TENCES",
            "es": "HABILIDADES",
            "pt": "HABILIDADES",
            "it": "COMPETENZE",
            "nl": "VAARDIGHEDEN",
            "ru": "\u041d\u0410\u0412\u042b\u041a\u0418",
            "pl": "UMIEJ\u0118TNO\u015aCI",
            "sv": "F\u00c4RDIGHETER",
            "no": "FERDIGHETER",
            "da": "F\u00c6RDIGHEDER",
            "fi": "TAIDOT",
            "cs": "DOVEDNOSTI",
            "hu": "K\u00c9SZS\u00c9GEK",
            "ro": "COMPETEN\u021aE",
            "ar": "\u0627\u0644\u0645\u0647\u0627\u0631\u0627\u062a",
            "zh": "\u6280\u80fd",
            "ja": "\u30b9\u30ad\u30eb",
            "ko": "\uae30\uc220",
            "hi": "\u0915\u094c\u0936\u0932",
            "id": "KEAHLIAN",
            "vi": "K\u1ef8 N\u0102NG",
            "th": "\u0e17\u0e31\u0e01\u0e29\u0e30",
        },
        "projects": {
            "en": "PROJECTS",
            "tr": "PROJELER",
            "de": "PROJEKTE",
            "fr": "PROJETS",
            "es": "PROYECTOS",
            "pt": "PROJETOS",
            "it": "PROGETTI",
            "nl": "PROJECTEN",
            "ru": "\u041f\u0420\u041e\u0415\u041a\u0422\u042b",
            "pl": "PROJEKTY",
            "sv": "PROJEKT",
            "no": "PROSJEKTER",
            "da": "PROJEKTER",
            "fi": "PROJEKTIT",
            "cs": "PROJEKTY",
            "hu": "PROJEKTEK",
            "ro": "PROIECTE",
            "ar": "\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639",
            "zh": "\u9879\u76ee",
            "ja": "\u30d7\u30ed\u30b8\u30a7\u30af\u30c8",
            "ko": "\ud504\ub85c\uc81d\ud2b8",
            "hi": "\u092a\u0930\u093f\u092f\u094b\u091c\u0928\u093e\u090f\u0902",
            "id": "PROYEK",
            "vi": "D\u1ef0 \u00c1N",
            "th": "\u0e42\u0e04\u0e23\u0e07\u0e01\u0e32\u0e23",
        },
        "certifications": {
            "en": "CERTIFICATIONS",
            "tr": "SERT\u0130F\u0130KALAR",
            "de": "ZERTIFIZIERUNGEN",
            "fr": "CERTIFICATIONS",
            "es": "CERTIFICACIONES",
            "pt": "CERTIFICA\u00c7\u00d5ES",
            "it": "CERTIFICAZIONI",
            "nl": "CERTIFICERINGEN",
            "ru": "\u0421\u0415\u0420\u0422\u0418\u0424\u0418\u041a\u0410\u0422\u042b",
            "pl": "CERTYFIKATY",
            "sv": "CERTIFIERINGAR",
            "no": "SERTIFISERINGER",
            "da": "CERTIFICERINGER",
            "fi": "SERTIFIKAATIT",
            "cs": "CERTIFIK\u00c1TY",
            "hu": "TAN\u00daS\u00cdTV\u00c1NYOK",
            "ro": "CERTIFIC\u0102RI",
            "ar": "\u0627\u0644\u0634\u0647\u0627\u062f\u0627\u062a",
            "zh": "\u8bc1\u4e66",
            "ja": "\u8cc7\u683c",
            "ko": "\uc790\uaca9\uc99d",
            "hi": "\u092a\u094d\u0930\u092e\u093e\u0923\u092a\u0924\u094d\u0930",
            "id": "SERTIFIKASI",
            "vi": "CH\u1ee8NG CH\u1ec8",
            "th": "\u0e43\u0e1a\u0e23\u0e31\u0e1a\u0e23\u0e2d\u0e07",
        },
        "languages": {
            "en": "LANGUAGES",
            "tr": "D\u0130LLER",
            "de": "SPRACHEN",
            "fr": "LANGUES",
            "es": "IDIOMAS",
            "pt": "IDIOMAS",
            "it": "LINGUE",
            "nl": "TALEN",
            "ru": "\u042f\u0417\u042b\u041a\u0418",
            "pl": "J\u0118ZYKI",
            "sv": "SPR\u00c5K",
            "no": "SPR\u00c5K",
            "da": "SPROG",
            "fi": "KIELET",
            "cs": "JAZYKY",
            "hu": "NYELVEK",
            "ro": "LIMBI",
            "ar": "\u0627\u0644\u0644\u063a\u0627\u062a",
            "zh": "\u8bed\u8a00",
            "ja": "\u8a00\u8a9e",
            "ko": "\uc5b8\uc5b4",
            "hi": "\u092d\u093e\u0937\u093e\u090f\u0902",
            "id": "BAHASA",
            "vi": "NG\u00d4N NG\u1eee",
            "th": "\u0e20\u0e32\u0e29\u0e32",
        },
        "interests": {
            "en": "INTERESTS",
            "tr": "\u0130LG\u0130 ALANLARI",
            "de": "INTERESSEN",
            "fr": "CENTRES D'INT\u00c9R\u00caT",
            "es": "INTERESES",
            "pt": "INTERESSES",
            "it": "INTERESSI",
            "nl": "INTERESSES",
            "ru": "\u0418\u041d\u0422\u0415\u0420\u0415\u0421\u042b",
            "pl": "ZAINTERESOWANIA",
            "sv": "INTRESSEN",
            "no": "INTERESSER",
            "da": "INTERESSER",
            "fi": "KIINNOSTUKSET",
            "cs": "Z\u00c1JMY",
            "hu": "\u00c9RDEKL\u0150D\u00c9S",
            "ro": "INTERESE",
            "ar": "\u0627\u0644\u0627\u0647\u062a\u0645\u0627\u0645\u0627\u062a",
            "zh": "\u5174\u8da3",
            "ja": "\u8da3\u5473",
            "ko": "\uad00\uc2ec\uc0ac",
            "hi": "\u0930\u0941\u091a\u093f\u092f\u093e\u0902",
            "id": "MINAT",
            "vi": "S\u1ede TH\u00cdCH",
            "th": "\u0e04\u0e27\u0e32\u0e21\u0e2a\u0e19\u0e43\u0e08",
        },
        "misc": {
            "en": "OTHER",
            "tr": "D\u0130\u011eER",
            "de": "SONSTIGES",
            "fr": "AUTRES",
            "es": "OTROS",
            "pt": "OUTROS",
            "it": "ALTRO",
            "nl": "OVERIG",
            "ru": "\u041f\u0420\u041e\u0427\u0415\u0415",
            "pl": "INNE",
            "sv": "\u00d6VRIGT",
            "no": "ANNET",
            "da": "ANDET",
            "fi": "MUUT",
            "cs": "OSTATN\u00cd",
            "hu": "EGY\u00c9B",
            "ro": "ALTELE",
            "ar": "\u0623\u062e\u0631\u0649",
            "zh": "\u5176\u4ed6",
            "ja": "\u305d\u306e\u4ed6",
            "ko": "\uae30\ud0c0",
            "hi": "\u0905\u0928\u094d\u092f",
            "id": "LAINNYA",
            "vi": "KH\u00c1C",
            "th": "\u0e2d\u0e37\u0e48\u0e19\u0e46",
        },
    }

    # Normalize variant keys to canonical
    _KEY_ALIASES = {
        "experiences": "experience",
        "exp": "experience",
        "work_experience": "experience",
        "professional_experience": "experience",
        "edu": "education",
        "academic": "education",
        "skill": "skills",
        "competencies": "skills",
        "project": "projects",
        "certification": "certifications",
        "certificates": "certifications",
        "language": "languages",
        "profile": "summary",
        "objective": "summary",
        "about": "summary",
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
    def _cell(text: str, bold: bool = False, indent: float = 0.0, fs: float | None = None, align: str = "L"):
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
        txt = re.sub(r"^[\u2022\u25aa\u25a0\-\*]+\s*", "", txt)
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
            has_title = bool((getattr(exp, "title", "") or "").strip() or (getattr(exp, "company", "") or "").strip())
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
