"""Recruiter Score — ported from services/job_match_service.py::recruiter_score.

Source location: ``services/job_match_service.py`` (NOT ``ats_scoring.py`` or
a ``recruiter_service.py`` — that name doesn't exist in the web repo; the
actual home of "would a recruiter open this / could they get hired /
would they get shortlisted" scoring is ``job_match_service.py``'s
``recruiter_score()`` function). It is the pure-rule variant: it takes a
``CVModel`` and an optional job-description string and returns a
dataclass — no DB reads/writes anywhere in it or in what it calls. The
DB-coupled code the plan's action item warned might exist
(``tests/test_recruiter_service_db.py``) turned out to test a *different*
system entirely — the web app's saved-candidate/pipeline-stage feature in
``routes/recruiter.py`` (CRUD over a `recruiter_candidates` table) — which
is unrelated to CV scoring and was not touched by this port.

Single-scalar reduction
------------------------
The source's ``RecruiterScoreResult`` has 3 sub-fields:
``recruiter_interest``, ``hireability``, ``shortlist_probability`` (plus
``strengths``/``concerns`` text lists). The source itself already computes
``shortlist_probability`` as ``round((interest + hireability) / 2)`` as its
baseline, then *optionally* nudges it +-15/+-10 when a job description is
given (via ``match_cv_to_job``, which blends keyword overlap with an
OpenAI-embedding-based semantic score).

This port returns exactly that baseline — ``round((interest + hireability)
/ 2)`` — and deliberately drops the job-description-driven adjustment
step, for two reasons:
  1. The embedding-based semantic half of that adjustment needs OpenAI,
     which this offline tool explicitly excludes (see the project plan's
     Context section — Domain/Semantic signals are excluded everywhere).
  2. Job-fit is already its own separately-weighted category in this
     scoring model (Job Fit: Experience Match / Role-Title Match /
     Keyword Match). Re-applying a job-match boost inside a *Background*
     criterion would double-count the same signal under two categories.
The interest/hireability formulas themselves (structure/experience/skills/
education signals, bullet-quality and quantified-achievement bonuses) are
copied verbatim from the source.

This module also needed ``services/ats_scoring.py::score_cv``'s other
sub-scores (``.structure``, ``.experience``, ``.keywords``, ``.education``,
``.ats``) that the source's ``recruiter_score()`` reads — so
``local_worker/cv_model/ats_scoring.py`` (the full module, not just
education/languages) was ported too; see that module and
``education_language.py`` for the two scoring modules that share it.
"""

from __future__ import annotations

import re

from cv_model import CVModel
from cv_model.ats_scoring import score_cv as _ats_score_cv


def _all_skills(model: CVModel) -> list[str]:
    skills: list[str] = list(model.skills or [])
    for cat_skills in (model.skills_categorized or {}).values():
        skills.extend(cat_skills)
    return skills


def recruiter_score(cv_model: CVModel) -> float:
    """Return a single 0-100 recruiter-appeal score for *cv_model*.

    See module docstring for the interest/hireability formulas' source and
    the single-scalar reduction this uses (average of the source's own
    ``recruiter_interest`` and ``hireability`` sub-scores).
    """
    cv_score = _ats_score_cv(cv_model)

    exp_count = len(cv_model.experiences)
    bullet_count = sum(len(e.bullets) for e in cv_model.experiences)
    skills = _all_skills(cv_model)
    has_summary = bool((cv_model.summary or "").strip())
    has_contact = bool(cv_model.email or cv_model.phone)

    # ── Recruiter interest (would they open the CV?) ──────────────────
    interest = 0

    if (cv_model.title or "").strip():
        interest += 15
    if has_summary:
        interest += 15
        summary_len = len((cv_model.summary or "").split())
        if summary_len >= 20:
            interest += 5

    if exp_count >= 3:
        interest += 25
    elif exp_count >= 1:
        interest += 15

    if len(skills) >= 10:
        interest += 15
    elif len(skills) >= 5:
        interest += 10
    elif len(skills) > 0:
        interest += 5

    if has_contact:
        interest += 5

    if cv_score.ats >= 80:
        interest += 10
    elif cv_score.ats >= 60:
        interest += 5

    if cv_model.education:
        interest += 10

    interest = max(0, min(100, interest))

    # ── Hireability (could they get the job?) ─────────────────────────
    hireability = 0

    hireability += int(cv_score.experience * 0.30)
    hireability += int(cv_score.structure * 0.20)
    hireability += int(cv_score.keywords * 0.15)
    hireability += int(cv_score.education * 0.10)

    if bullet_count >= 10:
        hireability += 10
    elif bullet_count >= 5:
        hireability += 5

    quant = sum(1 for e in cv_model.experiences for b in e.bullets if re.search(r"\d+[%$€£]|\d{2,}", b))
    if quant >= 3:
        hireability += 10
    elif quant >= 1:
        hireability += 5

    if len(cv_model.languages) >= 2:
        hireability += 5

    hireability = max(0, min(100, hireability))

    shortlist = round((interest + hireability) / 2)
    return float(max(0, min(100, shortlist)))
