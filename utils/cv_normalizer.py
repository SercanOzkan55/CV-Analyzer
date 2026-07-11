"""Generic CV normalization rules.

These rules apply to ALL CVs — they enforce structural correctness,
clean misplaced data, and normalize fields without CV-specific logic.

Usage:
    Called from ``agents.normalize_agent.normalize()`` (raw dicts) and
    ``services.schema_builder`` (typed schema).  Entry points:

    * ``apply_normalization_rules()``   — main orchestrator
    * ``sanitize_experience_entries()`` — raw dict level
    * ``create_education_from_text()``  — detect degree/school/year
    * ``guess_name()``                  — person-name heuristic
    * ``filter_language_codes()``       — reject ISO codes + tech names
    * ``redistribute_misc()``           — score-based misc redistribution
    * ``normalize_urls()``              — fix malformed URLs
    * ``ensure_summary()``              — summary rescue from misc/exp
    * ``strip_contact_from_section()``  — contact stripper (education)
    * ``strip_contact_from_all_sections()`` — contact stripper (all other sections)
    * ``validate_section_placement()``  — score-based section validation
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.cv_normalizer")

# ═══════════════════════════════════════════════════════════════════════════
# SHARED PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\(?\+?\d[\d()\-\s.]{7,}\d)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)

_MAX_URL_LEN = 500  # max characters in any single URL

_ADDRESS_RE = re.compile(
    r"\b(?:street|avenue|boulevard|road|drive|lane|apt\.?|suite"
    r"|floor|building|bldg|city|state|zip|postal|country"
    r"|mahalle|sokak|cadde|mah\.|cad\.|sk\.|no\s*:\s*\d"
    r"|P\.?O\.?\s*Box)\b",
    re.I,
)

_BIRTH_DATE_RE = re.compile(
    r"\b(?:birth\s*(?:date|day)?|date\s+of\s+birth|dob|doğum\s*(?:tarihi)?|geboren)"
    r"\s*:?\s*\d",
    re.I,
)
_BIRTH_LINE_RE = re.compile(
    r"^\s*(?:birth\s*(?:date|day)?|date\s+of\s+birth|dob|doğum\s*(?:tarihi)?|geboren)"
    r"\s*:?\s*",
    re.I,
)

_DEGREE_RE = re.compile(
    # "associate" alone is NOT a degree signal — it is one of the most common
    # job-title words (Sales Associate, Application Development Associate).
    # Only degree-context forms count: "Associate degree" / "Associate of Arts"
    # / "Associate from <institution>" (lookahead keeps the match at "Associate").
    r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
    r"|bachelor|master|diploma|associate(?:'s)?\s+(?:degree|of)|associate(?:'s)?(?=\s+from\b)|degree"
    r"|lisans|y[uü]ksek\s*lisans|doktora|[oö]n\s*lisans"
    r"|m[u\u00fc]hendisli[gk\u011f]\w*|engineering)\b",
    re.I,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:universit(?:y|e\w*)|[uü]niversite\w*|institute?\w*|enstit[uü]\w*"
    r"|college|school|facult(?:y|e\w*)|fak[uü]lte\w*"
    r"|academy|akademi\w*|polytechnic"
    r"|meslek\s*y[uü]ksek\s*okulu)\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# ISO 639-1 codes that must NOT appear as spoken-language entries
_ISO_LANG_CODES = {
    "en",
    "tr",
    "de",
    "fr",
    "es",
    "ru",
    "ar",
    "zh",
    "ja",
    "ko",
    "nl",
    "sv",
    "no",
    "da",
    "fi",
    "pl",
    "cs",
    "hu",
    "el",
    "ro",
    "bg",
    "hr",
    "sr",
    "uk",
    "he",
    "hi",
    "fa",
    "th",
    "vi",
    "id",
    "ms",
    "pt",
    "it",
    "ca",
    "sk",
    "sl",
    "lt",
    "lv",
    "et",
}

_MALFORMED_URL_RE = re.compile(
    r"\b(https?)\s*:\s+(\S+)",  # "https: example.com"
    re.I,
)

# Experience-entry contact patterns — things that MUST NOT be in exp bullets/fields
_CONTACT_BULLET_RE = re.compile(
    r"^(?:\s*(?:email|e-mail|phone|tel|telefon|address|adres|linkedin|website|web)\s*:\s*\S)",
    re.I,
)

# Tech names that must not appear in language lists
_TECH_NAME_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|docker"
    r"|kubernetes|aws|azure|gcp|sql|mongodb|redis|node\.?js"
    r"|django|flask|fastapi|spring|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|tensorflow|pytorch|scikit|pandas|excel"
    r"|linux|git|ruby|rails|php|laravel|swift|kotlin|flutter"
    r"|figma|photoshop|jira|confluence|docker|matlab|r\b)\b",
    re.I,
)

# Keywords for misc → education
_CERT_RE = re.compile(
    r"\b(?:certificate|certification|certified|sertifika|belge)\b",
    re.I,
)
_PROJECT_RE = re.compile(
    r"\b(?:project|proje|github\.com|gitlab\.com|bitbucket)\b",
    re.I,
)
_SKILL_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|docker"
    r"|kubernetes|aws|azure|gcp|sql|mongodb|redis|node\.?js"
    r"|django|flask|fastapi|spring|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|tensorflow|pytorch|scikit|pandas|excel)\b",
    re.I,
)
_INTEREST_RE = re.compile(
    r"\b(?:hobby|hobbies|interest|volunteer|swimming|reading|traveling"
    r"|gaming|photography|cooking|music|sport|yoga|chess|hiking"
    r"|writing|drawing|painting|gardening|cycling|running)\b",
    re.I,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. EXPERIENCE SECTION SANITIZER  (raw dict level)
# ═══════════════════════════════════════════════════════════════════════════

# Allowed keys on an experience dict.  Anything else is dropped.
_EXP_ALLOWED_KEYS = {"title", "company", "location", "start_date", "end_date", "bullets"}


def sanitize_experience_entries(
    experiences: List[Dict],
    data: Dict,
) -> List[Dict]:
    """Strict validation for experience entries.

    Allowed fields: title, company, (location, start_date, end_date,) bullets.
    Any other key is dropped.  Lines containing email, phone, address,
    birth date, university, or degree are removed or moved to the proper
    section in *data* (mutated in place).

    Returns the cleaned experience list.
    """
    from utils.section_scorer import is_contact_data

    cleaned_exps: List[Dict] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            cleaned_exps.append(exp)
            continue

        # ── Drop unknown keys ──
        for key in list(exp.keys()):
            if key not in _EXP_ALLOWED_KEYS:
                del exp[key]

        # ── Clean title / company fields ──
        for field_name in ("title", "company"):
            val = str(exp.get(field_name, ""))
            if not val:
                continue
            # Strip embedded email / phone — route to top-level
            email_m = _EMAIL_RE.search(val)
            if email_m:
                if not data.get("email"):
                    data["email"] = email_m.group(0)
                val = _EMAIL_RE.sub("", val).strip()
            phone_m = _PHONE_RE.search(val)
            if phone_m:
                if not data.get("phone"):
                    data["phone"] = phone_m.group(0).strip()
                val = _PHONE_RE.sub("", val).strip()
            # Strip address fragments
            if _ADDRESS_RE.search(val) and len(val.split()) <= 8:
                _maybe_set_location(val, data)
                val = ""
            # Strip birth date fragments
            if _BIRTH_DATE_RE.search(val):
                val = _BIRTH_DATE_RE.sub("", val).strip()
            exp[field_name] = val

        # ── Clean bullets ──
        raw_bullets = exp.get("bullets") or []
        kept_bullets: List[str] = []
        edu_bullets: List[str] = []
        for bullet in raw_bullets:
            b = str(bullet).strip()
            if not b:
                continue
            # Skip pure contact lines
            if _CONTACT_BULLET_RE.match(b):
                _route_contact_line(b, data)
                continue
            # Skip birth date lines
            if _BIRTH_LINE_RE.match(b):
                continue
            # Skip address lines (entire line is address)
            if _ADDRESS_RE.search(b) and len(b.split()) <= 8:
                _maybe_set_location(b, data)
                continue
            # Move education-like bullets (degree + university) to education
            if (_DEGREE_RE.search(b) or _INSTITUTION_RE.search(b)) and _YEAR_RE.search(b):
                edu_bullets.append(b)
                continue
            # Score-based contact check — catch edge cases the regex misses
            if is_contact_data(b):
                _route_contact_line(b, data)
                continue
            # Remove embedded email/phone but keep rest of bullet
            b = _EMAIL_RE.sub("", b).strip()
            b = _PHONE_RE.sub("", b).strip()
            if b and len(b) > 2:
                kept_bullets.append(b)
        exp["bullets"] = kept_bullets

        # Route education-like bullets that were extracted
        if edu_bullets:
            _create_edu_from_bullets(edu_bullets, data)

        # ── Check title/company for degree/university contamination ──
        title = str(exp.get("title", ""))
        company = str(exp.get("company", ""))
        combined = f"{title} {company}"
        has_degree = bool(_DEGREE_RE.search(combined))
        has_inst = bool(_INSTITUTION_RE.search(combined))
        has_year = bool(_YEAR_RE.search(f"{combined} {exp.get('start_date', '')} {exp.get('end_date', '')}"))

        if (has_degree or has_inst) and has_year and not kept_bullets:
            # This is an education entry masquerading as experience
            _move_exp_to_education(exp, data)
            continue  # Don't add to cleaned_exps

        # If title/company is *entirely* degree/university with no real
        # job content, clear it but keep the entry if it has bullets.
        if has_degree or has_inst:
            if _DEGREE_RE.search(title) and not _has_job_signal(title):
                exp["title"] = ""
            if _INSTITUTION_RE.search(company) and not _has_job_signal(company):
                exp["company"] = ""

        # Drop entries with no substance left
        if not exp.get("title") and not exp.get("company") and not kept_bullets:
            continue

        cleaned_exps.append(exp)

    return cleaned_exps


def _has_job_signal(text: str) -> bool:
    """Return True if *text* contains signals that look like a real job."""
    _JOB_RE = re.compile(
        r"\b(?:engineer|developer|manager|analyst|consultant|director"
        r"|lead|senior|junior|intern|coordinator|specialist|designer"
        r"|architect|administrator|officer|assistant|head\s+of"
        r"|associate|executive|scientist|technician|trainee|representative"
        r"|mühendis|geliştirici|müdür|uzman|stajyer)\b",
        re.I,
    )
    return bool(_JOB_RE.search(text))


def _move_exp_to_education(exp: Dict, data: Dict) -> None:
    """Move a whole experience entry to the education section."""
    edu_list = data.get("education")
    if not isinstance(edu_list, list):
        edu_list = []
        data["education"] = edu_list
    edu_list.append(
        {
            "degree": exp.get("title", ""),
            "school": exp.get("company", ""),
            "location": exp.get("location", ""),
            "start_date": exp.get("start_date", ""),
            "end_date": exp.get("end_date", ""),
            "gpa": "",
            "field": "",
        }
    )


def _create_edu_from_bullets(bullets: List[str], data: Dict) -> None:
    """Create education entries from bullets containing degree/university."""
    edu_list = data.get("education")
    if not isinstance(edu_list, list):
        edu_list = []
        data["education"] = edu_list
    for b in bullets:
        degree_m = _DEGREE_RE.search(b)
        inst_name = _extract_institution_name(b)
        years = _YEAR_RE.findall(b)
        edu_list.append(
            {
                "degree": degree_m.group(0) if degree_m else "",
                "school": inst_name,
                "start_date": years[0] if years else "",
                "end_date": years[1] if len(years) > 1 else "",
                "gpa": "",
                "field": "",
                "location": "",
            }
        )


def _route_contact_line(line: str, data: Dict) -> None:
    """Route a detected contact line (email/phone) to proper top-level fields."""
    email = _EMAIL_RE.search(line)
    if email and not data.get("email"):
        data["email"] = email.group(0)
        return
    phone = _PHONE_RE.search(line)
    if phone and not data.get("phone"):
        data["phone"] = phone.group(0).strip()


def _maybe_set_location(line: str, data: Dict) -> None:
    """Set location from an address-like line if location is empty."""
    if not data.get("location"):
        clean = re.sub(r"\b(?:address|adres)\s*:\s*", "", line, flags=re.I).strip()
        if clean:
            data["location"] = clean


# ═══════════════════════════════════════════════════════════════════════════
# 2. AUTO-CREATE EDUCATION FROM DETECTED TEXT
# ═══════════════════════════════════════════════════════════════════════════


def create_education_from_text(data: Dict) -> None:
    """Ensure education entries exist when degree + institution/year signals
    are found anywhere in the CV.

    Scans summary, misc, experience (title, company, bullets), skills,
    certifications, and interests.  All detected education entries are
    deduplicated against existing ones before appending.

    Mutates *data* in place.
    """
    # Collect all candidate text from every section
    sources: List[str] = []
    summary = data.get("summary", "")
    if isinstance(summary, str) and summary.strip():
        sources.append(summary)
    for item in data.get("misc") or []:
        if isinstance(item, str):
            sources.append(item)
    for exp in data.get("experiences") or []:
        if isinstance(exp, dict):
            # title + company may contain degree/institution
            title = exp.get("title", "")
            company = exp.get("company", "")
            dates = f"{exp.get('start_date', '')} {exp.get('end_date', '')}"
            if title or company:
                sources.append(f"{title} {company} {dates}")
            for b in exp.get("bullets") or []:
                sources.append(str(b))
    for item in data.get("skills") or []:
        if isinstance(item, str):
            sources.append(item)
    for cert in data.get("certifications") or []:
        if isinstance(cert, dict):
            sources.append(str(cert.get("name", "")))
        elif isinstance(cert, str):
            sources.append(cert)
    for item in data.get("interests") or []:
        if isinstance(item, str):
            sources.append(item)

    found_edu = _extract_education_from_lines(sources)
    if not found_edu:
        return

    # Deduplicate against existing education entries
    existing = data.get("education")
    if not isinstance(existing, list):
        existing = []
        data["education"] = existing

    existing_keys: set = set()
    for edu in existing:
        if isinstance(edu, dict):
            d = (edu.get("degree", "") or "").lower().strip()
            s = (edu.get("school", "") or "").lower().strip()
            existing_keys.add(f"{d}|{s}")

    for edu in found_edu:
        d = (edu.get("degree", "") or "").lower().strip()
        s = (edu.get("school", "") or "").lower().strip()
        key = f"{d}|{s}"
        if key not in existing_keys:
            existing.append(edu)
            existing_keys.add(key)


def _extract_education_from_lines(lines: List[str]) -> List[Dict]:
    """Scan lines for degree + institution + year combinations."""
    results: List[Dict] = []
    seen: set = set()
    for line in lines:
        if not line:
            continue
        has_degree = _DEGREE_RE.search(line)
        has_inst = _INSTITUTION_RE.search(line)
        has_year = _YEAR_RE.search(line)
        if has_degree and (has_inst or has_year):
            # Extract year
            years = _YEAR_RE.findall(line)
            start = years[0] if years else ""
            end = years[1] if len(years) > 1 else ""
            degree_match = has_degree.group(0)
            inst_match = has_inst.group(0) if has_inst else ""
            key = f"{degree_match.lower()}|{inst_match.lower()}"
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "degree": degree_match,
                    "school": _extract_institution_name(line),
                    "start_date": start,
                    "end_date": end,
                    "gpa": "",
                    "field": "",
                    "location": "",
                }
            )
    return results


def _extract_institution_name(line: str) -> str:
    """Extract the institution name from a line containing a university keyword."""
    match = re.search(
        r"(?:[\w\s]+(?:university|üniversite|institute|enstitü|college|school"
        r"|faculty|fakülte|academy|akademi)[\w\s]*)",
        line,
        re.I,
    )
    if match:
        return match.group(0).strip()
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# 3. NAME EXTRACTION HEURISTIC
# ═══════════════════════════════════════════════════════════════════════════

_NAME_DISQUALIFY = re.compile(
    r"@|https?://|linkedin|github|\.com|\.io|\d|[()[\]{}]",
    re.I,
)
_TITLE_HINTS = {
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
    "machine learning",
    # institutional
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
_SECTION_HEADERS = {
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


def _looks_like_name(text: str) -> bool:
    """Return True if *text* looks like a person name."""
    text = text.strip()
    if not text or _NAME_DISQUALIFY.search(text):
        return False
    words = text.split()
    if not (2 <= len(words) <= 4):
        return False
    if text == text.upper():
        return False
    if not any(w[0].isupper() for w in words if w):
        return False
    lowered = text.lower()
    if any(hint in lowered for hint in _TITLE_HINTS):
        return False
    if any(w.lower().rstrip(":") in _SECTION_HEADERS for w in words):
        return False
    return True


def guess_name(lines: List[str], limit: int = 5) -> Optional[str]:
    """Scan the first *limit* lines for a person name pattern.

    Returns the best candidate or None.
    """
    candidates: List[tuple[int, str]] = []
    for idx, line in enumerate((lines or [])[:limit]):
        c = (line or "").strip()
        if not c:
            continue
        if _looks_like_name(c):
            candidates.append((idx, c))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (len(t[1].split()), t[0]))
    return candidates[0][1]


def ensure_name(data: Dict) -> None:
    """If ``full_name`` is missing, attempt extraction from first lines.

    Mutates *data* in place.
    """
    if data.get("full_name"):
        return

    # Build candidate lines from known sources
    lines: List[str] = []
    # Raw header lines (from extract agent)
    header = data.get("header_lines") or data.get("header") or []
    if isinstance(header, list):
        lines.extend(str(l) for l in header[:5])
    # Fallback: summary first line, then misc
    summary = data.get("summary", "")
    if isinstance(summary, str) and summary:
        first_line = summary.split("\n")[0].strip()
        if first_line:
            lines.append(first_line)
    for item in (data.get("misc") or [])[:3]:
        lines.append(str(item))

    name = guess_name(lines)
    if name:
        data["full_name"] = name


# ═══════════════════════════════════════════════════════════════════════════
# 4. LANGUAGE CODE FILTER
# ═══════════════════════════════════════════════════════════════════════════


def filter_language_codes(languages: List[str]) -> List[str]:
    """Structural filter for language entries.

    Accepts entries that pass structural detection:
    * CEFR / JLPT proficiency level present, OR
    * level words (native, fluent, …), OR
    * sub-skill labels (writing, reading, …) with CEFR, OR
    * short items with no tech / date / URL signals.

    No language-name dictionary is consulted.
    """
    from utils.section_scorer import is_language_entry

    cleaned: List[str] = []
    for lang in languages:
        stripped = lang.strip()
        if not stripped or len(stripped) <= 1:
            continue
        # Reject URLs and emails early
        if _EMAIL_RE.search(stripped) or _URL_RE.search(stripped):
            continue
        # Reject pure numbers / punctuation
        if re.match(r"^[\d\W]+$", stripped):
            continue
        # Reject bare ISO codes (en, tr, de, …)
        if stripped.lower() in _ISO_LANG_CODES and len(stripped.split()) == 1:
            continue
        # Structural detection — permissive mode for items already in
        # the languages section
        if not is_language_entry(stripped, strict=False):
            continue
        cleaned.append(stripped)
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# 5. MISC SECTION RE-EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════


def redistribute_misc(data: Dict) -> None:
    """Move misc items into proper sections using multi-signal scoring.

    Each item is scored against all candidate sections.  The highest-scoring
    section wins; if no section scores above threshold → stays in misc.

    If *misc* had an explicit header in the original CV, require very-high
    confidence before moving any item out (section lock).

    Mutates *data* in place.
    """
    from utils.section_scorer import (
        score_text,
        locked_sections,
        LOCKED_MIN_SCORE,
        LOCKED_MIN_MARGIN,
    )

    misc = data.get("misc")
    if not isinstance(misc, list) or not misc:
        return

    locked = locked_sections(data.get("section_titles"))
    misc_locked = "misc" in locked

    _MIN_SCORE = LOCKED_MIN_SCORE if misc_locked else 0.35
    _MARGIN = LOCKED_MIN_MARGIN if misc_locked else 0.10

    # Sections we confidently redistribute to from misc.
    # "summary" is excluded — schema_builder handles misc→summary promotion.
    # "experience" is excluded — prose without structure shouldn't become exp.
    _ALLOWED_TARGETS = {
        "education",
        "certifications",
        "projects",
        "interests",
        "skills",
        "languages",
        "contact",
    }

    kept_misc: List[str] = []
    for item in misc:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()

        scores = score_text(text)
        best = scores.best()
        best_val = scores.best_score()

        # Keep in misc if score too low or target not allowed
        if best_val < _MIN_SCORE or best not in _ALLOWED_TARGETS:
            kept_misc.append(text)
            continue

        # Require a margin over runner-up to avoid ambiguous moves
        all_scores = sorted(scores.as_dict().values(), reverse=True)
        runner_up = all_scores[1] if len(all_scores) > 1 else 0.0
        if best_val - runner_up < _MARGIN:
            kept_misc.append(text)
            continue

        # Guard: don't move long prose to "skills" — that's likely experience
        if best == "skills" and len(text.split()) > 8:
            kept_misc.append(text)
            continue

        if best == "education":
            edu_list = data.get("education")
            if not isinstance(edu_list, list):
                edu_list = []
                data["education"] = edu_list
            edu_list.append(
                {
                    "degree": (_DEGREE_RE.search(text) or type("", (), {"group": lambda s, *a: ""})()).group(0)
                    if _DEGREE_RE.search(text)
                    else "",
                    "school": _extract_institution_name(text),
                    "start_date": _YEAR_RE.findall(text)[0] if _YEAR_RE.findall(text) else "",
                    "end_date": "",
                    "gpa": "",
                    "field": "",
                    "location": "",
                }
            )
        elif best == "certifications":
            cert_list = data.get("certifications")
            if not isinstance(cert_list, list):
                cert_list = []
                data["certifications"] = cert_list
            cert_list.append({"name": text, "issuer": "", "date": ""})
        elif best == "projects":
            proj_list = data.get("projects")
            if not isinstance(proj_list, list):
                proj_list = []
                data["projects"] = proj_list
            proj_list.append({"name": text[:80], "description": text, "bullets": []})
        elif best == "interests":
            interest_list = data.get("interests")
            if not isinstance(interest_list, list):
                interest_list = []
                data["interests"] = interest_list
            interest_list.append(text)
        elif best == "skills":
            skills_list = data.get("skills")
            if not isinstance(skills_list, list):
                skills_list = []
                data["skills"] = skills_list
            skills_list.append(text)
        elif best == "languages":
            lang_list = data.get("languages")
            if not isinstance(lang_list, list):
                lang_list = []
                data["languages"] = lang_list
            lang_list.append(text)
        elif best == "contact":
            _route_contact_line(text, data)
        else:
            kept_misc.append(text)
            continue
        continue

    # ── Second pass: pattern-based rescue ──────────────────────────────
    # Catch structured data the scorer missed.  Each item is tested with
    # hard regex patterns; first match wins.  Only truly unstructured
    # text survives into misc.
    final_misc: List[str] = []
    for text in kept_misc:
        section = _detect_structured_pattern(text, data)
        if section is None:
            final_misc.append(text)

    data["misc"] = final_misc


def _detect_structured_pattern(text: str, data: Dict) -> str | None:
    """Try to rescue *text* into a proper section using hard patterns.

    Returns the target section name if the item was moved, or ``None``
    if it should stay in misc.
    """
    has_degree = bool(_DEGREE_RE.search(text))
    has_institution = bool(_INSTITUTION_RE.search(text))
    has_year = bool(_YEAR_RE.search(text))
    has_job = _has_job_signal(text)
    has_cert = bool(_CERT_RE.search(text))
    has_project = bool(_PROJECT_RE.search(text))
    has_interest = bool(_INTEREST_RE.search(text))
    tech_hits = _TECH_NAME_RE.findall(text)
    word_count = len(text.split())

    # ── Education: degree keyword + (institution OR year) ──
    if has_degree and (has_institution or has_year):
        edu_list = data.get("education")
        if not isinstance(edu_list, list):
            edu_list = []
            data["education"] = edu_list
        edu_list.append(
            {
                "degree": (_DEGREE_RE.search(text).group(0) if _DEGREE_RE.search(text) else ""),
                "school": _extract_institution_name(text),
                "start_date": _YEAR_RE.findall(text)[0] if _YEAR_RE.findall(text) else "",
                "end_date": "",
                "gpa": "",
                "field": "",
                "location": "",
            }
        )
        return "education"

    # ── Certifications: certificate keyword present ──
    if has_cert and not has_job:
        cert_list = data.get("certifications")
        if not isinstance(cert_list, list):
            cert_list = []
            data["certifications"] = cert_list
        cert_list.append({"name": text, "issuer": "", "date": ""})
        return "certifications"

    # ── Experience: job title + (year OR company-like pattern) ──
    _COMPANY_RE = re.compile(
        r"\b(?:inc|llc|ltd|gmbh|corp|co\.|plc|a\.?ş|ş(?:ti|irketi)"
        r"|limited|company|group|holding|technologies|solutions"
        r"|consulting|services|systems|labs?|studio)\b",
        re.I,
    )
    if has_job and (has_year or bool(_COMPANY_RE.search(text))):
        exp_list = data.get("experiences")
        if not isinstance(exp_list, list):
            exp_list = []
            data["experiences"] = exp_list
        years = _YEAR_RE.findall(text)
        exp_list.append(
            {
                "title": text[:80],
                "company": "",
                "location": "",
                "start_date": years[0] if years else "",
                "end_date": years[1] if len(years) > 1 else "",
                "bullets": [],
            }
        )
        return "experiences"

    # ── Projects: project keyword or GitHub/GitLab URL ──
    if has_project:
        proj_list = data.get("projects")
        if not isinstance(proj_list, list):
            proj_list = []
            data["projects"] = proj_list
        proj_list.append({"name": text[:80], "description": text, "bullets": []})
        return "projects"

    # ── Skills: 3+ tech names detected (comma/slash-delimited lists) ──
    if len(tech_hits) >= 3 and word_count <= 20:
        skills_list = data.get("skills")
        if not isinstance(skills_list, list):
            skills_list = []
            data["skills"] = skills_list
        # Split on common delimiters and add individually
        parts = re.split(r"[,;|/]+", text)
        for part in parts:
            clean = part.strip()
            if clean:
                skills_list.append(clean)
        return "skills"

    # ── Interests: hobby/interest/volunteer keywords ──
    if has_interest and word_count <= 10:
        interest_list = data.get("interests")
        if not isinstance(interest_list, list):
            interest_list = []
            data["interests"] = interest_list
        interest_list.append(text)
        return "interests"

    # ── Languages: structural detection (CEFR / level / sub-skill) ──
    from utils.section_scorer import is_language_entry

    if is_language_entry(text, strict=True) and word_count <= 8:
        lang_list = data.get("languages")
        if not isinstance(lang_list, list):
            lang_list = []
            data["languages"] = lang_list
        lang_list.append(text)
        return "languages"

    # ── Contact: line is primarily email/phone/URL/address ──
    has_email = bool(_EMAIL_RE.search(text))
    has_phone = bool(_PHONE_RE.search(text))
    has_url = bool(_URL_RE.search(text))
    has_address = bool(_ADDRESS_RE.search(text))
    has_birth = bool(_BIRTH_DATE_RE.search(text))
    if (has_email or has_phone or has_address or has_birth) and word_count <= 10:
        _route_contact_line(text, data)
        return "contact"
    if has_url and not has_project and not len(tech_hits) and word_count <= 5:
        _route_contact_line(text, data)
        return "contact"

    return None


# ═══════════════════════════════════════════════════════════════════════════
# 6. URL NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════


def normalize_urls(data: Dict) -> None:
    """Fix malformed URLs like ``https: site.com`` → ``https://site.com``.

    Walks all string fields and list-of-string fields.
    """
    _fix_url_in_dict(data)


def _fix_url_string(text: str) -> str:
    """Fix ``https: site.com`` → ``https://site.com`` in a single string."""
    return _MALFORMED_URL_RE.sub(r"\1://\2", text)


def _fix_url_in_dict(d: Dict) -> None:
    """Recursively fix URLs in a dict.  Also truncate overlong URLs."""
    for key, val in list(d.items()):
        if isinstance(val, str):
            fixed = _fix_url_string(val)
            # Truncate overlong URLs
            if _URL_RE.search(fixed) and len(fixed) > _MAX_URL_LEN:
                logger.warning("url truncated: %d → %d chars", len(fixed), _MAX_URL_LEN)
                fixed = fixed[:_MAX_URL_LEN]
            if fixed != val:
                d[key] = fixed
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, str):
                    fixed = _fix_url_string(item)
                    if fixed != item:
                        val[i] = fixed
                elif isinstance(item, dict):
                    _fix_url_in_dict(item)
        elif isinstance(val, dict):
            _fix_url_in_dict(val)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ENSURE SUMMARY EXISTS
# ═══════════════════════════════════════════════════════════════════════════


def ensure_summary(data: Dict) -> None:
    """If summary is empty, try to derive one from misc or long experience bullets.

    Respects ``_summary_source`` lock: if source is ``"top"``, never
    overwrite.  Mutates *data* in place.
    """
    if data.get("summary"):
        return
    # If source was "top" the summary was explicitly cleared — unusual,
    # but don't re-populate from lower-priority sources.
    if data.get("_summary_source") == "top":
        return

    # Promote long misc items (>= 15 words, prose-like)
    misc = data.get("misc")
    if isinstance(misc, list):
        promoted: List[str] = []
        kept: List[str] = []
        for item in misc:
            if isinstance(item, str) and len(item.split()) >= 15:
                promoted.append(item)
            else:
                kept.append(item)
        if promoted:
            data["summary"] = " ".join(promoted)
            data["misc"] = kept
            return

    # Try first experience entry's first long bullet as summary
    for exp in data.get("experiences") or []:
        if isinstance(exp, dict):
            bullets = exp.get("bullets") or []
            for b in bullets:
                if isinstance(b, str) and len(b.split()) >= 20:
                    data["summary"] = b
                    return


# ═══════════════════════════════════════════════════════════════════════════
# 8. CONTACT STRIPPER (generic — works on education too)
# ═══════════════════════════════════════════════════════════════════════════


def strip_contact_from_education(data: Dict) -> None:
    """Remove contact info (email/phone/address/birth date) from education entries.

    Misplaced contact info is routed to top-level fields.
    Mutates *data* in place.
    """
    education = data.get("education")
    if not isinstance(education, list):
        return

    for edu in education:
        if not isinstance(edu, dict):
            continue
        # Check each string field for contact contamination
        for field_name in ("degree", "school", "field", "location"):
            val = edu.get(field_name, "")
            if not isinstance(val, str):
                continue
            # Extract and route any email/phone found
            email_m = _EMAIL_RE.search(val)
            if email_m and not data.get("email"):
                data["email"] = email_m.group(0)
            phone_m = _PHONE_RE.search(val)
            if phone_m and not data.get("phone"):
                data["phone"] = phone_m.group(0).strip()
            # Clean the field
            cleaned = _EMAIL_RE.sub("", val)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned != val:
                edu[field_name] = cleaned


def strip_contact_from_all_sections(data: Dict) -> None:
    """Remove contact info from ALL sections: projects, skills, certs, interests, languages.

    Misplaced contact info is routed to top-level fields.
    Mutates *data* in place.
    """
    # Projects (list of dicts)
    for proj in data.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        for field_name in ("name", "description"):
            val = proj.get(field_name, "")
            if not isinstance(val, str):
                continue
            email_m = _EMAIL_RE.search(val)
            if email_m and not data.get("email"):
                data["email"] = email_m.group(0)
            phone_m = _PHONE_RE.search(val)
            if phone_m and not data.get("phone"):
                data["phone"] = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", val)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned != val:
                proj[field_name] = cleaned
        bullets = proj.get("bullets")
        if isinstance(bullets, list):
            kept = []
            for b in bullets:
                b = str(b)
                email_m = _EMAIL_RE.search(b)
                if email_m and not data.get("email"):
                    data["email"] = email_m.group(0)
                phone_m = _PHONE_RE.search(b)
                if phone_m and not data.get("phone"):
                    data["phone"] = phone_m.group(0).strip()
                cleaned = _EMAIL_RE.sub("", b)
                cleaned = _PHONE_RE.sub("", cleaned).strip()
                if cleaned and len(cleaned) > 2:
                    kept.append(cleaned)
            proj["bullets"] = kept

    # Certifications (list of dicts)
    for cert in data.get("certifications") or []:
        if not isinstance(cert, dict):
            continue
        for field_name in ("name", "issuer", "date"):
            val = cert.get(field_name, "")
            if not isinstance(val, str):
                continue
            email_m = _EMAIL_RE.search(val)
            if email_m and not data.get("email"):
                data["email"] = email_m.group(0)
            phone_m = _PHONE_RE.search(val)
            if phone_m and not data.get("phone"):
                data["phone"] = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", val)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned != val:
                cert[field_name] = cleaned

    # Flat list sections: skills, interests, languages
    for section_key in ("skills", "interests", "languages"):
        items = data.get(section_key)
        if not isinstance(items, list):
            continue
        kept: List[str] = []
        for item in items:
            if not isinstance(item, str):
                kept.append(item)
                continue
            email_m = _EMAIL_RE.search(item)
            if email_m and not data.get("email"):
                data["email"] = email_m.group(0)
            phone_m = _PHONE_RE.search(item)
            if phone_m and not data.get("phone"):
                data["phone"] = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", item)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned and len(cleaned) > 1:
                kept.append(cleaned)
        data[section_key] = kept


# ═══════════════════════════════════════════════════════════════════════════
# 9. SCORE-BASED EXPERIENCE ENTRIES RE-EVALUATION
# ═══════════════════════════════════════════════════════════════════════════


def rescore_experience_entries(data: Dict) -> None:
    """Re-score each experience entry.  If an entry scores higher as
    education or another section, move it there.

    If *experience* had an explicit header in the original CV, require
    very-high confidence before moving any entry out (section lock).

    Mutates *data* in place.
    """
    from utils.section_scorer import (
        score_dict_entry,
        locked_sections,
        LOCKED_MIN_SCORE,
        LOCKED_MIN_MARGIN,
    )

    experiences = data.get("experiences")
    if not isinstance(experiences, list) or not experiences:
        return

    locked = locked_sections(data.get("section_titles"))
    exp_locked = "experience" in locked
    min_s = LOCKED_MIN_SCORE if exp_locked else 0.35
    min_m = LOCKED_MIN_MARGIN if exp_locked else 0.10

    kept_exp: List[Dict] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            kept_exp.append(exp)
            continue

        scores = score_dict_entry(exp)
        best = scores.best()

        if best == "education" and scores.education >= min_s and scores.education - scores.experience >= min_m:
            edu_list = data.get("education")
            if not isinstance(edu_list, list):
                edu_list = []
                data["education"] = edu_list
            edu_list.append(
                {
                    "degree": exp.get("title", ""),
                    "school": exp.get("company", ""),
                    "location": exp.get("location", ""),
                    "start_date": exp.get("start_date", ""),
                    "end_date": exp.get("end_date", ""),
                    "gpa": "",
                    "field": "",
                }
            )
        elif best == "contact" and scores.contact >= min_s and scores.contact - scores.experience >= min_m:
            text = " ".join(str(v) for v in exp.values() if isinstance(v, str))
            _route_contact_line(text, data)
        else:
            kept_exp.append(exp)

    data["experiences"] = kept_exp


# ═══════════════════════════════════════════════════════════════════════════
# 10. SCORE-BASED SECTION VALIDATION (all sections)
# ═══════════════════════════════════════════════════════════════════════════


def validate_section_placement(data: Dict) -> None:
    """Re-score items in education, projects, skills, certs, interests, languages.

    If an item scores confidently for a different section, move it there.
    Respects explicit-header locks: items in sections with an original
    header require very-high confidence to be moved out.

    Mutates *data* in place.
    """
    from utils.section_scorer import (
        score_text,
        score_dict_entry,
        locked_sections,
        LOCKED_MIN_SCORE,
        LOCKED_MIN_MARGIN,
    )

    locked = locked_sections(data.get("section_titles"))

    def _thresholds(section_key: str):
        is_locked = section_key in locked
        ms = LOCKED_MIN_SCORE if is_locked else 0.35
        mm = LOCKED_MIN_MARGIN if is_locked else 0.10
        return ms, mm

    # ── Education items that might be experience ──
    edu_list = data.get("education")
    if isinstance(edu_list, list) and edu_list:
        min_s, min_m = _thresholds("education")
        kept_edu: List[Dict] = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                kept_edu.append(edu)
                continue
            scores = score_dict_entry(edu)
            best = scores.best()
            if best == "experience" and scores.experience >= min_s and scores.experience - scores.education >= min_m:
                exp_list = data.get("experiences")
                if not isinstance(exp_list, list):
                    exp_list = []
                    data["experiences"] = exp_list
                exp_list.append(
                    {
                        "title": edu.get("degree", ""),
                        "company": edu.get("school", ""),
                        "location": edu.get("location", ""),
                        "start_date": edu.get("start_date", ""),
                        "end_date": edu.get("end_date", ""),
                        "bullets": [],
                    }
                )
            else:
                kept_edu.append(edu)
        data["education"] = kept_edu

    # ── Flat list sections: skills, interests, languages ──
    _FLAT_SECTION_MAP = {
        "skills": {"education", "certifications", "languages", "interests"},
        "interests": {"skills", "languages"},
        "languages": {"skills", "interests"},
    }
    for section_key, allowed_targets in _FLAT_SECTION_MAP.items():
        items = data.get(section_key)
        if not isinstance(items, list) or not items:
            continue
        min_s, min_m = _thresholds(section_key)
        kept: List = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                continue
            scores = score_text(item.strip())
            best = scores.best()
            best_val = scores.best_score()
            margin = scores.margin()
            if best != section_key and best in allowed_targets and best_val >= min_s and margin >= min_m:
                target_list = data.get(best)
                if not isinstance(target_list, list):
                    target_list = []
                    data[best] = target_list
                target_list.append(item.strip())
            else:
                kept.append(item)
        data[section_key] = kept


# ═══════════════════════════════════════════════════════════════════════════
# 11. COMBINED ENTRY POINT (raw-dict level, called from normalize_agent)
# ═══════════════════════════════════════════════════════════════════════════


def apply_normalization_rules(data: Dict) -> Dict:
    """Apply sanitization rules to raw data dict.

    Called after section resolution (cross-section fixes) has already run.
    This function only sanitizes — no section moving.

    Pipeline order:
    1. URL normalization
    2. Name extraction
    3. Experience sanitization (contact/address/birth stripping)
    4. Contact stripping from education
    4b. Contact stripping from all other sections
    5. Auto-create education if missing
    6. Language code + tech name filter
    7. Ensure summary exists

    Cross-section resolution (experience re-scoring, misc redistribution,
    section validation) is handled by ``section_resolver.resolve_parsed_entries``
    which runs before this function.

    Mutates *data* in place and returns it.
    """
    # 1. URL normalization (first — fixes malformed URLs before other rules parse them)
    normalize_urls(data)

    # 2. Name extraction if missing
    ensure_name(data)

    # 3. Experience sanitization — remove contact, address, birth date, edu lines
    experiences = data.get("experiences") or data.get("experience") or []
    if isinstance(experiences, list):
        data["experiences"] = sanitize_experience_entries(experiences, data)

    # 4. Strip contact info from education entries
    strip_contact_from_education(data)

    # 4b. Strip contact info from projects, skills, certs, interests, languages
    strip_contact_from_all_sections(data)

    # 5. Auto-create education if missing
    create_education_from_text(data)

    # 6. Language code + tech name filter
    languages = data.get("languages")
    if isinstance(languages, list):
        from services.cv_autofix_service import _normalize_language_lines

        languages = _normalize_language_lines(languages)
        data["languages"] = filter_language_codes(languages)

    # 7. Ensure summary exists if possible
    ensure_summary(data)

    return data
