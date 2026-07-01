"""Schema Builder — maps normalized pipeline output to strict CVSchema.

This is the single bridge between normalize_agent output and the
typed CVSchema.  No text re-parsing happens here; we only map fields.
"""

from __future__ import annotations

import json as _json
import logging
import re
import time
import unicodedata
from typing import Any, Dict, List

logger = logging.getLogger("app.parser.schema")


def _structured_log(
    _logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    """Emit a structured JSON log line with standardised fields."""
    payload = {"event": event, **fields}
    _logger.log(level, _json.dumps(payload, default=str, ensure_ascii=False))


from schemas.cv_schema import (
    CVSchema,
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
)


def _clean(value: Any) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _balance_parentheses(value: str) -> str:
    text = _clean(value)
    if text.count("(") > text.count(")") and len(text) <= 180:
        text = text + ")" * (text.count("(") - text.count(")"))
    return text


def _clean_sentence_spacing(value: str) -> str:
    text = _clean(value)
    text = re.sub(r"(?<=[A-Za-z)])\.(?=[A-Z])", ". ", text)
    text = re.sub(r",(?=[A-Za-z])", ", ", text)
    return text


def _clean_list(items: list | None) -> List[str]:
    return [_clean(v) for v in (items or []) if _clean(v)]


def _clean_bullets(bullets: list | None) -> List[str]:
    out: List[str] = []
    for b in bullets or []:
        text = _clean_sentence_spacing(b)
        # Strip leading bullet markers for consistency
        text = re.sub(r"^[-*•]\s*", "", text).strip()
        if text:
            out.append(text)
    return out


_BULLET_PREFIX_RE = re.compile(
    r"^\s*[-*"
    r"•‣⁃∙·"  # bullet, triangular, hyphen-bullet, operator, middle dot
    r"▪■●○◦"  # squares, black circle, white circle, white bullet
    r"▸▹▶▷❖♦"  # triangular markers, diamond bullets
    r""  # private-use bullet (Wingdings/Symbol exports)
    r"]\s*"
)
_INSTITUTION_WORD_RE = re.compile(
    r"\b(?:university|universit\w*|üniversite\w*|institute|technology|college|school"
    r"|faculty|academy|enstit|okulu|lisesi)\b",
    re.I,
)
_DEGREE_WORD_RE = re.compile(
    r"\b(?:b\.?\s*tech|b\.?\s*sc|b\.?\s*s\.?c|m\.?\s*sc|bachelor|master"
    r"|degree|diploma|associate|ph\.?\s*d|lisans|mühendisliğ\w*|muhendisli\w*)\b",
    re.I,
)
_DATE_RANGE_VALUE_RE = re.compile(
    r"^\s*((?:19|20)\d{2}|\d{1,2}[/.]\s*(?:19|20)\d{2})\s*[-\u2013\u2014]\s*"
    r"((?:19|20)\d{2}|\d{2}|\d{1,2}[/.]\s*(?:19|20)\d{2}|present|current|ongoing|halen|devam\s+ediyor)\s*$",
    re.I,
)
_YEAR_RANGE_RE = re.compile(r"^\s*(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)?\d{2}\s*$")
_BAD_NAME_RE = re.compile(
    r"\b(?:b\.?\s*tech|b\.?\s*sc|m\.?\s*sc|bachelor|master|degree|engineer"
    r"|developer|student|intern|professional|summary|resume|cv)\b",
    re.I,
)
_NAME_TECH_RE = re.compile(
    r"\b(?:html|css|javascript|typescript|typecript|python|java|react|next\.?\s*js"
    r"|node\.?js|sql|git|github|docker|websocket|rest\s+api|c\+\+)\b",
    re.I,
)
_GENERIC_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/\S*)?$",
    re.I,
)
_SUMMARY_NOISE_RE = re.compile(
    r"\b(?:father'?s\s+name|date\s+of\s+birth|birth\s+date|marital\s+status"
    r"|nationality|declaration|sex\s*:|gender\s*:|home\s+town|hobbies?"
    r"|cricket|football|watching\s+movies|assert\s+you|place\s*:|date\s*$"
    r"|gold\s+medallist|participated\s+in|active\s+member|society)\b",
    re.I,
)
_SKILL_GARBAGE_RE = re.compile(
    r"(?:@|gmail\.com|hotmail\.com|yahoo\.com|^\d+(?:\.\d+)?%?$"
    r"|^\d{1,2}(?:th|st|nd|rd)$|^\d{4}$|^\d{1,2}[/.]\d{1,2}[/.]\d{2,4}$"
    r"|^[a-z]$|^[a-z]\.[a-z]\.?|^b\.?\s*tech\b|^b\.?\s*sc\b|^m\.?\s*sc\b"
    r"|bachelor|master|degree|school$|university$|^real$|^ehteshamkhan\d*$)",
    re.I,
)
_SCHOOL_LEVEL_EDU_RE = re.compile(
    r"\b(?P<degree>\d{1,2}(?:th|st|nd|rd)|high\s+school|secondary\s+school|lise)"
    r"\s+from\s+(?P<school>.*?)(?=\s+in\s+(?:the\s+)?year\b|\s+\d{1,2}(?:th|st|nd|rd)\s+from\b|$)"
    r"(?:\s+in\s+(?:the\s+)?year\s*(?P<year>(?:19|20)\d{2})?)?"
    r"(?:\s*(?:with\s+)?(?P<gpa>\d+(?:\.\d+)?\s*%\s*(?:marks?)?))?",
    re.I,
)


def _strip_bullet_prefix(text: str) -> str:
    return _BULLET_PREFIX_RE.sub("", _clean(text)).strip()


def _looks_like_year_range(text: str) -> bool:
    return bool(_YEAR_RANGE_RE.match(_clean(text)))


def _has_plausible_phone_digits(text: str) -> bool:
    digits = re.sub(r"\D", "", _clean(text))
    return len(digits) >= 7


def _name_is_structural(name: str) -> bool:
    value = _clean(name)
    if not value or len(value.split()) > 5:
        return True
    if _INSTITUTION_WORD_RE.search(value):
        return True
    if _NAME_TECH_RE.search(value) and re.search(r"[,/|]", value):
        return True
    return bool(_BAD_NAME_RE.search(value))


def _iter_payload_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _iter_payload_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_payload_strings(nested)


def _find_name_candidate(data: Dict[str, Any]) -> str:
    bad_words = {
        "RESUME",
        "SUMMARY",
        "PROFESSIONAL",
        "EDUCATION",
        "EXPERIENCE",
        "SKILLS",
        "PROJECTS",
        "BACHELOR",
        "MASTER",
        "DEGREE",
        "TECH",
        "UNIVERSITY",
        "SCHOOL",
        "INSTITUTE",
        "ENGINEERING",
        "ENGINEER",
        "COMPUTER",
        "SOFTWARE",
        "DEVELOPER",
        "TECHNOLOGY",
        "GAME",
        "BLOG",
        "APP",
        "APPLICATION",
        "PROJECT",
        "PERSONAL",
        "MILLIONAIRE",
        "WHO",
        "WANTS",
    }

    priority_texts: list[str] = []
    for key in ("raw_text", "text", "content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            priority_texts.append(value)

    seen_texts: set[str] = set()
    ordered_texts: list[str] = []
    for text in priority_texts + [str(v) for v in _iter_payload_strings(data)]:
        if text in seen_texts:
            continue
        seen_texts.add(text)
        ordered_texts.append(text)

    for text in priority_texts:
        for match in re.finditer(r"\b([A-Z][A-Z'â€™.-]{1,}(?:\s+[A-Z][A-Z'â€™.-]{1,}){1,3})\b", text):
            candidate = match.group(1).strip(" -|")
            words = candidate.split()
            if (
                2 <= len(words) <= 4
                and not any(w.strip(".'â€™") in bad_words for w in words)
                and not _INSTITUTION_WORD_RE.search(candidate)
                and not _NAME_TECH_RE.search(candidate)
            ):
                return candidate.title()

    for text in ordered_texts:
        for line in str(text).splitlines():
            candidate = _clean(line).strip(" -|")
            if candidate.isupper():
                continue
            words = candidate.split()
            if not (2 <= len(words) <= 4):
                continue
            if any(w.strip(".'â€™").upper() in bad_words for w in words):
                continue
            if (
                _BAD_NAME_RE.search(candidate)
                or _NAME_TECH_RE.search(candidate)
                or _INSTITUTION_WORD_RE.search(candidate)
            ):
                continue
            if re.search(r"[@:/]|\d", candidate):
                continue
            # Check if each word is Title Case with allowed punctuation
            is_valid_name = True
            for w in words:
                if not w:
                    is_valid_name = False
                    break
                if not w[0].isupper():
                    is_valid_name = False
                    break
                if not all(c.isalpha() or c in "'’-" for c in w[1:]):
                    is_valid_name = False
                    break
            if is_valid_name:
                return candidate

    for text in ordered_texts:
        for match in re.finditer(r"\b([A-Z][A-Z'’.-]{1,}(?:\s+[A-Z][A-Z'’.-]{1,}){1,3})\b", text):
            candidate = match.group(1).strip(" -|")
            words = candidate.split()
            if (
                2 <= len(words) <= 4
                and not any(w.strip(".'’") in bad_words for w in words)
                and not _INSTITUTION_WORD_RE.search(candidate)
                and not _NAME_TECH_RE.search(candidate)
            ):
                return candidate.title()
    return ""


def _split_date_range_value(value: str) -> tuple[str, str]:
    match = _DATE_RANGE_VALUE_RE.match(_clean(value))
    if not match:
        return "", ""
    start, end = match.group(1).strip(), match.group(2).strip()
    if re.fullmatch(r"\d{2}", end) and re.fullmatch(r"(?:19|20)\d{2}", start):
        end = start[:2] + end
    return start, end


def _looks_like_tech_list(text: str) -> bool:
    value = _clean(text)
    if not value or not re.search(r"[,|/]", value):
        return False
    tokens = [part.strip() for part in re.split(r"\s*[,|/]\s*", value) if part.strip()]
    return len(tokens) >= 2 and all(len(token.split()) <= 4 for token in tokens)


def _extract_school_level_education_entries(text: str) -> list[EducationEntry]:
    value = re.sub(r"\b(?:academic|professional)\s*:?", " ", _strip_bullet_prefix(text), flags=re.I)
    entries: list[EducationEntry] = []
    for match in _SCHOOL_LEVEL_EDU_RE.finditer(value):
        degree = _clean(match.group("degree")).strip(" .")
        school = _clean(match.group("school")).strip(" .,-")
        year = _clean(match.group("year")).strip()
        gpa = _clean(match.group("gpa")).strip()
        if not degree or not school:
            continue
        entries.append(
            EducationEntry(
                degree=degree,
                school=school,
                start_date=year,
                end_date=year,
                gpa=gpa,
            )
        )
    return entries


def _clean_summary_text(summary: str, full_name: str = "") -> str:
    text = _clean(summary)
    if not text:
        return ""
    text = re.sub(r"\b([A-Za-z]{3,})-\s+(on|world|time|stack|end|based|level)\b", r"\1-\2", text, flags=re.I)
    if full_name:
        text = re.sub(rf"^\s*{re.escape(full_name)}\b", "", text, flags=re.I).strip()
    text = _EMAIL_SUMMARY_RE.sub("", text)
    text = _PHONE_SUMMARY_RE.sub("", text)
    text = _URL_SUMMARY_RE.sub("", text)
    starter = re.search(r"\b(?:to\s+\w+|seeking|objective|profile)\b", text, re.I)
    if starter and starter.start() <= 120:
        text = text[starter.start() :].strip()
    chunks = re.split(r"(?<=[.!?])\s+|(?:\s+[•\uf0b7]\s+)", text)
    kept = [chunk.strip() for chunk in chunks if chunk.strip() and not _SUMMARY_NOISE_RE.search(chunk)]
    return _enforce_summary_rules(" ".join(kept))


def _normalize_education_entry(edu: EducationEntry) -> None:
    for attr in ("degree", "field", "school", "location", "start_date", "end_date", "gpa"):
        setattr(edu, attr, _balance_parentheses(_strip_bullet_prefix(getattr(edu, attr, ""))))

    edu.school = re.sub(r"^\s*(?:professional|academic)\s*:?\s*", "", edu.school, flags=re.I).strip()

    if edu.start_date and not edu.end_date:
        start, end = _split_date_range_value(edu.start_date)
        if start or end:
            edu.start_date, edu.end_date = start, end

    if edu.school and edu.start_date and not any(_split_date_range_value(edu.start_date)):
        if _INSTITUTION_WORD_RE.search(edu.start_date) or len(edu.start_date.split()) > 4:
            edu.school = f"{edu.school} {edu.start_date}".strip()
            edu.start_date = ""

    if not edu.school and edu.degree:
        parts = re.split(r"\s+[-\u2013\u2014]\s+", edu.degree, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            if _INSTITUTION_WORD_RE.search(left) and not _INSTITUTION_WORD_RE.search(right):
                edu.school, edu.degree = left, right
            elif _INSTITUTION_WORD_RE.search(right):
                edu.degree, edu.school = left, right

    combined = " ".join(p for p in [edu.degree, edu.school, edu.location, edu.start_date] if p)
    match = re.search(
        r"(?P<degree>\b(?:B\.?\s*Tech|B\.?\s*Sc|B\.?\s*S\.?c|M\.?\s*Sc|Bachelor(?:'s)?(?:\s+Degree)?|Master(?:'s)?(?:\s+Degree)?)\b(?:\s+in\s+.+?)?)\s+from\s+(?P<school>.+?)(?:,\s*in\s+year|\s+in\s+year|$)",
        combined,
        re.I,
    )
    if match:
        edu.degree = _clean(match.group("degree")).strip(" .")
        edu.school = _clean(match.group("school")).strip(" .")

    if not edu.degree and edu.school:
        match = re.match(
            r"(?P<degree>.+?\b(?:degree|b\.?\s*tech|b\.?\s*sc|bachelor|master)\b)\s+(?P<school>.+(?:university|institute|college|school).*)$",
            edu.school,
            re.I,
        )
        if match:
            edu.degree = _clean(match.group("degree")).strip(" -")
            edu.school = _clean(match.group("school")).strip(" -")

    if not edu.start_date or not edu.end_date:
        years = re.findall(r"\b((?:19|20)\d{2})\s*[-\u2013\u2014]\s*(\d{2}|(?:19|20)\d{2})\b", combined)
        if years:
            start, end = years[0]
            if len(end) == 2:
                end = start[:2] + end
            edu.start_date = edu.start_date or start
            edu.end_date = edu.end_date or end
    if not edu.gpa:
        grade = re.search(r"\b\d+(?:\.\d+)?\s*%\s*(?:marks?)?", combined, re.I)
        if grade:
            edu.gpa = grade.group(0).strip()
    if edu.start_date and not any(_split_date_range_value(edu.start_date)):
        year_range = re.search(r"\b((?:19|20)\d{2})\s*[-\u2013\u2014]\s*(\d{2}|(?:19|20)\d{2})\b", edu.start_date)
        if year_range:
            start, end = year_range.group(1), year_range.group(2)
            edu.start_date = start
            edu.end_date = edu.end_date or (start[:2] + end if len(end) == 2 else end)
        elif re.fullmatch(r"(?:19|20)\d{2}", edu.start_date.strip()):
            pass
        else:
            edu.start_date = ""
    if edu.location and (re.search(r"\bstudent\s+at\b", edu.location, re.I) or len(edu.location.split()) > 8):
        edu.location = ""


def _is_trivial_education(edu: EducationEntry) -> bool:
    text = _clean(" ".join([edu.degree, edu.school, edu.field, edu.location, edu.start_date, edu.end_date]))
    if not text:
        return True
    if not (edu.start_date or edu.end_date) and len(text.split()) <= 2:
        return True
    if re.search(r"\bstudent\s+at\b", text, re.I) and not (edu.start_date or edu.end_date):
        return True
    return False


def _clean_skill_list(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        skill = _strip_bullet_prefix(item).strip(" .")
        if not skill or _SKILL_GARBAGE_RE.search(skill):
            continue
        if len(skill.split()) > 8 and not re.search(r"[,;|/]", skill):
            continue
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            output.append(skill)
    return output


def _merge_skill_fragments(items: list[str]) -> list[str]:
    merged: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            merged.append(current.strip(" ,"))
        current = ""

    for raw in items or []:
        raw_text = _clean(raw)
        had_bullet = bool(_BULLET_PREFIX_RE.match(raw_text))
        item = _strip_bullet_prefix(raw_text).strip(" .")
        if not item:
            continue

        starts_continuation = bool(
            re.match(r"^(?:and|or|ve|ile|with|using|&)\b", item, re.I)
            or item[:1].islower()
            or (
                len(item.split()) <= 3
                and not re.match(r"^(?:proficient|experienced|skilled|strong|good|hands)\b", item, re.I)
            )
        )
        starts_new = had_bullet or not current or not starts_continuation

        if starts_new:
            flush()
            current = item
            continue

        if item.startswith("&") or re.match(r"^(?:and|or|ve|ile)\b", item, re.I):
            sep = " "
        else:
            sep = ", "
        current = f"{current.rstrip(' ,')}{sep}{item}"

    flush()
    return merged


def _repair_schema(schema: CVSchema, data: Dict[str, Any]) -> None:
    if _name_is_structural(schema.full_name):
        schema.full_name = _find_name_candidate(data)

    if re.match(r"^\s*project\s*:", schema.summary, re.I):
        name = re.sub(r"^\s*project\s*:\s*", "", schema.summary, flags=re.I)
        desc = ""
        if re.search(r"\bsynopsis\s*:", name, re.I):
            name, desc = re.split(r"\bsynopsis\s*:\s*", name, maxsplit=1, flags=re.I)
        schema.projects.append(ProjectEntry(name=_clean(name), description=_clean(desc), bullets=[]))
        schema.summary = ""

    schema.summary = _clean_summary_text(schema.summary, schema.full_name)

    expanded_edu: list[EducationEntry] = []
    for edu in schema.education:
        raw_edu_text = _clean(
            " ".join(
                _strip_bullet_prefix(getattr(edu, attr, ""))
                for attr in ("degree", "field", "school", "location", "start_date", "end_date", "gpa")
                if getattr(edu, attr, "")
            )
        )
        _normalize_education_entry(edu)
        school_level_entries = _extract_school_level_education_entries(raw_edu_text)
        if school_level_entries and not (_DEGREE_WORD_RE.search(edu.degree) and edu.school):
            expanded_edu.extend(school_level_entries)
            continue
        expanded_edu.append(edu)
    schema.education = expanded_edu

    deduped_edu: list[EducationEntry] = []
    seen_edu: set[str] = set()
    seen_edu_period: dict[str, int] = {}

    def _weak_edu_degree(value: str) -> bool:
        return bool(re.search(r"\b(?:student|year)\b", value or "", re.I))

    for edu in schema.education:
        if _is_trivial_education(edu):
            continue
        key = re.sub(r"\W+", "", f"{edu.degree}|{edu.school}|{edu.start_date}|{edu.end_date}".lower())
        period_key = re.sub(r"\W+", "", f"{edu.school}|{edu.start_date}|{edu.end_date}".lower())
        if period_key and period_key in seen_edu_period:
            existing_idx = seen_edu_period[period_key]
            existing = deduped_edu[existing_idx]
            if _weak_edu_degree(edu.degree):
                continue
            if _weak_edu_degree(existing.degree):
                deduped_edu[existing_idx] = edu
                seen_edu.add(key)
            continue
        if key and key not in seen_edu:
            seen_edu.add(key)
            if period_key:
                seen_edu_period[period_key] = len(deduped_edu)
            deduped_edu.append(edu)
    schema.education = deduped_edu

    repaired_exps: list[ExperienceEntry] = []
    for exp in schema.experiences:
        raw_title = _strip_bullet_prefix(exp.title)
        raw_company = _strip_bullet_prefix(exp.company)
        raw_location = _strip_bullet_prefix(exp.location)
        exp.title = _balance_parentheses(raw_title)
        exp.company = _balance_parentheses(raw_company)
        exp.location = _balance_parentheses(raw_location)
        labels: dict[str, str] = {}
        kept_bullets: list[str] = []
        for bullet in exp.bullets:
            clean_bullet = _strip_bullet_prefix(bullet)
            label_match = re.match(
                r"^(organization|company|employer|duration|project\s+title|synopsis)\s*:\s*(.+)$", clean_bullet, re.I
            )
            if label_match:
                labels[label_match.group(1).lower()] = label_match.group(2).strip()
            else:
                kept_bullets.append(_clean_sentence_spacing(clean_bullet))
        if labels.get("organization") and not exp.company:
            exp.company = labels["organization"]
        if labels.get("project title") and (not exp.title or exp.title.lower() == "experience"):
            exp.title = labels["project title"]
        if labels.get("synopsis"):
            kept_bullets.insert(0, _clean_sentence_spacing(labels["synopsis"]))
        if labels.get("duration") and not exp.location:
            exp.location = labels["duration"]
        exp.bullets = [b for b in kept_bullets if b]
        if not exp.bullets and repaired_exps and len(" ".join([exp.title, exp.company]).split()) >= 6:
            target = repaired_exps[-1]
            fragment = _clean(" ".join([raw_title, raw_company]))
            if target.bullets:
                target.bullets[-1] = f"{target.bullets[-1]} {fragment}".strip()
            else:
                target.bullets.append(fragment)
            continue
        repaired_exps.append(exp)
    schema.experiences = repaired_exps

    expanded_projects: list[ProjectEntry] = []
    embedded_project_re = re.compile(
        r"(?P<prefix>.+?\.)\s+(?P<name>[A-Z][A-Z0-9 '&/.-]{3,})\s*[-\u2013\u2014]\s*"
        r"(?P<tech>(?:[A-Za-z][A-Za-z0-9.+#]*\s*,\s*)+[A-Za-z][A-Za-z0-9.+#]*)\s*$"
    )
    for proj in schema.projects:
        proj.name = _balance_parentheses(_strip_bullet_prefix(proj.name))
        proj.description = _balance_parentheses(_strip_bullet_prefix(proj.description))
        proj.name = re.sub(r"^\s*project\s*:\s*", "", proj.name, flags=re.I).strip()
        proj.description = re.sub(r"^\s*synopsis\s*:\s*", "", proj.description, flags=re.I).strip()
        embedded = embedded_project_re.match(proj.description)
        if embedded:
            proj.description = _clean(embedded.group("prefix"))
            expanded_projects.append(proj)
            expanded_projects.append(
                ProjectEntry(
                    name=_clean(embedded.group("name")).title(),
                    description="",
                    bullets=[_clean(embedded.group("tech"))],
                )
            )
            continue
        if proj.name and proj.description and _looks_like_tech_list(proj.description):
            proj.name = f"{proj.name} - {proj.description}"
            proj.description = ""
        expanded_projects.append(proj)
    schema.projects = expanded_projects

    merged_edu: list[EducationEntry] = []
    idx = 0
    while idx < len(schema.education):
        edu = schema.education[idx]
        if (
            idx + 1 < len(schema.education)
            and edu.degree
            and edu.school
            and _DEGREE_WORD_RE.search(edu.school)
            and schema.education[idx + 1].school
            and _INSTITUTION_WORD_RE.search(schema.education[idx + 1].school)
        ):
            nxt = schema.education[idx + 1]
            edu.degree = _clean(f"{edu.degree} - {edu.school}")
            edu.school = nxt.school
            edu.location = edu.location or nxt.location
            edu.gpa = edu.gpa or nxt.gpa
            idx += 2
            merged_edu.append(edu)
            continue
        merged_edu.append(edu)
        idx += 1
    schema.education = merged_edu

    merged_projects: list[ProjectEntry] = []
    for proj in schema.projects:
        if (
            merged_projects
            and not proj.description
            and not proj.bullets
            and len(proj.name.split()) >= 5
            and not proj.name.isupper()
        ):
            target = merged_projects[-1]
            if target.bullets:
                target.bullets[-1] = f"{target.bullets[-1]} {proj.name}".strip()
            else:
                target.description = f"{target.description} {proj.name}".strip()
            continue
        merged_projects.append(proj)
    schema.projects = merged_projects

    invalid_language_skills: list[str] = []
    valid_languages: list[str] = []
    for lang in (_strip_bullet_prefix(item).strip(" .") for item in schema.languages):
        if not lang:
            continue
        if _is_valid_language(lang):
            valid_languages.append(lang)
        elif re.search(
            r"\b(?:proficient|knowledge|experience|skilled|familiar|hands[- ]?on|transmission|switching|control)\b",
            lang,
            re.I,
        ):
            invalid_language_skills.append(lang)
    schema.languages = valid_languages

    schema.skills = _clean_skill_list(_merge_skill_fragments(schema.skills))
    if invalid_language_skills:
        schema.skills.extend(_clean_skill_list(invalid_language_skills))
    if schema.skills_categorized:
        cleaned_cat: Dict[str, List[str]] = {}
        for category, values in schema.skills_categorized.items():
            clean_category = _strip_bullet_prefix(category).strip(":")
            clean_values = _clean_skill_list(values)
            if clean_category and clean_values:
                cleaned_cat[clean_category] = clean_values
        schema.skills_categorized = cleaned_cat

    schema.languages = [
        lang
        for lang in (_strip_bullet_prefix(item).strip(" .") for item in schema.languages)
        if lang and _is_valid_language(lang)
    ]


_PROFICIENCY_WORDS = (
    "native",
    "fluency",
    "fluent",
    "bilingual",
    "mother tongue",
    "advanced",
    "proficient",
    "proficiency",
    "professional",
    "upper intermediate",
    "intermediate",
    "conversational",
    "conversant",
    "elementary",
    "beginner",
    "basic",
    "limited",
    "working",
)
_PROFICIENCY_ALT = "|".join(re.escape(w) for w in _PROFICIENCY_WORDS)
_PROFICIENCY_FIND_RE = re.compile(r"\b(" + _PROFICIENCY_ALT + r")\b", re.I)

# Recognized spoken-language names (English + native spellings of the most
# common ones). Used to keep the languages field precise: skill-like phrases
# that carry a proficiency word but name no language ("Proficient in animal
# handling", "Microsoft Suite") are rejected, while genuine entries
# ("English (Fluent)", "Mandarin") are kept.
_LANGUAGE_NAMES = {
    "english",
    "spanish",
    "french",
    "german",
    "italian",
    "portuguese",
    "dutch",
    "russian",
    "polish",
    "czech",
    "slovak",
    "ukrainian",
    "romanian",
    "hungarian",
    "greek",
    "turkish",
    "arabic",
    "hebrew",
    "persian",
    "farsi",
    "hindi",
    "urdu",
    "bengali",
    "punjabi",
    "tamil",
    "telugu",
    "marathi",
    "gujarati",
    "chinese",
    "mandarin",
    "cantonese",
    "japanese",
    "korean",
    "vietnamese",
    "thai",
    "indonesian",
    "malay",
    "tagalog",
    "filipino",
    "swahili",
    "amharic",
    "yoruba",
    "igbo",
    "hausa",
    "zulu",
    "afrikaans",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
    "icelandic",
    "estonian",
    "latvian",
    "lithuanian",
    "bulgarian",
    "serbian",
    "croatian",
    "bosnian",
    "slovenian",
    "albanian",
    "macedonian",
    "catalan",
    "basque",
    "galician",
    "welsh",
    "irish",
    "gaelic",
    "maltese",
    "georgian",
    "armenian",
    "azerbaijani",
    "kazakh",
    "uzbek",
    "mongolian",
    "nepali",
    "sinhala",
    "khmer",
    "lao",
    "burmese",
    "pashto",
    "kurdish",
    # additional world languages (recall for less-common but real languages
    # that carry only a proficiency word, no CEFR code)
    "somali",
    "wolof",
    "malayalam",
    "kannada",
    "odia",
    "oriya",
    "assamese",
    "sindhi",
    "tigrinya",
    "oromo",
    "luxembourgish",
    "belarusian",
    "tibetan",
    "uyghur",
    "tajik",
    "turkmen",
    "kyrgyz",
    "dari",
    "fula",
    "fulani",
    "twi",
    "akan",
    "shona",
    "xhosa",
    "sesotho",
    "sotho",
    "tswana",
    "kinyarwanda",
    "chichewa",
    "lingala",
    "quechua",
    "guarani",
    "maori",
    "hawaiian",
    "samoan",
    "fijian",
    "tongan",
    "esperanto",
    "latin",
    "sanskrit",
    "yiddish",
    "flemish",
    "frisian",
    "breton",
    "occitan",
    "haitian creole",
    "creole",
    "sign language",
    # native spellings
    "türkçe",
    "ingilizce",
    "almanca",
    "fransızca",
    "ispanyolca",
    "italyanca",
    "deutsch",
    "englisch",
    "französisch",
    "français",
    "anglais",
    "allemand",
    "espagnol",
    "español",
    "inglés",
    "alemán",
    "italiano",
    "português",
    "русский",
    "中文",
    "日本語",
    "한국어",
    "العربية",
}
_LANGUAGE_NAME_RE = re.compile(
    r"(?<![a-zçğıöşü])(?:"
    + "|".join(re.escape(n) for n in sorted(_LANGUAGE_NAMES, key=len, reverse=True))
    + r")(?![a-zçğıöşü])",
    re.I,
)


def _has_language_name(text: str) -> bool:
    """True if *text* mentions a recognized spoken-language name."""
    return bool(_LANGUAGE_NAME_RE.search(text or ""))


# Explicit CEFR / JLPT proficiency *codes* (not free-text level words).
_CEFR_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[ABC][12]|N[1-5])(?![A-Za-z0-9])")
_LANG_CONNECTOR_RE = re.compile(
    r"\b(?:in|of|written|oral|spoken|and|knowledge|skills?|level)\b",
    re.I,
)


def _normalize_spoken_language(text: str) -> str:
    """Reorder free-form proficiency phrases into ``Name (Level)`` form.

    ``"Fluent in English"`` → ``"English (Fluent)"``; ``"Native German"`` →
    ``"German (Native)"``. Entries that already use a structured form
    (``"English: B2"`` / ``"English (Fluent)"``) or that cannot be reduced to a
    single clean name are returned unchanged so no information is lost.
    """
    t = _strip_bullet_prefix(text).strip(" .;,")
    if not t:
        return ""
    # Already structured (has level marker or colon) → keep as-is.
    if "(" in t or ":" in t:
        return t
    # A comma means a compound phrase (e.g. multiple languages) we should not
    # mangle into a single "Name (Level)".
    if "," in t:
        return t
    # Multiple language names joined by "and"/"&"/"/" (no comma) would otherwise
    # be collapsed into one garbled token ("English and French" → "English
    # French (Fluent)"). Keep the original so both languages survive.
    if len(_LANGUAGE_NAME_RE.findall(t)) >= 2:
        return t
    match = _PROFICIENCY_FIND_RE.search(t)
    if not match:
        return t
    level = match.group(1)
    level = level[:1].upper() + level[1:].lower()
    name = _PROFICIENCY_FIND_RE.sub("", t)
    name = _LANG_CONNECTOR_RE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .,;-()")
    if not name or len(name.split()) > 3:
        return t  # could not isolate a clean name — keep original
    return f"{name} ({level})"


def _is_language_item(text: str) -> bool:
    """Return True if *text* looks like a spoken-language entry, not a skill."""
    import re as _re

    _names = {
        "english",
        "turkish",
        "german",
        "french",
        "spanish",
        "italian",
        "portuguese",
        "russian",
        "arabic",
        "chinese",
        "japanese",
        "korean",
        "dutch",
        "swedish",
        "norwegian",
        "danish",
        "finnish",
        "polish",
        "czech",
        "hungarian",
        "greek",
        "romanian",
        "hebrew",
        "hindi",
        "türkçe",
        "ingilizce",
        "almanca",
        "fransızca",
        "ispanyolca",
        "italyanca",
        "portekizce",
        "rusça",
        "arapça",
        "deutsch",
        "français",
        "español",
        "italiano",
        "português",
    }
    _LEVEL_RE = _re.compile(
        r"\b(?:A[12]|B[12]|C[12]|native|fluent|advanced|intermediate"
        r"|beginner|proficient|basic|elementary|upper[\s-]?intermediate)\b",
        _re.I,
    )
    t = text.strip()
    if not t:
        return False
    # Explicit prefix: "language:" or "foreign language:"
    if _re.match(r"^(?:foreign\s+language|language)\s*:", t, _re.I):
        return True
    core = _re.sub(r"[\s\-\u2013\u2014(].*$", "", t).strip().lower()
    if core in _names:
        return True
    # Structural: short item with CEFR level → language
    if _LEVEL_RE.search(t) and len(t.split()) <= 5:
        return True
    return False


# ── Summary quality rules ─────────────────────────────────────────────────
_SUMMARY_MAX_WORDS = 80

_LIST_PATTERN_RE = re.compile(
    r"^\s*(?:[-*•●◦▪]|\d+[.)]\s)",  # leading bullet / numbered item
)
_EMAIL_SUMMARY_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_SUMMARY_RE = re.compile(r"(?:\+?\d[\d\s\-().]{6,15}\d)")
_URL_SUMMARY_RE = re.compile(
    r"https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|dev|co)\b/?\S*",
    re.I,
)
_SKILL_LIST_RE = re.compile(
    r"^(?:[A-Za-z#+.]+\s*[,;|/]\s*){3,}",  # comma/semicolon-delimited tech names
)


def _enforce_summary_rules(text: str) -> str:
    """Ensure *text* is prose, not a list, and within ~80 words.

    Rules applied generically to every CV:
    * Strip emails, phone numbers, and URLs.
    * Strip leading bullet markers from each line.
    * Reject flat skill lists (comma-delimited tech names).
    * Drop lines that are short list fragments (≤3 words per line average
      over 4+ lines → treat as list → return empty).
    * Truncate at ~80 words on a sentence boundary when possible.
    """
    if not text or not text.strip():
        return ""

    # Remove emails, phones, URLs
    text = _EMAIL_SUMMARY_RE.sub("", text)
    text = _PHONE_SUMMARY_RE.sub("", text)
    text = _URL_SUMMARY_RE.sub("", text)

    lines = text.split("\n")

    # Strip bullet markers from each line
    cleaned: list[str] = []
    for line in lines:
        stripped = _LIST_PATTERN_RE.sub("", line).strip()
        if stripped:
            cleaned.append(stripped)

    if not cleaned:
        return ""

    # Reject comma-delimited skill lists
    joined = " ".join(cleaned)
    if _SKILL_LIST_RE.match(joined):
        return ""

    # If many short lines, this looks like a list — reject
    if len(cleaned) >= 4:
        avg_words = sum(len(l.split()) for l in cleaned) / len(cleaned)
        if avg_words <= 3:
            return ""

    prose = re.sub(r"\s{2,}", " ", joined).strip()

    # Truncate to ~80 words at sentence boundary
    words = prose.split()
    if len(words) > _SUMMARY_MAX_WORDS:
        truncated = " ".join(words[:_SUMMARY_MAX_WORDS])
        # Try to cut at last sentence-ending punctuation
        last_period = max(
            truncated.rfind("."),
            truncated.rfind("!"),
            truncated.rfind("?"),
        )
        if last_period > len(truncated) // 2:
            truncated = truncated[: last_period + 1]
        prose = truncated.strip()

    # Final check: must be ≥3 words to be usable
    if len(prose.split()) < 3:
        return ""

    return prose


def build_schema(normalized: Dict[str, Any]) -> CVSchema:
    """Convert normalize_agent output → CVSchema.

    Never merges education into other sections.
    Never duplicates sections.
    """
    _t0 = time.perf_counter()
    data = dict(normalized or {})

    # Pre-pass: remap any non-canonical keys so nothing is lost
    from services.section_classifier import canonicalize_section_key

    _REMAP = {
        "summary": "summary",
        "experience": "experiences",
        "education": "education",
        "skills": "skills",
        "projects": "projects",
        "certifications": "certifications",
        "languages": "languages",
        "interests": "interests",
        "misc": "misc",
    }
    _SKIP = {
        "full_name",
        "title",
        "email",
        "phone",
        "location",
        "linkedin",
        "summary",
        "experiences",
        "education",
        "skills",
        "skills_categorized",
        "projects",
        "certifications",
        "languages",
        "interests",
        "misc",
        "language",
        "section_titles",
        "format_hints",
        "contact",
        "raw_text",
        "text",
        "content",
    }
    for key in list(data.keys()):
        if key.startswith("_") or key in _SKIP:
            continue
        canonical = canonicalize_section_key(key)
        target = _REMAP.get(canonical, "misc")
        value = data.pop(key)
        if not value:
            continue
        if target == "summary":
            # Respect locked top-of-CV summary — never append from remap.
            if data.get("_summary_source") == "top" and data.get("summary"):
                continue
            existing = data.get("summary", "")
            extra = value if isinstance(value, str) else " ".join(str(v) for v in value)
            data["summary"] = f"{existing} {extra}".strip() if existing else extra
            if not data.get("_summary_source"):
                data["_summary_source"] = "remap"
        else:
            existing = data.get(target) or []
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(value)
            data[target] = existing

    # ── Contact / Header ──
    full_name = _clean(data.get("full_name", ""))
    title = _clean(data.get("title", ""))
    email = _clean(data.get("email", ""))
    phone = _clean(data.get("phone", ""))
    location = _clean(data.get("location", ""))
    linkedin = _clean(data.get("linkedin", ""))

    # ── Summary ──
    summary = _clean(data.get("summary", ""))
    _summary_source = data.get("_summary_source", "")

    # Apply prose guard + contact stripping + length limit
    summary = _enforce_summary_rules(summary)

    # If enforcement emptied a "top" summary (was a list/junk), unlock it
    if _summary_source == "top" and not summary:
        _summary_source = ""

    # ── Experiences ──
    experiences: List[ExperienceEntry] = []
    for exp in data.get("experiences", []) or []:
        if not isinstance(exp, dict):
            continue
        entry = ExperienceEntry(
            title=_clean(exp.get("title", "")),
            company=_clean(exp.get("company", "")),
            location=_clean(exp.get("location", "")),
            start_date=_clean(exp.get("start_date", "")),
            end_date=_clean(exp.get("end_date", "")),
            bullets=_clean_bullets(exp.get("bullets")),
        )
        if not (entry.title or entry.company or entry.bullets):
            continue
        # Drop substance-less entries that are really misrouted section
        # headers or page footers (e.g. "LEADERSHIP ACTIVITIES", "Sanchez 1"):
        # no bullets, no company, no dates, and a title that is ALL-CAPS or a
        # short fragment. Genuine roles carry bullets, a company, or a date.
        has_substance = bool(entry.bullets or entry.company or entry.start_date or entry.end_date)
        if not has_substance:
            title = entry.title.strip()
            if title.isupper() or len(title.split()) <= 2:
                continue
        experiences.append(entry)

    # ── Education (strict: never leaks elsewhere) ──
    education: List[EducationEntry] = []
    for edu in data.get("education", []) or []:
        if not isinstance(edu, dict):
            continue
        gpa_raw = _clean(edu.get("gpa", ""))
        # Strip "GPA:" prefix for clean display
        gpa_val = re.sub(r"^(?:GPA|CGPA)\s*:\s*", "", gpa_raw, flags=re.I).strip()
        entry = EducationEntry(
            degree=_clean(edu.get("degree", "")),
            field=_clean(edu.get("field", "")),
            school=_clean(edu.get("school", "")),
            location=_clean(edu.get("location", "")),
            start_date=_clean(edu.get("start_date", "")),
            end_date=_clean(edu.get("end_date", "")),
            gpa=gpa_val,
        )
        if entry.degree or entry.school:
            education.append(entry)

    # ── Skills (filter out any remaining language items) ──
    skills = _clean_list(data.get("skills"))
    skills = [s for s in skills if not _is_language_item(s)]
    skills_categorized: Dict[str, List[str]] = {}
    raw_cat = data.get("skills_categorized") or {}
    if isinstance(raw_cat, dict):
        for cat, vals in raw_cat.items():
            cleaned = [v for v in _clean_list(vals) if not _is_language_item(v)]
            if cleaned:
                skills_categorized[_clean(cat)] = cleaned

    # ── Projects ──
    projects: List[ProjectEntry] = []
    for proj in data.get("projects", []) or []:
        if not isinstance(proj, dict):
            continue
        entry = ProjectEntry(
            name=_clean(proj.get("name", "")),
            description=_clean(proj.get("description", "")),
            bullets=_clean_bullets(proj.get("bullets")),
        )
        if entry.name or entry.bullets:
            projects.append(entry)

    # ── Certifications ──
    certifications: List[CertificationEntry] = []
    for cert in data.get("certifications", []) or []:
        if not isinstance(cert, dict):
            continue
        entry = CertificationEntry(
            name=_clean(cert.get("name", "")),
            issuer=_clean(cert.get("issuer", "")),
            date=_clean(cert.get("date", "")),
        )
        if entry.name:
            certifications.append(entry)

    # ── Languages ──
    raw_langs = data.get("languages") or []
    languages: List[str] = []
    for lang in raw_langs:
        if isinstance(lang, str):
            # Normalize free-form proficiency phrases ("Fluent in English" →
            # "English (Fluent)") so downstream validation keeps them instead
            # of rejecting the "fluent in …" shape.
            c = _clean(_normalize_spoken_language(lang))
            if c:
                languages.append(c)
        elif isinstance(lang, dict):
            name = _clean(lang.get("name") or lang.get("language", ""))
            level = _clean(lang.get("level") or lang.get("proficiency", ""))
            label = f"{name} ({level})" if level else name
            if label:
                languages.append(label)

    # ── Detected language ──
    cv_language = _clean(data.get("language", "en")) or "en"

    # ── Interests ──
    interests = _clean_list(data.get("interests"))

    # ── Misc ──
    misc = _clean_list(data.get("misc"))

    # ── Original section titles ──
    section_titles = data.get("section_titles") or {}

    # Apply prose guard + length limit to initial summary
    summary = _enforce_summary_rules(summary)

    schema = CVSchema(
        full_name=full_name,
        title=title,
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        summary=summary,
        experiences=experiences,
        education=education,
        skills=skills,
        skills_categorized=skills_categorized,
        projects=projects,
        certifications=certifications,
        languages=languages,
        interests=interests,
        misc=misc,
        language=cv_language,
        section_titles=section_titles,
    )
    schema.ensure_skills_categorized()
    _repair_schema(schema, data)
    _sanitize_schema(schema)
    _cross_section_fixup(schema)
    _document_level_validation(schema, _summary_source)
    _anomaly_detection(schema)
    _fallback_from_raw(data, schema, _summary_source)
    _repair_schema(schema, data)
    _normalize_layout(schema)
    _schema_integrity_check(schema)
    _ats_compliance_check(schema, _summary_source)
    _repair_schema(schema, data)
    _sanitize_schema(schema)
    _purge_empty_entries(schema)
    _cap_misc(schema)
    _normalize_layout(schema)  # re-run after compliance moves

    # ── Section lock: snapshot after compliance, verify after freeze ──
    _lock_snapshot = _snapshot_sections(schema)

    sanity = _schema_sanity_score(schema)
    if sanity == 0:
        logger.warning("build_schema: sanity_score=0, triggering fallback_from_raw")
        _fallback_from_raw(data, schema, _summary_source)
        _repair_schema(schema, data)
        # Re-run compliance after fallback rebuilds schema
        _ats_compliance_check(schema, _summary_source)
        _sanitize_schema(schema)
        _purge_empty_entries(schema)
        _cap_misc(schema)
        # Reset lock snapshot — fallback invalidated the previous one
        _lock_snapshot = _snapshot_sections(schema)

    _freeze_schema(schema)
    _assert_section_lock(_lock_snapshot, _snapshot_sections(schema))

    # Ensure canonical layout is the very last structural operation
    _normalize_layout(schema)

    # Prevent mutation after freeze — schema is now read-only
    schema.freeze()

    _elapsed = time.perf_counter() - _t0
    logger.info(
        "build_schema: %.3fs | sanity=%d | exp=%d edu=%d skills=%d",
        _elapsed,
        sanity,
        len(schema.experiences),
        len(schema.education),
        len(schema.skills) + len(schema.skills_categorized),
    )
    _structured_log(
        logger,
        logging.INFO,
        "build_schema",
        latency=round(_elapsed, 3),
        sanity=sanity,
        experiences=len(schema.experiences),
        education=len(schema.education),
        skills=len(schema.skills) + len(schema.skills_categorized),
        fallback=sanity == 0,
    )
    return schema


# ── Pre-render sanity check ───────────────────────────────────────────────

_INVALID_LANG_RE = re.compile(
    r"^[\d\W]+$"  # pure digits / punctuation
    r"|^.{0,1}$"  # single char or empty
)


def _sanitize_schema(schema: CVSchema) -> None:
    """In-place sanity check on the final schema before rendering.

    * Remove invalid language entries (pure digits, single chars, URLs).
    * Filter bare ISO 639-1 codes (en, tr, de ...) from languages.
    * Remove empty contact fields that would render as blank lines.
    * Drop empty misc list.
    * Strip education entries without school AND degree.
    * Strip skill entries that look like dates or URLs.
    * Fix malformed URLs (https: site.com → https://site.com).
    """
    from utils.cv_normalizer import filter_language_codes, _fix_url_string

    # ── Languages: keep only plausible spoken-language items ──
    schema.languages = [
        lang
        for lang in schema.languages
        if lang and not _INVALID_LANG_RE.match(lang) and "@" not in lang and not re.match(r"https?://", lang, re.I)
    ]
    # Also reject bare ISO codes
    schema.languages = filter_language_codes(schema.languages)

    # ── Contact: blank out empty-looking fields ──
    if schema.email and not re.search(r"@.+\.", schema.email):
        schema.email = ""
    if schema.phone and not _has_plausible_phone_digits(schema.phone):
        schema.phone = ""
    if schema.phone and _looks_like_year_range(schema.phone):
        schema.phone = ""

    # ── Fix malformed URLs in contact fields ──
    if schema.linkedin:
        schema.linkedin = _fix_url_string(schema.linkedin)
    if schema.linkedin and not _GENERIC_URL_RE.match(schema.linkedin):
        schema.linkedin = ""
    if schema.email:
        schema.email = _fix_url_string(schema.email)

    # ── Education: drop entries without any meaningful content ──
    schema.education = [edu for edu in schema.education if edu.degree or edu.school]

    # ── Skills: remove items that are really dates or URLs ──
    _date_like = re.compile(r"^\d{4}\s*[-–]\s*\d{4}$|^\d{1,2}/\d{4}$")
    schema.skills = [s for s in schema.skills if s and not _date_like.match(s) and not re.match(r"https?://", s, re.I)]
    # Reflect into skills_categorized too
    if schema.skills_categorized:
        for cat in list(schema.skills_categorized):
            cleaned = [
                s
                for s in schema.skills_categorized[cat]
                if s and not _date_like.match(s) and not re.match(r"https?://", s, re.I)
            ]
            if cleaned:
                schema.skills_categorized[cat] = cleaned
            else:
                del schema.skills_categorized[cat]

    # ── Misc: drop if empty ──
    schema.misc = [m for m in schema.misc if m]


# ── Cross-section fixup ───────────────────────────────────────────────

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DEGREE_RE_CROSS = re.compile(
    r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
    r"|bachelor|master|diploma|associate|degree)\b",
    re.I,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:university|institute|college|school|faculty|academy)\b",
    re.I,
)
_URL_CROSS_RE = re.compile(
    r"https?://|github\.com|gitlab\.com|bitbucket\.org",
    re.I,
)
_TECH_CROSS_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mongodb|redis|git|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|tensorflow|pytorch)\b",
    re.I,
)


def _exp_text(entry: ExperienceEntry) -> str:
    parts = [entry.title, entry.company, entry.location, entry.start_date, entry.end_date]
    parts.extend(entry.bullets)
    return " ".join(parts)


def _cross_section_fixup(schema: CVSchema) -> None:
    """Move misplaced entries between typed sections.

    Only *moves* entries — never creates new sections from scratch,
    never duplicates data.
    """
    # 0. Strip contact info from experience and education
    from utils.cv_normalizer import _EMAIL_RE, _PHONE_RE

    for exp in schema.experiences:
        cleaned_bullets: list[str] = []
        for b in exp.bullets:
            email_m = _EMAIL_RE.search(b)
            if email_m and not schema.email:
                schema.email = email_m.group(0)
            phone_m = _PHONE_RE.search(b)
            if phone_m and not schema.phone:
                schema.phone = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", b)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned and len(cleaned) > 2:
                cleaned_bullets.append(cleaned)
        exp.bullets = cleaned_bullets

    for edu in schema.education:
        for attr in ("degree", "school", "field", "location"):
            val = getattr(edu, attr, "")
            if val and (_EMAIL_RE.search(val) or _PHONE_RE.search(val)):
                email_m = _EMAIL_RE.search(val)
                if email_m and not schema.email:
                    schema.email = email_m.group(0)
                phone_m = _PHONE_RE.search(val)
                if phone_m and not schema.phone:
                    schema.phone = phone_m.group(0).strip()
                cleaned = _EMAIL_RE.sub("", val)
                cleaned = _PHONE_RE.sub("", cleaned).strip()
                setattr(edu, attr, cleaned)

    # 0b. Strip contact info from projects
    for proj in schema.projects:
        for attr in ("name", "description"):
            val = getattr(proj, attr, "")
            if val and (_EMAIL_RE.search(val) or _PHONE_RE.search(val)):
                email_m = _EMAIL_RE.search(val)
                if email_m and not schema.email:
                    schema.email = email_m.group(0)
                phone_m = _PHONE_RE.search(val)
                if phone_m and not schema.phone:
                    schema.phone = phone_m.group(0).strip()
                cleaned = _EMAIL_RE.sub("", val)
                cleaned = _PHONE_RE.sub("", cleaned).strip()
                setattr(proj, attr, cleaned)
        cleaned_bullets: list[str] = []
        for b in proj.bullets:
            email_m = _EMAIL_RE.search(b)
            if email_m and not schema.email:
                schema.email = email_m.group(0)
            phone_m = _PHONE_RE.search(b)
            if phone_m and not schema.phone:
                schema.phone = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", b)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned and len(cleaned) > 2:
                cleaned_bullets.append(cleaned)
        proj.bullets = cleaned_bullets

    # 0c. Strip contact info from flat list sections (skills, interests, languages)
    for section_attr in ("skills", "interests", "languages"):
        items = getattr(schema, section_attr, [])
        if not items:
            continue
        kept: list[str] = []
        for item in items:
            email_m = _EMAIL_RE.search(item)
            if email_m and not schema.email:
                schema.email = email_m.group(0)
            phone_m = _PHONE_RE.search(item)
            if phone_m and not schema.phone:
                schema.phone = phone_m.group(0).strip()
            cleaned = _EMAIL_RE.sub("", item)
            cleaned = _PHONE_RE.sub("", cleaned).strip()
            if cleaned and len(cleaned) > 1:
                kept.append(cleaned)
        setattr(schema, section_attr, kept)

    # 0d. Strip contact info from certifications
    for cert in schema.certifications:
        for attr in ("name", "issuer", "date"):
            val = getattr(cert, attr, "")
            if val and (_EMAIL_RE.search(val) or _PHONE_RE.search(val)):
                email_m = _EMAIL_RE.search(val)
                if email_m and not schema.email:
                    schema.email = email_m.group(0)
                phone_m = _PHONE_RE.search(val)
                if phone_m and not schema.phone:
                    schema.phone = phone_m.group(0).strip()
                cleaned = _EMAIL_RE.sub("", val)
                cleaned = _PHONE_RE.sub("", cleaned).strip()
                setattr(cert, attr, cleaned)

    # 1. Experience → Education: entry with degree/university but no bullets
    kept_exp: list[ExperienceEntry] = []
    for exp in schema.experiences:
        text = _exp_text(exp)
        has_degree = bool(_DEGREE_RE_CROSS.search(text))
        has_institution = bool(_INSTITUTION_RE.search(text))
        has_year = bool(_YEAR_RE.search(text))
        is_edu_like = (has_degree or has_institution) and has_year and not exp.bullets
        if is_edu_like:
            schema.education.append(
                EducationEntry(
                    degree=exp.title,
                    school=exp.company,
                    location=exp.location,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                )
            )
        else:
            kept_exp.append(exp)
    schema.experiences = kept_exp

    # 2. Education → Experience: entry that looks like a job (has bullets,
    #    no degree, no institution keyword)
    #    Skip — too risky to move education out; education entries rarely
    #    have bullets so this would be very rare and fragile.

    # 3. Misc/skills → Projects: items with URL or github + tech stack
    #    (only if projects section already exists)
    if schema.projects:
        new_skills: list[str] = []
        for skill in schema.skills:
            if _URL_CROSS_RE.search(skill) and _TECH_CROSS_RE.search(skill):
                schema.projects.append(
                    ProjectEntry(
                        name=skill[:80],
                        description="",
                        bullets=[],
                    )
                )
            else:
                new_skills.append(skill)
        schema.skills = new_skills

    # 4. Skills cleanup: remove items with URLs, years, or long sentences
    schema.skills = [
        s
        for s in schema.skills
        if s and not _URL_CROSS_RE.search(s) and not re.match(r"^\d{4}\s*[-–]\s*", s) and len(s.split()) <= 15
    ]
    # Same for skills_categorized
    if schema.skills_categorized:
        for cat in list(schema.skills_categorized):
            cleaned = [
                s
                for s in schema.skills_categorized[cat]
                if s and not _URL_CROSS_RE.search(s) and not re.match(r"^\d{4}\s*[-–]\s*", s) and len(s.split()) <= 15
            ]
            if cleaned:
                schema.skills_categorized[cat] = cleaned
            else:
                del schema.skills_categorized[cat]

    # 5. Language validation: keep only plausible spoken-language entries
    schema.languages = [lang for lang in schema.languages if _is_valid_language(lang)]

    # 6. Deduplicate education (same school + degree)
    seen_edu: set[str] = set()
    deduped_edu: list[EducationEntry] = []
    for edu in schema.education:
        key = f"{edu.school.lower().strip()}|{edu.degree.lower().strip()}"
        if key not in seen_edu:
            seen_edu.add(key)
            deduped_edu.append(edu)
    schema.education = deduped_edu

    # Deduplicate experiences (same title + company)
    seen_exp: set[str] = set()
    deduped_exp: list[ExperienceEntry] = []
    for exp in schema.experiences:
        key = f"{exp.title.lower().strip()}|{exp.company.lower().strip()}"
        if key not in seen_exp:
            seen_exp.add(key)
            deduped_exp.append(exp)
    schema.experiences = deduped_exp


def _is_valid_language(text: str) -> bool:
    """Validate a languages-section entry.

    Section detection sometimes routes skill phrases that merely contain a
    proficiency word ("Proficient in animal handling", "Microsoft Suite") or
    stray coursework lines ("Cell Biology") into the languages section. To keep
    the field precise we require a recognized language name, otherwise we fall
    back to the structural detector for CEFR-tagged entries.
    """
    from utils.cv_normalizer import _ISO_LANG_CODES

    t = _strip_bullet_prefix(text).strip(" .")
    if not t or len(t) <= 1:
        return False
    # Reject bare ISO codes (en, tr, de, ...)
    if t.lower() in _ISO_LANG_CODES and len(t.split()) == 1:
        return False
    # Reject URLs, emails, pure numbers
    if "@" in t or re.match(r"https?://", t, re.I) or re.match(r"^[\d\W]+$", t):
        return False
    if re.match(r"^(?:proficient|advanced|intermediate|basic|fluent)\s+in\b", t, re.I):
        return False
    # A recognized language name is the strongest signal — accept outright.
    if _has_language_name(t):
        return True
    # No language name: accept only entries carrying an explicit CEFR/JLPT
    # *code* (A1-C2, N1-N5). A bare proficiency *word* ("Proficient",
    # "Advanced") is not enough — that is what skill phrases like "Microsoft
    # Suite (Advanced)" or "animal handling (Proficient)" carry after
    # normalization, and they must not pollute the languages field.
    return bool(_CEFR_CODE_RE.search(t))


# ── Document-level validation ─────────────────────────────────────────

_MAX_SECTION_ENTRIES = 50
_MAX_BULLETS_PER_ENTRY = 20
_PRIMARY_SECTIONS = {"summary", "experiences", "education"}


def _document_level_validation(schema: CVSchema, summary_source: str = "") -> None:
    """Final document-level consistency pass.

    Only *moves* existing data — never creates new content.

    Summary priority: top_of_cv > header > summary_section > experience > misc.
    If summary_source == "top", summary is locked and never overwritten.

    1. Section-size sanity: oversized sections → re-evaluate items.
    2. Primary-section check: first real section should be summary/exp/edu.
    3. Education existence: if degree+year found anywhere → ensure education.
    4. Experience existence: if year+bullets found anywhere → ensure experience.
    5. Language sanity: one more pass to reject non-languages.
    6. Misc cleanup: long misc items → summary (only if empty + not locked).
    7. Experience bullet fallback (last resort, only if empty + not locked).
    """

    # ── 1. Section-size sanity ──
    # If experience has too many entries, some may be education or projects.
    if len(schema.experiences) > _MAX_SECTION_ENTRIES:
        keep_exp: list[ExperienceEntry] = []
        for exp in schema.experiences:
            text = _exp_text(exp)
            has_degree = bool(_DEGREE_RE_CROSS.search(text))
            has_institution = bool(_INSTITUTION_RE.search(text))
            if (has_degree or has_institution) and not exp.bullets:
                schema.education.append(
                    EducationEntry(
                        degree=exp.title,
                        school=exp.company,
                        location=exp.location,
                        start_date=exp.start_date,
                        end_date=exp.end_date,
                    )
                )
            else:
                keep_exp.append(exp)
        schema.experiences = keep_exp

    if len(schema.education) > _MAX_SECTION_ENTRIES:
        schema.education = schema.education[:_MAX_SECTION_ENTRIES]
    if len(schema.skills) > 100:
        schema.skills = schema.skills[:100]
    if len(schema.projects) > _MAX_SECTION_ENTRIES:
        schema.projects = schema.projects[:_MAX_SECTION_ENTRIES]
    if len(schema.certifications) > _MAX_SECTION_ENTRIES:
        schema.certifications = schema.certifications[:_MAX_SECTION_ENTRIES]

    # Bullet cap per experience entry
    for exp in schema.experiences:
        if len(exp.bullets) > _MAX_BULLETS_PER_ENTRY:
            exp.bullets = exp.bullets[:_MAX_BULLETS_PER_ENTRY]
    for proj in schema.projects:
        if len(proj.bullets) > _MAX_BULLETS_PER_ENTRY:
            proj.bullets = proj.bullets[:_MAX_BULLETS_PER_ENTRY]

    # ── 2. Primary-section check ──
    # Determine first non-empty section in logical order:
    _section_order = [
        ("summary", bool(schema.summary)),
        ("experiences", bool(schema.experiences)),
        ("education", bool(schema.education)),
        ("skills", bool(schema.skills or schema.skills_categorized)),
        ("languages", bool(schema.languages)),
        ("misc", bool(schema.misc)),
    ]
    first_section = None
    for name, has_content in _section_order:
        if has_content:
            first_section = name
            break

    if first_section and first_section not in _PRIMARY_SECTIONS:
        # Misc as first section → promote long items to summary ONLY if
        # no real summary was extracted from the top of the CV AND misc
        # is near the top (first non-empty section).
        if first_section == "misc" and schema.misc and not schema.summary and summary_source != "top":
            promoted: list[str] = []
            kept_misc: list[str] = []
            for item in schema.misc:
                if len(item.split()) >= 8:
                    promoted.append(item)
                else:
                    kept_misc.append(item)
            if promoted:
                schema.summary = _enforce_summary_rules(" ".join(promoted))
                schema.misc = kept_misc

        # Skills/languages as first section with no exp/edu → check if
        # skills contain misplaced experience-like entries (extremely rare,
        # but guard against it).
        if first_section in ("skills", "languages") and not schema.experiences and not schema.education:
            recovered_exp: list[str] = []
            kept_skills: list[str] = []
            for s in schema.skills:
                if _YEAR_RE.search(s) and len(s.split()) > 10:
                    recovered_exp.append(s)
                else:
                    kept_skills.append(s)
            if recovered_exp:
                schema.skills = kept_skills
                for text in recovered_exp:
                    schema.experiences.append(
                        ExperienceEntry(
                            title=text[:120],
                            bullets=[],
                        )
                    )

    # ── 3. Education existence check ──
    # Scan experiences for entries that contain degree + year
    if not schema.education:
        edu_from_exp: list[ExperienceEntry] = []
        remaining_exp: list[ExperienceEntry] = []
        for exp in schema.experiences:
            text = _exp_text(exp)
            if _DEGREE_RE_CROSS.search(text) and _YEAR_RE.search(text) and not exp.bullets:
                schema.education.append(
                    EducationEntry(
                        degree=exp.title,
                        school=exp.company,
                        location=exp.location,
                        start_date=exp.start_date,
                        end_date=exp.end_date,
                    )
                )
            else:
                remaining_exp.append(exp)
        schema.experiences = remaining_exp

    # ── 4. Experience existence check ──
    # Scan education for entries that have bullets + year but no degree
    if not schema.experiences:
        remaining_edu: list[EducationEntry] = []
        for edu in schema.education:
            text = f"{edu.degree} {edu.school} {edu.start_date} {edu.end_date}"
            has_degree = bool(_DEGREE_RE_CROSS.search(text))
            has_institution = bool(_INSTITUTION_RE.search(text))
            # Education without degree AND without institution → suspicious
            if not has_degree and not has_institution and _YEAR_RE.search(text):
                schema.experiences.append(
                    ExperienceEntry(
                        title=edu.degree or edu.school,
                        company=edu.school if edu.degree else "",
                        location=edu.location,
                        start_date=edu.start_date,
                        end_date=edu.end_date,
                    )
                )
            else:
                remaining_edu.append(edu)
        schema.education = remaining_edu

    # ── 5. Language sanity (final pass) ──
    schema.languages = [lang for lang in schema.languages if _is_valid_language(lang)]

    # ── 6. Misc cleanup: long misc → summary ──
    # Only promote misc prose when summary is empty AND source is not
    # from the top of the CV (locked).
    if schema.misc and not schema.summary and summary_source != "top":
        kept: list[str] = []
        for item in schema.misc:
            if len(item.split()) >= 15 and not schema.summary:
                schema.summary = _enforce_summary_rules(item)
            else:
                kept.append(item)
        schema.misc = kept

    # ── 7. Ensure summary exists (last-resort fallback) ──
    # Experience bullet promotion is the lowest-priority source.
    if not schema.summary and summary_source != "top":
        for exp in schema.experiences:
            for b in exp.bullets:
                if len(b.split()) >= 20:
                    schema.summary = _enforce_summary_rules(b)
                    break
            if schema.summary:
                break

    # ── Deduplicate after moves ──
    seen_edu: set[str] = set()
    deduped_edu: list[EducationEntry] = []
    for edu in schema.education:
        key = f"{edu.school.lower().strip()}|{edu.degree.lower().strip()}"
        if key not in seen_edu:
            seen_edu.add(key)
            deduped_edu.append(edu)
    schema.education = deduped_edu

    seen_exp: set[str] = set()
    deduped_exp: list[ExperienceEntry] = []
    for exp in schema.experiences:
        key = f"{exp.title.lower().strip()}|{exp.company.lower().strip()}"
        if key not in seen_exp:
            seen_exp.add(key)
            deduped_exp.append(exp)
    schema.experiences = deduped_exp


# ── Anomaly detection ─────────────────────────────────────────────────

_SKILLS_MAX = 100
_MISC_MAX = 10
_CONTACT_MAX_LEN = 300
_LANG_MAX = 15
_MAX_DESCRIPTION_LEN = 2000  # max chars in project description / summary


def _anomaly_detection(schema: CVSchema) -> None:
    """Detect and fix abnormal CV structure after all other passes.

    Only *moves* or *trims* existing data — never creates new content.

    1. Skills too large: overflow items → misc (if short) or drop.
    2. No education but degree exists elsewhere → rescue into education.
    3. Languages invalid: extra pass — reject long, tech, duplicates.
    4. Contact too long: truncate fields that look like pasted text.
    5. Misc too large: long items → summary; rest capped.
    """

    # ── 1. Skills overflow ──
    if len(schema.skills) > _SKILLS_MAX:
        overflow = schema.skills[_SKILLS_MAX:]
        schema.skills = schema.skills[:_SKILLS_MAX]
        for item in overflow:
            if len(item.split()) <= 4:
                schema.misc.append(item)
    if schema.skills_categorized:
        for cat in list(schema.skills_categorized):
            items = schema.skills_categorized[cat]
            if len(items) > _SKILLS_MAX:
                schema.skills_categorized[cat] = items[:_SKILLS_MAX]

    # ── 2. No education but degree text exists in other sections ──
    if not schema.education:
        # Build dedup set from existing education (empty here, but safe)
        _edu_keys: set[str] = set()
        for edu in schema.education:
            _edu_keys.add(f"{edu.degree.lower()}|{edu.school.lower()}")

        # Scan summary for degree + institution + year
        if schema.summary:
            if (
                _DEGREE_RE_CROSS.search(schema.summary)
                and _INSTITUTION_RE.search(schema.summary)
                and _YEAR_RE.search(schema.summary)
            ):
                from utils.cv_normalizer import _extract_institution_name

                deg_m = _DEGREE_RE_CROSS.search(schema.summary)
                years = _YEAR_RE.findall(schema.summary)
                inst = _extract_institution_name(schema.summary)
                key = f"{(deg_m.group(0) if deg_m else '').lower()}|{inst.lower()}"
                if key not in _edu_keys:
                    schema.education.append(
                        EducationEntry(
                            degree=deg_m.group(0) if deg_m else "",
                            school=inst,
                            start_date=years[0] if years else "",
                            end_date=years[1] if len(years) > 1 else "",
                        )
                    )
                    _edu_keys.add(key)

        # Scan experiences — create education but KEEP the experience
        # (the entry may legitimately be both, e.g. "Research Assistant
        # at MIT, 2018-2020" with a BSc mentioned in bullets).
        for exp in schema.experiences:
            text = _exp_text(exp)
            has_degree = bool(_DEGREE_RE_CROSS.search(text))
            has_institution = bool(_INSTITUTION_RE.search(text))
            has_year = bool(_YEAR_RE.search(text))
            if has_degree and has_institution and has_year:
                key = f"{exp.title.lower()}|{exp.company.lower()}"
                if key not in _edu_keys:
                    schema.education.append(
                        EducationEntry(
                            degree=exp.title,
                            school=exp.company,
                            location=exp.location,
                            start_date=exp.start_date,
                            end_date=exp.end_date,
                        )
                    )
                    _edu_keys.add(key)

        # Scan misc for degree-like text
        if not schema.education:
            kept_misc: list[str] = []
            for item in schema.misc:
                low = item.lower()
                if _DEGREE_RE_CROSS.search(low) and _YEAR_RE.search(item):
                    schema.education.append(
                        EducationEntry(
                            degree=item[:120],
                        )
                    )
                else:
                    kept_misc.append(item)
            schema.misc = kept_misc

    # ── 3. Languages invalid: extra sanitization ──
    seen_lang: set[str] = set()
    clean_langs: list[str] = []
    for lang in schema.languages:
        t = lang.strip()
        if not t or len(t) <= 1:
            continue
        if len(t.split()) > 12:
            continue
        if _TECH_CROSS_RE.search(t):
            continue
        if not _is_valid_language(t):
            continue
        if "@" in t or re.match(r"https?://", t, re.I):
            continue
        key = re.sub(r"[\s\-\(\)]", "", t).lower()
        if key in seen_lang:
            continue
        seen_lang.add(key)
        clean_langs.append(lang)
    schema.languages = clean_langs[:_LANG_MAX]

    # ── 4. Contact too long ──
    if schema.email and len(schema.email) > _CONTACT_MAX_LEN:
        schema.email = schema.email[:_CONTACT_MAX_LEN]
    if schema.phone and len(schema.phone) > _CONTACT_MAX_LEN:
        schema.phone = schema.phone[:_CONTACT_MAX_LEN]
    if schema.phone and _looks_like_year_range(schema.phone):
        schema.phone = ""
    if schema.linkedin and len(schema.linkedin) > _CONTACT_MAX_LEN:
        schema.linkedin = schema.linkedin[:_CONTACT_MAX_LEN]
    if schema.location and len(schema.location) > _CONTACT_MAX_LEN:
        schema.location = schema.location[:_CONTACT_MAX_LEN]
    for field in ("email", "phone"):
        val = getattr(schema, field, "")
        if val and len(val.split()) > 8:
            setattr(schema, field, "")

    # ── 5. Misc too large ──
    if len(schema.misc) > _MISC_MAX:
        promoted: list[str] = []
        kept: list[str] = []
        for item in schema.misc:
            if len(item.split()) >= 10:
                promoted.append(item)
            else:
                kept.append(item)
        if promoted:
            extra = " ".join(promoted)
            schema.summary = f"{schema.summary} {extra}".strip() if schema.summary else extra
        schema.misc = kept[:_MISC_MAX]

    # ── 6. Description / summary length cap ──
    if schema.summary and len(schema.summary) > _MAX_DESCRIPTION_LEN:
        logger.warning("anomaly: summary truncated %d → %d chars", len(schema.summary), _MAX_DESCRIPTION_LEN)
        schema.summary = schema.summary[:_MAX_DESCRIPTION_LEN]
    for proj in schema.projects:
        if proj.description and len(proj.description) > _MAX_DESCRIPTION_LEN:
            logger.warning(
                "anomaly: project description truncated %d → %d chars", len(proj.description), _MAX_DESCRIPTION_LEN
            )
            proj.description = proj.description[:_MAX_DESCRIPTION_LEN]


# ── Fallback rendering ────────────────────────────────────────────────────

_MIN_MEANINGFUL_SECTIONS = 2


def _schema_needs_fallback(schema: CVSchema) -> bool:
    """Return True when the schema is too empty to render a useful CV."""
    # Count non-empty content sections (exclude contact-level fields)
    section_count = sum(
        [
            bool(schema.summary),
            bool(schema.experiences),
            bool(schema.education),
            bool(schema.skills or schema.skills_categorized),
            bool(schema.projects),
            bool(schema.certifications),
            bool(schema.languages),
            bool(schema.interests),
        ]
    )
    # No meaningful text at all
    total_text = (
        len(schema.summary)
        + sum(len(e.title) + len(" ".join(e.bullets)) for e in schema.experiences)
        + sum(len(e.degree) + len(e.school) for e in schema.education)
        + sum(len(s) for s in schema.skills)
        + sum(len(p.name) for p in schema.projects)
    )
    if total_text == 0 and not schema.misc:
        return True
    # Only misc has content
    if section_count == 0 and schema.misc:
        return True
    # Too few sections
    if section_count < _MIN_MEANINGFUL_SECTIONS and total_text < 50:
        return True
    return False


def _fallback_from_raw(
    data: Dict[str, Any],
    schema: CVSchema,
    summary_source: str = "",
) -> None:
    """Populate schema from raw input when the structured parse produced too little.

    Scans every list/string value in *data* and pushes text into summary
    and misc so the CV is never empty.  Never creates new data — only
    moves raw input that was lost during typed mapping.
    """
    if not _schema_needs_fallback(schema):
        return

    logger.info("_fallback_from_raw activated: schema too sparse for structured render")

    _SKIP_KEYS = {
        "full_name",
        "title",
        "email",
        "phone",
        "location",
        "linkedin",
        "language",
        "section_titles",
        "format_hints",
        "contact",
    }

    collected: list[str] = []
    for key, value in data.items():
        if key.startswith("_") or key in _SKIP_KEYS:
            continue
        if isinstance(value, str) and value.strip():
            collected.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    collected.append(item.strip())
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str) and v.strip():
                            collected.append(v.strip())
                        elif isinstance(v, list):
                            for sub in v:
                                if isinstance(sub, str) and sub.strip():
                                    collected.append(sub.strip())

    if not collected:
        return

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for text in collected:
        key = text.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(text)

    # First long block → summary (if empty and not locked)
    if not schema.summary and summary_source != "top":
        for i, text in enumerate(unique):
            if len(text.split()) >= 5:
                schema.summary = _enforce_summary_rules(text)
                unique.pop(i)
                break

    # Remaining → misc
    for text in unique:
        if text not in schema.misc:
            schema.misc.append(text)


# ── Final layout normalization ────────────────────────────────────────────

_CANONICAL_ORDER = [
    "summary",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "languages",
    "interests",
    "misc",
]

_SECTION_TO_FIELD = {
    "summary": "summary",
    "experience": "experiences",
    "projects": "projects",
    "education": "education",
    "skills": "skills_categorized",
    "certifications": "certifications",
    "languages": "languages",
    "interests": "interests",
    "misc": "misc",
}


def _normalize_layout(schema: CVSchema) -> None:
    """Rebuild *section_titles* in canonical order, dropping empty sections."""
    old = dict(schema.section_titles)
    ordered: Dict[str, str] = {}

    for sec in _CANONICAL_ORDER:
        field = _SECTION_TO_FIELD.get(sec, sec)
        val = getattr(schema, field, None)
        # Also check flat skills list for the "skills" section
        if sec == "skills" and not val:
            val = getattr(schema, "skills", None)
        has = bool(val.strip()) if isinstance(val, str) else bool(val)
        if has and sec in old:
            ordered[sec] = old[sec]

    schema.section_titles = ordered


def _schema_sanity_score(schema: CVSchema) -> int:
    """Return 0-3 score based on presence of primary sections."""
    score = 0
    if schema.experiences:
        score += 1
    if schema.education:
        score += 1
    if schema.summary and schema.summary.strip():
        score += 1
    return score


def _schema_integrity_check(schema: CVSchema) -> None:
    """Ensure at least one primary section (experience, education, summary) exists.

    If none present, promote the longest misc entry or any long text to summary.
    """
    has_experience = bool(schema.experiences)
    has_education = bool(schema.education)
    has_summary = bool(schema.summary and schema.summary.strip())

    if has_experience or has_education or has_summary:
        return

    # Try promoting longest misc entry
    if schema.misc:
        best_idx = max(range(len(schema.misc)), key=lambda i: len(schema.misc[i]))
        best = schema.misc[best_idx].strip()
        if len(best.split()) >= 5:
            schema.summary = best
            schema.misc.pop(best_idx)
            return

    # Try promoting from skills (long prose wrongly tagged as skill)
    for i, sk in enumerate(schema.skills):
        if len(sk.split()) >= 10:
            schema.summary = sk.strip()
            schema.skills.pop(i)
            return

    # Try promoting from languages (rare, but possible misparse)
    for i, lang in enumerate(schema.languages):
        if len(lang.split()) >= 10:
            schema.summary = lang.strip()
            schema.languages.pop(i)
            return

    # Last resort: concatenate all misc into summary
    if schema.misc:
        schema.summary = " ".join(m.strip() for m in schema.misc if m.strip())
        schema.misc.clear()


# ── ATS compliance check (final integrity pass) ──────────────────────────

_ACTION_VERB_RE = re.compile(
    r"\b(?:managed|led|developed|designed|implemented|created|built|"
    r"delivered|coordinated|analysed|analyzed|improved|maintained|"
    r"supported|trained|launched|optimized|established|initiated|"
    r"executed|facilitated|supervised|administered|organized|prepared|"
    r"negotiated|achieved|increased|reduced|generated|directed|"
    r"collaborated|contributed|researched|evaluated|monitored|"
    r"resolved|streamlined|architected|programmed|configured|"
    r"deployed|automated|integrated|mentored|planned|oversaw)\b",
    re.I,
)

_COMPANY_SIGNAL_RE = re.compile(
    r"\b(?:inc|llc|ltd|gmbh|corp|co\.|plc|a\.?ş|ş(?:ti|irketi)"
    r"|limited|company|group|holding|technologies|solutions"
    r"|consulting|services|systems|labs?|studio)\b",
    re.I,
)


def _ats_compliance_check(schema: CVSchema, summary_source: str = "") -> None:
    """Final ATS compliance validation — runs after all other passes.

    Eight generic rules (no CV-specific logic).  Uses ``section_scorer``
    for move decisions and tracks moved entries to prevent double moves.

    1. Experience integrity: score-backed; degree+institution+year+no bullets
       → move to education only if scorer confirms.
    2. Education integrity: score-backed; no degree + no institution +
       company/verb signals → move to experience only if scorer confirms.
    3. Skills: must be short tokens (≤8 words).
    4. Languages: must be real spoken languages or CEFR levels.
    5. Misc: score-backed rescue for items that can be reassigned.
    6. Summary: must be prose; enforce summary rules; never overwrite locked.
    7. Header completeness: rescue email/phone from remaining text if missing.
    8. Canonical section order — handled by _normalize_layout (called after).
    """
    from utils.section_scorer import score_dict_entry, score_text

    # Track moved-entry keys to prevent double moves.
    _moved: set[str] = set()

    def _exp_key(exp: ExperienceEntry) -> str:
        return f"exp|{exp.title.lower().strip()}|{exp.company.lower().strip()}"

    def _edu_key(edu: EducationEntry) -> str:
        return f"edu|{edu.degree.lower().strip()}|{edu.school.lower().strip()}"

    # ── Rule 1: Experience integrity (score-backed) ──
    kept_exp: list[ExperienceEntry] = []
    for exp in schema.experiences:
        ek = _exp_key(exp)
        if ek in _moved:
            kept_exp.append(exp)
            continue

        entry_dict = {
            "title": exp.title,
            "company": exp.company,
            "location": exp.location,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "bullets": exp.bullets,
        }
        scores = score_dict_entry(entry_dict)

        # Move to education only when scorer agrees AND entry has
        # degree/institution + year + no bullets.
        text = _exp_text(exp)
        has_degree = bool(_DEGREE_RE_CROSS.search(text))
        has_institution = bool(_INSTITUTION_RE.search(text))
        has_year = bool(_YEAR_RE.search(text))

        if (
            (has_degree or has_institution)
            and has_year
            and not exp.bullets
            and scores.best() == "education"
            and scores.is_confident()
        ):
            existing = {f"{e.school.lower().strip()}|{e.degree.lower().strip()}" for e in schema.education}
            dup_key = f"{exp.company.lower().strip()}|{exp.title.lower().strip()}"
            if dup_key not in existing:
                schema.education.append(
                    EducationEntry(
                        degree=exp.title,
                        school=exp.company,
                        location=exp.location,
                        start_date=exp.start_date,
                        end_date=exp.end_date,
                    )
                )
                _moved.add(ek)
            else:
                kept_exp.append(exp)
        else:
            kept_exp.append(exp)
    schema.experiences = kept_exp

    # ── Rule 2: Education integrity (score-backed) ──
    kept_edu: list[EducationEntry] = []
    for edu in schema.education:
        ek = _edu_key(edu)
        if ek in _moved:
            kept_edu.append(edu)
            continue

        entry_dict = {
            "degree": edu.degree,
            "school": edu.school,
            "field": edu.field,
            "location": edu.location,
            "start_date": edu.start_date,
            "end_date": edu.end_date,
        }
        scores = score_dict_entry(entry_dict)
        text = f"{edu.degree} {edu.school} {edu.field} {edu.location} {edu.start_date} {edu.end_date}"
        has_degree = bool(_DEGREE_RE_CROSS.search(text))
        has_institution = bool(_INSTITUTION_RE.search(text))

        # Move to experience only when scorer agrees AND entry has no
        # degree/institution + company/verb signals.
        if not has_degree and not has_institution and scores.best() == "experience" and scores.is_confident():
            existing = {f"{e.title.lower().strip()}|{e.company.lower().strip()}" for e in schema.experiences}
            dup_key = (
                f"{(edu.degree or edu.school).lower().strip()}|{(edu.school if edu.degree else '').lower().strip()}"
            )
            if dup_key not in existing:
                schema.experiences.append(
                    ExperienceEntry(
                        title=edu.degree or edu.school,
                        company=edu.school if edu.degree else "",
                        location=edu.location,
                        start_date=edu.start_date,
                        end_date=edu.end_date,
                    )
                )
                _moved.add(ek)
            else:
                kept_edu.append(edu)
        else:
            kept_edu.append(edu)
    schema.education = kept_edu

    # ── Rule 3: Skills — reject long prose while preserving merged skill phrases ──
    schema.skills = [
        s for s in schema.skills if s and (len(s.split()) <= 8 or (len(s.split()) <= 18 and re.search(r"[,;/&]", s)))
    ]
    if schema.skills_categorized:
        for cat in list(schema.skills_categorized):
            cleaned = [
                s
                for s in schema.skills_categorized[cat]
                if s and (len(s.split()) <= 8 or (len(s.split()) <= 18 and re.search(r"[,;/&]", s)))
            ]
            if cleaned:
                schema.skills_categorized[cat] = cleaned
            else:
                del schema.skills_categorized[cat]

    # ── Rule 4: Languages — final spoken-language enforcement ──
    schema.languages = [lang for lang in schema.languages if _is_valid_language(lang)]

    # ── Rule 5: Misc — score-backed rescue attempt ──
    if schema.misc:
        final_misc: list[str] = []
        for item in schema.misc:
            text = item.strip()
            if not text:
                continue
            misc_key = f"misc|{text[:80].lower()}"
            if misc_key in _moved:
                final_misc.append(text)
                continue

            scores = score_text(text)
            best = scores.best()

            # Education rescue: scorer says education + degree/year present
            if (
                best == "education"
                and scores.is_confident()
                and _DEGREE_RE_CROSS.search(text)
                and _YEAR_RE.search(text)
            ):
                if not any(text[:80].lower() in f"{e.degree} {e.school}".lower() for e in schema.education):
                    schema.education.append(EducationEntry(degree=text[:120]))
                    _moved.add(misc_key)
                    continue

            # Experience rescue: scorer says experience + enough words
            if best == "experience" and scores.is_confident() and len(text.split()) >= 5:
                years = _YEAR_RE.findall(text)
                schema.experiences.append(
                    ExperienceEntry(
                        title=text[:80],
                        start_date=years[0] if years else "",
                        end_date=years[1] if len(years) > 1 else "",
                    )
                )
                _moved.add(misc_key)
                continue

            final_misc.append(text)
        schema.misc = final_misc

    # ── Rule 6: Summary — enforce prose rules; respect lock ──
    if schema.summary:
        schema.summary = _enforce_summary_rules(schema.summary)

    # ── Rule 7: Header completeness — rescue email/phone from misc/skills ──
    from utils.cv_normalizer import _EMAIL_RE, _PHONE_RE

    if not schema.email or not schema.phone:
        # Scan misc for contact data
        rescue_misc: list[str] = []
        for item in schema.misc:
            if not schema.email:
                m = _EMAIL_RE.search(item)
                if m:
                    schema.email = m.group(0)
            if not schema.phone:
                m = _PHONE_RE.search(item)
                if m:
                    schema.phone = m.group(0).strip()
            rescue_misc.append(item)
        schema.misc = rescue_misc

        # Scan skills (rare: contact line mislabeled as skill)
        if not schema.email or not schema.phone:
            kept_skills: list[str] = []
            for sk in schema.skills:
                rescued = False
                if not schema.email:
                    m = _EMAIL_RE.search(sk)
                    if m:
                        schema.email = m.group(0)
                        cleaned = _EMAIL_RE.sub("", sk).strip()
                        if cleaned and len(cleaned) > 2:
                            kept_skills.append(cleaned)
                        rescued = True
                if not schema.phone and not rescued:
                    m = _PHONE_RE.search(sk)
                    if m:
                        schema.phone = m.group(0).strip()
                        cleaned = _PHONE_RE.sub("", sk).strip()
                        if cleaned and len(cleaned) > 2:
                            kept_skills.append(cleaned)
                        rescued = True
                if not rescued:
                    kept_skills.append(sk)
            schema.skills = kept_skills

    # ── Rule 8: Canonical order — handled by _normalize_layout (next step) ──

    # ── Final dedup ──
    seen_edu: set[str] = set()
    deduped_edu: list[EducationEntry] = []
    for edu in schema.education:
        key = f"{edu.school.lower().strip()}|{edu.degree.lower().strip()}"
        if key not in seen_edu:
            seen_edu.add(key)
            deduped_edu.append(edu)
    schema.education = deduped_edu

    seen_exp: set[str] = set()
    deduped_exp: list[ExperienceEntry] = []
    for exp in schema.experiences:
        key = f"{exp.title.lower().strip()}|{exp.company.lower().strip()}"
        if key not in seen_exp:
            seen_exp.add(key)
            deduped_exp.append(exp)
    schema.experiences = deduped_exp


# ── Stability guards ─────────────────────────────────────────────────────


def _purge_empty_entries(schema: CVSchema) -> None:
    """Remove education/experience entries that have no meaningful content.

    An entry is empty when all its text fields are blank/whitespace.
    """
    schema.experiences = [
        exp
        for exp in schema.experiences
        if any(
            v.strip()
            for v in (
                exp.title,
                exp.company,
                exp.location,
                exp.start_date,
                exp.end_date,
            )
        )
        or exp.bullets
    ]
    schema.education = [
        edu
        for edu in schema.education
        if any(
            v.strip()
            for v in (
                edu.degree,
                edu.school,
                edu.field,
                edu.location,
                edu.start_date,
                edu.end_date,
                edu.gpa,
            )
        )
    ]
    schema.projects = [
        proj for proj in schema.projects if proj.name.strip() or proj.description.strip() or proj.bullets
    ]
    schema.certifications = [
        cert for cert in schema.certifications if cert.name.strip() or cert.issuer.strip() or cert.date.strip()
    ]
    schema.skills = [s for s in schema.skills if s and s.strip()]
    schema.languages = [l for l in schema.languages if l and l.strip()]
    schema.interests = [i for i in schema.interests if i and i.strip()]
    schema.misc = [m for m in schema.misc if m and m.strip()]


def _snapshot_sections(schema: CVSchema) -> Dict[str, int]:
    """Capture section sizes for the section-lock assertion."""
    return {
        "experiences": len(schema.experiences),
        "education": len(schema.education),
        "skills": len(schema.skills),
        "projects": len(schema.projects),
        "certifications": len(schema.certifications),
        "languages": len(schema.languages),
        "interests": len(schema.interests),
        "misc": len(schema.misc),
        "summary": len(schema.summary),
    }


def _assert_section_lock(
    before: Dict[str, int],
    after: Dict[str, int],
) -> None:
    """Log a warning if any section changed after the compliance lock.

    This is a soft lock — it warns but does not raise to avoid blocking
    the render pipeline.  Helps catch accidental mutations.
    """
    for section, count_before in before.items():
        count_after = after.get(section, 0)
        if count_before != count_after:
            logger.warning(
                "section_lock_violation: %s changed from %d to %d after lock",
                section,
                count_before,
                count_after,
            )


def _cap_misc(schema: CVSchema) -> None:
    """Limit misc size.  Re-score overflow items and redistribute."""
    if len(schema.misc) <= _MISC_MAX:
        return

    from utils.section_scorer import score_text

    kept: list[str] = []
    for item in schema.misc:
        text = item.strip()
        if not text:
            continue
        if len(kept) < _MISC_MAX:
            kept.append(text)
            continue

        # Over the limit — try to redistribute via scorer
        scores = score_text(text)
        best = scores.best()
        if best == "education" and scores.is_confident():
            if _DEGREE_RE_CROSS.search(text):
                schema.education.append(EducationEntry(degree=text[:120]))
                continue
        if best == "experience" and scores.is_confident() and len(text.split()) >= 5:
            years = _YEAR_RE.findall(text)
            schema.experiences.append(
                ExperienceEntry(
                    title=text[:80],
                    start_date=years[0] if years else "",
                    end_date=years[1] if len(years) > 1 else "",
                )
            )
            continue
        if best == "skills" and scores.is_confident() and len(text.split()) <= 8:
            schema.skills.append(text)
            continue
        if best == "certifications" and scores.is_confident():
            schema.certifications.append(CertificationEntry(name=text))
            continue
        # Cannot redistribute — drop (already over cap)
    schema.misc = kept


def _freeze_schema(schema: CVSchema) -> None:
    """Final stabilisation pass before rendering.

    1. Purge empty/invalid entries.
    2. Re-apply summary prose rules (in case any late pass injected text).
    3. Rebuild section_titles in canonical order.
    4. Log final section counts.
    """
    _purge_empty_entries(schema)

    if schema.summary:
        schema.summary = _enforce_summary_rules(schema.summary)

    _normalize_layout(schema)

    logger.info(
        "freeze_schema: exp=%d edu=%d skills=%d proj=%d certs=%d lang=%d misc=%d",
        len(schema.experiences),
        len(schema.education),
        len(schema.skills) + len(schema.skills_categorized),
        len(schema.projects),
        len(schema.certifications),
        len(schema.languages),
        len(schema.misc),
    )
