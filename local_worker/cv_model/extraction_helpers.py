"""Trimmed extraction-helper port of ``services/cv_autofix_service.py``.

The web repo's ``cv_autofix_service.py`` is ~3,900 lines, but only a
fraction of it is actually used by the extraction pipeline
(``extract_agent.py`` / ``normalize_agent.py``): the rest is the CV
"Auto-Fix"/rewrite feature (``auto_fix_cv_text`` and everything it calls —
keyword boosting, action-verb injection, structured-text rendering, export
safety checks, etc.), which this offline tool does not have and does not
need.

This module ports ONLY the functions the extraction chain actually calls,
traced by following the real call graph from ``extract_agent.py``'s lazy
``_get_autofix_helpers()`` import and ``normalize_agent.py`` /
``cv_normalizer.py``'s lazy ``_normalize_language_lines`` import:

    _extract_contact_block, _parse_experience_entries,
    _parse_education_entries, _extract_categorized_skills,
    _parse_project_entries, _normalize_list_section,
    _normalize_skill_lines, _normalize_language_lines,
    guess_name_from_lines, _parse_sections (deterministic fallback parser)

Everything below is copied verbatim from the source functions' bodies
(regex patterns, thresholds, heuristics unchanged) — only the *imports*
were adapted:
  * ``from services.pdf_text_extractor import _normalize_private_use_glyphs``
    (used inside ``_clean_lines``) is NOT imported — that module pulls in
    FastAPI at module level for an unrelated HTTPException helper elsewhere
    in the file. Its ``_normalize_private_use_glyphs`` function itself has
    no FastAPI dependency, so it's copied inline here instead (see below).
  * ``from .language_service import SECTION_ALIASES, clean_lower`` (was
    ``from .language_service import ...`` in the source too — already a
    same-package relative import).
  * ``from .section_classifier import detect_sections as _block_detect_sections``
    (was ``from .section_classifier import detect_sections as
    _block_detect_sections`` in the source too).
"""

from __future__ import annotations

import difflib
import logging
import re

from .language_service import SECTION_ALIASES, clean_lower
from .section_classifier import detect_sections as _block_detect_sections

logger = logging.getLogger("local_worker.cv_model.extraction_helpers")


# ── Alias index (mirrors cv_autofix_service.py module setup) ──────────────
_AUTOFIX_FLAT_ALIASES: dict[str, str] = {}
for _canon, _als in SECTION_ALIASES.items():
    for _a in _als:
        _AUTOFIX_FLAT_ALIASES[_a] = _canon
_AUTOFIX_ALIAS_INDEX: dict[str, list[str]] = {}
for _a in _AUTOFIX_FLAT_ALIASES:
    if _a:
        _AUTOFIX_ALIAS_INDEX.setdefault(_a[0], []).append(_a)

NOISE_SECTION_ALIASES = {
    "references",
    "personal details",
    "marital status",
    "date of birth",
    "birth date",
    "nationality",
    "photo",
}

_SKILL_LANGUAGE_SUBLABEL_RE = re.compile(
    r"^\s*(?:diller|programlama\s+dilleri|languages?|programming\s+languages?)\s*:\s*$",
    re.IGNORECASE,
)


# ── Symbol-font glyph normalization ────────────────────────────────────────
# Copied from services/pdf_text_extractor.py's _normalize_private_use_glyphs
# (and its 3 supporting regexes) rather than imported, because that module
# imports FastAPI at the top level for an unrelated helper. This function
# itself has zero FastAPI/network/DB dependency.
_PRIVATE_USE_RE = re.compile("[-]+")
_CID_GLYPH_RE = re.compile(r"\(cid:\s*\d+\)", re.I)
_CID_BULLET_RE = re.compile(r"\(cid:\s*127\)", re.I)


def _normalize_private_use_glyphs(text: str) -> str:
    """Turn leading symbol-font glyphs into real bullets; drop the rest."""
    if not text or not (_PRIVATE_USE_RE.search(text) or _CID_GLYPH_RE.search(text)):
        return text
    out = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        leading_cid = _CID_GLYPH_RE.match(stripped) if stripped else None
        if stripped and (_PRIVATE_USE_RE.match(stripped) or leading_cid):
            indent = line[: len(line) - len(stripped)]
            stripped = _PRIVATE_USE_RE.sub(" ", stripped)
            stripped = _CID_GLYPH_RE.sub(" ", stripped, count=1).strip()
            line = indent + "• " + stripped
        else:
            line = _PRIVATE_USE_RE.sub(" ", line)
        line = _CID_BULLET_RE.sub("•", line)
        line = _CID_GLYPH_RE.sub(" ", line)
        out.append(line)
    return "\n".join(out)


def _normalize_heading(line: str) -> str:
    normalized = clean_lower(re.sub(r"[^\w\s]|[\d_]", " ", line, flags=re.UNICODE))
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if not heading:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return canonical
    # Fuzzy fallback for typos — e.g. "sumary" -> "summary"
    if len(heading) < 4:
        return None
    candidates = _AUTOFIX_ALIAS_INDEX.get(heading[0], [])
    if not candidates:
        return None
    matches = difflib.get_close_matches(heading, candidates, n=1, cutoff=0.82)
    if matches:
        return _AUTOFIX_FLAT_ALIASES[matches[0]]
    return None


def _noise_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if heading in NOISE_SECTION_ALIASES:
        return heading
    return None


def _clean_lines(text: str) -> list[str]:
    import unicodedata

    text = _normalize_private_use_glyphs(text)
    lines = []
    for line in text.split("\n"):
        clean = unicodedata.normalize("NFC", line)
        clean = re.sub(r"[ \t]+", " ", clean).strip()
        clean = re.sub(r"([A-Z][A-Za-z0-9]+)-\s+([A-Z][A-Za-z0-9]+)", r"\1-\2", clean)
        clean = re.sub(r"([a-z0-9])\-\s+([a-z0-9])", r"\1\2", clean)
        clean = re.sub(r"([A-Za-z])\(", r"\1 (", clean)
        lines.append(clean)
    compact: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                compact.append("")
            previous_blank = True
            continue
        compact.append(line)
        previous_blank = False
    return compact


def _parse_sections(cv_text: str) -> tuple[list[str], dict[str, list[str]], list[str]]:
    header_lines: list[str] = []
    sections: dict[str, list[str]] = {key: [] for key in SECTION_ALIASES}
    dropped_sections: list[str] = []
    current: str | None = None
    dropping = False

    for raw_line in _clean_lines(cv_text):
        if not raw_line:
            if current and not dropping and sections[current] and sections[current][-1] != "":
                sections[current].append("")
            continue

        canonical = _canonical_section(raw_line)
        if canonical == "languages" and current == "skills" and _SKILL_LANGUAGE_SUBLABEL_RE.match(raw_line):
            canonical = None
        if canonical:
            if canonical in {"references", "interests"}:
                dropped_sections.append(canonical)
                current = None
                dropping = True
                continue
            current = canonical
            dropping = False
            continue

        noise = _noise_section(raw_line)
        if noise:
            dropped_sections.append(noise)
            current = None
            dropping = True
            continue

        if dropping:
            continue
        if current is None:
            header_lines.append(raw_line)
        else:
            sections[current].append(raw_line)

    filled_sections = sum(
        1 for key, vals in sections.items() if key != "contact" and any((v or "").strip() for v in vals)
    )
    header_content_lines = [l for l in header_lines if l.strip()]
    if filled_sections < 2 and len(header_content_lines) > 4:
        block_sections, _, _ = _block_detect_sections(cv_text)
        _BLOCK_TO_ALIAS = {
            "summary": "summary",
            "experience": "experience",
            "education": "education",
            "skills": "skills",
            "projects": "projects",
            "certifications": "certifications",
            "languages": "languages",
            "contact": "contact",
        }
        new_header: list[str] = []
        for block_label, block_lines in block_sections.items():
            alias_key = _BLOCK_TO_ALIAS.get(block_label)
            if alias_key and alias_key in sections:
                existing = [v for v in sections[alias_key] if (v or "").strip()]
                if not existing:
                    sections[alias_key] = list(block_lines)
            elif block_label == "header":
                new_header.extend(block_lines)
            elif block_label == "noise":
                dropped_sections.append(block_label)

        if new_header:
            header_lines = new_header

    if len(header_lines) > 6 and not _header_has_contact(header_lines):
        first_section = next(
            (k for k in ("summary", "experience", "education") if any((v or "").strip() for v in sections.get(k, []))),
            None,
        )
        if first_section:
            sections[first_section] = header_lines + sections[first_section]
            header_lines = []

    return header_lines, sections, sorted(set(dropped_sections))


# ── Name detection helper ─────────────────────────────────────────────────

_NAME_DISQUALIFY_RE = re.compile(
    r"@|https?://|linkedin|github|\.com|\.io|\d|[\(\)\[\]{}]|:",
    re.I,
)
_TITLE_HINT_WORDS = {
    "engineer",
    "developer",
    "student",
    "manager",
    "analyst",
    "specialist",
    "consultant",
    "architect",
    "designer",
    "intern",
    "lead",
    "director",
    "officer",
    "professor",
    "scientist",
    "coordinator",
    "researcher",
    "instructor",
    "teacher",
    "programmer",
    "administrator",
    "trainer",
    "senior",
    "junior",
    "associate",
    "assistant",
    "head",
    "chief",
    "freelance",
    "full-stack",
    "frontend",
    "backend",
    "devops",
    "data",
    "software",
    "web",
    "mobile",
    "cloud",
    "cyber",
    "machine learning",
    "ai",
    "qa",
    "quality",
    "university",
    "department",
    "faculty",
    "computer",
    "engineering",
    "science",
    "technology",
    "academy",
    "school",
}
_SECTION_HEADER_WORDS = {
    "profile",
    "summary",
    "objective",
    "about",
    "personal",
    "information",
    "contact",
    "details",
    "experience",
    "education",
    "skills",
    "projects",
    "languages",
    "interests",
    "references",
    "certifications",
    "achievements",
    "publications",
    "activities",
    "hobbies",
    "awards",
    "volunteer",
    "work",
}
_TRAILING_TITLE_RE = re.compile(
    r"\b(?:student|engineer|developer|intern|manager|specialist)\s*$",
    re.I,
)


def _looks_like_person_name(text: str) -> bool:
    """Return True if *text* looks like a person name."""
    text = text.strip()
    if not text:
        return False
    if _NAME_DISQUALIFY_RE.search(text):
        return False
    words = text.split()
    if not (2 <= len(words) <= 4):
        return False
    if not any(w[0].isupper() for w in words if w):
        return False
    lowered = text.lower()
    if any(hint in lowered for hint in _TITLE_HINT_WORDS):
        return False
    if any(w.lower().rstrip(":") in _SECTION_HEADER_WORDS for w in words):
        return False
    if _TRAILING_TITLE_RE.search(text):
        return False
    return True


def guess_name_from_lines(lines: list[str], limit: int = 5) -> str | None:
    """Scan the first *limit* lines for a person name pattern.

    Priority: valid name -> shortest -> closest to top.
    Also rejects lines that look like section headers.
    """
    candidates: list[tuple[int, str]] = []
    for idx, line in enumerate((lines or [])[:limit]):
        candidate = (line or "").strip()
        if not candidate:
            continue
        if _looks_like_person_name(candidate):
            candidates.append((idx, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (len(t[1].split()), t[0]))
    return candidates[0][1]


# ── Header safety: reject header blocks without any contact signal ──
_CONTACT_SIGNAL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"  # email
    r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"  # phone
    r"|linkedin\.com|github\.com"  # profile URLs
    r"|https?://",  # any URL
    re.IGNORECASE,
)


def _header_has_contact(lines: list[str]) -> bool:
    """Return True if at least one line contains an email, phone, or profile URL."""
    return any(_CONTACT_SIGNAL_RE.search(line) for line in lines if line)


def _extract_contact_block(
    header_lines: list[str],
    explicit_lines: list[str],
) -> tuple[str | None, list[str], list[str], list[str]]:
    lines = [line for line in header_lines + explicit_lines if line]
    name = None
    title_lines: list[str] = []
    contacts: list[str] = []
    leftovers: list[str] = []
    title_hint_words = (
        "engineer",
        "developer",
        "student",
        "manager",
        "analyst",
        "specialist",
        "consultant",
        "architect",
        "designer",
        "intern",
        "lead",
        "director",
        "officer",
        "professor",
        "assistant",
        "coordinator",
        "technician",
        "administrator",
        "backend",
        "frontend",
        "fullstack",
        "full-stack",
        "software",
        "data",
        "devops",
        "qa",
        "tester",
        "mühendis",
        "muhendis",
        "geliştirici",
        "gelistirici",
        "uzman",
        "stajyer",
        "analist",
        "tasarımcı",
        "tasarimci",
        "yönetici",
        "yonetici",
        "öğretmen",
        "ogretmen",
        "hemşire",
        "hemsire",
        "satış",
        "satis",
        "danışman",
        "danisman",
        "koordinatör",
        "koordinator",
        "entwickler",
        "ingenieur",
        "leiter",
        "spezialist",
        "berater",
        "architekt",
        "assistent",
        "praktikant",
        "développeur",
        "developpeur",
        "ingénieur",
        "directeur",
        "spécialiste",
        "specialiste",
        "architecte",
        "stagiaire",
        "administrateur",
        "desarrollador",
        "ingeniero",
        "director",
        "especialista",
        "consultor",
        "arquitecto",
        "asistente",
        "becario",
        "administrador",
    )

    _CONTACT_LABEL_RE = re.compile(
        r"^\s*[\w\s\-]{1,30}\s*:\s*",
        re.I | re.UNICODE,
    )
    _ADDRESS_LABEL_RE = re.compile(
        r"^\s*(?:adres|address|location|adress[ei]?|direcci[oó]n|ubicaci[oó]n"
        r"|standort|lieu|indirizzo|morada|lokasyon|konum)"
        r"\s*:\s*",
        re.I | re.UNICODE,
    )

    def _extract_email(line: str) -> str | None:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I)
        return match.group(0) if match else None

    def _extract_phone(line: str) -> str | None:
        match = re.search(r"(?:\(?\+?\d[\d()\-. ]{7,}\d)", line)
        if not match:
            return None
        val = match.group(0).strip()
        if re.fullmatch(r"\d{1,4}[./]\d{1,2}[./]\d{1,4}", val):
            return None
        return val

    def _extract_url(line: str) -> str | None:
        match = re.search(
            r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/\S*)?", line, re.I
        )
        if not match:
            return None
        url = match.group(0).strip().rstrip(",.;")
        if url.lower().startswith(("linkedin.com", "github.com", "www.")):
            url = f"https://{url}"
        return url

    for index, line in enumerate(lines):
        if index <= 2 and name is None and _looks_like_person_name(line):
            if not re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", line, re.I):
                name = line
                continue

        label_match = _CONTACT_LABEL_RE.match(line)
        if label_match:
            value_part = line[label_match.end() :].strip()
            if value_part:
                email = _extract_email(value_part)
                phone = _extract_phone(value_part)
                url = _extract_url(value_part)
                if email:
                    contacts.append(email)
                    continue
                if phone:
                    contacts.append(phone)
                    continue
                if url:
                    contacts.append(url)
                    continue
                if _ADDRESS_LABEL_RE.match(line):
                    leftovers.append(value_part)
                    continue

        tokenized = [part.strip() for part in re.split(r"\s*[|;]\s*", line) if part.strip()]
        if not tokenized:
            tokenized = [line]

        consumed_any = False
        unconsumed_tokens: list[str] = []
        for token in tokenized:
            email = _extract_email(token)
            if email:
                contacts.append(email)
                consumed_any = True
                continue
            phone = _extract_phone(token)
            if phone:
                contacts.append(phone)
                consumed_any = True
                continue
            if any(
                key in token.lower()
                for key in ("linkedin", "github", "portfolio", "http://", "https://", ".com", ".io")
            ):
                url = _extract_url(token)
                contacts.append(url or token)
                consumed_any = True
                continue
            unconsumed_tokens.append(token)

        if consumed_any and unconsumed_tokens:
            leftovers.extend(unconsumed_tokens)

        if not consumed_any:
            lowered_line = line.lower()
            looks_like_title = (
                len(line.split()) <= 10
                and not re.search(r"\d|@", line)
                and any(word in lowered_line for word in title_hint_words)
            )
            if looks_like_title:
                title_lines.append(line)
            else:
                leftovers.append(line)

    deduped_contacts: list[str] = []
    seen = set()
    for value in contacts:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_contacts.append(value.strip())

    deduped_titles: list[str] = []
    title_seen = set()
    for value in title_lines:
        key = value.strip().lower()
        if not key or key in title_seen:
            continue
        title_seen.add(key)
        deduped_titles.append(value.strip())

    if not name:
        name = guess_name_from_lines(header_lines)

    if name and re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", name, re.I):
        contacts.append(name)
        name = guess_name_from_lines(header_lines)
        if name and re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", name, re.I):
            name = None

    if name:
        name_lower = name.strip().lower()
        leftovers = [lo for lo in leftovers if lo.strip().lower() != name_lower]

    leftovers = [lo for lo in leftovers if len(lo.strip()) >= 2]

    return name, deduped_titles, deduped_contacts, leftovers


def _normalize_list_section(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        if not line:
            continue
        parts = re.split(r"\s*[|,/;]\s*", line)
        if len(parts) == 1:
            parts = re.split(r"\s{2,}", line)
        for part in parts:
            cleaned = part.strip(" -*•")
            if cleaned:
                items.append(cleaned)
    deduped: list[str] = []
    seen = set()
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


# ── Sub-skill aware language normalizer ─────────────────────────────────
_LEVELS_PATTERN = (
    r"(A[12]|B[12]|C[12]"
    r"|native|fluent|advanced|intermediate|beginner|proficient|basic|elementary"
    r"|ana\s*dil|ileri|orta|ba[sş]lang[iı][cç]"
    r"|langue\s*maternelle|courant|avanc[eé]|interm[eé]diaire|d[eé]butant"
    r"|muttersprache|flie[ßs]end|verhandlungssicher|fortgeschritten|mittelstufe|grundkenntnisse|anf[aä]nger"
    r"|nativo|fluido|avanzado|intermedio|principiante)"
)

_SUBSKILLS_PATTERN = (
    r"(writing|reading|listening|speaking|oral|written"
    r"|yazma|okuma|dinleme|konu[sş]ma|yaz[iı]l[iı]|s[oö]zl[uü]"
    r"|[eé]crire|lire|[eé]couter|parler|[eé]crit"
    r"|schreiben|lesen|h[oö]ren|sprechen|schriftlich|m[uü]ndlich"
    r"|escritura|lectura|escucha|habla|escrito)"
)

_SUBSKILL_CEFR_RE = re.compile(
    _SUBSKILLS_PATTERN + r"\s*:?\s*" + _LEVELS_PATTERN,
    re.I,
)
_ORPHAN_SUBSKILL_RE = re.compile(
    r"^\s*[()]*\s*" + _SUBSKILLS_PATTERN + r"\s*:?\s*" + _LEVELS_PATTERN + r"\s*[()]*\s*$",
    re.I,
)
_ORPHAN_LEVEL_RE = re.compile(
    r"^\s*\(?\s*" + _LEVELS_PATTERN + r"\s*\)?\s*$",
    re.I,
)

from .section_scorer import KNOWN_LANGUAGES as _KNOWN_LANGS  # noqa: E402


def _normalize_language_lines(lines: list[str]) -> list[str]:
    """Normalize language section lines, preserving CEFR details."""
    items = []
    for line in lines:
        if not line:
            continue
        detailed_match = re.match(
            r"^([A-Za-zÀ-ɏЀ-ӿĞğİıŞşÇçÖöÜü ]{2,24})\s*:\s*(.+)$",
            line,
        )
        if detailed_match:
            language_name = detailed_match.group(1).strip()
            detail = detailed_match.group(2).strip()
            if (
                language_name.lower() in _KNOWN_LANGS
                and re.search(_LEVELS_PATTERN, detail, re.I)
                and re.search(_SUBSKILLS_PATTERN, detail, re.I)
            ):
                items.append(f"{language_name}: {detail}")
                continue
        parts = re.split(r"\s*[|;/]\s*", line)
        if len(parts) == 1:
            parts = re.split(r"\s{2,}", line)

        sub_items = []
        for part in parts:
            for chunk in re.split(r"\s*,\s*", part):
                cleaned = chunk.strip(" -*•:")
                if cleaned:
                    sub_items.append(cleaned)
        items.extend(sub_items)

    merged: list[str] = []
    for item in items:
        if _ORPHAN_SUBSKILL_RE.match(item) or _ORPHAN_LEVEL_RE.match(item):
            if merged:
                merged[-1] = merged[-1] + ", " + item.strip()
        else:
            merged.append(item)

    result: list[str] = []
    _prefix_re = re.compile(r"^(?:foreign\s+languages?|languages?(?:\s+known)?)\s*:\s*", re.I)
    for entry in merged:
        entry = _prefix_re.sub("", entry).strip()
        if not entry:
            continue

        pairs = _SUBSKILL_CEFR_RE.findall(entry)
        if pairs and len(pairs) >= 2:
            first_skill_match = _SUBSKILL_CEFR_RE.search(entry)
            lang_name = entry[: first_skill_match.start()].strip(" :,-–—()")
            if not lang_name:
                for token in entry.split():
                    if token.strip(" :,-()").lower() in _KNOWN_LANGS:
                        lang_name = token.strip(" :,-()")
                        break
            if lang_name:
                parts_str = [
                    f"{skill.capitalize()}: {level.upper() if len(level) <= 2 else level.capitalize()}"
                    for skill, level in pairs
                ]
                result.append(f"{lang_name.capitalize()} ({', '.join(parts_str)})")
                continue

        match = re.search(
            r"^([A-Za-zÀ-ɏЀ-ӿĞğİıŞşÇçÖöÜü\s]+?)\s*[:\-–—,\s]?\s*\(?\s*"
            + _LEVELS_PATTERN
            + r"\s*\)?$",
            entry,
            re.I | re.UNICODE,
        )
        if match:
            lang = match.group(1).strip(" :,-–—()")
            level = match.group(2).strip()
            if lang.lower() in _KNOWN_LANGS or len(lang.split()) <= 2:
                formatted_level = level.upper() if len(level) <= 2 else level.capitalize()
                result.append(f"{lang.capitalize()} ({formatted_level})")
                continue

        result.append(entry)

    seen: set = set()
    deduped: list[str] = []
    for item in result:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item.strip())
    return deduped


def _normalize_skill_lines(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        if not line:
            continue
        major_parts = re.split(r"[|;/]", line)
        for part in major_parts:
            for chunk in part.split(","):
                cleaned = chunk.strip(" -*•")
                if cleaned:
                    items.append(cleaned)

    merged: list[str] = []
    index = 0
    while index < len(items):
        current = items[index]
        if current.lower() == "real" and index + 1 < len(items) and items[index + 1].lower().startswith("time"):
            merged.append(f"Real-Time {items[index + 1][4:].strip()}".strip())
            index += 2
            continue
        merged.append(current)
        index += 1

    deduped: list[str] = []
    seen = set()
    for item in merged:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


# ── Action-verb detection (used by _parse_experience_entries) ─────────────
_BOOST_ACTION_VERBS = [
    "led",
    "managed",
    "developed",
    "implemented",
    "designed",
    "delivered",
    "optimized",
    "created",
    "improved",
    "built",
    "launched",
    "coordinated",
    "established",
    "streamlined",
    "executed",
    "analyzed",
    "achieved",
    "automated",
    "resolved",
    "maintained",
    "collaborated",
    "configured",
    "integrated",
    "deployed",
    "enhanced",
    "reduced",
    "increased",
    "spearheaded",
    "architected",
    "engineered",
]

_ALL_ACTION_VERBS = set(_BOOST_ACTION_VERBS) | {
    "directed",
    "supervised",
    "oversaw",
    "orchestrated",
    "mentored",
    "coached",
    "exceeded",
    "surpassed",
    "earned",
    "won",
    "awarded",
    "founded",
    "initiated",
    "introduced",
    "pioneered",
    "upgraded",
    "refactored",
    "modernized",
    "revamped",
    "transformed",
    "accelerated",
    "assessed",
    "evaluated",
    "researched",
    "investigated",
    "identified",
    "diagnosed",
    "audited",
    "reviewed",
    "benchmarked",
    "shipped",
    "completed",
    "expanded",
    "scaled",
    "grew",
    "generated",
    "boosted",
    "decreased",
    "minimized",
    "eliminated",
    "consolidated",
    "cut",
    "saved",
    "presented",
    "communicated",
    "negotiated",
    "facilitated",
    "documented",
    "reported",
    "trained",
    "taught",
    "educated",
    "programmed",
    "migrated",
    "containerized",
    "provisioned",
    "instrumented",
}


def _starts_with_action_verb(line: str) -> bool:
    """Check if a bullet line already starts with a recognized action verb."""
    cleaned = re.sub(r"^[-•*]\s*", "", line).strip().lower()
    first_word = cleaned.split()[0] if cleaned.split() else ""
    for verb in _ALL_ACTION_VERBS:
        if re.match(r"\b" + re.escape(verb) + r"(?:s|ed|ing|d)?\b", first_word):
            return True
    return False


def _split_concatenated_bullets(lines: list[str]) -> list[str]:
    """Pre-process experience lines: split bullets joined on the same line."""
    result: list[str] = []
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue
        if re.match(r"^\s*[*•‣–—▪■●○◦]", line):
            parts = re.split(r"\s+(?=[*•‣–—▪■●○◦](?:\s|[A-Z]))", line)
            for part in parts:
                part = part.strip()
                if part:
                    result.append(part)
        elif re.match(r"^\s*-\s", line):
            parts = re.split(r"\s+(?=-\s[A-Z])", line)
            for part in parts:
                part = part.strip()
                if part:
                    result.append(part)
        else:
            result.append(line)
    return result


def _parse_experience_entries(lines: list[str]) -> list[dict]:
    lines = _split_concatenated_bullets(lines)
    entries: list[dict] = []
    current: dict | None = None

    _date_token = (
        r"(?:\d{1,2}[/.]\s*)?(?:19|20)\d{2}"
        r"|[A-Za-zÀ-ɏЀ-ӿ]{2,12}\.?\s+(?:19|20)\d{2}"
    )
    _date_sep = (
        r"(?:[-–—~→]"
        r"|\bto\b|\buntil\b|\btill?\b|\bthrough\b"
        r"|\bile\b|\bbis\b|\bau\b|\bà\b|\bhasta\b|\bal?\b)"
    )
    _present_words = (
        r"present|current|ongoing|now|today|to\s+date|till\s+date"
        r"|halen|devam\s+ediyor|günümüz|şu\s+an"
        r"|heute|aktuell|laufend|gegenwärtig"
        r"|aujourd'hui|présent|actuel(?:lement)?|en\s+cours"
        r"|presente|actual(?:idad|mente)?|hasta\s+ahora"
        r"|oggi|attuale|ad\s+oggi|atual(?:mente)?"
        r"|الآن|حاليا|حتى\s+الآن"
    )
    _date_range_anywhere_re = re.compile(
        rf"\(?\s*(?:tarih|date|duration|period)?\s*[:：]?\s*"
        rf"(?P<start>{_date_token})\s*{_date_sep}\s*"
        rf"(?P<end>{_date_token}|{_present_words})\s*\)?",
        re.I | re.UNICODE,
    )
    _date_range_full_re = re.compile(
        rf"^\(?\s*(?P<start>{_date_token})\s*{_date_sep}\s*"
        rf"(?P<end>{_date_token}|{_present_words})\s*\)?$",
        re.I | re.UNICODE,
    )
    _date_range_reversed_re = re.compile(
        rf"^\s*(?P<end>{_date_token})\)?\s*{_date_sep}\s*\(?\s*"
        rf"(?:tarih|date|duration|period)\s*[:：]?\s*(?P<start>{_date_token})\s*$",
        re.I | re.UNICODE,
    )

    def _extract_date_range(value: str) -> tuple[str, str, str]:
        text = (value or "").strip()
        if not text:
            return "", "", ""
        match = _date_range_reversed_re.search(text)
        if not match:
            match = _date_range_anywhere_re.search(text)
        if not match:
            match = _date_range_full_re.search(text)
        if not match:
            return text, "", ""
        start = match.group("start").strip(" ()")
        end = match.group("end").strip(" ()")
        cleaned = (text[: match.start()] + " " + text[match.end() :]).strip(" -–—|()")
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned, start, end

    _ROLE_KEYWORDS = {
        "engineer",
        "developer",
        "manager",
        "analyst",
        "designer",
        "architect",
        "lead",
        "director",
        "consultant",
        "specialist",
        "coordinator",
        "administrator",
        "intern",
        "trainee",
        "associate",
        "senior",
        "junior",
        "principal",
        "staff",
        "head",
        "chief",
        "vp",
        "president",
        "officer",
        "scientist",
        "researcher",
        "technician",
        "programmer",
        "lecturer",
        "professor",
        "assistant",
        "executive",
        "founder",
        "co-founder",
        "cto",
        "ceo",
        "cfo",
        "coo",
        "devops",
        "qa",
        "tester",
    }

    def _looks_like_role(text: str) -> bool:
        words = set(re.split(r"[\s/,.-]+", text.lower()))
        return bool(words & _ROLE_KEYWORDS)

    def _new_entry(title: str) -> dict:
        title, start_date, end_date = _extract_date_range(title)
        entry = {
            "title": title,
            "company": "",
            "location": "",
            "start_date": start_date,
            "end_date": end_date,
            "bullets": [],
        }
        if " - " in title or " – " in title:
            parts = re.split(r"\s+[–-]\s+", title, maxsplit=1)
            if len(parts) == 2:
                a, b = parts[0].strip(), parts[1].strip()
                a_is_role = _looks_like_role(a)
                b_is_role = _looks_like_role(b)
                if a_is_role and not b_is_role:
                    entry["title"] = a
                    entry["company"] = b
                elif b_is_role and not a_is_role:
                    entry["title"] = b
                    entry["company"] = a
                else:
                    entry["title"] = a
                    entry["company"] = b
        return entry

    _month_word = r"[A-Za-zÀ-ɏЀ-ӿ]{2,12}\.?"
    year_pattern = r"(?:19|20)\d{2}"
    _numeric_prefix = r"(?:\d{1,2}[/.]\s*)?"
    _present_kw = r"(?!(?:19|20)\d{2}\b)[A-Za-zÀ-ɏЀ-ӿ]{3,}(?:\s+[A-Za-zÀ-ɏ]{2,})?"
    date_range_pattern = re.compile(
        rf"^(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}"
        rf"\s*(?:[-–—]|to)\s*"
        rf"(?:(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}|{_present_kw})$",
        re.I,
    )
    single_date_pattern = re.compile(
        rf"^(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}$",
        re.I,
    )

    def _is_date_like(value: str) -> bool:
        clean = value.strip()
        if not clean:
            return False
        _, range_start, range_end = _extract_date_range(clean)
        if range_start or range_end:
            return True
        if date_range_pattern.match(clean):
            return True
        if single_date_pattern.match(clean):
            return True
        if re.match(rf"^{year_pattern}\s*[-–—]\s*$", clean):
            return True
        return False

    def _try_split_pipe_header(line: str) -> dict | None:
        if "|" not in line:
            return None
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            return None

        non_date_parts: list[str] = []
        start_date, end_date = "", ""
        for part in parts:
            if _is_date_like(part):
                start_date = part
            elif re.search(r"\b(?:19|20)\d{2}\b\s*(?:[-–]|to)\s*", part, re.I):
                if "–" in part:
                    start_date, end_date = [p.strip() for p in part.split("–", 1)]
                elif " - " in part:
                    start_date, end_date = [p.strip() for p in part.split(" - ", 1)]
                elif re.search(r"\bto\b", part, re.I):
                    start_date, end_date = [p.strip() for p in re.split(r"\bto\b", part, maxsplit=1, flags=re.I)]
                else:
                    start_date = part
            else:
                non_date_parts.append(part)

        title, company, location = "", "", ""
        if len(non_date_parts) >= 2:
            a, b = non_date_parts[0], non_date_parts[1]
            a_is_role = _looks_like_role(a)
            b_is_role = _looks_like_role(b)
            if b_is_role and not a_is_role:
                company, title = a, b
            elif a_is_role and not b_is_role:
                title, company = a, b
            else:
                company, title = a, b
            if len(non_date_parts) >= 3:
                location = non_date_parts[2]
        elif len(non_date_parts) == 1:
            title = non_date_parts[0]

        entry = _new_entry(title)
        entry["company"] = company
        entry["location"] = location
        entry["start_date"] = start_date
        entry["end_date"] = end_date
        return entry

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        _bullet_m = re.match(r"^\s*[-*•–—‣▪■●○◦]\s*", line)
        if _bullet_m and not _is_date_like(line):
            bullet_text = line[_bullet_m.end() :].strip()
            _is_short_role = len(bullet_text.split()) <= 3 and _looks_like_role(bullet_text)
            if bullet_text and not _is_short_role:
                if current is None:
                    current = _new_entry("Experience")
                current["bullets"].append(bullet_text)
                continue

        pipe_entry = _try_split_pipe_header(line)
        if pipe_entry:
            pipe_parts = [p.strip() for p in line.split("|") if p.strip()]
            if current and current.get("title") and not current.get("company") and len(pipe_parts) <= 2:
                current["company"] = pipe_entry.get("title", "")
                current["start_date"] = pipe_entry.get("start_date", "")
                current["end_date"] = pipe_entry.get("end_date", "")
                if pipe_entry.get("company"):
                    current["location"] = pipe_entry["company"]
            else:
                if current:
                    entries.append(current)
                current = pipe_entry
            continue

        if current is None:
            current = _new_entry(line)
            continue

        cleaned_date_line, range_start, range_end = _extract_date_range(line)
        if range_start or range_end:
            residue = cleaned_date_line if cleaned_date_line != line else ""
            residue_words = len(residue.split()) if residue else 0
            residue_is_header = (
                residue
                and 3 <= residue_words <= 12
                and not residue[0].islower()
                and not _starts_with_action_verb(residue)
            )
            established = bool(current.get("bullets") or current.get("start_date") or current.get("end_date"))
            if residue_is_header and established:
                entries.append(current)
                current = _new_entry(line)
                continue
            if not current.get("start_date"):
                current["start_date"] = range_start
            if not current.get("end_date"):
                current["end_date"] = range_end
            if residue:
                if not current.get("company") and _looks_like_role(residue) and residue_words <= 8:
                    current["company"] = residue.strip(" .")
                elif residue_words > 6:
                    current["bullets"].append(line.strip())
                elif not current.get("location"):
                    current["location"] = residue
            continue

        if (not current.get("start_date") and not current.get("end_date")) and _is_date_like(line):
            if "–" in line:
                start, end = [p.strip() for p in line.split("–", 1)]
            elif "-" in line:
                start, end = [p.strip() for p in line.split("-", 1)]
            elif "to" in line.lower():
                start, end = [p.strip() for p in re.split(r"\bto\b", line, maxsplit=1, flags=re.I)]
            else:
                start, end = line.strip(), ""
            current["start_date"] = start
            current["end_date"] = end
            continue

        if not current.get("company") and (" - " in line or " – " in line):
            parts = re.split(r"\s+[–-]\s+", line, maxsplit=1)
            current["company"] = parts[0].strip()
            if len(parts) > 1:
                current["location"] = parts[1].strip()
            continue

        if current.get("bullets"):
            previous_bullet = current["bullets"][-1].rstrip()
            if (
                previous_bullet
                and previous_bullet[-1] not in ".!?:;"
                and not (len(line.split()) <= 8 and _looks_like_role(line))
            ):
                current["bullets"][-1] = f"{previous_bullet} {line}".strip()
                continue

        if (
            line
            and line[0].islower()
            and (
                current.get("bullets")
                or (current.get("title") and (current.get("company") or current.get("start_date")))
            )
        ):
            if current.get("bullets"):
                current["bullets"][-1] = (current["bullets"][-1].rstrip() + " " + line).strip()
            else:
                current["bullets"].append(line)
            continue

        if current.get("company") and current.get("title"):
            if len(line.split()) >= 5 or _starts_with_action_verb(line):
                current["bullets"].append(line)
                continue

        if current.get("bullets") or (current.get("company") and current.get("title")):
            entries.append(current)
            current = _new_entry(line)
            continue

        if not current.get("company"):
            current["company"] = line
        else:
            current["location"] = line

    if current:
        entries.append(current)

    def _merge_wrapped_bullets(bullets: list[str]) -> list[str]:
        merged: list[str] = []
        for bullet in bullets:
            prev = merged[-1] if merged else ""
            if (
                merged
                and bullet
                and bullet[0].islower()
                and prev
                and prev[-1] not in ".!?:;"
                and len(prev) + len(bullet) < 600
            ):
                merged[-1] = f"{prev} {bullet}"
            else:
                merged.append(bullet)
        return merged

    for entry in entries:
        entry["bullets"] = _merge_wrapped_bullets(entry.get("bullets") or [])
        title, company = entry.get("title", ""), entry.get("company", "")
        if title and company and _looks_like_role(company) and not _looks_like_role(title):
            entry["title"], entry["company"] = company, title

    return [entry for entry in entries if entry.get("title") or entry.get("bullets")]


# ── Degree detection for education parsing ──
_DEGREE_RE = re.compile(
    r"^\s*(?:"
    r"B\.?\s*S\.?c?\.?|M\.?\s*S\.?c?\.?|B\.?\s*A\.?|M\.?\s*A\.?|"
    r"B\.?\s*E(?:ng)?\.?|M\.?\s*E(?:ng)?\.?|"
    r"Ph\.?\s*D\.?|M\.?\s*B\.?\s*A\.?|"
    r"Bachelor|Master|Diploma|Associate|Doctor(?:ate)?|Certificate"
    r")(?:\s|[.,'’]|$)",
    re.I,
)
_DEGREE_TITLE_RE = re.compile(
    r"\b(?:"
    r"engineer(?:ing)?|"
    r"medicine|medical\s+doctor|doctor\s+of\s+medicine|"
    r"nurs(?:e|ing)|pharmacy|dentistry|physiotherapy|"
    r"law|lawyer|attorney|juris(?:prudence)?|"
    r"architect(?:ure)?|interior\s+design|industrial\s+design|"
    r"physicist?|chemist(?:ry)?|biolog(?:y|ist)|mathemati(?:cs|cian)|statistic(?:s|ian)|"
    r"psycholog(?:y|ist)|sociolog(?:y|ist)|economist?|economics|"
    r"political\s+science|international\s+relations|"
    r"philosoph(?:y|er)|histor(?:y|ian)|linguist(?:ics)?|"
    r"business\s+administration|management|accounting|finance|marketing|"
    r"teaching|pedagog(?:y|ue)|education|"
    r"journalism|communication|public\s+relations|"
    r"graphic\s+design|fine\s+arts|"
    r"computer\s+science|information\s+(?:technology|systems)|data\s+science|"
    r"cyber\s*security|artificial\s+intelligence"
    r")\s*$",
    re.I,
)
_DEGREE_TR_RE = re.compile(
    r"\b(?:lisans|y[uü]ksek\s*lisans|doktora|[oö]n\s*lisans"
    r"|m[uü]hendisli[gkğ]\w*|b[oö]l[uü]m\w*)\b",
    re.I,
)
_PAREN_DATE_RE = re.compile(
    r"\((\d{4})\s*[-–—]\s*(\d{4}|[A-Za-zÀ-ɏЀ-ӿ]{3,}(?:\s+[A-Za-zÀ-ɏ]{2,})?)\)\s*$",
    re.I,
)


def _looks_like_degree(line: str) -> bool:
    """Return True if the line looks like the start of a new education entry."""
    return bool(_DEGREE_RE.search(line)) or bool(_DEGREE_TR_RE.search(line)) or bool(_DEGREE_TITLE_RE.search(line))


def _extract_paren_dates(text: str) -> tuple:
    """Extract parenthetical dates from end of line, return (clean, start, end)."""
    m = _PAREN_DATE_RE.search(text)
    if m:
        return text[: m.start()].strip(), m.group(1), m.group(2)
    return text, "", ""


def _new_edu_entry() -> dict:
    return {
        "degree": "",
        "school": "",
        "location": "",
        "start_date": "",
        "end_date": "",
        "gpa": "",
        "field": "",
    }


def _parse_date_range(line: str) -> tuple:
    """Parse a date range from a line, return (start, end)."""
    compact_match = re.match(
        r"^\s*((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|present|current)\s*$",
        line,
        re.I,
    )
    if compact_match:
        return compact_match.group(1), compact_match.group(2)
    if "–" in line:
        s, e = [p.strip() for p in line.split("–", 1)]
    elif " - " in line:
        s, e = [p.strip() for p in line.split(" - ", 1)]
    elif re.search(r"\bto\b", line, re.I):
        s, e = [p.strip() for p in re.split(r"\bto\b", line, maxsplit=1, flags=re.I)]
    else:
        s, e = line.strip(), ""
    return s, e


def _parse_education_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    university_keywords = (
        "university",
        "universit",
        "institute",
        "enstit",
        "college",
        "school",
        "faculty",
        "fakülte",
        "fakulte",
        "academy",
        "akademi",
        "üniversite",
        "universitesi",
    )

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        lowered = line.lower()

        if (
            current
            and current.get("degree")
            and current.get("school")
            and (current.get("start_date") or current.get("end_date"))
        ):
            school_low = current["school"].lower()
            if any(kw in lowered for kw in university_keywords) and not any(
                kw in school_low for kw in university_keywords
            ):
                pass
            else:
                entries.append(current)
                current = None

        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                if current and current.get("school") and not current.get("degree"):
                    pass
                else:
                    if current:
                        entries.append(current)
                    current = _new_edu_entry()
                for part in parts:
                    lp = part.lower()
                    part_gpa = re.search(r"\b\d(?:\.\d{1,2})?\s*/\s*(?:4(?:\.0+)?|5(?:\.0+)?)\b", part)
                    if "gpa" in lp or "cgpa" in lp or part_gpa:
                        current["gpa"] = re.sub(r"^\s*(?:c?gpa)\s*:\s*", "", part, flags=re.I).strip()
                    elif any(kw in lp for kw in university_keywords):
                        current["school"] = part
                    elif re.search(r"(?:19|20)\d{2}\s*(?:[-–]|to)\s*", part, re.I):
                        current["start_date"], current["end_date"] = _parse_date_range(part)
                    elif re.match(r"^(?:19|20)\d{2}$", part.strip()):
                        if not current["start_date"]:
                            current["start_date"] = part.strip()
                        else:
                            current["end_date"] = part.strip()
                    elif not current["degree"]:
                        current["degree"] = part
                    elif not current["school"]:
                        current["school"] = part
                    else:
                        current["location"] = part
                continue

        gpa_like = re.search(r"\b\d(?:\.\d{1,2})?\s*/\s*(?:4(?:\.0+)?|5(?:\.0+)?)\b", line)
        if "gpa" in lowered or "cgpa" in lowered or "not:" in lowered or gpa_like:
            if current:
                current["gpa"] = line
            elif entries:
                entries[-1]["gpa"] = line
            continue

        if _looks_like_degree(line):
            deg_clean, sd, ed = _extract_paren_dates(line)
            if (
                current
                and not current.get("degree")
                and (current.get("school") or current.get("start_date") or current.get("end_date"))
            ):
                current["degree"] = deg_clean
                if sd:
                    current["start_date"] = sd
                if ed:
                    current["end_date"] = ed
            else:
                if current:
                    entries.append(current)
                current = _new_edu_entry()
                current["degree"] = deg_clean
                current["start_date"] = sd
                current["end_date"] = ed
            continue

        if any(kw in lowered for kw in university_keywords):
            if current is None:
                current = _new_edu_entry()
            if current.get("school"):
                existing_low = current["school"].lower()
                if any(kw in existing_low for kw in university_keywords):
                    entries.append(current)
                    current = _new_edu_entry()
                else:
                    current["school"] = current["school"] + " " + line
                    continue
            current["school"] = line
            continue

        if re.search(r"(?:19|20)\d{2}", line):
            if current is None:
                current = _new_edu_entry()
            current["start_date"], current["end_date"] = _parse_date_range(line)
            continue

        if current is None:
            current = _new_edu_entry()
            current["school"] = line
            continue

        if not current.get("school"):
            current["school"] = line
        else:
            current["location"] = line

    if current:
        entries.append(current)

    expanded: list[dict] = []
    for entry in entries:
        degree = (entry.get("degree") or "").strip()
        transfer_match = re.match(
            r"^(.+?)\s*\(Transferred\)\s*\((.+?)\s*\((\d{4})\s*[-–]\s*(Present|\d{4})\)\)$",
            degree,
            re.I,
        )
        if transfer_match:
            old_entry = dict(entry)
            old_entry["degree"] = transfer_match.group(1).strip() + " (Transferred)"
            old_entry["start_date"] = ""
            old_entry["end_date"] = ""
            expanded.append(old_entry)
            new_entry = dict(entry)
            new_entry["degree"] = transfer_match.group(2).strip()
            new_entry["start_date"] = transfer_match.group(3).strip()
            new_entry["end_date"] = transfer_match.group(4).strip()
            expanded.append(new_entry)
        else:
            expanded.append(entry)

    normalized_entries: list[dict] = []
    pending_school: dict | None = None
    school_context: dict[str, str] = {}
    for entry in expanded:
        if entry.get("school") and not entry.get("degree") and not entry.get("gpa"):
            if pending_school is not None:
                normalized_entries.append(pending_school)
            pending_school = entry
            school_context = {key: entry.get(key, "") for key in ("school", "start_date", "end_date", "location")}
            continue

        if entry.get("degree") and not entry.get("school") and school_context:
            for key, value in school_context.items():
                if value and not entry.get(key):
                    entry[key] = value
            pending_school = None
        elif pending_school is not None:
            normalized_entries.append(pending_school)
            pending_school = None

        if entry.get("school"):
            school_context = {key: entry.get(key, "") for key in ("school", "start_date", "end_date", "location")}
        normalized_entries.append(entry)

    if pending_school is not None:
        normalized_entries.append(pending_school)

    for entry in normalized_entries:
        for key in ("degree", "school", "start_date", "end_date", "gpa", "field", "location"):
            entry.setdefault(key, "")

    return normalized_entries


def _extract_categorized_skills(lines: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    categories: dict[str, list[str]] = {}
    uncategorized: list[str] = []
    last_category = ""

    def _add_to_category(name: str, items: list[str]) -> None:
        bucket = categories.setdefault(name, [])
        for item in items:
            if item not in bucket:
                bucket.append(item)

    pending_category = ""

    for raw in lines or []:
        line = str(raw or "").strip()
        if not line:
            continue
        if ":" in line:
            category, values = line.split(":", 1)
            category_clean = category.strip()
            values = values.lstrip(" |")
            items = [item.strip(" -*•") for item in re.split(r"\s*[,;/|]\s*", values) if item.strip(" -*•")]
            if category_clean and items:
                _add_to_category(category_clean, items)
                last_category = category_clean
                pending_category = ""
                continue
            if category_clean and not items and len(category_clean.split()) <= 4:
                pending_category = category_clean
                continue
        if (
            last_category
            and not pending_category
            and len(line.split()) <= 3
            and categories.get(last_category)
            and not re.match(r"^\s*[-*•]\s+", line)
        ):
            categories[last_category][-1] = f"{categories[last_category][-1]} {line}".strip()
            continue

        stripped = re.sub(r"^\s*[-*•]\s*", "", line).strip()
        items = [item.strip(" -*•") for item in re.split(r"\s*[,;/|]\s*", stripped) if item.strip(" -*•")]
        if pending_category and items:
            _add_to_category(pending_category, items)
            last_category = pending_category
            pending_category = ""
            continue
        if re.match(r"^\s*[-*•]\s+", line):
            uncategorized.append(stripped)
        else:
            uncategorized.extend(items)

    if uncategorized:
        dedup_uncat: list[str] = []
        seen = set()
        for item in uncategorized:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            dedup_uncat.append(item)
        if not categories:
            categories.setdefault("Technical Skills", dedup_uncat)

    flattened: list[str] = []
    seen_flat = set()
    for values in categories.values():
        for value in values:
            key = value.lower()
            if key in seen_flat:
                continue
            seen_flat.add(key)
            flattened.append(value)
    return categories, flattened


def _looks_like_description(line: str) -> bool:
    """Return True if *line* reads like a project description rather than a title."""
    if len(line) > 80:
        return True
    stripped = line.rstrip()
    if stripped.endswith((".", "!")):
        return True
    words = line.split()
    if len(words) >= 5:
        lc = sum(1 for w in words if w[:1].islower())
        if lc / len(words) > 0.5:
            return True
    return False


_KNOWN_TECHS = {
    "python",
    "javascript",
    "java",
    "c++",
    "c#",
    "ruby",
    "php",
    "go",
    "rust",
    "react",
    "angular",
    "vue",
    "django",
    "flask",
    "spring",
    "node",
    "nodejs",
    "nextjs",
    "reactjs",
    "vuejs",
    "aspnet",
    "express",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "redis",
    "elasticsearch",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "jenkins",
    "git",
    "html",
    "css",
    "sass",
    "less",
    "bootstrap",
    "tailwind",
    "typescript",
    "jquery",
    "redux",
    "graphql",
    "rest",
    "api",
    "apis",
    "fastapi",
    "pytorch",
    "tensorflow",
    "keras",
    "opencv",
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "matlab",
    "r",
    "swift",
    "kotlin",
    "android",
    "ios",
    "flutter",
    "dart",
    "scala",
    "haskell",
    "perl",
    "bash",
    "shell",
    "powershell",
    "linux",
    "unix",
    "windows",
    "macos",
    "ansible",
    "terraform",
    "vagrant",
    "firebase",
    "sqlite",
    "oracle",
    "mssql",
    "cassandra",
    "mariadb",
    "dynamodb",
    "neo4j",
    "kafka",
    "rabbitmq",
    "celery",
    "webpack",
    "babel",
    "vite",
    "npm",
    "yarn",
    "pnpm",
    "c",
    "assembly",
    "lisp",
    "prolog",
    "clojure",
    "elixir",
    "erlang",
    "lua",
    "oop",
    "restful",
    "ci",
    "cd",
    "agile",
    "scrum",
    "kanban",
    "github",
    "gitlab",
    "nginx",
    "apache",
    "iis",
    "tomcat",
    "springboot",
    "hibernate",
    "jpa",
    "jdbc",
    "unity",
    "unreal",
    "godot",
    "blender",
    "photoshop",
    "figma",
    "sketch",
    "tcp",
    "udp",
    "ip",
    "dns",
    "http",
    "https",
    "ssh",
    "ssl",
    "tls",
}


def _looks_like_tech_list(line: str) -> bool:
    """Return True if *line* is a comma/pipe-separated list of short tokens."""
    stripped = line.strip()
    if not re.search(r"[,|/]", stripped):
        return False
    tokens = re.split(r"\s*[,|/]\s*", stripped)
    tokens = [t.strip() for t in tokens if t.strip()]
    if len(tokens) < 3:
        return False

    first_token = tokens[0]
    first_word = first_token.split()[0].lower() if first_token.split() else ""
    first_word = re.sub(r"[^\w+##\-#]", "", first_word)
    if first_token and first_token[0].isupper() and first_word not in _KNOWN_TECHS:
        return False

    return all(len(t.split()) <= 4 for t in tokens)


_MAX_PROJECT_ENTRIES = 200  # max project entries from parser loop


def _parse_project_entries(lines: list[str]) -> list[dict]:
    _TECH_HDR = re.compile(
        r"^\s*(?:used\s+technologies|tech(?:nology|nologies)?\s*(?:stack|used)?"
        r"|tools(?:\s+(?:used|&|and)\s+\w+)?"
        r"|stack|kullan[ıi]lan\s+teknolojiler"
        r"|technologies\s+used)\s*[:：\-]\s*",
        re.I,
    )
    _LINK_HDR = re.compile(
        r"^\s*(?:link|website|web\s*site|github|demo|url|live|repo|repository"
        r"|kaynak|site)\s*[:：]\s*",
        re.I,
    )
    _URL_LINE = re.compile(r"^\s*(?:https?://\S+|www\.\S+)\s*$", re.I)
    _BULLET_RE_PROJ = re.compile(r"^\s*[-*•–—‣▪■●○◦►]\s+")

    _PROJECT_CONTINUATION_RE = re.compile(
        r"^(?:and|or|with|to|for|in|on|of|by|as|using|between|while|through|that|which|ve|ile|i[cç]in|olarak)\b",
        re.I,
    )

    def _looks_like_project_continuation(value: str, current_entry: dict | None = None) -> bool:
        text = (value or "").strip()
        if not text or _BULLET_RE_PROJ.match(text):
            return False

        is_continuation_word = bool(_PROJECT_CONTINUATION_RE.match(text))

        if current_entry and current_entry.get("bullets"):
            previous_bullet = current_entry["bullets"][-1].rstrip()
            if previous_bullet and previous_bullet[-1] not in ".!?:;":
                return True

        first_char = text[0] if text else ""
        if first_char.islower() or is_continuation_word:
            return True

        if current_entry and current_entry.get("bullets"):
            prev_bullet = current_entry["bullets"][-1].strip()
            if prev_bullet.endswith((".", "!", "?")):
                return False

        if len(text.split()) >= 6 and not text.isupper():
            words = text.split()
            cap_words = sum(1 for w in words if w and w[0].isupper())
            if cap_words >= len(words) // 2:
                return False
            return True

        return False

    entries: list[dict] = []
    current: dict | None = None

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        _title_tech_m = re.match(
            r"^(.+?)\s*[–—|–—-]\s+(.+)$",
            line,
        )
        if _title_tech_m and _looks_like_tech_list(_title_tech_m.group(2)):
            if current is not None:
                entries.append(current)
            current = {
                "name": _title_tech_m.group(1).strip(),
                "description": _title_tech_m.group(2).strip(),
                "bullets": [],
            }
            continue

        m_bullet = _BULLET_RE_PROJ.match(line)
        if m_bullet:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            current.setdefault("bullets", []).append(line[m_bullet.end() :].strip())
            continue

        m = _TECH_HDR.match(line)
        if m:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            after = line[m.end() :].strip()
            if after:
                desc = current.get("description", "")
                current["description"] = (desc + " | " + after) if desc else after
            continue

        m_link = _LINK_HDR.match(line)
        if m_link:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            after = line[m_link.end() :].strip() or line.strip()
            current.setdefault("bullets", []).append(after)
            continue

        if _URL_LINE.match(line) and current is not None:
            current.setdefault("bullets", []).append(line.strip())
            continue

        if current is not None and _looks_like_tech_list(line):
            desc = current.get("description", "")
            current["description"] = (desc + " | " + line).strip(" |") if desc else line
            continue

        if (
            current is not None
            and not current.get("bullets")
            and len(line.split()) == 1
            and not _BULLET_RE_PROJ.match(line)
            and not re.search(r"\d{4}|https?://|@", line)
        ):
            desc = current.get("description", "")
            if desc and re.search(r",", desc):
                current["description"] = desc + ", " + line
                continue

        if (
            current is not None
            and current.get("description", "").rstrip().endswith(",")
            and len(line.split()) <= 3
            and not _BULLET_RE_PROJ.match(line)
        ):
            desc = current["description"]
            current["description"] = (desc + " " + line).rstrip(",").strip()
            continue

        if current is not None and current.get("bullets") and _looks_like_project_continuation(line, current):
            current["bullets"][-1] = (current["bullets"][-1].rstrip() + " " + line).strip()
            continue

        if current is not None and not current.get("bullets") and _looks_like_description(line):
            desc = current.get("description", "")
            current["description"] = (desc + " " + line).strip() if desc else line
            continue

        if current is not None:
            entries.append(current)
        current = {"name": line, "description": "", "bullets": []}

    if current is not None:
        entries.append(current)

    if len(entries) > _MAX_PROJECT_ENTRIES:
        logger.warning("parse_projects: entries capped %d -> %d", len(entries), _MAX_PROJECT_ENTRIES)
        entries = entries[:_MAX_PROJECT_ENTRIES]

    return entries
