# -*- coding: utf-8 -*-
"""Extraction Quality Validator — hard-fail rules + scoring.

Validates pipeline output against raw CV text to catch:
- Missing contact info (email, phone, name)
- Garbage skills (emails, grades, dates in skill list)
- Broken language entries ("e n", single chars)
- Summary contamination (project/education content in summary)
- Reversed or corrupted dates
- Education/project field corruption

Returns a quality report with score, issues, and hard-fail flag.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger("app.extraction_validator")


# ── Patterns ──────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"\(?\+?\d[\d()\-\s.]{7,}\d")
_URL_RE = re.compile(r"https?://|linkedin\.com|github\.com", re.I)

# Tokens that should NEVER appear as skills
_SKILL_GARBAGE_PATTERNS = [
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),  # email
    re.compile(r"\(?\+?\d[\d()\-\s.]{7,}\d"),  # phone
    re.compile(r"^\d{1,2}(?:th|st|nd|rd)$", re.I),  # ordinals: 10th, 12th
    re.compile(r"^\d+\.?\d*%$"),  # percentages: 80.34%
    re.compile(r"^\d{4}$"),  # bare years: 2022
    re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$"),  # dates: 13.10.2003
    re.compile(r"^https?://", re.I),  # URLs
    re.compile(r"^www\.", re.I),  # www URLs
    re.compile(r"gmail\.com|hotmail\.com|yahoo\.com", re.I),  # email domains
    re.compile(r"^[a-z]$", re.I),  # single chars
    re.compile(r"^[a-z]\.[a-z]", re.I),  # abbreviations like c.b.s.e
    re.compile(r"^\d+\.?\d*$"),  # bare numbers: 62.2, 3.80
    re.compile(r"^u\.p\.?$", re.I),  # location abbreviations
]

# Known language names (lowercase) — for validation
_VALID_LANGUAGE_NAMES = {
    "english",
    "turkish",
    "french",
    "german",
    "spanish",
    "portuguese",
    "italian",
    "dutch",
    "russian",
    "polish",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
    "czech",
    "hungarian",
    "romanian",
    "arabic",
    "chinese",
    "japanese",
    "korean",
    "hindi",
    "indonesian",
    "vietnamese",
    "thai",
    "greek",
    "hebrew",
    "persian",
    "urdu",
    "bengali",
    "tagalog",
    "malay",
    "swahili",
    "filipino",
    # Turkish names
    "türkçe",
    "ingilizce",
    "fransızca",
    "almanca",
    "ispanyolca",
    "portekizce",
    "italyanca",
    "rusça",
    "arapça",
    "japonca",
    "korece",
    "çince",
    "hintçe",
    "farsça",
}

# Experience/project keywords that should NOT appear in summary
_SUMMARY_CONTAMINATION_KEYWORDS = [
    "windmill",
    "microcontroller",
    "synopsis",
    "marching band",
    "intramural",
    "volleyball",
    "cricket",
    "football",
    "hobbies",
    "father's name",
    "marital status",
    "nationality",
    "declaration",
    "assert you",
    "gold medallist",
    "participated in various",
]


def _extract_emails_from_raw(raw_text: str) -> List[str]:
    return [m.group(0) for m in _EMAIL_RE.finditer(raw_text)]


def _extract_phones_from_raw(raw_text: str) -> List[str]:
    return [m.group(0).strip() for m in _PHONE_RE.finditer(raw_text)]


def _is_garbage_skill(skill: str) -> bool:
    """Return True if the skill token looks like garbage (email, grade, date, etc.)."""
    skill = skill.strip()
    if not skill or len(skill) < 2:
        return True
    for pattern in _SKILL_GARBAGE_PATTERNS:
        if pattern.search(skill):
            return True
    return False


def _is_valid_language_entry(entry: str) -> bool:
    """Return True if the language entry is valid (not broken like 'e n').

    Must have at least one of:
    - Known language name as first word
    - CEFR level (A1-C2)
    - Proficiency word (native, fluent, etc.)
    Rejects: URLs, email fragments, section titles, and random text.
    """
    entry = entry.strip()
    if not entry:
        return False
    # Too short — likely broken
    if len(entry) <= 2:
        return False
    # Reject entries that look like URLs, emails, or section titles
    if re.search(r"https?://|@|\.com|\.io|\.edu", entry, re.I):
        return False
    # Reject entries that look like core section headers or heavy structural text
    # (Kept strictly to global CV standard sections to avoid false positives)
    section_words = {
        "education",
        "experience",
        "skills",
        "projects",
        "summary",
        "profile",
        "objective",
        "blog",
        "website",
        "development",
        "engineer",
        "degree",
        "university",
        "bachelor",
        "master",
    }
    entry_lower = entry.lower()
    entry_words_lower = [w.lower().rstrip(":,;") for w in entry.split()]
    # If any word is a section-header word, it's not a language
    if any(w in section_words for w in entry_words_lower):
        return False
    # Known language name as first word
    first_word = entry_words_lower[0] if entry_words_lower else ""
    if first_word in _VALID_LANGUAGE_NAMES:
        return True
    # Has CEFR level (A1, B2, C1, etc.)
    if re.search(r"\b[ABC][12]\b", entry, re.I):
        return True
    # Has proficiency word
    if re.search(
        r"\b(?:native|fluent|advanced|intermediate|beginner|proficient|basic"
        r"|ana\s*dil|ileri|orta|başlangıç)\b",
        entry,
        re.I,
    ):
        return True
    # Reject everything else — if it doesn't match any positive signal,
    # it's probably not a language entry
    return False


# Symbol/digit and conjunction-led starts that mark a wrapped sentence
# fragment rather than a real role line. (Case-insensitive only for the word
# list — the lowercase-start test is handled separately so IGNORECASE does not
# defeat it.)
_FRAGMENT_SYMBOL_RE = re.compile(r"^[&,;:.\-–—(]|^\(?\d")
_FRAGMENT_WORD_RE = re.compile(
    r"^(?:and|or|such\s+as|with|the|of|for|to|in|by|but|was|were|also)\b",
    re.I,
)
# Leading bullet glyphs (incl. private-use Wingdings/Symbol points) — a real
# role title never starts with one.
_FRAGMENT_BULLET_RE = re.compile(r"^[•●○◦▪■‣⁃∙·▸▹▶▷]")
# Bare structural labels that are section/field headers, not job titles.
_FRAGMENT_LABEL_WORDS = {
    "experience",
    "organization",
    "organisation",
    "department",
    "designation",
    "objective",
    "profile",
    "declaration",
    "summary",
    "skills",
    "references",
    "education",
    "projects",
    "responsibilities",
    "key responsibilities",
    "personal details",
    "company",
}


def _looks_fragmented_title(title: str) -> bool:
    """True if an experience *title* looks like a fragment, not a real role.

    These dominate the experience list when a table or an unusual layout
    (e.g. "ORGANIZATION:/KEY RESPONSIBILITIES:") is mis-split into tiny entries.
    """
    t = (title or "").strip()
    if not t:
        return True
    # Leading bullet glyph (incl. private-use Wingdings/Symbol points).
    if _FRAGMENT_BULLET_RE.match(t) or 0xE000 <= ord(t[0]) <= 0xF8FF:
        return True
    # Starts lowercase → mid-sentence wrap (case-sensitive on purpose).
    if t[0].islower():
        return True
    if _FRAGMENT_SYMBOL_RE.match(t):
        return True
    if _FRAGMENT_WORD_RE.match(t):
        return True
    # Bare structural label / section word used as a title.
    label = re.sub(r"\s*[:\-–—].*$", "", t).strip().lower()
    if label in _FRAGMENT_LABEL_WORDS:
        return True
    # ALL-CAPS short phrase → a section header that leaked in
    # ("KEY RESPONSIBILITIES", "PAST EXPERIENCE", "BUT").
    if t.isupper() and len(t.split()) <= 3:
        return True
    return False


def _check_experience_fragmentation(extracted: dict) -> List[str]:
    """Detect over-split / garbage experience lists from hard layouts.

    Tables and non-standard structures get shredded into many tiny entries
    with fragment titles and few bullets. We flag those so the caller can fall
    back to an LLM re-parse instead of shipping garbage.
    """
    entries = [e for e in extracted.get("experiences", []) or [] if isinstance(e, dict)]
    n = len(entries)
    if n < 4:
        return []

    fragmented = sum(1 for e in entries if _looks_fragmented_title(str(e.get("title", ""))))
    frag_ratio = fragmented / n
    avg_bullets = sum(len(e.get("bullets") or []) for e in entries) / n

    issues: List[str] = []
    # Rule A: fragment-titled entries dominate the list.
    if frag_ratio >= 0.4:
        issues.append(f"experience_fragmented: {fragmented}/{n} fragment-like titles")
    # Rule B: many entries but almost no bullets → over-split table/structure.
    if n >= 8 and avg_bullets < 1.2:
        issues.append(f"experience_oversplit: {n} entries, avg {avg_bullets:.1f} bullets/entry")
    return issues


def _check_summary_contamination(summary: str) -> List[str]:
    """Return list of contamination signals found in summary."""
    if not summary:
        return []
    issues = []
    summary_lower = summary.lower()
    for keyword in _SUMMARY_CONTAMINATION_KEYWORDS:
        if keyword in summary_lower:
            issues.append(f"summary_contains_'{keyword}'")
    return issues


def _check_date_integrity(extracted: dict) -> List[str]:
    """Check for reversed or corrupted dates."""
    issues = []

    # Check experience dates
    for i, exp in enumerate(extracted.get("experiences", [])):
        if not isinstance(exp, dict):
            continue
        start = str(exp.get("start_date", "")).strip()
        end = str(exp.get("end_date", "")).strip()
        if start and end:
            # Check for reversed parentheses or labels in date
            if "(" in end and ")" in start:
                issues.append(f"experience[{i}]_date_parens_reversed")
            if "tarih" in start.lower() or "tarih" in end.lower():
                issues.append(f"experience[{i}]_date_label_leaked")

    # Check education dates
    for i, edu in enumerate(extracted.get("education", [])):
        if not isinstance(edu, dict):
            continue
        start = str(edu.get("start_date", "")).strip()
        end = str(edu.get("end_date", "")).strip()
        if start and end:
            # Try to extract years and check order
            start_years = re.findall(r"\b((?:19|20)\d{2})\b", start)
            end_years = re.findall(r"\b((?:19|20)\d{2})\b", end)
            if start_years and end_years:
                try:
                    if int(start_years[0]) > int(end_years[0]):
                        issues.append(f"education[{i}]_date_reversed")
                except ValueError:
                    pass
    return issues


def validate_extraction(
    raw_text: str,
    extracted: dict,
    *,
    strict: bool = True,
) -> dict:
    """Validate extracted CV data against raw text.

    Args:
        raw_text: Original CV text (from PDF or input)
        extracted: Pipeline output dict (from extract_structured + normalize)
        strict: If True, apply hard-fail rules

    Returns:
        {
            "quality_score": 0-100,
            "issues": [...],
            "hard_fails": [...],
            "needs_llm_fallback": bool,
            "garbage_skills": [...],
            "broken_languages": [...],
        }
    """
    issues: List[str] = []
    hard_fails: List[str] = []
    score = 100  # Start at 100, subtract for problems

    # ── 1. Contact Preservation ──────────────────────────────────────────

    # Email
    raw_emails = _extract_emails_from_raw(raw_text)
    extracted_email = str(extracted.get("email", "")).strip()
    if raw_emails and not extracted_email:
        hard_fails.append(f"email_lost: raw has {raw_emails[0]} but output is empty")
        score -= 15

    # Phone
    raw_phones = _extract_phones_from_raw(raw_text)
    extracted_phone = str(extracted.get("phone", "")).strip()
    if raw_phones and not extracted_phone:
        hard_fails.append(f"phone_lost: raw has phone but output is empty")
        score -= 10

    # Name
    extracted_name = str(extracted.get("full_name", "")).strip()
    if not extracted_name:
        hard_fails.append("name_missing")
        score -= 15
    else:
        # Check if name looks like a degree or job title
        name_lower = extracted_name.lower()
        title_words = {
            "engineer",
            "developer",
            "student",
            "manager",
            "b.tech",
            "b.sc",
            "m.sc",
            "bachelor",
            "master",
            "intern",
            "mühendis",
            "öğrenci",
            "stajyer",
        }
        if any(tw in name_lower for tw in title_words):
            hard_fails.append(f"name_is_title: '{extracted_name}'")
            score -= 15

    # ── 2. Skills Quality ─────────────────────────────────────────────────

    skills_flat = extracted.get("skills", [])
    if isinstance(skills_flat, list):
        garbage_skills = [s for s in skills_flat if _is_garbage_skill(str(s))]
        if garbage_skills:
            hard_fails.append(f"garbage_skills: {garbage_skills[:5]}")
            score -= min(20, len(garbage_skills) * 3)
    else:
        garbage_skills = []

    # Also check skills_categorized
    skills_cat = extracted.get("skills_categorized", {})
    if isinstance(skills_cat, dict):
        for cat, items in skills_cat.items():
            if isinstance(items, list):
                cat_garbage = [s for s in items if _is_garbage_skill(str(s))]
                if cat_garbage:
                    issues.append(f"garbage_in_category_{cat}: {cat_garbage[:3]}")
                    score -= min(10, len(cat_garbage) * 2)

    # ── 3. Language Quality ──────────────────────────────────────────────

    languages = extracted.get("languages", [])
    broken_languages = []
    if isinstance(languages, list):
        for lang in languages:
            lang_str = str(lang).strip()
            if not _is_valid_language_entry(lang_str):
                broken_languages.append(lang_str)
        if broken_languages:
            hard_fails.append(f"broken_languages: {broken_languages}")
            score -= min(15, len(broken_languages) * 5)

    # ── 4. Summary Contamination ─────────────────────────────────────────

    summary = str(extracted.get("summary", "")).strip()
    contamination = _check_summary_contamination(summary)
    if contamination:
        hard_fails.append(f"summary_contaminated: {contamination[:3]}")
        score -= min(15, len(contamination) * 5)

    # ── 5. Date Integrity ────────────────────────────────────────────────

    date_issues = _check_date_integrity(extracted)
    if date_issues:
        hard_fails.append(f"date_corruption: {date_issues}")
        score -= min(10, len(date_issues) * 5)

    # ── 6. Section Counts ────────────────────────────────────────────────

    # Check if raw text has experience-like content but extracted has none
    exp_signals = re.findall(
        r"\b(?:experience|deneyim|intern|staj|worked|managed|developed)\b",
        raw_text,
        re.I,
    )
    exp_entries = extracted.get("experiences", [])
    if len(exp_signals) >= 3 and not exp_entries:
        issues.append("experience_section_lost")
        score -= 10

    # Check education
    edu_signals = re.findall(
        r"\b(?:university|üniversite|bachelor|lisans|education|eğitim|b\.sc|b\.tech)\b",
        raw_text,
        re.I,
    )
    edu_entries = extracted.get("education", [])
    if len(edu_signals) >= 2 and not edu_entries:
        hard_fails.append("education_section_lost")
        score -= 20

    # ── 7. Education Field Corruption ────────────────────────────────────

    for i, edu in enumerate(edu_entries):
        if not isinstance(edu, dict):
            continue
        degree = str(edu.get("degree", ""))
        school = str(edu.get("school", ""))
        # Check if activity/project leaked into education
        activity_words = {"marching band", "volleyball", "cricket", "football", "chess", "debate", "club", "society"}
        for field_name, field_val in [("degree", degree), ("school", school)]:
            for aw in activity_words:
                if aw in field_val.lower():
                    hard_fails.append(f"education[{i}].{field_name}_contains_activity: '{aw}'")
                    score -= 10

    # ── 8. Experience Fragmentation / Over-splitting ─────────────────────

    frag_issues = _check_experience_fragmentation(extracted)
    if frag_issues:
        hard_fails.append(f"experience_garbage: {frag_issues}")
        score -= 30

    # ── Final Score ──────────────────────────────────────────────────────

    score = max(0, min(100, score))
    needs_fallback = bool(hard_fails) or score < 70

    result = {
        "quality_score": score,
        "issues": issues,
        "hard_fails": hard_fails,
        "needs_llm_fallback": needs_fallback,
        "garbage_skills": garbage_skills if isinstance(skills_flat, list) else [],
        "broken_languages": broken_languages,
    }

    if needs_fallback:
        logger.warning(
            "extraction_quality_low score=%d hard_fails=%d issues=%d",
            score,
            len(hard_fails),
            len(issues),
        )
    else:
        logger.info("extraction_quality_ok score=%d", score)

    return result
