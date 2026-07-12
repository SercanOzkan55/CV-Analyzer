"""Extract Agent — converts raw CV text into structured JSON.

Pipeline:
  raw text → layout_analyzer → section_classifier → section_scorer
  → section_resolver → cv_normalizer → schema_builder
  → ats_compliance_check → freeze → render

The agent extracts data fields without formatting or optimizing.
It handles multi-column layouts, broken lines, and non-standard
CV formats by focusing purely on data extraction.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Dict, List

from services.layout_analyzer import analyze_layout
from services.section_classifier import detect_sections, canonicalize_section_key, get_parser
from services.section_resolver import resolve_raw_sections
from services.language_service import detect_language

logger = logging.getLogger("app.extract_agent")

# ── Security limits ────────────────────────────────────────────────────────
_SAFE_MODE = os.getenv("SAFE_MODE", "").lower() in ("1", "true", "yes")
_MAX_TEXT_LEN = 50_000 if _SAFE_MODE else 100_000
_MAX_LINES = 1_000 if _SAFE_MODE else 2_000
_MAX_TOTAL_WORDS = 25_000 if _SAFE_MODE else 50_000


def _get_autofix_helpers():
    """Lazy import to avoid circular dependency with cv_autofix_service."""
    from services.cv_autofix_service import (
        _extract_contact_block,
        _parse_experience_entries,
        _parse_education_entries,
        _extract_categorized_skills,
        _parse_project_entries,
        _normalize_list_section,
        _normalize_skill_lines,
        _normalize_language_lines,
    )

    return (
        _extract_contact_block,
        _parse_experience_entries,
        _parse_education_entries,
        _extract_categorized_skills,
        _parse_project_entries,
        _normalize_list_section,
        _normalize_skill_lines,
        _normalize_language_lines,
    )


def _sections_from_classifier(
    text: str,
) -> tuple[List[str], Dict[str, List[str]], List[str], Dict[str, str], Dict[str, str]]:
    """Build section buckets using the new pipeline:

    layout_analyzer → section_classifier → section_resolver

    Returns (header_lines, sections, dropped_sections, section_titles, section_sources).
    compatible with downstream extract helpers.
    """
    # ── Step 1: Layout analysis (multi-column detection + structural metadata) ──
    layout_info = analyze_layout(text)
    text = layout_info.linearized_text  # guaranteed single-column
    logger.debug(
        "layout_type=%s  lines=%d  header_style=%s",
        layout_info.layout_type,
        layout_info.line_count,
        layout_info.header_style,
    )

    # ── Step 2: Section classification (receives layout_type) ──
    detected, section_titles, section_sources = get_parser()(text, layout_type=layout_info.layout_type)

    # Remap any non-canonical keys from classifier into known buckets
    _KNOWN = {
        "summary",
        "experience",
        "education",
        "skills",
        "projects",
        "certifications",
        "languages",
        "interests",
        "contact",
        "header",
        "noise",
        "misc",
    }
    remapped: Dict[str, List[str]] = {}
    for k, v in detected.items():
        canonical = canonicalize_section_key(k)
        if canonical not in _KNOWN:
            canonical = "misc"
        remapped.setdefault(canonical, [])
        remapped[canonical].extend(v)
    detected = remapped

    # The classifier puts name/title/contact info under "contact" key.
    # We use those as header_lines so _extract_contact_block can parse
    # name, title, email, phone, etc.
    contact_lines = list(detected.get("contact", []) or [])
    header_from_classifier = list(detected.get("header", []) or [])

    sections: Dict[str, List[str]] = {
        "summary": list(detected.get("summary", []) or []),
        "experience": list(detected.get("experience", []) or []),
        "education": list(detected.get("education", []) or []),
        "skills": list(detected.get("skills", []) or []),
        "projects": list(detected.get("projects", []) or []),
        "certifications": list(detected.get("certifications", []) or []),
        "languages": list(detected.get("languages", []) or []),
        "interests": list(detected.get("interests", []) or []),
        "misc": list(detected.get("misc", []) or []),
        "contact": contact_lines,
    }

    # Prefer explicit header bucket; fall back to contact lines (common case)
    header_lines = header_from_classifier if header_from_classifier else contact_lines
    # When contact lines are used as header, clear the contact section to avoid
    # _extract_contact_block processing the same lines twice.
    if not header_from_classifier and contact_lines:
        sections["contact"] = []

    # Some visual CVs start with name/title lines and no contact block.  If the
    # classifier scores those short leading lines as interests/misc, rescue them
    # into the header so name parsing can still see them.
    if not header_lines:
        known_headers = {str(v).strip() for v in (section_titles or {}).values() if str(v).strip()}
        leading_header: list[str] = []
        for raw_line in text.split("\n"):
            stripped = (raw_line or "").strip()
            if not stripped or stripped == "multi_col_fixed":
                continue
            if stripped in known_headers:
                break
            if len(stripped.split()) <= 6:
                leading_header.append(stripped)
            if len(leading_header) >= 4:
                break
        if leading_header:
            header_lines.extend(leading_header)
            leading_set = {line.lower() for line in leading_header}
            for key in list(sections.keys()):
                if key == "contact":
                    continue
                sections[key] = [line for line in sections.get(key, []) if line.strip().lower() not in leading_set]

    # Enforce canonical section order regardless of PDF layout
    _SECTION_ORDER = [
        "summary",
        "experience",
        "education",
        "projects",
        "skills",
        "certifications",
        "languages",
        "interests",
        "misc",
        "contact",
    ]
    ordered: Dict[str, List[str]] = {}
    for key in _SECTION_ORDER:
        if sections.get(key):
            ordered[key] = sections[key]
    sections = ordered

    dropped_sections: List[str] = []
    if detected.get("noise"):
        dropped_sections.append("noise")

    # Preserve old contract: expose concrete dropped section names when present.
    noise_aliases = {
        "references",
        "personal details",
        "marital status",
        "date of birth",
        "birth date",
        "nationality",
        "photo",
    }
    for raw_line in text.split("\n"):
        line = re.sub(r"[^a-zA-Z ]+", " ", (raw_line or "")).lower().strip()
        line = re.sub(r"\s+", " ", line)
        if line in noise_aliases and line not in dropped_sections:
            dropped_sections.append(line)

    # ── Clean noise tokens from every section ──
    _NOISE_CHARS = set(" \t|–—-:,;/*\\•*\"'`")
    for _sec_key in list(sections.keys()):
        _sec_lines = sections.get(_sec_key, [])
        if _sec_lines:
            sections[_sec_key] = [
                l
                for l in _sec_lines
                if l.strip() and l.strip() not in _NOISE_TOKENS and not all(ch in _NOISE_CHARS for ch in l.strip())
            ]

    # ── Step 3: Section resolution (fix cross-section misclassifications) ──
    sections_before = {k: len(v) for k, v in sections.items()}
    logger.debug("sections_before_resolver=%s", sections_before)

    sections = resolve_raw_sections(sections, header_lines, section_titles)

    sections_after = {k: len(v) for k, v in sections.items()}
    logger.debug("sections_after_resolver=%s", sections_after)

    return header_lines, sections, dropped_sections, section_titles, section_sources


EXTRACT_PROMPT = """
Extract CV data.

Return JSON.

Fields:

profile
education[]
experience[]
projects[]
skills[]
languages[]

Do not format.
Do not optimize.
Only extract.
"""


def _clean_text(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# Multi-column detection/reconstruction is now handled upstream by
# Multi-column detection/reconstruction is handled by layout_analyzer.py.
# The text arriving here is already linearised single-column.


# ── Merge guard patterns ──────────────────────────────────────────────────
# Lines matching these patterns must never merge with neighbours.
_MERGE_CONTACT_LABEL_RE = re.compile(
    r"^\s*(?:e-?\s*posta|e-?\s*mail|telefon|phone|tel|mobile|fax"
    r"|adres|address|do\u011fum|birth|dob|date\s+of\s+birth"
    r"|web(?:site)?|linkedin|github|portfolio)\s*[:\uff1a]",
    re.I,
)
_MERGE_CONTACT_SIGNAL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"
    r"|https?://"
    r"|linkedin\.com|github\.com",
    re.I,
)
_MERGE_BIRTH_RE = re.compile(
    r"\b(?:birth|do\u011fum|dob|geboren|date\s+of\s+birth|geburtsdatum|geburtstag|nacid[oa]|fecha\s+de\s+nacimiento|n\u00e9e?|date\s+de\s+naissance)\b",
    re.I,
)
_MERGE_EDUCATION_START_RE = re.compile(
    r"\b(?:universit(?:y|e\w*|ad\w*|ä\w*)|[u\u00fc]niversite\w*|institute?\w*|enstit[u\u00fc]\w*|instituto\w*"
    r"|college|school|schule\w*|\u00e9cole\w*|escuela\w*|facult(?:y|e\w*|ad\w*)|fak[u\u00fc]lte\w*"
    r"|academy|akademi\w*|academia\w*|polytechnic"
    r"|m[u\u00fc]hendisli[gk\u011f]\w*|engineering|ing\u00e9nierie\w*|ingenier\u00eda\w*"
    r"|bachelor|master|maestr\u00eda\w*|ma\u00eetrise\w*|licence\w*|licenciatura\w*"
    r"|diploma\w*|dipl\u00f4me\w*|diplom\w*|degree|ph\.?d|m\.?b\.?a"
    r"|lisans|y[u\u00fc]ksek\s*lisans|doktora|[o\u00f6]n\s*lisans|doctorat\w*|doctorado\w*"
    r"|studium|studiengang|hochschule\w*|bachillerato\w*)\b",
    re.I,
)


def _is_fullname(line: str) -> bool:
    words = line.strip().split()
    if not (2 <= len(words) <= 4):
        return False
    if not all(w.isalpha() for w in words):
        return False
    # Case 1: All uppercase
    if all(len(w) >= 2 and w.isupper() for w in words):
        return True
    # Case 2: Title Case
    if all(len(w) >= 2 and w[0].isupper() and w[1:].islower() for w in words):
        return True
    return False


def _is_colon_label(line: str) -> bool:
    if ":" not in line:
        return False
    parts = line.split(":", 1)
    left, right = parts[0], parts[1]
    left_stripped = left.strip()
    if not (2 <= len(left_stripped) <= 20):
        return False
    if not all(c.isalpha() or c.isspace() for c in left_stripped):
        return False
    if not right.strip():
        return False
    return True


def _merge_wrapped_lines(text: str) -> str:
    """Merge broken/wrapped lines back into complete sentences.

    PDF extraction often splits sentences across multiple lines.
    This merges them unless the line is a bullet, header, or follows
    a sentence-ending punctuation.

    Blank lines are preserved so that downstream `split_blocks` can
    properly separate sections.
    """
    lines = text.split("\n")
    merged: List[str] = []
    buffer = ""
    last_was_header = False

    # Bullet markers including en-dash and triangular bullet
    _BULLET_RE = re.compile(r"^\s*[-\u2022\u2023\u2013\u2014\u25aa\u25a0*]\s")

    for line in lines:
        line = line.strip()

        if not line:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append("")  # ← preserve blank line as section separator
            last_was_header = False
            continue

        # Bullet lines are never merged
        if _BULLET_RE.match(line) or line.startswith(
            ("-", "\u2022", "*", "\u2023", "\u2013 ", "\u2014 ", "\u25aa", "\u25a0")
        ):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        # Section headers (all caps, short, no email/url/digits) are never merged
        if line.isupper() and len(line.split()) <= 5 and not re.search(r"@|https?://|\.\.com|\.io|\d{3,}", line, re.I):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            last_was_header = True
            continue

        # Title Case section headers (1-2 words, capitalized, in header hints)
        if len(line.split()) <= 3 and line[0].isupper():
            from services.section_classifier import _sniff_header

            if _sniff_header(line):
                if buffer:
                    merged.append(buffer)
                    buffer = ""
                merged.append(line)
                last_was_header = True
                continue

        # ── Contact / birth / education lines must stay separate ──
        # Rejoin words split by a discretionary PDF line-end hyphen before
        # structural keyword guards inspect the continuation line.
        if buffer.endswith("-") and line[:1].islower():
            buffer = buffer[:-1] + line
            continue

        if _MERGE_CONTACT_LABEL_RE.match(line) or _MERGE_CONTACT_SIGNAL_RE.search(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        if _MERGE_BIRTH_RE.search(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        if _MERGE_EDUCATION_START_RE.search(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        # Capitalized full name (2-4 words) — never merge
        if _is_fullname(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        # Colon-prefixed label lines are standalone
        if _is_colon_label(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        # First content line after a header always starts a fresh buffer
        if last_was_header:
            last_was_header = False
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines containing years / dates are standalone
        if re.search(r"\b(19|20)\d{2}\b", line):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines ending with colon are standalone (sub-headers)
        if line.endswith(":"):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Pipe-delimited lines (contact, skills) are standalone
        if "|" in line:
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines that look like GPA are standalone
        if re.search(r"\b(?:GPA|CGPA)\b", line, re.I):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines that look like university/school names are standalone
        if re.search(r"\b(?:university|college|institute|faculty|academy|school)\b", line, re.I):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Structural: capitalized multi-word line with a year → standalone
        # (catches institution/company names in any language)
        if re.search(r"\b(?:19|20)\d{2}\b", line) and line[0].isupper() and len(line.split()) >= 2:
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines that look like degree names are standalone
        if re.search(
            r"^\s*(?:B\.?S\.?c?|M\.?S\.?c?|B\.?A|M\.?A|Ph\.?D|M\.?B\.?A|Bachelor|Master|Diploma|Associate|Degree)\b",
            line,
            re.I,
        ):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Lines that look like company/role headers are standalone
        if re.search(r"\b(?:Inc|Ltd|LLC|GmbH|A\.Ş|Corp|S\.A|S\.L|SARL|SAS|S\.R\.L|A\.G)\b", line):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        # Merge into buffer only if this line is a continuation
        if buffer:
            first_char = line[0] if line else ""
            continuation_words = ("and", "with", "of", "to", "for", "in", "the", "a", "an", "or", "at", "by", "as")
            is_continuation = first_char.islower() or line.split()[0].lower() in continuation_words
            if is_continuation and not buffer.endswith((".", ":", ";")):
                buffer += " " + line
            else:
                merged.append(buffer)
                buffer = line
        else:
            buffer = line

    if buffer:
        merged.append(buffer)

    return "\n".join(merged)


# ── Noise tokens that carry no semantic value ─────────────────────────────
_NOISE_TOKENS = frozenset({'""', "|", "||", ":", ",", "-", "–", "—", "•", "*", "/", "\\"})


_NOISE_CHARS = set(" \t|–—-:,;/*\\•*\"'`")


_BULLET_PREFIX_RE = re.compile(r"^\s*[-*•\u2013\u2014\u2023\u25aa\u25a0►]\s+\S")


def _clean_noise_lines(text: str) -> str:
    """Remove lines that consist solely of noise tokens, separators, or empty
    quotes.  Also strip stray leading/trailing separators from lines,
    but preserve bullet-prefixed lines (e.g. ``- Developed REST APIs``).
    """
    cleaned: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Drop lines that are nothing but noise tokens / whitespace
        if stripped in _NOISE_TOKENS or (stripped and all(ch in _NOISE_CHARS for ch in stripped)):
            continue
        # Preserve bullet markers – only strip leading noise on non-bullet lines
        if not _BULLET_PREFIX_RE.match(stripped):
            stripped = re.sub(r"^[\s|–—\-:,;]+", "", stripped)
        stripped = re.sub(r"[\s|–—\-:,;]+$", "", stripped)
        cleaned.append(stripped)
    return "\n".join(cleaned)


def extract_structured(cv_text: str) -> Dict:
    """Extract structured data from raw CV text.

    Returns a dict with canonical CV fields - no formatting applied,
    no optimization, pure extraction.
    """
    # Normalize line endings
    raw = unicodedata.normalize("NFC", str(cv_text or ""))
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return _empty_structure()

    # ── Security: truncate oversized input ──
    if len(raw) > _MAX_TEXT_LEN:
        logger.warning("extract: input truncated %d → %d chars", len(raw), _MAX_TEXT_LEN)
        raw = raw[:_MAX_TEXT_LEN]
    _lines = raw.split("\n")
    if len(_lines) > _MAX_LINES:
        logger.warning("extract: lines truncated %d → %d", len(_lines), _MAX_LINES)
        raw = "\n".join(_lines[:_MAX_LINES])

    # Strip upstream multi-column marker if present
    if raw.startswith("multi_col_fixed"):
        raw = raw[len("multi_col_fixed") :].lstrip("\n")

    # Security: cap total word count
    _words = raw.split()
    if len(_words) > _MAX_TOTAL_WORDS:
        logger.warning("extract: words truncated %d → %d", len(_words), _MAX_TOTAL_WORDS)
        raw = " ".join(_words[:_MAX_TOTAL_WORDS])

    # Always merge wrapped/broken lines (PDF extraction splits sentences)
    raw = _merge_wrapped_lines(raw)

    # Clean noise tokens (empty quotes, stray pipes/separators)
    raw = _clean_noise_lines(raw)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", raw).strip()
    if not text:
        return _empty_structure()

    # Lazy import to avoid circular dependency
    (
        _extract_contact_block,
        _parse_experience_entries,
        _parse_education_entries,
        _extract_categorized_skills,
        _parse_project_entries,
        _normalize_list_section,
        _normalize_skill_lines,
        _normalize_language_lines,
    ) = _get_autofix_helpers()

    # Section classifier runs AFTER flatten so it sees single-column text
    header_lines, sections, dropped, section_titles, section_sources = _sections_from_classifier(text)

    # FIX 5: If classifier found <2 non-empty sections, re-run classifier
    filled = sum(1 for v in sections.values() if v)
    if filled < 2:
        # Re-merge and retry (text may just need line-merge cleanup)
        text = _merge_wrapped_lines(text)
        text = re.sub(r"[ \t]+", " ", text).strip()
        header_lines, sections, dropped, section_titles, section_sources = _sections_from_classifier(text)

    name, title_lines, contacts, leftover = _extract_contact_block(header_lines, sections.get("contact", []))

    # ── Name rescue: if name still missing, scan raw first lines ──
    if not name:
        from services.cv_autofix_service import guess_name_from_lines

        first_raw = [l.strip() for l in raw.split("\n")[:8] if l.strip()]
        name = guess_name_from_lines(first_raw, limit=8)

    def _bad_name_candidate(value: str) -> bool:
        low = (value or "").lower().strip()
        if not low:
            return True
        if any(ch.isdigit() for ch in low) or any(tok in low for tok in ("@", "http", "www.", "/", "|")):
            return True
        if re.search(r"\bfrom\b", low):
            return True
        if low in {"skills", "communication", "languages", "education", "projects", "sql", "java"}:
            return True
        return False

    def _looks_like_person_name(value: str) -> bool:
        text_value = (value or "").strip()
        words = text_value.split()
        if not (2 <= len(words) <= 4):
            return False
        if any(ch.isdigit() for ch in text_value) or any(ch in text_value for ch in "@/|:"):
            return False
        return any(ch.islower() for ch in text_value) or text_value.isupper()

    _job_title_re = re.compile(
        r"\b(?:engineer(?:ing)?|developer|analyst|designer|architect|manager|researcher"
        r"|intern|consultant|specialist|student|officer|assistant)\b",
        re.I,
    )
    if _bad_name_candidate(name):
        raw_lines = [l.strip() for l in raw.split("\n") if l.strip()]
        known_headers = {str(v).strip().lower() for v in (section_titles or {}).values()}
        skip_headers = known_headers | {
            "multi_col_fixed",
            "communication",
            "skills",
            "languages",
            "education",
            "projects",
            "personal information",
            "personal profile",
            "summary",
            "experience",
            "work background",
            "career timeline",
        }
        for idx, candidate in enumerate(raw_lines[:60]):
            if candidate.lower() in skip_headers:
                continue
            if not _looks_like_person_name(candidate):
                continue
            next_line = raw_lines[idx + 1] if idx + 1 < len(raw_lines) else ""
            if next_line and _job_title_re.search(next_line):
                name = candidate
                if not title_lines:
                    title_lines = [next_line]
                for sec_key in ("interests", "misc", "education", "skills"):
                    sections[sec_key] = [
                        line
                        for line in sections.get(sec_key, [])
                        if line.strip().lower() not in {candidate.lower(), next_line.lower()}
                    ]
                break

    # Extract email, phone, location, linkedin from contacts
    # GUARD: only extract fields that are still empty
    email, phone, location, linkedin = "", "", "", ""
    for token in contacts:
        lowered = (token or "").lower()
        if not email and re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", token, re.I):
            match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", token, re.I)
            email = match.group(0) if match else ""
        elif not phone and re.search(r"(?:\(?\+?\d[\d()\-. ]{7,}\d)", token):
            match = re.search(r"(?:\(?\+?\d[\d()\-. ]{7,}\d)", token)
            phone = match.group(0).strip() if match else ""
        elif not linkedin and any(k in lowered for k in ("linkedin", "github", "http")):
            linkedin = token.strip()

    if not location and leftover:
        _addr_label_re = re.compile(
            r"^\s*(?:adres|address|location|adress[ei]?|direcci[oó]n|ubicaci[oó]n"
            r"|standort|lieu|indirizzo|morada|lokasyon|konum)\s*:\s*",
            re.I,
        )
        # First pass: prefer "City, Country" pattern (e.g. "Istanbul, Turkey")
        _city_country_re = re.compile(
            r"^[A-Za-z\u00C0-\u024F\u0400-\u04FF\s\-]+,\s*[A-Za-z\u00C0-\u024F\u0400-\u04FF\s\-]+$"
        )
        for raw in leftover:
            candidate = str(raw or "").strip()
            if len(candidate) < 2:
                continue
            if re.search(r"@|https?://|linkedin|github|\d{5,}", candidate, re.I):
                continue
            candidate = _addr_label_re.sub("", candidate).strip()
            if candidate and _city_country_re.match(candidate):
                location = candidate
                break

        # Second pass: take first reasonable leftover if no city/country match
        if not location:
            for raw in leftover:
                candidate = str(raw or "").strip()
                if len(candidate) < 2:
                    continue
                if re.search(r"@|https?://|linkedin|github|\d{5,}", candidate, re.I):
                    continue
                candidate = _addr_label_re.sub("", candidate).strip()
                if candidate:
                    location = candidate
                    break

    # ── Contact-field rescue: scan remaining sections for stray email/phone ──
    if not email or not phone:
        for _sec_key in ("experience", "education", "misc", "summary"):
            for _line in sections.get(_sec_key, []):
                if not email:
                    _m = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", _line or "", re.I)
                    if _m:
                        email = _m.group(0)
                if not phone:
                    _m = re.search(r"(?:\(?\+?\d[\d()\-. ]{7,}\d)", _line or "")
                    if _m:
                        phone = _m.group(0).strip()

    # Parse sub-structures
    experience_lines = [l for l in sections.get("experience", []) if l]
    education_lines = [l for l in sections.get("education", []) if l]
    skill_lines = [l for l in sections.get("skills", []) if l]
    project_lines = [l for l in sections.get("projects", []) if l]
    language_lines = sections.get("languages", [])
    cert_lines = [l for l in sections.get("certifications", []) if l]
    summary_lines = [l for l in sections.get("summary", []) if l]
    interest_lines = [l for l in sections.get("interests", []) if l]
    misc_lines = [l for l in sections.get("misc", []) if l]

    experiences = _parse_experience_entries(experience_lines)
    education = _parse_education_entries(education_lines)
    skills_cat, skills_flat = _extract_categorized_skills(skill_lines)
    if not skills_flat:
        skills_flat = _normalize_skill_lines(skill_lines)
    projects = _parse_project_entries(project_lines)
    languages = _normalize_language_lines(language_lines)
    certifications = [{"name": l, "issuer": "", "date": ""} for l in cert_lines]
    interests = _normalize_list_section(interest_lines)
    misc = [l.strip() for l in misc_lines if l.strip()]

    summary = " ".join(l for l in summary_lines if l).strip()

    # ── Summary position check ──────────────────────────────────────
    # Only accept summary from early sections.  If it appeared AFTER
    # experience or skills in the original document, demote it to misc.
    _LATE_SECTIONS = {"experience", "skills"}
    _summary_is_late = False
    if summary and section_titles:
        title_keys = list(section_titles.keys())
        if "summary" in title_keys:
            summary_idx = title_keys.index("summary")
            for late_key in _LATE_SECTIONS:
                if late_key in title_keys and title_keys.index(late_key) < summary_idx:
                    _summary_is_late = True
                    break

    if _summary_is_late:
        summary_title = (section_titles.get("summary") or "").strip().lower()
        summary_text = summary.strip()
        profile_title = re.search(
            r"\b(?:personal\s+information|professional\s+summary|summary|profile|about|objective|kişisel\s+bilgi|profil|özet)\b",
            summary_title,
            re.I,
        )
        profile_content = (
            len(summary_text.split()) >= 8
            and re.search(
                r"\b(?:student|engineer|developer|focused|experienced|passionate|skilled|"
                r"öğrenci|mühendis|geliştirici|odaklı|deneyimli|yetkin)\b",
                summary_text,
                re.I,
            )
            and not re.search(
                r"\b(?:father|mother|date\s+of\s+birth|birth\s+date|marital|sex|gender|nationality|"
                r"baba|anne|doğum|medeni|cinsiyet|uyruk)\b",
                summary_text,
                re.I,
            )
        )
        if profile_title and profile_content:
            _summary_is_late = False

    if _summary_is_late:
        # Demote late summary to misc; don't use as primary summary
        misc_lines = [l for l in sections.get("misc", []) if l]
        misc_lines.extend(summary_lines)
        summary = ""
        summary_lines = []
        misc = [l.strip() for l in misc_lines if l.strip()]

    # Tag summary origin so downstream stages can enforce priority.
    # "top" = extracted from a dedicated summary/profile/objective section
    # that appeared before experience/skills AND has ≥5 words.
    _summary_source = ""
    if summary and len(summary.split()) >= 5 and not _summary_is_late:
        _summary_source = "top"

    # Detect CV language
    lang = detect_language(text)

    return {
        "full_name": name or "",
        "title": " | ".join(title_lines) if title_lines else "",
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "summary": summary,
        "_summary_source": _summary_source,
        "experiences": experiences,
        "education": education,
        "skills_categorized": skills_cat,
        "skills": skills_flat,
        "projects": projects,
        "certifications": certifications,
        "languages": languages,
        "interests": interests,
        "misc": misc,
        "language": lang,
        "section_titles": section_titles,
        "_section_sources": section_sources,
        "_multi_column_detected": False,
        "_dropped_sections": dropped,
    }


def _empty_structure() -> Dict:
    return {
        "full_name": "",
        "title": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "summary": "",
        "experiences": [],
        "education": [],
        "skills_categorized": {},
        "skills": [],
        "projects": [],
        "certifications": [],
        "languages": [],
        "interests": [],
        "misc": [],
        "language": "en",
        "section_titles": {},
        "_multi_column_detected": False,
        "_dropped_sections": [],
    }
