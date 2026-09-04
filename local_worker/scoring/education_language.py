"""Education / Language scoring — ported from services/ats_scoring.py's
``_score_education`` / ``_score_languages``.

Both operate purely on ``CVModel`` fields (``model.education`` entries'
``degree``/``field``/``start_date``/``end_date``, and ``model.languages``)
with no other dependency — confirmed by reading the source function bodies
in full during the Phase 4 port. Logic and thresholds are copied verbatim.
"""

from __future__ import annotations

from cv_model import CVModel


def education_score(cv_model: CVModel) -> float:
    """Score 0-100 based on education entries and degree presence.

    Ported verbatim from ``services/ats_scoring.py::_score_education``.
    """
    education = list(cv_model.education or [])
    n = len(education)
    if n == 0:
        return 0.0

    base = 50 if n == 1 else 65

    has_degree = any((e.degree or "").strip() for e in education)
    if has_degree:
        base += 20

    has_field = any((e.field or "").strip() for e in education)
    if has_field:
        base += 10

    has_dates = any((e.start_date or "").strip() or (e.end_date or "").strip() for e in education)
    if has_dates:
        base += 5

    return float(max(0, min(100, base)))


def language_score(cv_model: CVModel) -> float:
    """Score 0-100 based on language count.

    Ported verbatim from ``services/ats_scoring.py::_score_languages``.
    """
    n = len(cv_model.languages or [])
    if n == 0:
        return 0.0
    if n == 1:
        return 50.0
    if n == 2:
        return 75.0
    return 100.0
