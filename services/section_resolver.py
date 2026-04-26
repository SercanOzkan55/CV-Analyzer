"""Section resolver — fix cross-section misclassifications.

Operates at two levels:

1. ``resolve_raw_sections()``  — on raw line-lists, BEFORE entry parsers.
   Consolidates the post-classification ``_normalize_sections()`` logic
   that was previously in ``extract_agent.py``.

2. ``resolve_parsed_entries()`` — on structured dicts, AFTER entry parsers.
   Consolidates ``_cross_section_fixup_raw()`` (from ``normalize_agent``),
   ``redistribute_misc()``, ``validate_section_placement()``, and
   ``rescore_experience_entries()`` (from ``cv_normalizer``).

Pipeline position:
    section_scorer → **section_resolver** → cv_normalizer
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List

import time

logger = logging.getLogger("app.section_resolver")

# ── Security limits ────────────────────────────────────────────────────────
_SAFE_MODE = os.getenv("SAFE_MODE", "").lower() in ("1", "true", "yes")
_MAX_SECTION_LINES = 250 if _SAFE_MODE else 500
_MAX_HEADER_LINES = 30 if _SAFE_MODE else 50
_MAX_MISC_LINES = 50 if _SAFE_MODE else 100
_MAX_ITERATIONS = 250 if _SAFE_MODE else 500
_RESOLVER_TIMEOUT_SECONDS = float(
    os.getenv("RESOLVER_TIMEOUT_SECONDS", "2" if _SAFE_MODE else "3") or "3"
)

# ═══════════════════════════════════════════════════════════════════════════
# SHARED PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

_DEGREE_RE = re.compile(
    r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
    r"|bachelor|master|diploma|associate|degree"
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
_URL_RE = re.compile(
    r"https?://\S+|www\.\S+|github\.com|linkedin\.com|gitlab\.com"
    r"|bitbucket\.org|\.io/|\.com/",
    re.I,
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\(?\+?\d[\d()\-\s.]{7,}\d)")
_TECH_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mongodb|redis|git|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|tensorflow|pytorch|scikit|pandas|linux"
    r"|spring|ruby|rails|php|laravel|swift|kotlin|flutter|dart"
    r"|next\.?js|express|graphql|terraform|jenkins|ci/cd"
    r"|figma|jira|confluence|sass|scss|webpack|vite|nginx)\b",
    re.I,
)
_SKILL_DELIM_RE = re.compile(r"[,;|/]")
_DATE_RANGE_RE = re.compile(
    r"(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|ongoing|halen|günümüz)",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*[-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s")
_INTEREST_RE = re.compile(
    r"\b(?:hobby|hobbies|interest|volunteer|swimming|reading|traveling"
    r"|gaming|photography|cooking|music|sport|yoga|chess|hiking"
    r"|writing|drawing|painting|gardening|cycling|running|camping"
    r"|fishing|dancing|singing|blogging|community)\b",
    re.I,
)
_CEFR_RE = re.compile(
    r"\b(?:A[12]|B[12]|C[12]"               # CEFR levels
    r"|N[1-5]"                                # JLPT levels
    r"|native|fluent|advanced|intermediate"
    r"|beginner|proficient|basic|elementary"
    r"|upper[\s-]?intermediate"
    r"|mother\s*tongue|bilingual)\b",
    re.I,
)
_TECH_HEADER_RE = re.compile(
    r"^\s*(?:used\s+technologies|tech(?:nology|nologies)?\s*(?:stack|used)?"
    r"|tools(?:\s+(?:used|&|and)\s+\w+)?)\s*[:：\-]?\s*$",
    re.I,
)
_TECH_INLINE_RE = re.compile(
    r"^\s*(?:used\s+technologies|tech(?:nology|nologies)?\s*(?:stack|used)?"
    r"|tools(?:\s+(?:used|&|and)\s+\w+)?)\s*[:：\-]\s*(.+)",
    re.I,
)
_BLOG_RE = re.compile(
    r"\b(?:blog|portfolio|personal\s*(?:website|site|page)"
    r"|my\s*(?:website|site|page))\b",
    re.I,
)
_CONTACT_LABEL_RE = re.compile(
    r"^\s*(?:e-?\s*posta|e-?\s*mail|telefon|phone|tel|mobile|fax"
    r"|adres|address|do\u011fum|birth|dob|date\s+of\s+birth"
    r"|web(?:site)?|linkedin|github|portfolio)\s*[:\uff1a]",
    re.I,
)
_BIRTH_RE = re.compile(
    r"\b(?:birth|do\u011fum|dob|geboren|date\s+of\s+birth)\b", re.I,
)

# ── Patterns for parsed-entry resolution ──────────────────────────────────
_URL_RAW_RE = re.compile(
    r"https?://|github\.com|gitlab\.com|bitbucket\.org", re.I,
)
_TECH_RAW_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mongodb|redis|git|html|css)\b",
    re.I,
)
# Action verbs — structural signal for experience/project content
_ACTION_VERB_RE = re.compile(
    r"\b(?:develop|built|design|implement|manage|create|deploy|maintain"
    r"|integrat|automat|optimiz|migrat|refactor|monitor|analyz"
    r"|test|debug|launch|lead|deliver|coordinat|establish"
    r"|geli[sş]tir|olu[sş]tur|tasarla|y[oö]net|ger[cç]ekle[sş]tir"
    r"|entegre|otomat|optimize)\w*\b",
    re.I,
)
# GPA / grade pattern
_GPA_RE = re.compile(
    r"\b(?:gpa|grade|cgpa|not\s*ortalamas[iı])\s*[:\-]?\s*\d", re.I,
)


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 1 — RAW LINE-LIST RESOLUTION (pre-parser)
# ═══════════════════════════════════════════════════════════════════════════

def resolve_raw_sections(
    sections: Dict[str, List[str]],
    header_lines: List[str],
    section_titles: Dict[str, str] | None = None,
) -> Dict[str, List[str]]:
    """Fix misrouted blocks in raw classified sections.

    Applied after the classifier assigns lines to section buckets
    but before downstream parsers consume them.  Only moves lines
    between buckets — never drops content.

    *section_titles* maps canonical key → header text from the classifier.
    Sections present in this dict are **header-placed** and receive softer
    enforcement (the header is authoritative).

    Rules (in resolver order):
    0. Contact extraction — pull email/phone/URL/birth lines out
    1. Education rescue — degree/gpa + year → education (not institution-only)
    2. URL routing — standalone URLs → header/contact
    3. Skills rescue — short tech tokens / comma-separated → skills
    4. Used-Technologies header → skills
    5. Interests detection — short phrases → interests
    6. Languages detection — CEFR / language names → languages
    7. Misc sweep — rescore remaining misc
    8. Skills enforcement (soft) — long items without delimiter/tech/colon → misc
    """
    _titled: set[str] = set((section_titles or {}).keys())

    # ── Security: cap section sizes ──
    for _sk in list(sections.keys()):
        _sv = sections[_sk]
        if isinstance(_sv, list) and len(_sv) > _MAX_SECTION_LINES:
            logger.warning("resolver: section %s truncated %d → %d lines",
                           _sk, len(_sv), _MAX_SECTION_LINES)
            sections[_sk] = _sv[:_MAX_SECTION_LINES]
    if len(header_lines) > _MAX_HEADER_LINES:
        logger.warning("resolver: header truncated %d → %d lines",
                       len(header_lines), _MAX_HEADER_LINES)
        header_lines[:] = header_lines[:_MAX_HEADER_LINES]

    _t0_resolve = time.perf_counter()

    # ── Rule 0: Contact-line extraction & birth-date protection ───────
    # Aggressive: scan ALL sections — contact must go to header.
    def _is_misplaced_contact(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if _DATE_RANGE_RE.search(stripped) or _YEAR_RE.search(stripped):
            return False
        if _CONTACT_LABEL_RE.match(stripped):
            return True
        if _BIRTH_RE.search(stripped) and len(stripped.split()) <= 8:
            return True
        if _EMAIL_RE.search(stripped) and len(stripped.split()) <= 5:
            return True
        if _PHONE_RE.search(stripped) and len(stripped.split()) <= 5:
            return True
        # Standalone email/phone anywhere → header
        if _EMAIL_RE.match(stripped):
            return True
        if _PHONE_RE.match(stripped):
            return True
        return False

    for src_key in list(sections.keys()):
        if src_key == "contact":
            continue
        src = sections.get(src_key, [])
        if not src:
            continue
        keep, contact_out = [], []
        for line in src:
            if _is_misplaced_contact(line):
                contact_out.append(line)
            else:
                keep.append(line)
        if contact_out:
            sections[src_key] = keep
            header_lines.extend(contact_out)
            logger.debug("rule0: moved %d contact lines from %s → header",
                         len(contact_out), src_key)

    # ── Rule 1: Education rescue ──────────────────────────────────────
    # Require degree OR gpa keyword.  Institution alone is not enough.
    def _is_education_block(lines_chunk: list[str]) -> bool:
        text = " ".join(lines_chunk).lower()
        has_degree = bool(_DEGREE_RE.search(text))
        has_inst = bool(_INSTITUTION_RE.search(text))
        has_year = bool(_YEAR_RE.search(text))
        has_gpa = bool(_GPA_RE.search(text))
        bullet_ct = sum(1 for l in lines_chunk if _BULLET_RE.match(l))
        # degree + institution + year → always education
        if has_degree and has_inst and has_year:
            return True
        # degree + (institution OR year) with few bullets → education
        if has_degree and (has_inst or has_year) and bullet_ct <= 1:
            return True
        # gpa keyword present → education
        if has_gpa and (has_inst or has_year or has_degree):
            return True
        # institution + year WITHOUT degree → NOT education (institution alone not enough)
        return False

    # Only scan misc and experience; skip header-placed sections
    for src_key in ("misc", "experience"):
        if src_key in _titled:
            continue
        src = sections.get(src_key, [])
        if not src:
            continue
        edu_lines: list[str] = []
        keep: list[str] = []
        current_block: list[str] = []
        for line in src:
            if not line.strip():
                if current_block:
                    if _is_education_block(current_block):
                        edu_lines.extend(current_block)
                        edu_lines.append("")
                    else:
                        keep.extend(current_block)
                        keep.append("")
                    current_block = []
                else:
                    keep.append(line)
            else:
                current_block.append(line)
        if current_block:
            if _is_education_block(current_block):
                edu_lines.extend(current_block)
            else:
                keep.extend(current_block)
        if edu_lines:
            sections[src_key] = [l for l in keep if l.strip() or keep.index(l) < len(keep) - 1]
            sections.setdefault("education", [])
            sections["education"].extend(edu_lines)
            logger.debug("rule1: moved %d education lines from %s",
                         len(edu_lines), src_key)

    # ── Rule 2: URL routing ──────────────────────────────────────────
    def _is_standalone_url_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if _BULLET_RE.match(stripped):
            return False
        if _URL_RE.search(stripped):
            url_span = _URL_RE.search(stripped)
            if url_span and len(url_span.group(0)) >= len(stripped) * 0.4:
                return True
            if len(stripped.split()) <= 4:
                return True
        if _EMAIL_RE.match(stripped) and len(stripped.split()) <= 2:
            return True
        return False

    for src_key in ("misc", "projects", "skills"):
        src = sections.get(src_key, [])
        if not src:
            continue
        keep, urls = [], []
        for line in src:
            if _is_standalone_url_line(line):
                urls.append(line)
            else:
                keep.append(line)
        if urls:
            sections[src_key] = keep
            header_lines.extend(urls)

    # ── Rule 3: Skills rescue ─────────────────────────────────────────
    def _is_skill_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if _DATE_RANGE_RE.search(stripped):
            return False
        if _URL_RE.search(stripped):
            return False
        words = stripped.split()
        delims = len(_SKILL_DELIM_RE.findall(stripped))
        tech_hits = len(_TECH_RE.findall(stripped))
        if delims >= 2 and tech_hits >= 1:
            return True
        if tech_hits >= 2 and len(words) <= 8:
            return True
        if len(words) <= 3 and tech_hits >= 1 and delims == 0:
            return True
        if ":" in stripped and delims >= 1 and tech_hits >= 1:
            return True
        return False

    misc = sections.get("misc", [])
    if misc:
        keep, skills = [], []
        for line in misc:
            if _is_skill_line(line):
                skills.append(line)
            else:
                keep.append(line)
        if skills:
            sections["misc"] = keep
            sections.setdefault("skills", [])
            sections["skills"].extend(skills)

    # ── Rule 4: Used Technologies header → skills ─────────────────────
    misc = sections.get("misc", [])
    if misc:
        keep, tech_block = [], []
        in_tech_block = False
        for line in misc:
            if _TECH_HEADER_RE.match(line):
                in_tech_block = True
                tech_block.append(line)
            elif in_tech_block:
                if not line.strip():
                    in_tech_block = False
                    keep.append(line)
                else:
                    tech_block.append(line)
            else:
                keep.append(line)
        if tech_block:
            sections["misc"] = keep
            sections.setdefault("skills", [])
            sections["skills"].extend(tech_block)

    # ── Rule 4a: Copy tech-header from projects/experience → skills ──
    for src_key in ("projects", "experience"):
        src = sections.get(src_key, [])
        if not src:
            continue
        tech_copies: list[str] = []
        in_tech_block = False
        for line in src:
            stripped = line.strip()
            m = _TECH_INLINE_RE.match(stripped)
            if m:
                tech_copies.append(m.group(1).strip())
                in_tech_block = False
                continue
            if _TECH_HEADER_RE.match(stripped):
                in_tech_block = True
                continue
            if in_tech_block:
                if not stripped:
                    in_tech_block = False
                else:
                    tech_copies.append(line)
                continue
        if tech_copies:
            sections.setdefault("skills", [])
            sections["skills"].extend(tech_copies)

    # ── Rule 4b: Blog / portfolio → projects ─────────────────────────
    misc = sections.get("misc", [])
    if misc:
        keep_blog, blog_proj = [], []
        for line in misc:
            stripped = line.strip()
            if stripped and _BLOG_RE.search(stripped) and _URL_RE.search(stripped):
                blog_proj.append(line)
            else:
                keep_blog.append(line)
        if blog_proj:
            sections["misc"] = keep_blog
            sections.setdefault("projects", [])
            sections["projects"].extend(blog_proj)

    # ── Rule 5: Interests detection ───────────────────────────────────
    misc = sections.get("misc", [])
    if misc:
        keep, interests = [], []
        for line in misc:
            stripped = line.strip()
            if not stripped:
                keep.append(line)
                continue
            text_low = stripped.lower()
            has_date = (bool(_DATE_RANGE_RE.search(text_low))
                        or len(_YEAR_RE.findall(text_low)) >= 2)
            has_url = bool(_URL_RE.search(stripped))
            has_tech = bool(_TECH_RE.search(text_low))
            words = stripped.split()
            is_short = len(words) <= 8
            if (not has_date and not has_url and not has_tech
                    and is_short and _INTEREST_RE.search(text_low)):
                interests.append(line)
            else:
                keep.append(line)
        if interests:
            sections["misc"] = keep
            sections.setdefault("interests", [])
            sections["interests"].extend(interests)

    # ── Rule 6: Languages detection ───────────────────────────────────
    misc = sections.get("misc", [])
    if misc:
        keep, langs = [], []
        for line in misc:
            stripped = line.strip()
            if not stripped:
                keep.append(line)
                continue
            if _CEFR_RE.search(stripped):
                langs.append(line)
            else:
                keep.append(line)
        if langs:
            sections["misc"] = keep
            sections.setdefault("languages", [])
            sections["languages"].extend(langs)

    # ── Rule 7: Final misc sweep ──────────────────────────────────────
    misc = sections.get("misc", [])
    if misc:
        final_keep: list[str] = []
        for line in misc:
            stripped = line.strip()
            if not stripped:
                final_keep.append(line)
                continue
            text_low = stripped.lower()
            # Education: require degree OR gpa (institution alone not enough)
            if (_DEGREE_RE.search(text_low) or _GPA_RE.search(text_low)) and (
                    _INSTITUTION_RE.search(text_low) or _YEAR_RE.search(text_low)):
                sections.setdefault("education", [])
                sections["education"].append(line)
                continue
            if _is_skill_line(line):
                sections.setdefault("skills", [])
                sections["skills"].append(line)
                continue
            final_keep.append(line)
        sections["misc"] = final_keep

    # ── Rule 8: Skills enforcement (soft) — short tokens preferred ─────
    # >6 words allowed if delimiter OR tech OR colon present.
    # Skip header-placed skills section (header is authoritative).
    if "skills" not in _titled:
        skills_lines = sections.get("skills", [])
        if skills_lines:
            valid_skills: list[str] = []
            ejected_from_skills: list[str] = []
            for line in skills_lines:
                stripped = line.strip()
                if not stripped:
                    continue
                words = stripped.split()
                has_delim = bool(_SKILL_DELIM_RE.search(stripped))
                has_tech = bool(_TECH_RE.search(stripped))
                has_colon = ":" in stripped
                is_short = len(words) <= 6
                if is_short or has_delim or has_tech or has_colon:
                    valid_skills.append(line)
                else:
                    ejected_from_skills.append(line)
            if ejected_from_skills:
                sections["skills"] = valid_skills
                sections.setdefault("misc", [])
                sections["misc"].extend(ejected_from_skills)
                logger.debug("rule8: ejected %d long items from skills → misc",
                             len(ejected_from_skills))

    # ── Rule 9: Projects enforcement — must contain url or tech ───────
    # Only enforce on blocks that arrived from misc/other (not from an
    # explicit header).  When a section header like "PROJECTS" is present,
    # the classifier is authoritative — do not second-guess it.
    # This rule is therefore a no-op for header-placed blocks and only
    # catches stray lines promoted during earlier rules (blog, etc.).

    # ── Deduplicate skills ────────────────────────────────────────────
    skills = sections.get("skills", [])
    if skills:
        seen: set[str] = set()
        deduped: list[str] = []
        for line in skills:
            key = line.strip().lower()
            if not key:
                continue
            if key not in seen:
                seen.add(key)
                deduped.append(line)
        sections["skills"] = deduped

    # ── Misc must be last: re-run final sweep ───────────────────────
    misc = sections.get("misc", [])
    if misc:
        rescued: list[str] = []
        for line in misc:
            stripped = line.strip()
            if not stripped:
                continue
            text_low = stripped.lower()
            # Education: degree OR gpa (institution alone not enough)
            if (_DEGREE_RE.search(text_low) or _GPA_RE.search(text_low)) and (
                    _INSTITUTION_RE.search(text_low) or _YEAR_RE.search(text_low)):
                sections.setdefault("education", [])
                sections["education"].append(line)
                continue
            # Skills: tech keyword or delimited short tokens
            if _is_skill_line(line):
                sections.setdefault("skills", [])
                sections["skills"].append(line)
                continue
            # Interests: hobby keywords
            if (_INTEREST_RE.search(text_low)
                    and len(stripped.split()) <= 8
                    and not _URL_RE.search(stripped)
                    and not _DATE_RANGE_RE.search(stripped)):
                sections.setdefault("interests", [])
                sections["interests"].append(line)
                continue
            # Languages: CEFR
            if _CEFR_RE.search(stripped) and len(stripped.split()) <= 8:
                sections.setdefault("languages", [])
                sections["languages"].append(line)
                continue
            rescued.append(line)
        if len(rescued) < len(misc):
            logger.debug("misc_sweep: rescued %d of %d misc items",
                         len(misc) - len(rescued), len(misc))
        sections["misc"] = rescued

    # ── Security: cap misc size ──
    _misc = sections.get("misc", [])
    if len(_misc) > _MAX_MISC_LINES:
        logger.warning("resolver: misc capped %d → %d lines",
                       len(_misc), _MAX_MISC_LINES)
        sections["misc"] = _misc[:_MAX_MISC_LINES]

    # Remove empty sections
    sections = {k: v for k, v in sections.items() if v and any(l.strip() for l in v)}

    # Log resolver summary
    _elapsed = time.perf_counter() - _t0_resolve
    if _elapsed > _RESOLVER_TIMEOUT_SECONDS:
        logger.warning("resolver: slow execution %.2fs (limit %.1fs)",
                       _elapsed, _RESOLVER_TIMEOUT_SECONDS)
    logger.debug("resolver_moves: sections=%s (%.3fs)",
                 {k: len(v) for k, v in sections.items()}, _elapsed)

    return sections


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 2 — PARSED-ENTRY RESOLUTION (post-parser)
# ═══════════════════════════════════════════════════════════════════════════

def _dict_text(d: dict) -> str:
    """Flatten a dict entry into searchable text."""
    parts = []
    for v in d.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)


def resolve_parsed_entries(data: Dict) -> None:
    """Move misplaced dict entries between parsed sections.

    Combines three formerly separate passes:
    1. Structural fixup (experience→education, skills cleanup, language validation)
    2. Score-based misc redistribution
    3. Score-based cross-section validation

    Mutates *data* in place.
    """
    _t0 = time.perf_counter()
    _fixup_experience_to_education(data)
    _cleanup_skills(data)
    _enforce_projects(data)
    _validate_languages(data)
    _deduplicate_sections(data)
    _rescore_experience_entries(data)
    _redistribute_misc(data)
    _validate_section_placement(data)
    _eject_false_education(data)
    _elapsed = time.perf_counter() - _t0
    if _elapsed > _RESOLVER_TIMEOUT_SECONDS:
        logger.warning("resolve_parsed: slow execution %.2fs (limit %.1fs)",
                       _elapsed, _RESOLVER_TIMEOUT_SECONDS)


# ── 1. Experience → Education ─────────────────────────────────────────────

def _fixup_experience_to_education(data: Dict) -> None:
    """Move experience entries that look like education (degree/gpa,
    not institution alone) into the education section.

    Strict: degree+institution+year → education regardless of bullets.
    Requires degree OR gpa keyword — institution alone is not enough.
    """
    experiences = data.get("experiences")
    education = data.get("education")

    if not isinstance(experiences, list):
        experiences = []
    if not isinstance(education, list):
        education = []

    kept_exp: list = []
    for exp in experiences:
        if not isinstance(exp, dict):
            kept_exp.append(exp)
            continue
        text = _dict_text(exp)
        has_degree = bool(_DEGREE_RE.search(text))
        has_institution = bool(_INSTITUTION_RE.search(text))
        has_year = bool(_YEAR_RE.search(text))
        has_gpa = bool(_GPA_RE.search(text))
        bullets = exp.get("bullets") or []
        # degree + institution + year → always education
        is_edu = has_degree and has_institution and has_year
        # degree + year with no bullets → education
        if not is_edu:
            is_edu = has_degree and has_year and len(bullets) == 0
        # gpa + (institution or year) → education
        if not is_edu:
            is_edu = has_gpa and (has_institution or has_year)
        # institution alone without degree/gpa → NOT education
        if is_edu:
            education.append({
                "degree": exp.get("title", ""),
                "school": exp.get("company", ""),
                "location": exp.get("location", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "gpa": "",
                "field": "",
            })
            logger.debug("parsed: exp→edu %r", exp.get("title", ""))
        else:
            kept_exp.append(exp)
    data["experiences"] = kept_exp
    data["education"] = education


def _eject_false_education(data: Dict) -> None:
    """Eject education entries that are actually activities, clubs, or unrelated."""
    education = data.get("education")
    if not isinstance(education, list) or not education:
        return
        
    kept_edu = []
    misc_list = data.get("misc")
    if not isinstance(misc_list, list):
        misc_list = []
        data["misc"] = misc_list
        
    for edu in education:
        if not isinstance(edu, dict):
            kept_edu.append(edu)
            continue
            
        text = _dict_text(edu).lower()
        
        # Activity/club signals
        is_activity = bool(re.search(r"\b(member|club|band|volleyball|basketball|football|soccer|choir|intramural|society|association)\b", text))
        
        has_degree = bool(_DEGREE_RE.search(text))
        has_gpa = bool(_GPA_RE.search(text))
        
        if is_activity and not has_degree and not has_gpa:
            # Eject to misc
            flat = edu.get("school", "") or edu.get("degree", "") or _dict_text(edu)
            if flat and flat.strip():
                misc_list.append(flat.strip())
            logger.debug("parsed: ejected false education %r", flat[:40])
            continue
            
        kept_edu.append(edu)
        
    data["education"] = kept_edu


# ── 2. Skills cleanup ────────────────────────────────────────────────────

def _cleanup_skills(data: Dict) -> None:
    """Remove skill items with URLs, years, or long sentences.

    Strict: >6 words allowed if delimiter OR tech OR colon present.
    """
    skills = data.get("skills")
    if isinstance(skills, list):
        cleaned: list[str] = []
        for s in skills:
            if not isinstance(s, str) or not s.strip():
                continue
            if _URL_RAW_RE.search(s):
                continue
            if re.match(r"^\d{4}\s*[-\u2013]\s*", s):
                continue
            words = s.split()
            has_delim = bool(_SKILL_DELIM_RE.search(s))
            has_tech = bool(_TECH_RAW_RE.search(s))
            has_colon = ":" in s
            # Short token, or has delimiter/tech/colon → keep
            if len(words) <= 6 or has_delim or has_tech or has_colon:
                cleaned.append(s)
            else:
                logger.debug("parsed: ejected long skill %r (%d words)",
                             s[:40], len(words))
        data["skills"] = cleaned


# ── 2b. Projects enforcement — must contain url or tech ──────────────────

def _enforce_projects(data: Dict) -> None:
    """Eject project entries that lack structural project signals → misc.

    Keep if: url OR tech OR bullets OR action verbs OR (title + bullets).
    If projects came from an explicit header (source == "header"), keep all.
    """
    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        return

    # Header authority: if projects section came from an explicit header, keep all
    sources = data.get("_section_sources") or {}
    if sources.get("projects") == "header":
        return

    kept: list = []
    for proj in projects:
        if not isinstance(proj, dict):
            kept.append(proj)
            continue
        text = _dict_text(proj)
        has_url = bool(_URL_RAW_RE.search(text))
        has_tech = bool(_TECH_RAW_RE.search(text))
        has_bullets = bool(proj.get("bullets"))
        has_verbs = bool(_ACTION_VERB_RE.search(text))
        has_title = bool((proj.get("name") or "").strip())
        # Keep if any structural signal is present
        if has_url or has_tech or has_bullets or has_verbs or (has_title and has_bullets):
            kept.append(proj)
        else:
            # Eject to misc as flattened text
            misc_list = data.get("misc")
            if not isinstance(misc_list, list):
                misc_list = []
                data["misc"] = misc_list
            flat = proj.get("name", "") or proj.get("description", "")
            if flat and flat.strip():
                misc_list.append(flat.strip())
            logger.debug("parsed: ejected project %r (no structural signal)",
                         proj.get("name", "")[:40])
    data["projects"] = kept


# ── 3. Language validation ───────────────────────────────────────────────

def _validate_languages(data: Dict) -> None:
    """Keep only plausible language entries."""
    languages = data.get("languages")
    if isinstance(languages, list):
        data["languages"] = [
            lang for lang in languages
            if isinstance(lang, (str, dict))
            and (isinstance(lang, dict) or (
                lang.strip()
                and len(lang.strip()) > 1
                and not re.match(r"^[\d\W]+$", lang.strip())
                and "@" not in lang
                and not re.match(r"https?://", lang, re.I)
            ))
        ]


# ── 4. Deduplication ────────────────────────────────────────────────────

def _deduplicate_sections(data: Dict) -> None:
    """Merge duplicate entries in dict-list sections."""
    for key in ("education", "experiences", "projects", "certifications"):
        items = data.get(key)
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            continue
        seen: set = set()
        deduped: list = []
        for item in items:
            vals = [str(v).strip().lower() for v in item.values()
                    if isinstance(v, str) and v.strip()][:2]
            k = "|".join(vals)
            if k and k not in seen:
                seen.add(k)
                deduped.append(item)
            elif not k:
                deduped.append(item)
        data[key] = deduped


# ── 5. Score-based experience re-evaluation ──────────────────────────────

def _rescore_experience_entries(data: Dict) -> None:
    """Re-score each experience entry; if it scores higher as education
    or contact, move it there."""
    from utils.section_scorer import (
        score_dict_entry, locked_sections,
        LOCKED_MIN_SCORE, LOCKED_MIN_MARGIN,
    )

    experiences = data.get("experiences")
    if not isinstance(experiences, list) or not experiences:
        return

    locked = locked_sections(data.get("section_titles"))
    exp_locked = "experience" in locked
    min_s = LOCKED_MIN_SCORE if exp_locked else 0.35
    min_m = LOCKED_MIN_MARGIN if exp_locked else 0.10

    kept_exp: list = []
    for exp in experiences:
        if not isinstance(exp, dict):
            kept_exp.append(exp)
            continue

        scores = score_dict_entry(exp)
        best = scores.best()

        if (best == "education"
                and scores.education >= min_s
                and scores.education - scores.experience >= min_m):
            edu_list = data.get("education")
            if not isinstance(edu_list, list):
                edu_list = []
                data["education"] = edu_list
            edu_list.append({
                "degree": exp.get("title", ""),
                "school": exp.get("company", ""),
                "location": exp.get("location", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "gpa": "",
                "field": "",
            })
        elif (best == "contact"
              and scores.contact >= min_s
              and scores.contact - scores.experience >= min_m):
            # Let normalizer handle contact routing — just drop from experience
            pass
        else:
            kept_exp.append(exp)

    data["experiences"] = kept_exp


# ── 6. Score-based misc redistribution ────────────────────────────────────

def _redistribute_misc(data: Dict) -> None:
    """Move misc items into proper sections using multi-signal scoring."""
    from utils.section_scorer import (
        score_text, locked_sections,
        LOCKED_MIN_SCORE, LOCKED_MIN_MARGIN,
    )

    misc = data.get("misc")
    if not isinstance(misc, list) or not misc:
        return

    # Security: cap iteration count
    if len(misc) > _MAX_ITERATIONS:
        logger.warning("redistribute_misc: items capped %d → %d", len(misc), _MAX_ITERATIONS)
        misc = misc[:_MAX_ITERATIONS]
        data["misc"] = misc

    locked = locked_sections(data.get("section_titles"))
    misc_locked = "misc" in locked

    _MIN_SCORE = LOCKED_MIN_SCORE if misc_locked else 0.30
    _MARGIN = LOCKED_MIN_MARGIN if misc_locked else 0.08

    _ALLOWED_TARGETS = {
        "education", "certifications", "projects", "interests",
        "skills", "languages", "contact",
    }

    kept_misc: list = []
    for item in misc:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()

        scores = score_text(text)
        best = scores.best()
        best_val = scores.best_score()

        if best_val < _MIN_SCORE or best not in _ALLOWED_TARGETS:
            kept_misc.append(text)
            continue

        all_scores = sorted(scores.as_dict().values(), reverse=True)
        runner_up = all_scores[1] if len(all_scores) > 1 else 0.0
        if best_val - runner_up < _MARGIN:
            kept_misc.append(text)
            continue

        if best == "skills" and len(text.split()) > 6:
            has_delim = bool(_SKILL_DELIM_RE.search(text))
            has_tech = bool(_TECH_RE.search(text))
            has_colon = ":" in text
            if not (has_delim or has_tech or has_colon):
                kept_misc.append(text)
                continue

        _route_misc_item(data, best, text)
        continue

    # Second pass: pattern-based rescue
    final_misc: list = []
    for text in kept_misc:
        section = _detect_structured_pattern(text, data)
        if section is None:
            final_misc.append(text)

    data["misc"] = final_misc


def _route_misc_item(data: Dict, target: str, text: str) -> None:
    """Route a single misc item to *target* section."""
    if target == "education":
        edu_list = data.get("education")
        if not isinstance(edu_list, list):
            edu_list = []
            data["education"] = edu_list
        edu_list.append({
            "degree": (_DEGREE_RE.search(text).group(0) if _DEGREE_RE.search(text) else ""),
            "school": text,
            "start_date": _YEAR_RE.findall(text)[0] if _YEAR_RE.findall(text) else "",
            "end_date": "",
            "gpa": "",
            "field": "",
            "location": "",
        })
    elif target == "certifications":
        cert_list = data.get("certifications")
        if not isinstance(cert_list, list):
            cert_list = []
            data["certifications"] = cert_list
        cert_list.append({"name": text, "issuer": "", "date": ""})
    elif target == "projects":
        proj_list = data.get("projects")
        if not isinstance(proj_list, list):
            proj_list = []
            data["projects"] = proj_list
        proj_list.append({"name": text[:80], "description": text, "bullets": []})
    elif target == "interests":
        interest_list = data.get("interests")
        if not isinstance(interest_list, list):
            interest_list = []
            data["interests"] = interest_list
        interest_list.append(text)
    elif target == "skills":
        skills_list = data.get("skills")
        if not isinstance(skills_list, list):
            skills_list = []
            data["skills"] = skills_list
        skills_list.append(text)
    elif target == "languages":
        lang_list = data.get("languages")
        if not isinstance(lang_list, list):
            lang_list = []
            data["languages"] = lang_list
        lang_list.append(text)


def _detect_structured_pattern(text: str, data: Dict) -> str | None:
    """Try to rescue *text* into a proper section using hard patterns.

    Returns the target section name if the item was moved, or ``None``
    if it should stay in misc.
    """
    has_degree = bool(_DEGREE_RE.search(text))
    has_institution = bool(_INSTITUTION_RE.search(text))
    has_year = bool(_YEAR_RE.search(text))
    has_gpa = bool(_GPA_RE.search(text))
    tech_hits = _TECH_RE.findall(text)
    word_count = len(text.split())

    # Education: degree OR gpa required (institution alone not enough)
    if (has_degree or has_gpa) and (has_institution or has_year):
        _route_misc_item(data, "education", text)
        return "education"

    # Skills: 3+ tech names (comma/slash-delimited)
    if len(tech_hits) >= 3 and word_count <= 20:
        skills_list = data.get("skills")
        if not isinstance(skills_list, list):
            skills_list = []
            data["skills"] = skills_list
        parts = re.split(r"[,;|/]+", text)
        for part in parts:
            clean = part.strip()
            if clean:
                skills_list.append(clean)
        return "skills"

    # Interests: hobby/interest keywords
    if _INTEREST_RE.search(text) and word_count <= 10:
        _route_misc_item(data, "interests", text)
        return "interests"

    # Languages: structural detection (CEFR / level / sub-skill)
    from utils.section_scorer import is_language_entry
    if is_language_entry(text, strict=True) and word_count <= 8:
        _route_misc_item(data, "languages", text)
        return "languages"

    return None


# ── 7. Score-based section validation ────────────────────────────────────

def _validate_section_placement(data: Dict) -> None:
    """Re-score items in education, skills, interests, languages.
    Move misplaced items to their best-scoring section."""
    from utils.section_scorer import (
        score_text, score_dict_entry, locked_sections,
        LOCKED_MIN_SCORE, LOCKED_MIN_MARGIN,
    )

    locked = locked_sections(data.get("section_titles"))

    def _thresholds(section_key: str):
        is_locked = section_key in locked
        ms = LOCKED_MIN_SCORE if is_locked else 0.35
        mm = LOCKED_MIN_MARGIN if is_locked else 0.10
        return ms, mm

    # Education items that might be experience
    edu_list = data.get("education")
    if isinstance(edu_list, list) and edu_list:
        if len(edu_list) > _MAX_ITERATIONS:
            logger.warning("validate_placement: education capped %d → %d", len(edu_list), _MAX_ITERATIONS)
            edu_list = edu_list[:_MAX_ITERATIONS]
            data["education"] = edu_list
        min_s, min_m = _thresholds("education")
        kept_edu: list = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                kept_edu.append(edu)
                continue
            scores = score_dict_entry(edu)
            best = scores.best()
            if (best == "experience"
                    and scores.experience >= min_s
                    and scores.experience - scores.education >= min_m):
                exp_list = data.get("experiences")
                if not isinstance(exp_list, list):
                    exp_list = []
                    data["experiences"] = exp_list
                exp_list.append({
                    "title": edu.get("degree", ""),
                    "company": edu.get("school", ""),
                    "location": edu.get("location", ""),
                    "start_date": edu.get("start_date", ""),
                    "end_date": edu.get("end_date", ""),
                    "bullets": [],
                })
            else:
                kept_edu.append(edu)
        data["education"] = kept_edu

    # Flat list sections: skills, interests, languages
    _FLAT_SECTION_MAP = {
        "skills": {"education", "certifications", "languages", "interests"},
        "interests": {"skills", "languages"},
        "languages": {"skills", "interests"},
    }
    for section_key, allowed_targets in _FLAT_SECTION_MAP.items():
        items = data.get(section_key)
        if not isinstance(items, list) or not items:
            continue
        if len(items) > _MAX_ITERATIONS:
            logger.warning("validate_placement: %s capped %d → %d",
                           section_key, len(items), _MAX_ITERATIONS)
            items = items[:_MAX_ITERATIONS]
            data[section_key] = items
        min_s, min_m = _thresholds(section_key)
        kept: list = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                continue
            scores = score_text(item.strip())
            best = scores.best()
            best_val = scores.best_score()
            margin = scores.margin()
            if (best != section_key and best in allowed_targets
                    and best_val >= min_s and margin >= min_m):
                target_list = data.get(best)
                if not isinstance(target_list, list):
                    target_list = []
                    data[best] = target_list
                target_list.append(item.strip())
            else:
                kept.append(item)
        data[section_key] = kept
