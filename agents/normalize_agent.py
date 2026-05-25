"""Normalize Agent — ATS CV normalizer.

This is the second step of the pipeline:
  raw text → extract → NORMALIZE → format → PDF

Rules:
- Fix broken lines (hyphenated words, split sentences)
- Fix multi-column CV layout artifacts
- Keep GPA with its education entry
- Keep bullets as separate items (never merge)
- Do not merge sections
- Convert to canonical ATS section order
- Enforce single-column layout
- Respect max line length
- Generic normalization: contact/edu cleanup in exp, auto education,
  name extraction, language code filter, misc redistribution, URL fix
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from typing import Dict, List

import yaml

logger = logging.getLogger("app.normalize_agent")

NORMALIZE_PROMPT = """
You are ATS CV normalizer.

Rules:

- Fix broken lines
- Fix multi column CV
- Keep GPA with education
- Keep bullets separate
- Do not merge sections
- Convert to ATS order

Input CV may have multiple columns.
Ignore visual layout.
Reconstruct logical order.
"""

# ── config loading ──

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ats_config.yaml")

_DEFAULT_SECTION_ORDER = [
    "header",
    "summary",
    "experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "languages",
    "interests",
    "misc",
]

_DEFAULT_RULES = {
    "keep_gpa_with_education": True,
    "force_single_column": False,
    "keep_bullets": True,
    "max_line_length": 90,
    "detect_multi_column": False,
}


def _load_config() -> Dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_section_order() -> List[str]:
    config = _load_config()
    return config.get("section_order", _DEFAULT_SECTION_ORDER)


def get_rules() -> Dict:
    config = _load_config()
    return {**_DEFAULT_RULES, **(config.get("rules") or {})}


# ── normalization helpers ──

def _fix_broken_lines(text: str) -> str:
    """Fix lines broken by PDF extraction: hyphenated words, split sentences."""
    lines = text.split("\n")
    fixed: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Fix hyphenated word break: "algo-\nrithm" → "algorithm"
        if line.rstrip().endswith("-") and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and next_line[0].islower():
                line = line.rstrip()[:-1] + next_line
                i += 2
                fixed.append(line)
                continue
        fixed.append(line)
        i += 1
    return "\n".join(fixed)


def _fix_bullet_separation(bullets: List[str]) -> List[str]:
    """Ensure each bullet is a separate item — never merge bullets together."""
    result: List[str] = []
    for item in bullets:
        text = str(item or "").strip()
        if not text:
            continue
        # Split on embedded bullet markers
        parts = re.split(r"\n\s*[-•*]\s*", text)
        for j, part in enumerate(parts):
            cleaned = part.strip()
            cleaned = re.sub(r"^[-•*]\s*", "", cleaned).strip()
            if cleaned:
                result.append(cleaned)
    return result


def _enforce_gpa_with_education(education: List[Dict]) -> List[Dict]:
    """Ensure GPA stays attached to its education entry — never floats away."""
    for edu in education:
        gpa = edu.get("gpa", "")
        if isinstance(gpa, str) and gpa.strip():
            # Clean the GPA value but keep it attached
            gpa_clean = gpa.replace("GPA:", "").replace("gpa:", "").replace("CGPA:", "").strip()
            edu["gpa"] = gpa_clean
        # Ensure all fields exist
        edu.setdefault("degree", "")
        edu.setdefault("school", "")
        edu.setdefault("start_date", "")
        edu.setdefault("end_date", "")
        edu.setdefault("gpa", "")
        edu.setdefault("field", "")
        edu.setdefault("location", "")
    return education


def _normalize_experience_bullets(experiences: List[Dict], rules: Dict) -> List[Dict]:
    """Normalize experience entries: fix bullets, enforce line length."""
    max_len = rules.get("max_line_length", 90)
    for exp in experiences:
        # Fix bullets — keep each one separate
        raw_bullets = exp.get("bullets", [])
        exp["bullets"] = _fix_bullet_separation(raw_bullets)

        # Strip leaked GPA/education content from experience bullets
        # (happens when multi-column reconstruction is imprecise)
        cleaned = []
        for b in exp["bullets"]:
            b = re.sub(r"\s*(?:GPA|CGPA)\s*:\s*\d[\d./]*\s*$", "", b, flags=re.I).strip()
            if b:
                cleaned.append(b)
        exp["bullets"] = cleaned

        # Trim overly long bullets
        trimmed = []
        for b in exp["bullets"]:
            if len(b) > max_len * 3:
                b = b[:max_len * 3 - 3].rstrip() + "..."
            trimmed.append(b)
        exp["bullets"] = trimmed

    return experiences


def _reorder_sections(structured: Dict, section_order: List[str]) -> Dict:
    """Reorder the structured data keys to match ATS section order.

    This doesn't change the data, just records the intended order
    so downstream formatters can respect it.
    """
    # GUARD: never overwrite section order if extract already set it
    if "_section_order" not in structured:
        structured["_section_order"] = section_order
    return structured


# ── Structural language detection for skill/language separation ──

from utils.section_scorer import is_language_entry as _is_structural_lang
from utils.section_scorer import CEFR_RE as _LANG_LEVEL_RE

_LANG_PREFIX_RE = re.compile(
    r"^(?:foreign\s+languages?|languages?(?:\s+known)?)\s*:\s*",
    re.IGNORECASE,
)


def _is_language_item(text: str) -> bool:
    """Return True if *text* looks like a language entry, not a technical skill.

    Uses purely structural signals: CEFR / JLPT levels, proficiency words,
    sub-skill labels (writing/reading/listening/speaking), and absence of
    tech names, dates, and URLs.  No language-name dictionary is consulted.
    """
    return _is_structural_lang(text, strict=True)


def _split_languages_from_skills(skills: list) -> tuple[list, list]:
    """Partition *skills* into (kept_skills, extracted_languages)."""
    kept: list = []
    langs: list = []
    for item in skills:
        text = str(item or "").strip()
        if not text:
            continue
        if _is_language_item(text):
            # Clean prefix before adding
            cleaned = _LANG_PREFIX_RE.sub("", text).strip()
            langs.append(cleaned or text)
        else:
            kept.append(text)
    return kept, langs


def normalize(structured: Dict) -> Dict:
    """Main normalize entry point.

    Takes structured extracted data and normalizes it:
    - Remaps any non-canonical section keys
    - Fixes broken lines in text fields
    - Ensures GPA stays with education
    - Keeps bullets as separate items
    - Enforces ATS section ordering
    - Single-column layout enforcement
    """
    from services.section_classifier import canonicalize_section_key

    rules = get_rules()
    section_order = get_section_order()
    normalized = dict(structured)

    # FIX: preserve original section order from extract if present
    _orig_section_order = structured.get("_section_order")

    # Step 0: remap any non-canonical keys so nothing is lost
    _LIST_KEYS = {
        "experiences", "education", "skills", "skills_categorized",
        "projects", "certifications", "languages", "interests", "misc",
    }
    _REMAP_TARGETS = {
        "summary": "summary",
        "experience": "experiences",
        "education": "education",
        "skills": "skills",
        "projects": "projects",
        "certifications": "certifications",
        "languages": "languages",
        "interests": "interests",
        "misc": "misc",
        "contact": "contact",
    }
    for key in list(normalized.keys()):
        if key.startswith("_") or key in (
            "full_name", "title", "email", "phone", "location", "linkedin",
            "summary", "experiences", "education", "skills", "skills_categorized",
            "projects", "certifications", "languages", "interests", "misc", "language",
            "section_titles", "format_hints", "contact",
        ):
            continue
        canonical = canonicalize_section_key(key)
        target = _REMAP_TARGETS.get(canonical, "misc")
        value = normalized.pop(key)
        if not value:
            continue
        if target == "summary":
            # If summary already came from a top-of-CV section, don't
            # append scraped text from non-canonical keys.
            if normalized.get("_summary_source") == "top" and normalized.get("summary"):
                continue
            existing = normalized.get("summary", "")
            extra = value if isinstance(value, str) else " ".join(str(v) for v in value)
            normalized["summary"] = f"{existing} {extra}".strip() if existing else extra
            if not normalized.get("_summary_source"):
                normalized["_summary_source"] = "remap"
        elif target in _LIST_KEYS:
            existing = normalized.get(target) or []
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(value)
            normalized[target] = existing

    # 1. Fix broken lines in summary
    summary = normalized.get("summary", "")
    if isinstance(summary, str):
        normalized["summary"] = _fix_broken_lines(summary).strip()

    # 2. Rescue GPA from experience bullets BEFORE cleaning
    # (multi-column reconstruction sometimes leaks GPA into wrong section)
    education = normalized.get("education") or []
    if isinstance(education, list) and education:
        has_any_gpa = any((edu.get("gpa") or "").strip() for edu in education)
        if not has_any_gpa:
            for exp in (normalized.get("experiences") or normalized.get("experience") or []):
                for bullet in (exp.get("bullets") or []):
                    gpa_match = re.search(
                        r"(?:GPA|CGPA)\s*:\s*(\d[\d./]+)", str(bullet), re.I,
                    )
                    if gpa_match:
                        education[0]["gpa"] = gpa_match.group(1)
                        break
                if (education[0].get("gpa") or "").strip():
                    break

    # 3. Normalize education — keep GPA attached
    if isinstance(education, list):
        normalized["education"] = _enforce_gpa_with_education(education)

    # 3b. Education field length guard. Degree/school names can be long
    # ("... University - Engineering (English, Full Scholarship)"), so keep
    # generous limits there and only cap clearly runaway text.
    edu_list = normalized.get("education") or []
    if isinstance(edu_list, list):
        for _edu in edu_list:
            if not isinstance(_edu, dict):
                continue
            _edu_limits = {"degree": 24, "school": 24, "field": 12, "location": 10}
            for _fld in ("degree", "school", "field", "location"):
                _val = str(_edu.get(_fld, "")).strip()
                _limit = _edu_limits[_fld]
                if _val and len(_val.split()) > _limit:
                    _edu[_fld] = " ".join(_val.split()[:_limit])

    # 4. Normalize experience bullets — keep separate, strip leaked GPA
    experiences = normalized.get("experiences") or normalized.get("experience") or []
    if isinstance(experiences, list):
        normalized["experiences"] = _normalize_experience_bullets(experiences, rules)

    # 4b. Experience quality filter (Task 7):
    #   Valid experience entries should have at least one signal:
    #   a year, a company/role hint, or an action verb bullet.
    _YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b|present|current|ongoing|halen|günümüz", re.I)
    _valid_exps: list = []
    for _exp in (normalized.get("experiences") or []):
        if not isinstance(_exp, dict):
            continue
        _exp_text = " ".join([
            str(_exp.get("company", "")),
            str(_exp.get("title", "")),
            str(_exp.get("start_date", "")),
            str(_exp.get("end_date", "")),
            " ".join(str(b) for b in (_exp.get("bullets") or [])),
        ])
        # Accept if: has a year, has at least 1 bullet, or has a title/company
        has_year = bool(_YEAR_RE.search(_exp_text))
        has_bullets = bool(_exp.get("bullets"))
        has_role = bool(str(_exp.get("title", "")).strip() or str(_exp.get("company", "")).strip())
        if has_year or has_bullets or has_role:
            _valid_exps.append(_exp)
    normalized["experiences"] = _valid_exps

    # 4. Normalize project bullets
    projects = normalized.get("projects") or normalized.get("project") or []
    if isinstance(projects, list):
        for proj in projects:
            raw_bullets = proj.get("bullets", [])
            proj["bullets"] = _fix_bullet_separation(raw_bullets)

    # 5. Deduplicate skills
    skills = normalized.get("skills") or normalized.get("skill") or []
    if isinstance(skills, list):
        seen = set()
        deduped = []
        for s in skills:
            _s = str(s).strip()
            # 5a. Strip prefix only when the content after ':' is a single
            #     value (no commas/semicolons/pipes).  If the suffix
            #     contains delimiters (≥2 items) leave the line intact so
            #     step 5aa can promote it to skills_categorized.
            _prefix_m = re.match(r'^[A-Za-z\u00C0-\u024F]+(?:\s+[A-Za-z\u00C0-\u024F]+){0,2}\s*:\s+', _s)
            if _prefix_m:
                _after = _s[_prefix_m.end():].strip()
                _delimited = re.split(r'[,;|]', _after)
                _delimited = [x.strip() for x in _delimited if x.strip()]
                if len(_delimited) < 2:
                    # Single value → drop the prefix
                    _s = _after
            if not _s:
                continue
            key = _s.lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(_s)
        normalized["skills"] = deduped

    # 5-filter. Skills quality filter (Task 6):
    #   Reject entries that look like long sentences rather than skill tokens.
    #   Reject garbage tokens: emails, phones, dates, percentages, URLs, single chars.
    _garbage_re = re.compile(
        r"^(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})$"  # email
        r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"               # phone
        r"|(?:^\d{1,2}(?:th|st|nd|rd)$)"                # ordinals
        r"|(?:^\d+\.?\d*%$)"                            # percentages
        r"|(?:^\d{4}$)"                                 # bare years
        r"|(?:^\d{1,2}[./]\d{1,2}[./]\d{2,4}$)"         # dates
        r"|(?:^https?://|^www\.)"                       # URLs
        r"|(?:gmail\.com|hotmail\.com|yahoo\.com)"      # email domains
        r"|(?:^[a-z]$)"                                 # single char
        r"|(?:^[a-z]\.[a-z]\.?$)"                       # short abbreviations
        r"|(?:^\d+\.?\d*$)",                            # bare numbers
        re.IGNORECASE
    )
    _filtered_skills: list = []
    for _sk_item in (normalized.get("skills") or []):
        _sk_str = str(_sk_item).strip()
        if not _sk_str:
            continue
        # Drop strict garbage tokens
        if _garbage_re.search(_sk_str):
            continue
        # Accept: lines with commas/pipes (multi-skill listings)
        if re.search(r"[,;|]", _sk_str):
            _filtered_skills.append(_sk_str)
            continue
        # Reject: long sentences (> 8 words without delimiters)
        if len(_sk_str.split()) > 8:
            continue
        _filtered_skills.append(_sk_str)
    normalized["skills"] = _filtered_skills

    # 5aa. Parse "Category: item1, item2" into skills_categorized
    _raw_skills = normalized.get("skills") or []
    _cat_from_flat: Dict[str, list] = {}
    _kept_flat: list = []
    for _sk in _raw_skills:
        _sk_str = str(_sk).strip()
        _cat_m = re.match(r'^([A-Za-z\u00C0-\u024F]+(?:\s+[A-Za-z\u00C0-\u024F]+){0,2})\s*:\s+(.+)$', _sk_str)
        if _cat_m:
            _cat_name = _cat_m.group(1).strip()
            _cat_items = [x.strip() for x in re.split(r'[,;|]', _cat_m.group(2)) if x.strip()]
            if _cat_items and len(_cat_items) >= 2:
                _cat_from_flat.setdefault(_cat_name, []).extend(_cat_items)
                continue
        _kept_flat.append(_sk_str)
    normalized["skills"] = _kept_flat
    if _cat_from_flat:
        _existing_cat = normalized.get("skills_categorized") or {}
        if not isinstance(_existing_cat, dict):
            _existing_cat = {}
        for _ck, _cv in _cat_from_flat.items():
            _existing_cat.setdefault(_ck, []).extend(_cv)
        normalized["skills_categorized"] = _existing_cat

    # 5b. Move language items out of skills → languages
    normalized["skills"], _extracted_langs = _split_languages_from_skills(
        normalized.get("skills") or []
    )
    # Also clean skills_categorized
    raw_cat = normalized.get("skills_categorized")
    if isinstance(raw_cat, dict):
        cleaned_cat: Dict[str, list] = {}
        for cat, vals in list(raw_cat.items()):
            if not isinstance(vals, list):
                vals = [vals]
            kept, cat_langs = _split_languages_from_skills(vals)
            _extracted_langs.extend(cat_langs)
            if kept:
                cleaned_cat[cat] = kept
        normalized["skills_categorized"] = cleaned_cat

    # Merge extracted language items into languages list (deduplicated)
    existing_langs = normalized.get("languages") or normalized.get("language") or []
    if not isinstance(existing_langs, list):
        existing_langs = [existing_langs] if existing_langs else []
    _existing_lower = {str(l).strip().lower() for l in existing_langs}
    for lang in _extracted_langs:
        if str(lang).strip().lower() not in _existing_lower:
            existing_langs.append(lang)
            _existing_lower.add(str(lang).strip().lower())
    normalized["languages"] = existing_langs

    # 6. Deduplicate and validate languages
    languages = normalized.get("languages") or []
    if isinstance(languages, list):
        seen = set()
        deduped = []
        _lang_garbage_re = re.compile(
            r"https?(?::|/|$)|@|\.com|\.io|\.edu"
            r"|\b(?:education|experience|skills|projects|summary|profile"
            r"|objective|blog|website|development|engineer|degree|university"
            r"|bachelor|master|software|technology|health|sports|teamwork|personal)\b",
            re.IGNORECASE
        )
        for lang in languages:
            key = str(lang).strip().lower()
            # Drop corrupted tokens: "e n", "tr", "en", single characters
            if not key or len(key.replace(" ", "")) <= 2:
                continue
            # Drop if it contains an underscore (e.g. 'abk_website')
            if "_" in key:
                continue
            # Drop entries that look like section headers or URLs
            if _lang_garbage_re.search(key):
                continue
            if key not in seen:
                seen.add(key)
                deduped.append(str(lang).strip())
        normalized["languages"] = deduped

    # 6b. Strip empty / noise tokens from all flat-list sections
    _NOISE_TOKENS = frozenset({'""', '|', '||', ':', ',', '-', '–', '—', '•', '*', '/', '\\'})
    for _flat_key in ("skills", "languages", "interests", "misc"):
        _items = normalized.get(_flat_key)
        if isinstance(_items, list):
            normalized[_flat_key] = [
                s for s in _items
                if isinstance(s, str) and s.strip() and s.strip() not in _NOISE_TOKENS
                and len(s.strip()) > 1
            ]

    # 6c. Strip empty / noise tokens from dict-list sections (experience, education, projects, certifications)
    for _dict_key in ("experiences", "education", "projects", "certifications"):
        _entries = normalized.get(_dict_key)
        if not isinstance(_entries, list):
            continue
        for _entry in _entries:
            if not isinstance(_entry, dict):
                continue
            for _field, _val in list(_entry.items()):
                if isinstance(_val, str) and _val.strip() in _NOISE_TOKENS:
                    _entry[_field] = ""
                elif isinstance(_val, list):
                    _entry[_field] = [
                        v for v in _val
                        if isinstance(v, str) and v.strip() and v.strip() not in _NOISE_TOKENS
                        and len(v.strip()) > 1
                    ]

    # 6d. Contact must not be inside experience entries
    _CONTACT_IN_EXP_RE = re.compile(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
        r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"
        r"|\b(?:birth|doğum|dob)\b"
        r"|\b(?:adres|address|mahalle|sokak|cadde)\b",
        re.I,
    )
    exps = normalized.get("experiences")
    if isinstance(exps, list):
        for _exp in exps:
            if not isinstance(_exp, dict):
                continue
            # Strip contact data from title/company
            for _fld in ("title", "company"):
                _v = str(_exp.get(_fld, ""))
                if _v and _CONTACT_IN_EXP_RE.search(_v) and len(_v.split()) <= 6:
                    _exp[_fld] = ""
            # Strip contact lines from bullets
            _kept_bullets = []
            for _b in (_exp.get("bullets") or []):
                _b_str = str(_b).strip()
                if _b_str and not (
                    _CONTACT_IN_EXP_RE.search(_b_str) and len(_b_str.split()) <= 6
                ):
                    _kept_bullets.append(_b_str)
            _exp["bullets"] = _kept_bullets

    # 6e. Merge duplicate skills_categorized entries
    _scat = normalized.get("skills_categorized")
    if isinstance(_scat, dict):
        merged_cat: Dict[str, list] = {}
        for _cat_key, _cat_vals in _scat.items():
            _norm_key = str(_cat_key).strip()
            if not _norm_key:
                continue
            if not isinstance(_cat_vals, list):
                _cat_vals = [_cat_vals] if _cat_vals else []
            # Find existing category (case-insensitive)
            _found = None
            for _mk in merged_cat:
                if _mk.lower() == _norm_key.lower():
                    _found = _mk
                    break
            if _found:
                merged_cat[_found].extend(_cat_vals)
            else:
                merged_cat[_norm_key] = list(_cat_vals)
        # Deduplicate within each category
        for _mk in merged_cat:
            seen_items: set = set()
            deduped_items: list = []
            for _item in merged_cat[_mk]:
                _ik = str(_item).strip().lower()
                if _ik and _ik not in seen_items:
                    seen_items.add(_ik)
                    deduped_items.append(str(_item).strip())
            merged_cat[_mk] = deduped_items
        normalized["skills_categorized"] = merged_cat

    # 7. Set section order — preserve original CV order if extract provided one
    if _orig_section_order:
        normalized["_section_order"] = _orig_section_order
    else:
        normalized = _reorder_sections(normalized, section_order)

    # 7b. Formatting hints for layout engine / renderers.
    normalized["format_hints"] = {
        "bold": ["header.name", "section.title", "experience.company", "education.degree"],
        "max_chars_per_line": 80,
        "section_separator": "line_break",
    }

    # 7c. Section consistency & size guard
    _normalize_section_consistency(normalized)

    # 7d. Section resolution (cross-section fixup via resolver)
    from services.section_resolver import resolve_parsed_entries
    resolve_parsed_entries(normalized)

    # 7e. Sanitization rules (normalizer only sanitizes — no section moving)
    from utils.cv_normalizer import apply_normalization_rules
    apply_normalization_rules(normalized)

    # 8. Mark as normalized
    normalized["_normalized"] = True

    # 8b. Log final schema counts for debugging
    _schema_counts = {}
    for _sk in ("experiences", "education", "skills", "projects",
                "certifications", "languages", "interests", "misc"):
        _sv = normalized.get(_sk)
        if isinstance(_sv, list):
            _schema_counts[_sk] = len(_sv)
    logger.debug("final_schema_counts=%s", _schema_counts)

    # 9. Security: cap serialized output size
    try:
        _json_size = len(json.dumps(normalized, default=str))
        if _json_size > _MAX_JSON_SIZE:
            logger.warning("normalize: JSON output too large %d > %d, trimming",
                           _json_size, _MAX_JSON_SIZE)
            # Trim the largest list sections until under limit
            _list_keys = ["experiences", "education", "skills", "projects",
                          "certifications", "languages", "interests", "misc"]
            for _trim_key in sorted(_list_keys,
                                     key=lambda k: len(json.dumps(normalized.get(k, []), default=str)),
                                     reverse=True):
                _tv = normalized.get(_trim_key)
                if isinstance(_tv, list) and len(_tv) > 5:
                    normalized[_trim_key] = _tv[:len(_tv) // 2]
                    _json_size = len(json.dumps(normalized, default=str))
                    if _json_size <= _MAX_JSON_SIZE:
                        break
    except (TypeError, ValueError):
        pass

    return normalized


# ── Section consistency ──────────────────────────────────────────────────

_SECTION_SIZE_LIMIT = 60  # lines — if a section exceeds this, re-evaluate


# ── Security limits ────────────────────────────────────────────────────────
_MAX_SECTION_ENTRIES = 50    # max entries in any dict-list section
_MAX_SECTION_LINES = 500     # max items in any flat-list section
_MAX_BULLETS_PER_ENTRY = 30  # max bullets per experience/project entry
_MAX_WORDS_PER_LINE = 200    # truncate absurdly long lines
_MAX_JSON_SIZE = 500_000     # max serialized output size (bytes)


def _normalize_section_consistency(data: Dict) -> None:
    """Post-normalize sanity checks.

    1. Section size guard — if any list section has too many raw entries,
       trim obvious noise (empty strings, duplicates) to stay reasonable.
    2. Remove fully empty sections so downstream doesn't render blanks.
    3. Hard caps on section items, entry counts, bullet counts, line length.
    """
    _list_sections = [
        "experiences", "education", "skills", "projects",
        "certifications", "languages", "interests", "misc",
    ]
    for key in _list_sections:
        val = data.get(key)
        if not isinstance(val, list):
            continue
        # Strip empty entries
        val = [v for v in val if v]
        # Deduplicate preserving order (for flat lists)
        if val and isinstance(val[0], str):
            seen: set = set()
            deduped: List = []
            for item in val:
                k = item.strip().lower()
                if k not in seen:
                    seen.add(k)
                    deduped.append(item)
            val = deduped
        data[key] = val

    # ── Hard caps (security) ──
    for key in _list_sections:
        val = data.get(key)
        if not isinstance(val, list):
            continue
        # Dict-list sections (experiences, education, projects, certifications)
        if val and isinstance(val[0], dict):
            if len(val) > _MAX_SECTION_ENTRIES:
                logger.warning("normalize: %s capped %d → %d entries",
                               key, len(val), _MAX_SECTION_ENTRIES)
                data[key] = val[:_MAX_SECTION_ENTRIES]
            # Cap bullets per entry
            for _entry in data[key]:
                if isinstance(_entry, dict):
                    _bullets = _entry.get("bullets")
                    if isinstance(_bullets, list) and len(_bullets) > _MAX_BULLETS_PER_ENTRY:
                        _entry["bullets"] = _bullets[:_MAX_BULLETS_PER_ENTRY]
        # Flat-list sections (skills, languages, interests, misc)
        elif len(val) > _MAX_SECTION_LINES:
            logger.warning("normalize: %s capped %d → %d items",
                           key, len(val), _MAX_SECTION_LINES)
            data[key] = val[:_MAX_SECTION_LINES]
        # Truncate absurdly long individual strings
        for _i, _item in enumerate(data.get(key, [])):
            if isinstance(_item, str) and len(_item.split()) > _MAX_WORDS_PER_LINE:
                data[key][_i] = " ".join(_item.split()[:_MAX_WORDS_PER_LINE])

    # Remove empty list sections entirely so renderers skip them
    for key in _list_sections:
        val = data.get(key)
        if isinstance(val, list) and not val:
            data.pop(key, None)


# ── Cross-section fixup (raw dicts) ────────────────────────────────────


