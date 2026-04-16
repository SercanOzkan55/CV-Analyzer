import difflib
import re
from typing import Dict, List

from .ats_service import analyze_cv
from .skill_service import extract_skills
from . import rewrite_service


MAX_INPUT_CHARS = 20000
SUMMARY_MAX_CHARS = 500

SECTION_ALIASES = {
    "summary": {
        "summary",
        "professional summary",
        "profile",
        "about",
        "objective",
        "career summary",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
    },
    "education": {"education", "academic background", "qualifications"},
    "skills": {
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "technologies",
    },
    "projects": {"projects", "project experience"},
    "certifications": {"certifications", "certificates", "licenses"},
    "languages": {"languages", "language skills"},
    "contact": {"contact", "contact information"},
}

NOISE_SECTION_ALIASES = {
    "references",
    "hobbies",
    "interests",
    "personal details",
    "personal information",
    "marital status",
    "date of birth",
    "birth date",
    "nationality",
    "photo",
}

SECTION_ORDER = [
    "summary",
    "experience",
    "education",
    "skills",
    "certifications",
    "projects",
    "languages",
]

SECTION_TITLES = {
    "summary": "PROFESSIONAL SUMMARY",
    "experience": "EXPERIENCE",
    "education": "EDUCATION",
    "skills": "SKILLS",
    "certifications": "CERTIFICATIONS",
    "projects": "PROJECTS",
    "languages": "LANGUAGES",
}


def _guard_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(value) > MAX_INPUT_CHARS:
        value = value[:MAX_INPUT_CHARS]
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def _normalize_heading(line: str) -> str:
    normalized = re.sub(r"[^a-zA-Z ]+", " ", line).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if not heading:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return canonical
    return None


def _noise_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if heading in NOISE_SECTION_ALIASES:
        return heading
    return None


def _clean_lines(text: str) -> List[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    compact: List[str] = []
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


def _parse_sections(cv_text: str) -> tuple[list[str], Dict[str, List[str]], List[str]]:
    header_lines: List[str] = []
    sections: Dict[str, List[str]] = {key: [] for key in SECTION_ALIASES}
    dropped_sections: List[str] = []
    current: str | None = None
    dropping = False

    for raw_line in _clean_lines(cv_text):
        if not raw_line:
            if current and not dropping and sections[current] and sections[current][-1] != "":
                sections[current].append("")
            continue

        canonical = _canonical_section(raw_line)
        if canonical:
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

    return header_lines, sections, sorted(set(dropped_sections))


def _extract_contact_block(header_lines: List[str], explicit_lines: List[str]) -> tuple[str | None, List[str], List[str]]:
    lines = [line for line in header_lines + explicit_lines if line]
    name = None
    contacts: List[str] = []
    leftovers: List[str] = []

    for index, line in enumerate(lines):
        if index == 0 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,80}", line) and not re.search(r"\d|@|http", line):
            name = line
            continue
        if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I):
            contacts.append(line)
            continue
        if re.search(r"(?:\+?\d[\d()\- ]{7,}\d)", line):
            contacts.append(line)
            continue
        if any(token in line.lower() for token in ("linkedin", "github", "portfolio", "http://", "https://")):
            contacts.append(line)
            continue
        leftovers.append(line)

    return name, contacts, leftovers


def _extract_skill_names(skill_result: dict) -> List[str]:
    if not isinstance(skill_result, dict):
        return []
    if "found" in skill_result:
        found = skill_result.get("found") or []
        return sorted(str(item).strip() for item in found if str(item).strip())

    values: List[str] = []
    for key in ("all_skills", "technical_skills", "soft_skills"):
        raw = skill_result.get(key) or []
        values.extend(str(item).strip() for item in raw if str(item).strip())
    deduped = []
    seen = set()
    for item in values:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _sentences_from_line(line: str) -> List[str]:
    if line.startswith(("- ", "* ", "• ")):
        return [line[2:].strip()]
    if len(line) < 90:
        return [line]
    parts = re.split(r"(?<=[.!?])\s+", line)
    return [part.strip(" -") for part in parts if part.strip(" -")]


def _normalize_experience(lines: List[str]) -> List[str]:
    result: List[str] = []
    for line in lines:
        if not line:
            continue
        if re.search(r"\b(?:19|20)\d{2}\b", line) or "present" in line.lower():
            result.append(line)
            continue
        if len(line.split()) <= 8 and not line.startswith(("- ", "* ", "• ")):
            result.append(line)
            continue
        for sentence in _sentences_from_line(line):
            if sentence:
                result.append(f"- {sentence}")
    return result


def _normalize_list_section(lines: List[str]) -> List[str]:
    items: List[str] = []
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
    deduped: List[str] = []
    seen = set()
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _normalize_summary(summary_lines: List[str], fallback_lines: List[str], preferred_skills: List[str]) -> str:
    summary = " ".join(line for line in summary_lines if line).strip()
    if not summary:
        summary = " ".join(line for line in fallback_lines[:2] if line).strip()
    if not summary and preferred_skills:
        top_skills = ", ".join(preferred_skills[:6])
        summary = f"Core skills: {top_skills}."
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[: SUMMARY_MAX_CHARS - 3].rstrip() + "..."
    return summary


def _ordered_skills(cv_text: str, explicit_skill_lines: List[str], job_description: str) -> List[str]:
    explicit = _normalize_list_section(explicit_skill_lines)
    cv_skills = _extract_skill_names(extract_skills(cv_text))
    job_skills = set(skill.lower() for skill in _extract_skill_names(extract_skills(job_description)))

    combined = explicit + [skill for skill in cv_skills if skill.lower() not in {item.lower() for item in explicit}]
    matched = [skill for skill in combined if skill.lower() in job_skills]
    rest = [skill for skill in combined if skill.lower() not in job_skills]
    return matched + rest


def _build_structured_cv(cv_text: str, job_description: str = "") -> tuple[str, Dict[str, List[str]], List[str]]:
    header_lines, sections, dropped_sections = _parse_sections(cv_text)
    name, contacts, leftover_header = _extract_contact_block(header_lines, sections.get("contact", []))

    experience_lines = _normalize_experience(sections.get("experience", []))
    education_lines = [line for line in sections.get("education", []) if line]
    certification_lines = [line for line in sections.get("certifications", []) if line]
    project_lines = _normalize_experience(sections.get("projects", []))
    language_lines = _normalize_list_section(sections.get("languages", []))
    skills = _ordered_skills(cv_text, sections.get("skills", []), job_description)
    summary = _normalize_summary(sections.get("summary", []), leftover_header, skills)

    output_lines: List[str] = []
    if name:
        output_lines.append(name)
    if contacts:
        output_lines.append(" | ".join(contacts[:4]))

    structured_sections: Dict[str, List[str]] = {}
    if summary:
        structured_sections["summary"] = [summary]
    if experience_lines:
        structured_sections["experience"] = experience_lines
    if education_lines:
        structured_sections["education"] = education_lines
    if skills:
        structured_sections["skills"] = [", ".join(skills[:20])]
    if certification_lines:
        structured_sections["certifications"] = certification_lines
    if project_lines:
        structured_sections["projects"] = project_lines
    if language_lines:
        structured_sections["languages"] = language_lines

    if output_lines:
        output_lines.append("")

    for key in SECTION_ORDER:
        values = structured_sections.get(key) or []
        if not values:
            continue
        output_lines.append(SECTION_TITLES[key])
        output_lines.extend(values)
        output_lines.append("")

    structured_text = "\n".join(line for line in output_lines).strip()
    return structured_text, structured_sections, dropped_sections


def _render_structured_sections(
    name: str | None,
    contacts: List[str],
    structured_sections: Dict[str, List[str]],
) -> str:
    output_lines: List[str] = []
    if name:
        output_lines.append(name)
    if contacts:
        output_lines.append(" | ".join(contacts[:4]))
    if output_lines:
        output_lines.append("")

    for key in SECTION_ORDER:
        values = [value for value in (structured_sections.get(key) or []) if value]
        if not values:
            continue
        output_lines.append(SECTION_TITLES[key])
        output_lines.extend(values)
        output_lines.append("")

    return "\n".join(output_lines).strip()


_BOOST_ACTION_VERBS = [
    "led", "managed", "developed", "implemented", "designed", "delivered",
    "optimized", "created", "improved", "built", "launched", "coordinated",
    "established", "streamlined", "executed", "analyzed", "achieved",
    "automated", "resolved", "maintained", "collaborated", "configured",
    "integrated", "deployed", "enhanced", "reduced", "increased",
    "spearheaded", "architected", "engineered",
]

# Full set of action verbs (from ats_service) for detection purposes
_ALL_ACTION_VERBS = set(_BOOST_ACTION_VERBS) | {
    "directed", "supervised", "oversaw", "orchestrated", "mentored", "coached",
    "exceeded", "surpassed", "earned", "won", "awarded",
    "founded", "initiated", "introduced", "pioneered",
    "upgraded", "refactored", "modernized", "revamped", "transformed", "accelerated",
    "assessed", "evaluated", "researched", "investigated", "identified",
    "diagnosed", "audited", "reviewed", "benchmarked",
    "shipped", "completed",
    "expanded", "scaled", "grew", "generated", "boosted",
    "decreased", "minimized", "eliminated", "consolidated", "cut", "saved",
    "presented", "communicated", "negotiated", "facilitated", "documented",
    "reported", "trained", "taught", "educated",
    "programmed", "migrated", "containerized", "provisioned", "instrumented",
}


def _starts_with_action_verb(line: str) -> bool:
    """Check if a bullet line already starts with a recognized action verb."""
    cleaned = re.sub(r"^[-•*]\s*", "", line).strip().lower()
    first_word = cleaned.split()[0] if cleaned.split() else ""
    for verb in _ALL_ACTION_VERBS:
        if re.match(r"\b" + re.escape(verb) + r"(?:s|ed|ing|d)?\b", first_word):
            return True
    return False


def _add_action_verb_to_bullet(line: str, used_verbs: set) -> str:
    """Prepend a diverse action verb to a bullet that lacks one."""
    cleaned = re.sub(r"^[-•*]\s*", "", line).strip()
    if not cleaned:
        return line
    # Pick a verb not recently used for diversity
    available = [v for v in _BOOST_ACTION_VERBS if v not in used_verbs]
    if not available:
        available = _BOOST_ACTION_VERBS[:10]
    verb = available[0]
    used_verbs.add(verb)
    # Capitalize verb, lowercase the original start
    first_char = cleaned[0].lower() if cleaned[0].isupper() else cleaned[0]
    return f"- {verb.capitalize()} {first_char}{cleaned[1:]}"


def _ensure_bullet_format(line: str) -> str:
    """Normalize bullet markers to consistent '- ' style."""
    stripped = line.strip()
    if stripped.startswith("• "):
        return "- " + stripped[2:]
    if stripped.startswith("* "):
        return "- " + stripped[2:]
    if stripped.startswith("-") and not stripped.startswith("- "):
        return "- " + stripped[1:].lstrip()
    return line


def _boost_keywords(
    structured_text: str,
    structured_sections: Dict[str, List[str]],
    job_description: str,
) -> str:
    header_lines, parsed_sections, _ = _parse_sections(structured_text)
    name, contacts, _ = _extract_contact_block(header_lines, parsed_sections.get("contact", []))

    cv_skills = _extract_skill_names(extract_skills(structured_text))
    job_skills = _extract_skill_names(extract_skills(job_description))
    overlaps = [skill for skill in job_skills if skill.lower() in {v.lower() for v in cv_skills}]

    boosted_sections = {key: list(values) for key, values in structured_sections.items()}

    # 1) Enrich summary with keyword overlap (idempotent — skip if already present)
    summary_lines = list(boosted_sections.get("summary", []))
    if job_description.strip() and overlaps:
        reinforcement = f"Relevant strengths include {', '.join(overlaps[:6])}."
        # Check if any "Relevant strengths include" phrase already exists
        already_has = any("relevant strengths include" in (s or "").lower() for s in summary_lines)
        if not already_has:
            if summary_lines:
                summary_lines[0] = f"{summary_lines[0].rstrip('.')}. {reinforcement}".strip()
            else:
                summary_lines = [reinforcement]
    boosted_sections["summary"] = summary_lines

    # 2) Re-order skills: job-matching first
    if job_description.strip():
        current_skills = _normalize_list_section(boosted_sections.get("skills", []))
        overlap_set = {s.lower() for s in overlaps}
        merged = overlaps + [s for s in current_skills if s.lower() not in overlap_set]
        if merged:
            boosted_sections["skills"] = [", ".join(merged[:20])]

    # 3) Add action verbs to experience bullets that lack them
    experience_lines = list(boosted_sections.get("experience", []))
    used_verbs: set = set()
    new_experience: List[str] = []
    for line in experience_lines:
        if not line or not line.startswith("- "):
            new_experience.append(line)
            continue
        if _starts_with_action_verb(line):
            new_experience.append(_ensure_bullet_format(line))
            continue
        new_experience.append(_add_action_verb_to_bullet(line, used_verbs))
    boosted_sections["experience"] = new_experience

    # Also boost project bullets
    project_lines = list(boosted_sections.get("projects", []))
    new_projects: List[str] = []
    for line in project_lines:
        if not line or not line.startswith("- "):
            new_projects.append(line)
            continue
        if _starts_with_action_verb(line):
            new_projects.append(_ensure_bullet_format(line))
            continue
        new_projects.append(_add_action_verb_to_bullet(line, used_verbs))
    boosted_sections["projects"] = new_projects

    # 4) Normalize all bullet markers to "- " for formatting consistency
    for section_key in ("experience", "projects", "certifications"):
        lines = boosted_sections.get(section_key, [])
        boosted_sections[section_key] = [_ensure_bullet_format(l) for l in lines]

    # 5) Ensure required sections exist (even if minimal)
    if not boosted_sections.get("skills"):
        if cv_skills:
            boosted_sections["skills"] = [", ".join(cv_skills[:15])]
    if not boosted_sections.get("summary"):
        top = cv_skills[:6] if cv_skills else overlaps[:6]
        if top:
            boosted_sections["summary"] = [f"Professional with expertise in {', '.join(top)}."]

    return _render_structured_sections(name, contacts, boosted_sections)


def _parse_experience_entries(lines: List[str]) -> List[Dict]:
    entries: List[Dict] = []
    current: Dict | None = None
    for line in lines:
        if not line:
            continue
        if line.startswith("- "):
            if current is None:
                current = {"title": "Experience", "company": "", "location": "", "start_date": "", "end_date": "", "bullets": []}
                entries.append(current)
            current.setdefault("bullets", []).append(line[2:].strip())
            continue
        if current is None or current.get("title") or current.get("bullets"):
            current = {
                "title": line,
                "company": "",
                "location": "",
                "start_date": "",
                "end_date": "",
                "bullets": [],
            }
            entries.append(current)
            continue
    return [entry for entry in entries if entry.get("title") or entry.get("bullets")]


def _parse_education_entries(lines: List[str]) -> List[Dict]:
    entries: List[Dict] = []
    for line in lines:
        if not line:
            continue
        entries.append(
            {
                "degree": line,
                "school": "",
                "location": "",
                "start_date": "",
                "end_date": "",
                "gpa": "",
                "field": "",
            }
        )
    return entries


def _parse_project_entries(lines: List[str]) -> List[Dict]:
    entries: List[Dict] = []
    current: Dict | None = None
    for line in lines:
        if not line:
            continue
        if line.startswith("- "):
            if current is None:
                current = {"name": "Project", "description": "", "bullets": []}
                entries.append(current)
            current.setdefault("bullets", []).append(line[2:].strip())
            continue
        current = {"name": line, "description": "", "bullets": []}
        entries.append(current)
    return entries


def structured_text_to_builder_payload(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
) -> Dict:
    cv_text = _guard_text(cv_text, "cv_text")
    header_lines, sections, _ = _parse_sections(cv_text)
    name, contacts, leftover_header = _extract_contact_block(header_lines, sections.get("contact", []))

    email = ""
    phone = ""
    location = ""
    linkedin = ""
    for line in contacts:
        if not email and re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I):
            email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I)
            email = email_match.group(0) if email_match else ""
        if not phone and re.search(r"(?:\+?\d[\d()\- ]{7,}\d)", line):
            phone_match = re.search(r"(?:\+?\d[\d()\- ]{7,}\d)", line)
            phone = phone_match.group(0) if phone_match else ""
        if not linkedin and any(token in line.lower() for token in ("linkedin", "github", "portfolio", "http://", "https://")):
            linkedin = line

    if leftover_header:
        location = leftover_header[0]

    skills = _normalize_list_section(sections.get("skills", []))
    languages = _normalize_list_section(sections.get("languages", []))
    certifications = [{"name": line, "issuer": "", "date": ""} for line in sections.get("certifications", []) if line]

    return {
        "full_name": name or "Optimized CV",
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "summary": _normalize_summary(sections.get("summary", []), leftover_header, skills),
        "experiences": _parse_experience_entries(_normalize_experience(sections.get("experience", []))),
        "education": _parse_education_entries([line for line in sections.get("education", []) if line]),
        "skills": skills,
        "certifications": certifications,
        "projects": _parse_project_entries(_normalize_experience(sections.get("projects", []))),
        "languages": languages,
        "job_description": job_description or "",
        "template": "classic",
        "output_format": "docx",
        "lang": lang,
    }


def _diff_preview(before_text: str, after_text: str) -> List[str]:
    diff = difflib.unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile="original",
        tofile="optimized",
        lineterm="",
    )
    return list(diff)[:120]


def auto_fix_cv_text(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    use_ai: bool = True,
) -> Dict:
    cv_text = _guard_text(cv_text, "cv_text")
    job_description = (job_description or "").strip()

    before_ats = analyze_cv(cv_text, job_description, lang=lang)
    structured_text, structured_sections, dropped_sections = _build_structured_cv(
        cv_text, job_description
    )
    structured_ats = analyze_cv(structured_text, job_description, lang=lang)

    deterministic_candidate = _boost_keywords(structured_text, structured_sections, job_description)
    deterministic_ats = analyze_cv(deterministic_candidate, job_description, lang=lang)

    optimized_text = cv_text
    best_score = float(before_ats.get("overall_score", 0) or 0)
    used_ai = False
    warnings: List[str] = []

    if float(structured_ats.get("overall_score", 0) or 0) >= best_score:
        optimized_text = structured_text
        best_score = float(structured_ats.get("overall_score", 0) or 0)

    if float(deterministic_ats.get("overall_score", 0) or 0) >= best_score:
        optimized_text = deterministic_candidate
        best_score = float(deterministic_ats.get("overall_score", 0) or 0)

    if use_ai and rewrite_service.ai_rewrite_available():
        try:
            candidate = rewrite_service.rewrite_cv_for_ats(
                cv_text=optimized_text,
                job_description=job_description,
                lang=lang,
            ).strip()
            if candidate:
                candidate_ats = analyze_cv(candidate, job_description, lang=lang)
                candidate_score = float(candidate_ats.get("overall_score", 0) or 0)
                if candidate_score >= best_score:
                    optimized_text = candidate
                    best_score = candidate_score
                    used_ai = True
                else:
                    warnings.append("AI rewrite was skipped because it did not improve the ATS score.")
        except Exception as exc:
            warnings.append(f"AI rewrite unavailable: {exc}")

    after_ats = analyze_cv(optimized_text, job_description, lang=lang)
    score_delta = round(
        float(after_ats.get("overall_score", 0)) - float(before_ats.get("overall_score", 0)),
        2,
    )

    return {
        "original_cv_text": cv_text,
        "optimized_cv_text": optimized_text,
        "before_ats": before_ats,
        "after_ats": after_ats,
        "score_delta": score_delta,
        "used_ai": used_ai,
        "dropped_sections": dropped_sections,
        "structured_sections": sorted(structured_sections.keys()),
        "warnings": warnings,
        "diff_preview": _diff_preview(cv_text, optimized_text),
        "builder_payload": structured_text_to_builder_payload(
            optimized_text,
            job_description=job_description,
            lang=lang,
        ),
    }