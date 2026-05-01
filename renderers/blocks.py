from __future__ import annotations

import logging
import re
import textwrap
import unicodedata
from typing import List

logger = logging.getLogger("app.blocks")

from schemas.cv_model import CVModel, Education, Experience, Project


# ── Standalone-diacritic → combining-diacritic mapping ──
# PDF extractors often emit standalone diacritics *before* the base letter
# instead of proper combining characters (e.g. ¨O instead of Ö).
_STANDALONE_TO_COMBINING: dict[str, str] = {
    "\u00A8": "\u0308",  # DIAERESIS  ¨  → ö ü ä ë ï
    "\u00B8": "\u0327",  # CEDILLA    ¸  → ç ş
    "\u02D8": "\u0306",  # BREVE      ˘  → ğ
    "\u02D9": "\u0307",  # DOT ABOVE  ˙  → İ
    "\u00B4": "\u0301",  # ACUTE      ´  → é á í
    "\u0060": "\u0300",  # GRAVE      `  → è à
    "\u02DC": "\u0303",  # TILDE      ˜  → ñ ã
    "\u02C7": "\u030C",  # CARON      ˇ  → š č ž
    "\u02DA": "\u030A",  # RING ABOVE ˚  → å
}

_DIACRIT_BEFORE_LETTER_RE = re.compile(
    "([" + "".join(re.escape(d) for d in _STANDALONE_TO_COMBINING) + r"])([A-Za-z\u00C0-\u024F])"
)


def fix_decomposed_diacritics(text: str) -> str:
    """Convert standalone diacritics before letters to proper composed chars.

    PDF extractors frequently produce '¨O' instead of 'Ö', '¸s' instead of
    'ş', '˘g' instead of 'ğ', etc.  This function re-orders them so that
    NFC normalisation can compose them into the correct codepoint.
    """
    def _reorder(m: re.Match) -> str:
        combining = _STANDALONE_TO_COMBINING[m.group(1)]
        return m.group(2) + combining          # letter + combining mark
    text = _DIACRIT_BEFORE_LETTER_RE.sub(_reorder, text)
    return unicodedata.normalize("NFC", text)


def _clean(value: str) -> str:
    """Normalise text: NFC, fix encoding artefacts, collapse whitespace."""
    text = fix_decomposed_diacritics(str(value or ""))
    # Normalize line endings
    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text)
    # Strip markdown bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Clean bullet markers from display text (•, \u2022, ‣, \u2023)
    text = text.replace("\u2022", "-").replace("\u2023", "-").replace("\u25aa", "-").replace("\u25a0", "-")
    # Normalise en-dash / em-dash / box bullets used as bullet prefix at line start
    text = re.sub(r"(?m)^[\u2013\u2014\u25aa\u25a0]\s+", "- ", text)
    # Fix "-\s*-" duplicate bullet prefix
    text = re.sub(r"^-\s*-\s*", "- ", text)
    # Fix "Word- Next" \u2192 "Word \u2014 Next" (em dash) — only ASCII before dash
    text = re.sub(r"([A-Za-z0-9])-\s{2,}([A-Z])", "\\1 \u2014 \\2", text)
    # Fix "Word(" → "Word ("
    text = re.sub(r"([A-Za-z])\(", r"\1 (", text)
    # Collapse horizontal whitespace only (preserve \n)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ── header helpers ──────────────────────────────────────────────────────────

# Structural pattern: values that cannot be a person's name.
_NOT_NAME_RE = re.compile(r"[:@]|\d")

_CONTACT_RE = re.compile(r"@|https?://|linkedin|github|\.com|\.io|\d{5,}", re.I)


def _is_likely_location(text: str) -> bool:
    """Return *True* if *text* looks like a place rather than a person name."""
    if not text:
        return False
    if "," in text:                         # "Istanbul, Turkey"
        return True
    if re.search(r"\d", text):              # zip / street nr
        return True
    return False


def _rescue_name(model: CVModel):
    """Return (name, title, location) ensuring *name* is populated when possible.

    Rules
    -----
    * If full_name is already set → keep it.
    * If full_name is empty and *location* does NOT look like a location
      (no comma, no digits, no URL/email tokens, 2-5 words) → promote it
      to name and clear location.
    * If still empty, try to detect from the first line of summary.
    * Never touch the parser; only re-shuffle builder fields.
    """
    from services.cv_autofix_service import _looks_like_person_name

    name = (model.full_name or "").strip()
    title = str(getattr(model, "title", "") or "").strip()
    location = (model.location or "").strip()

    if not name and location:
        if (
            not _is_likely_location(location)
            and not _CONTACT_RE.search(location)
            and _looks_like_person_name(location)
        ):
            name = location
            location = ""

    # Last resort: check if summary starts with a name-like line
    if not name:
        summary = (model.summary or "").strip()
        first_line = summary.split("\n")[0].strip() if summary else ""
        if _looks_like_person_name(first_line):
            name = first_line

    return name, title, location


# ── public helpers ──────────────────────────────────────────────────────────


def render_header(model: CVModel) -> List[str]:
    name, title, location = _rescue_name(model)

    # Build contact parts — never include the name
    raw_parts = [
        (model.email or "").strip(),
        (model.phone or "").strip(),
        location,
        str(getattr(model, "linkedin", "") or "").strip(),
    ]
    name_lower = name.lower().strip()
    name_words = {w.lower() for w in name.split() if len(w) > 1} if name else set()
    contact_parts = []
    for p in raw_parts:
        if not p:
            continue
        p_lower = p.lower().strip()
        # Skip if the part IS the name
        if p_lower == name_lower:
            continue
        # Skip if the name is a substring of the part
        if name_lower and len(name_lower) > 3 and name_lower in p_lower:
            continue
        # Skip if the part IS just one of the name words (first or last)
        if p_lower in name_words:
            continue
        contact_parts.append(p)
    contact = " | ".join(contact_parts)

    lines: List[str] = []
    if name:
        lines.append(name)       # Rule 1: name always first
    if title:
        lines.append(title)       # Rule 4: title always second
    if contact:
        lines.append(contact)     # Rule 5: contact never contains name
    return lines


def _split_bullets(raw: str) -> List[str]:
    """Split a string that may contain embedded bullet markers into separate items."""
    # Normalise bullet markers to a common form
    text = raw.replace("\u2022", "\n-").replace("\u2023", "\n-").replace("\u25aa", "\n-").replace("\u25a0", "\n-")
    # Treat en-dash / em-dash at start of line as bullet markers
    text = re.sub(r"(?m)^\s*[\u2013\u2014]\s+", "\n- ", text)
    # Split on patterns like "- •", "-•", newline-dash
    text = re.sub(r"\s*-\s*\n-", "\n-", text)
    parts: List[str] = []
    for chunk in re.split(r"\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Strip leading bullet markers
        chunk = re.sub(r"^[\u2022\u25aa\u25a0\-\*]+\s*", "", chunk).strip()
        if chunk:
            parts.append(chunk)
    return parts


def _looks_like_tech_list(text: str) -> bool:
    value = _clean(text)
    if not value or not re.search(r"[,|/]", value):
        return False
    tokens = [part.strip() for part in re.split(r"\s*[,|/]\s*", value) if part.strip()]
    if len(tokens) < 2:
        return False
    if any(len(token.split()) > 4 for token in tokens):
        return False
    return not re.search(r"\b(?:developed|implemented|designed|managed|created|built|geliştirdi|tasarladı)\b", value, re.I)


def render_experience(exp: Experience) -> List[str]:
    """Return structured lines: [title_line, date_line, bullet, bullet, …]"""
    lines: List[str] = []

    # Line 1: Title – Company
    title = _clean(exp.title)
    company = _clean(exp.company)
    header = " \u2013 ".join(p for p in [title, company] if p)
    if header:
        lines.append(header)

    # Line 2: Date | Location
    start = _clean(exp.start_date)
    end = _clean(exp.end_date)
    location = _clean(getattr(exp, "location", "") or "")
    meta: List[str] = []
    if start or end:
        meta.append(" \u2013 ".join(p for p in [start, end] if p))
    if location:
        meta.append(location)
    if meta:
        lines.append(" | ".join(meta))

    # Bullets — each on its own line, guaranteed "- " prefix
    for b in exp.bullets:
        text = str(b or "").strip()
        if not text:
            continue
        # Split embedded bullets (e.g. "text - •next bullet")
        for part in _split_bullets(text):
            if part:
                lines.append("- " + part)

    return lines


def render_education(edu: Education) -> List[str]:
    lines: List[str] = []
    degree = _clean(getattr(edu, "degree", "") or "")
    field = _clean(getattr(edu, "field", "") or "")
    school = _clean(getattr(edu, "school", "") or "")

    # Line 1: Degree – School
    if "|" in degree:
        for d in degree.split("|"):
            d = d.strip()
            if d:
                if school:
                    lines.append(f"{d} \u2013 {school}")
                else:
                    lines.append(d)
    else:
        deg_text = degree + (f" in {field}" if field else "")
        if deg_text.strip() and school:
            lines.append(f"{deg_text} \u2013 {school}")
        elif deg_text.strip():
            lines.append(deg_text)
        elif school:
            lines.append(school)

    # Line 2: Date range
    start = _clean(getattr(edu, "start_date", "") or "")
    end = _clean(getattr(edu, "end_date", "") or "")
    date_parts: List[str] = []
    if start or end:
        date_parts.append(" \u2013 ".join(p for p in [start, end] if p))
    loc = _clean(getattr(edu, "location", "") or "")
    if loc:
        date_parts.append(loc)
    if date_parts:
        lines.append(" | ".join(date_parts))

    # Line 3: GPA (separate line)
    gpa = _clean(getattr(edu, "gpa", "") or "")
    if gpa:
        gpa = gpa.replace("GPA:", "").replace("gpa:", "").strip()
        lines.append(f"GPA: {gpa}")

    return lines


def render_project(proj: Project) -> List[str]:
    lines: List[str] = []
    name = _clean(getattr(proj, "name", "") or "")
    desc = _clean(getattr(proj, "description", "") or "")

    # Fix "Name-Tech" → "Name — Tech" in project titles
    name = re.sub(r"([A-Za-z0-9])\u2013\s*([A-Z])", "\\1 \u2014 \\2", name)
    name = re.sub(r"([A-Za-z0-9])-\s*([A-Z][a-z])", "\\1 \u2014 \\2", name)

    # If description is only a technology stack, keep it on the project title
    # line so project layouts stay consistent across parsed CV variants.
    if name and desc and _looks_like_tech_list(desc):
        name = f"{name} \u2013 {desc}"
        desc = ""

    if name:
        lines.append(name)
    if desc:
        lines.append(desc)

    for b in getattr(proj, "bullets", []) or []:
        text = str(b or "").strip()
        if not text:
            continue
        # Split embedded bullets
        for part in _split_bullets(text):
            if part:
                lines.append("- " + part)

    return lines


def render_skills(model: CVModel) -> List[str]:
    lines: List[str] = []
    skills_map = model.skills_categorized or {}
    for category, values in skills_map.items():
        clean_values = [str(v).strip() for v in values or [] if str(v).strip()]
        if not clean_values:
            continue
        full_line = f"{str(category).strip()}: {', '.join(clean_values)}"
        lines.append(full_line)
    return lines


def render_block(lines: List[str]) -> List[str]:
    result: List[str] = []
    for line in lines or []:
        cleaned = _clean(line)
        if cleaned:
            result.append(cleaned)
    return result


def render_section_generic(
    title: str,
    items: list,
    item_renderer=None,
) -> List[str]:
    if not items:
        return []
    lines: List[str] = [str(title or "").strip()]
    for item in items:
        if item_renderer:
            lines.extend(item_renderer(item))
        else:
            text = str(item or "").strip()
            if text:
                lines.append(text)
    return render_block(lines)


# ── Render safety ───────────────────────────────────────────────────────────

_BULLET_MARKER_RE = re.compile(
    r"^\s*[\u2022\u2023\u25aa\u25a0\u2013\u2014*\-]+\s*"
)

_MAX_LINE_WIDTH = 120

# ── Render safety limits ──────────────────────────────────────────────────
_MAX_RENDER_SECTIONS = 15
_MAX_RENDER_ENTRIES = 50        # max experience/education/project entries
_MAX_RENDER_BULLETS = 20        # max bullets per entry
_MAX_RENDER_ITEMS = 200         # max total flat-list items (skills, etc.)
_MAX_RENDER_CHARS = 200_000     # max total rendered characters

_RENDER_CANONICAL_ORDER = [
    "summary", "experience", "education", "projects", "skills",
    "certifications", "languages", "interests", "misc",
]

_RENDER_SECTION_TO_FIELD = {
    "summary": "summary",
    "experience": "experiences",
    "education": "education",
    "projects": "projects",
    "skills": "skills_categorized",
    "certifications": "certifications",
    "languages": "languages",
    "interests": "interests",
    "misc": "misc",
}

_MAX_HEADER_FIELD_LEN = 200    # max characters per header field


def _sanitize_header_fields(model: CVModel) -> None:
    """Validate and enforce canonical header field order.

    Canonical order (for rendering):
    full_name → title → location → email → phone → linkedin

    Structural checks (no CV-specific rules):
    * If ``full_name`` contains ':', digits, or '@' it cannot be a
      person's name.  Swap it with ``location`` when location looks
      like a name (no structural noise); otherwise clear ``full_name``.
    * If ``full_name`` has commas or digits (address pattern) → move to
      location.
    * If ``full_name`` is still empty, scan other header fields for a
      value that looks like 2-4 capitalised words.

    Mutates *model* in-place.
    """
    from services.cv_autofix_service import _looks_like_person_name

    # ── Clean empty pipe tokens from header fields ──
    _PIPE_CLEANUP_RE = re.compile(r'(?:^\s*\|\s*|\s*\|\s*$|\s*\|\s*(?=\|))')
    for _fld in ("full_name", "title", "email", "phone", "location", "linkedin"):
        _val = getattr(model, _fld, "") or ""
        # Security: cap header field length
        if len(_val) > _MAX_HEADER_FIELD_LEN:
            logger.warning("header field %s truncated %d → %d",
                           _fld, len(_val), _MAX_HEADER_FIELD_LEN)
            _val = _val[:_MAX_HEADER_FIELD_LEN]
            setattr(model, _fld, _val)
        if "|" in _val:
            # Collapse empty pipe segments, strip leading/trailing pipes
            _val = _PIPE_CLEANUP_RE.sub("", _val).strip()
            _val = re.sub(r'\s*\|\s*\|\s*', ' | ', _val)  # collapse double pipes
            _val = _val.strip(" |")
            setattr(model, _fld, _val)

    name = model.full_name
    loc = model.location

    # ── Detect address-in-name: commas or digits → location ──
    if name and _is_likely_location(name) and not _looks_like_person_name(name):
        if not loc:
            model.location = name
        model.full_name = ""
        name = ""
        loc = model.location

    # ── Original noise check: ':', '@', digits ──
    if name and _NOT_NAME_RE.search(name):
        # location looks like a plausible name: no ':', digits, '@'
        if loc and not _NOT_NAME_RE.search(loc) and _looks_like_person_name(loc):
            model.full_name = loc
            model.location = name
        else:
            # Neither field is a valid name — clear full_name so
            # _rescue_name can attempt recovery later.
            model.full_name = ""
            if not loc:
                model.location = name
        name = model.full_name

    # ── Last resort: scan other header fields for a name-like value ──
    if not name:
        for _fld in ("location", "title"):
            _val = (getattr(model, _fld, "") or "").strip()
            if _val and _looks_like_person_name(_val):
                model.full_name = _val
                setattr(model, _fld, "")
                break


def prepare_for_render(model: CVModel) -> CVModel:
    """Apply generic render-safety rules and return a safe copy.

    All rules are CV-format agnostic and apply to every output format.

    1. Deep-copy the model so renderers never mutate the caller's data.
    2. Skip empty sections — purge entries with no meaningful content.
    3. Wrap long lines safely — break at word boundaries.
    4. Normalize bullets — consistent '- ' prefix, strip stray markers.
    5. Header must tolerate missing fields — guarantee string defaults.
    6. Ensure canonical section order in section_titles.
    7. Sanitize header fields — validate full_name, enforce field order.
    """
    # ── Rule 5: Do not mutate original; deep copy first ──
    safe = model.model_copy(deep=True)

    # ── Rule 4: Header must tolerate missing fields ──
    safe.full_name = (safe.full_name or "").strip()
    safe.title = (safe.title or "").strip()
    safe.email = (safe.email or "").strip()
    safe.phone = (safe.phone or "").strip()
    safe.location = (safe.location or "").strip()
    safe.linkedin = str(getattr(safe, "linkedin", "") or "").strip()
    safe.summary = (safe.summary or "").strip()

    # ── Rule 7: Sanitize & order header fields ──
    _sanitize_header_fields(safe)

    # ── Rule 1: Skip empty sections ──
    safe.experiences = [
        exp for exp in safe.experiences
        if any(v.strip() for v in (
            exp.title, exp.company, exp.location,
            exp.start_date, exp.end_date,
        )) or exp.bullets
    ]
    safe.education = [
        edu for edu in safe.education
        if any(v.strip() for v in (
            edu.degree, edu.school, edu.field,
            edu.location, edu.start_date, edu.end_date, edu.gpa,
        ))
    ]
    safe.projects = [
        proj for proj in safe.projects
        if proj.name.strip() or proj.description.strip() or proj.bullets
    ]
    safe.certifications = [
        cert for cert in safe.certifications
        if cert.name.strip() or cert.issuer.strip() or cert.date.strip()
    ]
    if safe.skills_categorized:
        safe.skills_categorized = {
            cat: [s for s in vals if s and s.strip()]
            for cat, vals in safe.skills_categorized.items()
            if vals and any(s and s.strip() for s in vals)
        }
    safe.languages = [l for l in safe.languages if l and l.strip()]
    safe.interests = [i for i in safe.interests if i and i.strip()]
    safe.misc = [m for m in safe.misc if m and m.strip()]

    # ── Render safety: cap section sizes to prevent huge output ──
    if len(safe.experiences) > _MAX_RENDER_ENTRIES:
        logger.warning("render: experiences capped %d → %d",
                       len(safe.experiences), _MAX_RENDER_ENTRIES)
        safe.experiences = safe.experiences[:_MAX_RENDER_ENTRIES]
    if len(safe.education) > _MAX_RENDER_ENTRIES:
        safe.education = safe.education[:_MAX_RENDER_ENTRIES]
    if len(safe.projects) > _MAX_RENDER_ENTRIES:
        safe.projects = safe.projects[:_MAX_RENDER_ENTRIES]
    if len(safe.certifications) > _MAX_RENDER_ENTRIES:
        safe.certifications = safe.certifications[:_MAX_RENDER_ENTRIES]
    for exp in safe.experiences:
        if len(exp.bullets) > _MAX_RENDER_BULLETS:
            exp.bullets = exp.bullets[:_MAX_RENDER_BULLETS]
    for proj in safe.projects:
        if len(proj.bullets) > _MAX_RENDER_BULLETS:
            proj.bullets = proj.bullets[:_MAX_RENDER_BULLETS]
    if len(safe.skills) > _MAX_RENDER_ITEMS:
        safe.skills = safe.skills[:_MAX_RENDER_ITEMS]
    if safe.skills_categorized and len(safe.skills_categorized) > _MAX_RENDER_ITEMS:
        safe.skills_categorized = dict(list(safe.skills_categorized.items())[:_MAX_RENDER_ITEMS])
    if len(safe.languages) > _MAX_RENDER_ITEMS:
        safe.languages = safe.languages[:_MAX_RENDER_ITEMS]
    if len(safe.interests) > _MAX_RENDER_ITEMS:
        safe.interests = safe.interests[:_MAX_RENDER_ITEMS]
    if len(safe.misc) > _MAX_RENDER_ITEMS:
        safe.misc = safe.misc[:_MAX_RENDER_ITEMS]

    # ── Rule 3: Normalize bullets before render ──
    for exp in safe.experiences:
        exp.bullets = _normalize_bullet_list(exp.bullets)
    for proj in safe.projects:
        proj.bullets = _normalize_bullet_list(proj.bullets)

    # ── Rule 2: Wrap long lines safely ──
    safe.summary = _wrap_long_text(safe.summary)
    for exp in safe.experiences:
        exp.bullets = [_wrap_long_text(b) for b in exp.bullets]
    for proj in safe.projects:
        proj.bullets = [_wrap_long_text(b) for b in proj.bullets]
    safe.misc = [_wrap_long_text(m) for m in safe.misc]

    # ── Rule 6: Ensure canonical section order ──
    if safe.section_titles:
        old = dict(safe.section_titles)
        ordered: dict[str, str] = {}
        for sec in _RENDER_CANONICAL_ORDER:
            field = _RENDER_SECTION_TO_FIELD.get(sec, sec)
            val = getattr(safe, field, None)
            has = bool(val.strip()) if isinstance(val, str) else bool(val)
            if has and sec in old:
                ordered[sec] = old[sec]
        safe.section_titles = ordered

    return safe


def _normalize_bullet_list(bullets: List[str]) -> List[str]:
    """Ensure every bullet is clean, non-empty, with no stray markers."""
    out: List[str] = []
    for b in bullets or []:
        text = str(b or "").strip()
        if not text:
            continue
        # Strip stray bullet markers from the start
        text = _BULLET_MARKER_RE.sub("", text).strip()
        if text:
            out.append(text)
    return out


def _wrap_long_text(text: str, width: int = _MAX_LINE_WIDTH) -> str:
    """Soft-wrap text at word boundaries if it exceeds *width* chars.

    Preserves existing newlines.  Returns the wrapped text as a single
    string with embedded newlines.
    """
    if not text or len(text) <= width:
        return text
    lines = text.split("\n")
    wrapped: List[str] = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.append(textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False))
    return "\n".join(wrapped)
