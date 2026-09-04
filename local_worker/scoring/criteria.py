"""Scoring-criteria registry — the single source of truth for the Local
Worker's weighted CV scoring model.

Three top-level structures:

  * ``CATEGORIES`` — the 4-category budget (Skills Match / Job Fit /
    CV Quality / Background) used by the (future, Phase 3) two-level
    weight UI. ``default_weight`` here mirrors the plan's target model.
  * ``CRITERIA`` — one entry per criterion: category, label, description,
    a ``default_weight`` (see note below), and a ``scorer`` callable with
    the uniform signature ``scorer(cv_text: str, config: dict) -> float``,
    or ``None`` for the 3 criteria reserved for a later phase.
  * ``PRESETS`` — named, ready-to-apply weight distributions across all
    12 criterion keys. Every preset's weights sum to exactly 100.

Why ``CRITERIA[key]["default_weight"]`` for required_skills / nice_to_have
_skills / content_quality is 70 / 20 / 10 (their *original*, pre-Phase-2
values) rather than a share of the new 4-category split:
``worker.py::score_cv`` falls back to this exact field when a caller's
``config["scoring_weights"]`` omits a key, and the pre-existing test
``test_score_cv_honors_custom_scoring_weights`` (plus any saved job
config that predates this phase) depends on that fallback reproducing
the old 70/20/10-sums-to-100 behavior unchanged when no weights are
supplied at all. Every other (new) criterion's ``default_weight`` is
0.0 for the same reason — an old caller that never mentions the new
criteria must not suddenly have them silently activated with a nonzero
weight. This is why ``PRESETS["balanced"]`` is a **separate**, hand-authored
mapping rather than something derived from ``default_weight`` — it
represents the new, all-9-criteria target distribution described in the
plan, which is a materially different split from the legacy fallback.
"""

from . import (
    ats_format,
    education_language,
    experience_match,
    keyword_match,
    recruiter_score as recruiter_score_module,
    role_title_match,
    skills_coverage,
    soft_skills,
)

import cv_model as _cv_model_pkg

CATEGORIES: dict[str, dict] = {
    "skills_match": {"label": "Skills Match", "default_weight": 45},
    "job_fit": {"label": "Job Fit", "default_weight": 30},
    "cv_quality": {"label": "CV Quality", "default_weight": 15},
    "background": {"label": "Background", "default_weight": 10},
}


# ── Standalone scorers for the 3 pre-existing criteria ───────────────
# worker.py::score_cv keeps its own richer, config-aware matching logic
# (fuzzy/synonym-aware `_matches_term`) for the actual scoring path —
# these exist only so the registry has a genuine, self-contained,
# working scorer for every live criterion (used by
# tests/test_scoring_criteria_registry.py's completeness check), without
# creating a circular import back into worker.py.


def _simple_term_match_ratio(cv_text: str, terms: list) -> float:
    text_lower = (cv_text or "").lower()
    terms = [t for t in (terms or []) if t]
    if not terms:
        return 100.0
    matched = sum(1 for t in terms if t.lower() in text_lower)
    return round((matched / len(terms)) * 100.0, 2)


def _required_skills_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return _simple_term_match_ratio(cv_text, config.get("required_skills"))


def _nice_to_have_skills_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return _simple_term_match_ratio(cv_text, config.get("nice_to_have_skills"))


def _content_quality_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    # Same length-based heuristic worker.py uses, rescaled to a plain 0-100.
    return round(min(100.0, max(0.0, len(cv_text or "") / 30.0)), 2)


# ── Adapters for the 6 ported text-based criteria (uniform signature) ─
# All scorers share one (cv_text, config, cv_model=None) signature so
# worker.py::score_cv can call every criterion's scorer identically. Only
# the 3 Background criteria below actually use cv_model; these 9 ignore it.


def _skills_coverage_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return skills_coverage.skills_coverage_score(cv_text, config.get("description", ""))


def _experience_match_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return experience_match.experience_score(cv_text, config.get("description", ""))


def _role_title_match_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return role_title_match.role_title_match_score(cv_text, config.get("description", ""))


def _keyword_match_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return keyword_match.keyword_match_score(cv_text, config.get("description", ""))


def _ats_format_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return ats_format.ats_format_score(cv_text)


def _soft_skills_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return soft_skills.soft_skills_score(cv_text)


# ── Adapters for the 3 Background criteria (Phase 4) ──────────────────
# These need a structured CVModel, not raw text. When the caller already
# parsed one (worker.py::score_cv builds it once per file and passes it
# through), reuse it; otherwise parse lazily so these scorers still work
# standalone (e.g. the registry completeness test below, which calls every
# scorer as `scorer(cv_text, config)` with no cv_model). A CV that fails to
# structurally parse falls back to an empty CVModel (score 0) rather than
# raising — see cv_model.parse_cv_model's docstring.


def _resolve_cv_model(cv_text: str, cv_model):
    if cv_model is not None:
        return cv_model
    return _cv_model_pkg.parse_cv_model(cv_text)


def _education_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return education_language.education_score(_resolve_cv_model(cv_text, cv_model))


def _language_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return education_language.language_score(_resolve_cv_model(cv_text, cv_model))


def _recruiter_score_scorer(cv_text: str, config: dict, cv_model=None) -> float:
    return recruiter_score_module.recruiter_score(_resolve_cv_model(cv_text, cv_model))


CRITERIA: dict[str, dict] = {
    # ── Skills Match ──────────────────────────────────────────────
    "required_skills": {
        "category": "skills_match",
        "label": "Required Skills",
        "default_weight": 70.0,
        "description": "Share of the job's required skills found in the CV.",
        "scorer": _required_skills_scorer,
    },
    "nice_to_have_skills": {
        "category": "skills_match",
        "label": "Nice-to-have Skills",
        "default_weight": 20.0,
        "description": "Share of the job's nice-to-have skills found in the CV.",
        "scorer": _nice_to_have_skills_scorer,
    },
    "skills_coverage": {
        "category": "skills_match",
        "label": "Skills Coverage",
        "default_weight": 0.0,
        "description": "Taxonomy-based skill coverage: CV skills matched against a categorized skill database, independent of the exact required/nice-to-have wording.",
        "scorer": _skills_coverage_scorer,
    },
    # ── Job Fit ───────────────────────────────────────────────────
    "experience_match": {
        "category": "job_fit",
        "label": "Experience Match",
        "default_weight": 0.0,
        "description": "Years of experience implied by the CV versus what the job description asks for.",
        "scorer": _experience_match_scorer,
    },
    "role_title_match": {
        "category": "job_fit",
        "label": "Role/Title Match",
        "default_weight": 0.0,
        "description": "How closely the CV's implied job title and seniority match the job description's.",
        "scorer": _role_title_match_scorer,
    },
    "keyword_match": {
        "category": "job_fit",
        "label": "Keyword Match",
        "default_weight": 0.0,
        "description": "TF-IDF-weighted word and phrase overlap between the CV and the job description.",
        "scorer": _keyword_match_scorer,
    },
    # ── CV Quality ────────────────────────────────────────────────
    "ats_format": {
        "category": "cv_quality",
        "label": "ATS Format Compliance",
        "default_weight": 0.0,
        "description": "Section presence, formatting consistency, bullet usage, length, and contact-info completeness.",
        "scorer": _ats_format_scorer,
    },
    "content_quality": {
        "category": "cv_quality",
        "label": "Content Quality",
        "default_weight": 10.0,
        "description": "Simple content-depth heuristic based on CV length.",
        "scorer": _content_quality_scorer,
    },
    "soft_skills": {
        "category": "cv_quality",
        "label": "Soft Skills",
        "default_weight": 0.0,
        "description": "Coverage of common soft-skill terms (leadership, teamwork, communication, ...).",
        "scorer": _soft_skills_scorer,
    },
    # ── Background (Phase 4 — needs the structural CVModel parser) ──────
    "education": {
        "category": "background",
        "label": "Education",
        "default_weight": 3.3,
        "description": "Degree presence, field of study, and dates across the CV's parsed education "
        "entries (ported from services/ats_scoring.py::_score_education).",
        "scorer": _education_scorer,
    },
    "language": {
        "category": "background",
        "label": "Language",
        "default_weight": 3.3,
        "description": "Number of languages listed on the CV (ported from "
        "services/ats_scoring.py::_score_languages).",
        "scorer": _language_scorer,
    },
    "recruiter_score": {
        "category": "background",
        "label": "Recruiter Score",
        "default_weight": 3.4,
        "description": "Holistic recruiter-appeal signal — title/summary/experience-depth/skills-breadth "
        "'interest' blended with an experience/structure/keywords/education-weighted 'hireability' "
        "(ported from services/job_match_service.py::recruiter_score).",
        "scorer": _recruiter_score_scorer,
    },
}

# Historical note: education/language/recruiter_score were reserved with
# scorer=None until Phase 4 ported the CVModel structural parser they need
# (see local_worker/cv_model/). No criterion is reserved anymore — this
# tuple is kept (now empty) so any code or test that still references it
# keeps working.
RESERVED_CRITERIA: tuple[str, ...] = ()


# ── Presets ────────────────────────────────────────────────────────
# All 12 keys are listed explicitly (reserved criteria pinned at 0) so a
# preset is always a complete, unambiguous weight assignment. Each sums
# to exactly 100.
#
# "balanced" is the plan's target 4-category split (Skills Match / Job
# Fit / CV Quality / Background = 45 / 30 / 15 / 10) with one adjustment:
# Background's 10 points are temporarily folded into CV Quality (15 -> 20)
# because its 3 members are reserved/inactive in this phase (weight-0,
# no scorer) — assigning them a nonzero preset weight would be a no-op
# at best. Phase 4 should reclaim Background's share once
# education/language/recruiter_score are implemented.

PRESETS: dict[str, dict[str, float]] = {
    "balanced": {
        "required_skills": 25.0,
        "nice_to_have_skills": 10.0,
        "skills_coverage": 15.0,
        "experience_match": 12.0,
        "role_title_match": 8.0,
        "keyword_match": 10.0,
        "ats_format": 8.0,
        "content_quality": 7.0,
        "soft_skills": 5.0,
        "education": 0.0,
        "language": 0.0,
        "recruiter_score": 0.0,
    },
    "skills_focused": {
        # Skills Match -> ~60, Job Fit and CV Quality scaled down by 0.8.
        "required_skills": 30.0,
        "nice_to_have_skills": 12.0,
        "skills_coverage": 18.0,
        "experience_match": 10.0,
        "role_title_match": 6.0,
        "keyword_match": 8.0,
        "ats_format": 6.0,
        "content_quality": 6.0,
        "soft_skills": 4.0,
        "education": 0.0,
        "language": 0.0,
        "recruiter_score": 0.0,
    },
    "ats_focused": {
        # CV Quality -> ~35, Skills Match and Job Fit scaled down by ~0.8125.
        "required_skills": 20.0,
        "nice_to_have_skills": 8.0,
        "skills_coverage": 13.0,
        "experience_match": 10.0,
        "role_title_match": 6.0,
        "keyword_match": 8.0,
        "ats_format": 14.0,
        "content_quality": 12.0,
        "soft_skills": 9.0,
        "education": 0.0,
        "language": 0.0,
        "recruiter_score": 0.0,
    },
}


def preset_total(name: str) -> float:
    """Sum of a preset's weights — used by tests to assert it equals 100."""
    return sum(PRESETS[name].values())
