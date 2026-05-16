"""Job Description Matching & CV Feedback Service.

Provides:
    1. ``match_cv_to_job``  — keyword + semantic match with gap analysis
    2. ``generate_feedback`` — actionable improvement suggestions
    3. ``recruiter_score``   — hireability / shortlist probability

All functions accept a ``CVModel`` and optional job text.  No external
API calls are required for keyword matching; semantic match uses the
existing ``embedding_service`` when OpenAI is configured.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import List

from schemas.cv_model import CVModel
from services.keyword_service import (
    _extract_meaningful_words,
    _token_freq,
    compare as keyword_compare,
    keyword_match_score,
)
from utils.cv_text import build_cv_text

logger = logging.getLogger("app.job_match")


# ═══════════════════════════════════════════════════════════════════════════
# 1. JOB MATCHING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of matching a CV against a job description."""
    match_score: float          # 0-100
    keyword_score: float        # 0-100
    semantic_score: float       # 0-100  (0 when embedding unavailable)
    missing_keywords: list[str] = field(default_factory=list)
    weak_keywords: list[str] = field(default_factory=list)
    strong_keywords: list[str] = field(default_factory=list)
    extra_keywords: list[str] = field(default_factory=list)
    keyword_coverage_pct: float = 0.0
    suggested_keywords: list[str] = field(default_factory=list)


# Re-export for backward compatibility (external imports use this name)
_cv_text = build_cv_text


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors.  Returns 0.0 on degenerate input."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_match(cv_text_str: str, job_text: str) -> float:
    """Return 0-100 semantic similarity via embedding cosine.

    Returns 0.0 silently when the embedding service is unavailable.
    """
    try:
        from services.embedding_service import get_embedding
        cv_emb = get_embedding(cv_text_str)
        job_emb = get_embedding(job_text)
        if cv_emb is None or job_emb is None:
            return 0.0
        sim = _cosine_similarity(cv_emb, job_emb)
        # cosine similarity [-1,1] → map to [0,100]
        return round(max(0.0, min(100.0, sim * 100)), 2)
    except Exception:
        logger.debug("semantic match unavailable", exc_info=True)
        return 0.0


def match_cv_to_job(model: CVModel, job_text: str) -> MatchResult:
    """Match a CV against a job description.

    Combines:
        - keyword match (60% weight)
        - semantic / embedding match (40% weight, 0 when unavailable)
    """
    if not (job_text or "").strip():
        return MatchResult(
            match_score=0.0,
            keyword_score=0.0,
            semantic_score=0.0,
        )

    cv_txt = _cv_text(model)

    # Keyword analysis via existing keyword_service
    gap = keyword_compare(cv_txt, job_text)
    kw_score = keyword_match_score(cv_txt, job_text)

    # Semantic analysis (graceful no-op when OpenAI not configured)
    sem_score = _semantic_match(cv_txt, job_text)

    # Combined score
    if sem_score > 0:
        combined = round(0.6 * kw_score + 0.4 * sem_score, 2)
    else:
        combined = kw_score

    return MatchResult(
        match_score=combined,
        keyword_score=kw_score,
        semantic_score=sem_score,
        missing_keywords=gap.get("missing_keywords", []),
        weak_keywords=gap.get("weak_keywords", []),
        strong_keywords=gap.get("strong_keywords", []),
        extra_keywords=gap.get("extra_keywords", []),
        keyword_coverage_pct=gap.get("keyword_coverage_pct", 0.0),
        suggested_keywords=gap.get("suggested_keywords", []),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. FEEDBACK GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class FeedbackItem:
    category: str       # "skills" | "experience" | "education" | "structure" | "content"
    priority: str       # "high" | "medium" | "low"
    message: str


@dataclass(frozen=True, slots=True)
class FeedbackResult:
    items: list[FeedbackItem] = field(default_factory=list)
    score_before: int = 0
    potential_score: int = 0


def _all_skills(model: CVModel) -> list[str]:
    skills: list[str] = list(model.skills or [])
    for cat_skills in (model.skills_categorized or {}).values():
        skills.extend(cat_skills)
    return skills


def generate_feedback(
    model: CVModel,
    job_text: str = "",
    match_result: MatchResult | None = None,
) -> FeedbackResult:
    """Generate actionable feedback to improve the CV.

    If *job_text* is provided, feedback includes job-specific keyword gaps.
    """
    from services.ats_scoring import score_cv

    score = score_cv(model)
    items: list[FeedbackItem] = []
    potential_boost = 0

    # ── Structure feedback ────────────────────────────────────────────
    if not (model.summary or "").strip():
        items.append(FeedbackItem("structure", "high", "Add a professional summary — most ATS systems look for this section"))
        potential_boost += 5
    if not model.experiences:
        items.append(FeedbackItem("structure", "high", "Add work experience — this is the most important section for ATS ranking"))
        potential_boost += 10
    if not model.education:
        items.append(FeedbackItem("structure", "medium", "Add education details to improve completeness"))
        potential_boost += 4
    if not model.languages:
        items.append(FeedbackItem("structure", "low", "Consider adding languages to stand out in international markets"))
        potential_boost += 2
    if not model.projects and not model.certifications:
        items.append(FeedbackItem("structure", "low", "Add projects or certifications to demonstrate practical skills"))
        potential_boost += 2

    # ── Skills feedback ───────────────────────────────────────────────
    skills = _all_skills(model)
    if len(skills) == 0:
        items.append(FeedbackItem("skills", "high", "Add technical skills — ATS systems rely heavily on skill keywords"))
        potential_boost += 8
    elif len(skills) < 5:
        items.append(FeedbackItem("skills", "medium", f"You have only {len(skills)} skills listed — aim for 8-15 relevant skills"))
        potential_boost += 5

    # ── Experience quality ────────────────────────────────────────────
    if model.experiences:
        total_bullets = sum(len(e.bullets) for e in model.experiences)
        avg_bullets = total_bullets / len(model.experiences)
        if avg_bullets < 2:
            items.append(FeedbackItem("experience", "high", "Add more bullet points to your roles — aim for 3-5 per position"))
            potential_boost += 6

        # Check for quantified achievements
        quant_count = sum(
            1 for e in model.experiences
            for b in e.bullets
            if re.search(r"\d+[%$€£]|\d{2,}", b)
        )
        if quant_count == 0 and total_bullets > 0:
            items.append(FeedbackItem("content", "high", "Add quantified achievements (e.g. 'Reduced costs by 30%', 'Managed team of 8')"))
            potential_boost += 5
        elif quant_count < 3 and total_bullets >= 5:
            items.append(FeedbackItem("content", "medium", "Add more measurable results — numbers make your impact concrete"))
            potential_boost += 3

    # ── Contact info ──────────────────────────────────────────────────
    if not model.email:
        items.append(FeedbackItem("structure", "high", "Add your email address — recruiters need a way to contact you"))
        potential_boost += 2
    if not model.phone:
        items.append(FeedbackItem("structure", "medium", "Consider adding a phone number"))
        potential_boost += 1

    # ── Job-specific feedback ─────────────────────────────────────────
    if match_result and match_result.missing_keywords:
        top_missing = match_result.missing_keywords[:10]
        kw_list = ", ".join(top_missing)
        items.append(FeedbackItem(
            "skills", "high",
            f"Add these keywords from the job description: {kw_list}",
        ))
        potential_boost += min(10, len(top_missing))

    if match_result and match_result.weak_keywords:
        top_weak = match_result.weak_keywords[:5]
        kw_list = ", ".join(top_weak)
        items.append(FeedbackItem(
            "content", "medium",
            f"Strengthen these keywords (mentioned only once): {kw_list}",
        ))
        potential_boost += 3

    potential = min(100, score.overall + potential_boost)

    return FeedbackResult(
        items=items,
        score_before=score.overall,
        potential_score=potential,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. RECRUITER SCORE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RecruiterScoreResult:
    """Recruiter-facing assessment of a candidate."""
    recruiter_interest: int     # 0-100  — would a recruiter open this CV?
    hireability: int            # 0-100  — could this person get hired?
    shortlist_probability: int  # 0-100  — chance of making the shortlist
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


def recruiter_score(
    model: CVModel,
    job_text: str = "",
) -> RecruiterScoreResult:
    """Produce a recruiter-perspective score for a CV.

    Combines ATS score dimensions with job relevance (when provided)
    to estimate recruiter interest, hireability, and shortlist probability.
    """
    from services.ats_scoring import score_cv

    cv_score = score_cv(model)
    strengths: list[str] = []
    concerns: list[str] = []

    # ── Base signals ──────────────────────────────────────────────────
    exp_count = len(model.experiences)
    bullet_count = sum(len(e.bullets) for e in model.experiences)
    skills = _all_skills(model)
    has_summary = bool((model.summary or "").strip())
    has_contact = bool(model.email or model.phone)

    # ── Recruiter interest (would they open the CV?) ──────────────────
    interest = 0

    # Title / headline
    if (model.title or "").strip():
        interest += 15
        strengths.append("Clear professional title")
    else:
        concerns.append("No professional title/headline")

    # Summary
    if has_summary:
        interest += 15
        summary_len = len((model.summary or "").split())
        if summary_len >= 20:
            interest += 5
    else:
        concerns.append("Missing professional summary")

    # Experience depth
    if exp_count >= 3:
        interest += 25
        strengths.append(f"{exp_count} relevant positions")
    elif exp_count >= 1:
        interest += 15
    else:
        concerns.append("No work experience listed")

    # Skills breadth
    if len(skills) >= 10:
        interest += 15
        strengths.append(f"{len(skills)} skills listed")
    elif len(skills) >= 5:
        interest += 10
    elif len(skills) > 0:
        interest += 5
    else:
        concerns.append("No skills listed")

    # Contact completeness
    if has_contact:
        interest += 5

    # ATS compatibility bonus
    if cv_score.ats >= 80:
        interest += 10
    elif cv_score.ats >= 60:
        interest += 5

    # Education
    if model.education:
        interest += 10
        has_degree = any((e.degree or "").strip() for e in model.education)
        if has_degree:
            strengths.append("Formal education listed")

    interest = max(0, min(100, interest))

    # ── Hireability (could they get the job?) ─────────────────────────
    hireability = 0

    # Weighted from ATS scores
    hireability += int(cv_score.experience * 0.30)
    hireability += int(cv_score.structure * 0.20)
    hireability += int(cv_score.keywords * 0.15)
    hireability += int(cv_score.education * 0.10)

    # Bullet quality signals domain expertise
    if bullet_count >= 10:
        hireability += 10
        strengths.append("Detailed role descriptions")
    elif bullet_count >= 5:
        hireability += 5

    # Quantified achievements signal impact
    quant = sum(
        1 for e in model.experiences
        for b in e.bullets
        if re.search(r"\d+[%$€£]|\d{2,}", b)
    )
    if quant >= 3:
        hireability += 10
        strengths.append("Quantified achievements")
    elif quant >= 1:
        hireability += 5

    # Languages bonus for international roles
    if len(model.languages) >= 2:
        hireability += 5

    hireability = max(0, min(100, hireability))

    # ── Shortlist probability ─────────────────────────────────────────
    # Base: average of interest and hireability
    shortlist = round((interest + hireability) / 2)

    # Job match boost/penalty
    if (job_text or "").strip():
        match = match_cv_to_job(model, job_text)
        if match.match_score >= 70:
            shortlist += 15
            strengths.append(f"Strong job match ({match.match_score:.0f}%)")
        elif match.match_score >= 50:
            shortlist += 5
        elif match.match_score < 30:
            shortlist -= 10
            concerns.append(f"Low job relevance ({match.match_score:.0f}%)")

        if match.missing_keywords:
            top = match.missing_keywords[:5]
            concerns.append(f"Missing key skills: {', '.join(top)}")

    shortlist = max(0, min(100, shortlist))

    return RecruiterScoreResult(
        recruiter_interest=interest,
        hireability=hireability,
        shortlist_probability=shortlist,
        strengths=strengths[:10],
        concerns=concerns[:10],
    )
