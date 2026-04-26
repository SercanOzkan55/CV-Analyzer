"""ATS CV Scoring — PRIMARY quality & compatibility scorer.

Takes a ``CVModel`` and produces a ``ScoreResult`` with category scores
(0–100 each) and a weighted overall score.

This is the **authoritative** scorer.  For detailed text-level analysis
(section feedback, industry tips, next-step suggestions) see
``ats_service.py``.

Usage::

    from services.ats_scoring import score_cv
    result = score_cv(cv_model)
    print(result.overall, result.structure, ...)
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from schemas.cv_model import CVModel
from utils.cv_text import build_cv_text


# ── Result model ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ScoreResult:
    overall: int
    structure: int
    keywords: int
    experience: int
    education: int
    languages: int
    ats: int
    length: int
    soft_skills: int = 0


# ── Weights for overall score ─────────────────────────────────────────────
# Defaults — overridden by ATS_WEIGHT_<KEY> env vars or ats_config.yaml.
_DEFAULT_WEIGHTS: dict[str, float] = {
    "structure": 0.18,
    "keywords": 0.14,
    "experience": 0.18,
    "education": 0.10,
    "languages": 0.05,
    "ats": 0.18,
    "length": 0.09,
    "soft_skills": 0.08,
}


def _load_weights() -> dict[str, float]:
    """Load weights from env vars, falling back to defaults.

    Env vars: ATS_WEIGHT_STRUCTURE, ATS_WEIGHT_KEYWORDS, etc.
    Values are normalized so they sum to 1.0.
    """
    weights = dict(_DEFAULT_WEIGHTS)
    for key in list(weights):
        env_val = os.getenv(f"ATS_WEIGHT_{key.upper()}")
        if env_val:
            try:
                weights[key] = float(env_val)
            except ValueError:
                pass
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        return dict(_DEFAULT_WEIGHTS)
    return {k: v / total for k, v in weights.items()}


_WEIGHTS: dict[str, float] = _load_weights()


# ── Helpers ───────────────────────────────────────────────────────────────

def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def _word_count(model: CVModel) -> int:
    """Rough word count across all text fields of the model."""
    parts: list[str] = []
    parts.append(model.summary or "")
    for exp in model.experiences:
        parts.append(exp.title)
        parts.append(exp.company)
        parts.extend(exp.bullets)
    for edu in model.education:
        parts.append(edu.degree)
        parts.append(edu.school)
        parts.append(edu.field)
    for proj in model.projects:
        parts.append(proj.name)
        parts.append(proj.description)
        parts.extend(proj.bullets)
    for cat_skills in model.skills_categorized.values():
        parts.extend(cat_skills)
    parts.extend(model.skills)
    parts.extend(model.languages)
    parts.extend(model.interests)
    parts.extend(model.misc)
    text = " ".join(p for p in parts if p)
    return len(text.split())


def _all_skills(model: CVModel) -> list[str]:
    """Return a flat deduplicated list of skills."""
    skills: list[str] = list(model.skills or [])
    for cat_skills in (model.skills_categorized or {}).values():
        skills.extend(cat_skills)
    seen: set[str] = set()
    unique: list[str] = []
    for s in skills:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _total_bullets(model: CVModel) -> int:
    count = 0
    for exp in model.experiences:
        count += len(exp.bullets)
    for proj in model.projects:
        count += len(proj.bullets)
    return count


# Unified text flattener from utils
_full_text = build_cv_text


# ── Individual scorers ────────────────────────────────────────────────────

def _score_structure(model: CVModel) -> int:
    """Reward presence of canonical sections. Max 100."""
    score = 0
    # +25 for experience (most important)
    if model.experiences:
        score += 25
    # +20 for education
    if model.education:
        score += 20
    # +20 for skills
    if _all_skills(model):
        score += 20
    # +15 for summary
    if (model.summary or "").strip():
        score += 15
    # +10 for languages
    if model.languages:
        score += 10
    # +10 for projects or certifications
    if model.projects or model.certifications:
        score += 10
    return _clamp(score)


def _score_length(model: CVModel) -> int:
    """Penalise CVs that are too short or too long."""
    wc = _word_count(model)
    if wc < 50:
        return 10
    if wc < 100:
        return 30
    if wc < 200:
        return 55
    if wc <= 800:
        return 100
    if wc <= 1200:
        return 85
    if wc <= 1500:
        return 65
    # > 1500 words — too verbose
    return 40


def _score_ats(model: CVModel) -> int:
    """ATS compatibility: penalise non-parseable patterns."""
    score = 100
    text = _full_text(model)

    # Penalty: icon / emoji / special characters that ATS can't parse
    icon_count = sum(
        1 for ch in text
        if unicodedata.category(ch).startswith(("So", "Sk"))
    )
    if icon_count > 0:
        score -= min(25, icon_count * 5)

    # Penalty: very long lines (>120 chars) suggest table/multi-column
    lines = text.split("\n")
    long_lines = sum(1 for ln in lines if len(ln) > 120)
    if long_lines > 3:
        score -= 15
    elif long_lines > 0:
        score -= 5

    # Penalty: no sections detected (flat text)
    has_exp = bool(model.experiences)
    has_edu = bool(model.education)
    has_skills = bool(_all_skills(model))
    sections_present = sum([has_exp, has_edu, has_skills])
    if sections_present == 0:
        score -= 30
    elif sections_present == 1:
        score -= 10

    # Penalty: pipe/tab characters suggesting table layout
    table_chars = text.count("|") + text.count("\t")
    if table_chars > 10:
        score -= 15
    elif table_chars > 3:
        score -= 5

    # Bonus: contact info present (email, phone)
    if model.email:
        score += 5
    if model.phone:
        score += 5

    return _clamp(score)


def _score_keywords(model: CVModel) -> int:
    """Score based on skill count. Job-match scoring added later."""
    skills = _all_skills(model)
    n = len(skills)
    if n == 0:
        return 10
    if n < 3:
        return 30
    if n < 5:
        return 50
    if n <= 10:
        return 75
    if n <= 20:
        return 90
    return 100


def _score_experience(model: CVModel) -> int:
    """Score based on experience count and bullet quality."""
    n = len(model.experiences)
    if n == 0:
        return 0
    if n == 1:
        base = 35
    elif n == 2:
        base = 55
    elif n <= 4:
        base = 75
    else:
        base = 85

    # Bullet bonus: well-described roles
    total_bullets = sum(len(e.bullets) for e in model.experiences)
    avg_bullets = total_bullets / n if n else 0
    if avg_bullets >= 4:
        base += 15
    elif avg_bullets >= 2:
        base += 10
    elif avg_bullets >= 1:
        base += 5

    # Quantified results bonus: numbers in bullets suggest measurable impact
    quant_count = sum(
        1 for e in model.experiences
        for b in e.bullets
        if re.search(r"\d+[%$€£]|\d{2,}", b)
    )
    if quant_count >= 3:
        base += 5

    return _clamp(base)


def _score_education(model: CVModel) -> int:
    """Score based on education entries and degree presence."""
    n = len(model.education)
    if n == 0:
        return 0

    base = 50 if n == 1 else 65

    # Degree bonus
    has_degree = any(
        (e.degree or "").strip() for e in model.education
    )
    if has_degree:
        base += 20

    # Field of study bonus
    has_field = any(
        (e.field or "").strip() for e in model.education
    )
    if has_field:
        base += 10

    # Date bonus
    has_dates = any(
        (e.start_date or "").strip() or (e.end_date or "").strip()
        for e in model.education
    )
    if has_dates:
        base += 5

    return _clamp(base)


def _score_languages(model: CVModel) -> int:
    """Score based on language count."""
    n = len(model.languages)
    if n == 0:
        return 0
    if n == 1:
        return 50
    if n == 2:
        return 75
    return 100


# ── Soft skills scoring ───────────────────────────────────────────────────

_SOFT_SKILL_PATTERNS = [
    r"\bleadership\b", r"\bteamwork\b", r"\bcommunication\b",
    r"\bcollaboration\b", r"\bproblem.solving\b", r"\btime.management\b",
    r"\bcritical.thinking\b", r"\badaptability\b", r"\bcreativity\b",
    r"\bmentoring\b", r"\bnegotiation\b", r"\bpresentation\b",
    r"\bstakeholder\b", r"\bcross.functional\b", r"\bstrategic\b",
    r"\binitiative\b", r"\bempathy\b", r"\bconflict.resolution\b",
]


def _score_soft_skills(model: CVModel) -> int:
    """Score based on soft skill mentions across all text."""
    text = _full_text(model).lower()
    if not text:
        return 0
    hits = sum(1 for p in _SOFT_SKILL_PATTERNS if re.search(p, text))
    # Scale: 0 hits → 0, 1-2 → 25, 3-4 → 50, 5-7 → 75, 8+ → 100
    if hits == 0:
        return 0
    if hits <= 2:
        return 25
    if hits <= 4:
        return 50
    if hits <= 7:
        return 75
    return 100


# ── Main entry point ──────────────────────────────────────────────────────

def score_cv(model: CVModel) -> ScoreResult:
    """Score a CV model across all categories.

    Returns a ``ScoreResult`` with per-category scores (0–100) and a
    weighted ``overall`` score.
    """
    scores = {
        "structure": _score_structure(model),
        "keywords": _score_keywords(model),
        "experience": _score_experience(model),
        "education": _score_education(model),
        "languages": _score_languages(model),
        "ats": _score_ats(model),
        "length": _score_length(model),
        "soft_skills": _score_soft_skills(model),
    }

    # Weighted average
    weighted = sum(scores[k] * _WEIGHTS.get(k, 0) for k in scores)
    overall = _clamp(round(weighted))

    return ScoreResult(overall=overall, **scores)
