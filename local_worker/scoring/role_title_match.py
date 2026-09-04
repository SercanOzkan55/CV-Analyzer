"""Role/title-match criterion (ported from services/pipeline_runtime.py).

Ported: ``_title_match_score``, ``_seniority_match_score``,
``_detect_seniority`` (and the small ``_extract_probable_job_title``
helper they depend on), originally around lines 602-724 of
``services/pipeline_runtime.py``.

The source file combines title_match and seniority_match with other
signals (keyword coverage, experience) inside a larger weighted formula
(``_build_match_score_v2``, ~line 827: ``title_match * 0.20 + seniority_match
* 0.15`` alongside two other terms) — there's no standalone formula that
combines just these two. Per the plan, this module averages them 50/50
to produce one ``role_title_match_score``.
"""

import re


def clean_lower(text: str) -> str:
    """Locale-independent lowercasing (mirrors language_service.clean_lower)."""
    if not text:
        return ""
    text = text.replace("İ", "i")
    lowered = text.lower()
    lowered = lowered.replace("i̇", "i").replace("i̇", "i")
    return lowered


def _extract_probable_job_title(text: str) -> str:
    source = str(text or "")
    patterns = [
        r"\b(?:hiring|looking for|seeking|position|role)\s+(?:a|an)?\s*([A-Za-z][A-Za-z0-9\-\s]{3,60})",
        r"\b([A-Za-z][A-Za-z0-9\-\s]{3,60})\s+(?:position|role)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.I)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip(" -:;,.\t\n")
            if title:
                return title
    return ""


def _title_match_score(cv_text: str, job_description: str) -> float:
    title = _extract_probable_job_title(job_description)
    if not title:
        return 50.0
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_cv = re.sub(r"[^a-z0-9]+", " ", str(cv_text or "").lower())
    if normalized_title and normalized_title in normalized_cv:
        return 100.0
    title_tokens = {tok for tok in normalized_title.split() if len(tok) > 2}
    if not title_tokens:
        return 50.0
    cv_tokens = set(normalized_cv.split())
    overlap = len(title_tokens & cv_tokens)
    return round((overlap / max(1, len(title_tokens))) * 100.0, 2)


_SENIORITY_PATTERNS = {
    "intern": [
        "intern", "internship", "trainee", "stajyer", "praktikant", "stagiaire",
        "pasante", "becario", "tirocinante", "practicante",
    ],
    "junior": [
        "junior", "entry level", "entry-level", "associate", "júnior",
        "juniorentwickler", "débutant", "debutant", "principiante",
    ],
    "mid": [
        "mid", "mid level", "mid-level", "intermediate", "regular", "mittelstufe",
        "confirmé", "confirme", "intermedio",
    ],
    "senior": [
        "senior", "lead", "principal", "staff", "experienced", "kıdemli", "kidemli",
        "leiter", "chef", "responsable", "avanzado",
    ],
    "manager": [
        "manager", "head", "director", "vp", "chief", "yönetici", "yonetici",
        "müdür", "mudur", "geschäftsführer", "directeur", "gerente", "jefe", "diretor",
    ],
}

_SENIORITY_RANK = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "manager": 5}


def _detect_seniority(text: str) -> str:
    lowered = clean_lower(text or "")
    for level, patterns in _SENIORITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(r"\b" + re.escape(pattern) + r"\b", lowered):
                return level
    return "unknown"


def _seniority_match_score(cv_text: str, job_description: str) -> float:
    jd_level = _detect_seniority(job_description)
    cv_level = _detect_seniority(cv_text)
    if jd_level == "unknown" or cv_level == "unknown":
        return 60.0
    if jd_level == cv_level:
        return 100.0

    distance = abs(_SENIORITY_RANK.get(jd_level, 3) - _SENIORITY_RANK.get(cv_level, 3))
    if distance == 1:
        return 75.0
    if distance == 2:
        return 55.0
    return 35.0


def role_title_match_score(cv_text: str, job_description: str) -> float:
    """Combine title match and seniority match into one 0-100 score."""
    title_match = _title_match_score(cv_text, job_description)
    seniority_match = _seniority_match_score(cv_text, job_description)
    return round((title_match + seniority_match) / 2.0, 2)
