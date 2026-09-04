"""Structured CV parsing — ported from the web repo's extraction pipeline.

Phase 4 port. Mirrors (trimmed of web-only concerns) the chain:

    raw text -> layout_analyzer -> section_classifier -> section_resolver
    -> extraction_helpers (parsing) -> extract_agent.extract_structured()
    -> normalize_agent.normalize() -> CVModel.from_mapping()

Source (web repo, for the drift-guard test and future re-sync):
    agents/extract_agent.py, agents/normalize_agent.py,
    schemas/cv_model.py, services/layout_analyzer.py,
    services/section_classifier.py, services/section_resolver.py,
    services/language_service.py, services/cv_voice_service.py,
    services/ats_scoring.py, utils/section_scorer.py,
    utils/cv_normalizer.py, utils/cv_text.py,
    services/section_aliases.py, services/section_patterns.py, and the
    extraction-only subset of services/cv_autofix_service.py (see
    extraction_helpers.py's module docstring for exactly which functions).

None of this touches ``database``, ``models``, FastAPI app config, or any
network/LLM client — confirmed by tracing the actual import graph during
the port (see the Phase 4 implementation report).

Use ``parse_cv_model()`` from the local_worker scoring code — it never
raises, so a CV that fails to structurally parse degrades to an empty
CVModel (and therefore a low-but-valid score) instead of crashing a batch.
"""

from __future__ import annotations

import logging

from .schema import CVModel, Experience, Education, Project, Certification
from .extract_agent import extract_structured
from .normalize_agent import normalize

logger = logging.getLogger("local_worker.cv_model")

__all__ = [
    "CVModel",
    "Experience",
    "Education",
    "Project",
    "Certification",
    "parse_cv_model",
]


def parse_cv_model(cv_text: str) -> CVModel:
    """Parse raw CV text into a structured :class:`CVModel`.

    Never raises: any structural-parse failure (malformed input, an
    unsupported layout, a bad scanned-image OCR dump, etc.) is caught and
    an empty ``CVModel()`` is returned instead, so callers (worker.py's
    ``score_cv``) can score the 3 Background criteria as a low-but-valid
    0 rather than crashing the whole batch.
    """
    try:
        structured = extract_structured(cv_text or "")
        normalized = normalize(structured)
        return CVModel.from_mapping(normalized)
    except Exception:
        logger.warning("parse_cv_model: structural parse failed, falling back to empty CVModel", exc_info=True)
        return CVModel()
