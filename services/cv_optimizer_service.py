"""CV Optimizer Service — Smart rewrite + keyword injection.

Provides:
    1. ``rewrite_cv``       — auto-fix CV based on feedback & job description
    2. ``optimize_keywords`` — inject missing keywords into appropriate places
    3. ``RewriteResult``     — result dataclass with before/after + changelog

All functions operate on ``CVModel`` in-memory — no external API calls unless
the caller opts in to AI-assisted rewrite (future).
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import List

from schemas.cv_model import CVModel, Experience
from services.keyword_service import (
    _extract_meaningful_words,
    compare as keyword_compare,
)

logger = logging.getLogger("app.cv_optimizer")

# ── Action verb bank for bullet rewriting ────────────────────────────────
_ACTION_VERBS = [
    "Developed",
    "Implemented",
    "Designed",
    "Led",
    "Managed",
    "Optimized",
    "Delivered",
    "Built",
    "Reduced",
    "Increased",
    "Automated",
    "Integrated",
    "Streamlined",
    "Architected",
    "Deployed",
    "Migrated",
    "Established",
    "Orchestrated",
    "Spearheaded",
    "Transformed",
    "Launched",
    "Mentored",
    "Collaborated",
    "Analyzed",
    "Resolved",
    "Scaled",
    "Configured",
]

_WEAK_STARTERS = re.compile(
    r"^(responsible\s+for|worked\s+on|helped\s+with|assisted\s+in|was\s+involved|did|"
    r"handles?|took\s+part|participated|i\s+)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════
# RESULT DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ChangeItem:
    """Single change applied to the CV."""

    section: str  # "summary" | "skills" | "experience" | "structure"
    action: str  # "added" | "rewritten" | "improved" | "injected"
    detail: str


@dataclass(frozen=True, slots=True)
class RewriteResult:
    """Result of a smart CV rewrite."""

    model: CVModel
    changes: list[ChangeItem] = field(default_factory=list)
    score_before: int = 0
    score_after: int = 0
    keywords_added: list[str] = field(default_factory=list)
    keywords_strengthened: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class KeywordOptResult:
    """Result of keyword optimization."""

    model: CVModel
    added_to_skills: list[str] = field(default_factory=list)
    added_to_summary: list[str] = field(default_factory=list)
    added_to_bullets: list[str] = field(default_factory=list)
    total_added: int = 0
    coverage_before: float = 0.0
    coverage_after: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 1. SMART CV REWRITE
# ═══════════════════════════════════════════════════════════════════════════


def optimize_cv(model: CVModel, job_text: str = "") -> RewriteResult:
    """Auto-fix CV based on job description and quality feedback.

    Strategy (rule-based, no AI calls):
        1. Inject missing keywords into skills
        2. Improve summary with job-relevant terms
        3. Rewrite weak experience bullets (action verbs, quantification)
        4. Fill structural gaps (summary, skills section)
        5. Score before/after via ``ats_scoring``
    """
    from services.ats_scoring import score_cv

    before = score_cv(model)
    m = model.model_copy(deep=True)
    changes: list[ChangeItem] = []
    kw_added: list[str] = []
    kw_strengthened: list[str] = []

    # ── Step 1: Keyword gap analysis ──────────────────────────────────
    gap = {}
    if (job_text or "").strip():
        from services.job_match_service import _cv_text

        cv_txt = _cv_text(m)
        gap = keyword_compare(cv_txt, job_text)

    missing = gap.get("missing_keywords", [])
    weak = gap.get("weak_keywords", [])

    # ── Step 2: Inject missing keywords into skills ───────────────────
    existing_skills_lower = {s.lower() for s in (m.skills or [])}
    for cat_skills in (m.skills_categorized or {}).values():
        existing_skills_lower.update(s.lower() for s in cat_skills)

    skills_to_add = [kw for kw in missing[:15] if kw.lower() not in existing_skills_lower]
    if skills_to_add:
        if not m.skills_categorized:
            m.skills_categorized = {}
        target_cat = "Technical Skills"
        if target_cat not in m.skills_categorized:
            m.skills_categorized[target_cat] = []
        m.skills_categorized[target_cat].extend(kw.title() if len(kw) > 3 else kw.upper() for kw in skills_to_add)
        m.skills = list(m.skills or []) + [kw.title() if len(kw) > 3 else kw.upper() for kw in skills_to_add]
        changes.append(
            ChangeItem(
                "skills",
                "added",
                f"Added {len(skills_to_add)} missing keywords: {', '.join(skills_to_add[:8])}",
            )
        )
        kw_added.extend(skills_to_add)

    # ── Step 3: Improve summary ───────────────────────────────────────
    summary_changed = False
    if not (m.summary or "").strip():
        # Generate a basic summary from existing data
        parts = []
        if m.title:
            parts.append(f"Experienced {m.title}")
        elif m.experiences:
            parts.append(f"Experienced {m.experiences[0].title}")
        else:
            parts.append("Motivated professional")

        if m.skills:
            top_skills = m.skills[:5]
            parts.append(f"with expertise in {', '.join(top_skills)}")

        exp_years = len(m.experiences)
        if exp_years > 0:
            parts.append(
                f"and {exp_years}+ years of progressive experience" if exp_years >= 3 else f"with hands-on experience"
            )

        parts.append(
            "delivering high-quality results. "
            "Proven track record of driving efficiency and collaborating "
            "with cross-functional teams."
        )
        m.summary = " ".join(parts)
        changes.append(ChangeItem("summary", "added", "Generated professional summary"))
        summary_changed = True

    # Inject top missing keywords into existing summary
    if not summary_changed and missing and (m.summary or "").strip():
        summary_words = _extract_meaningful_words(m.summary)
        inject = [kw for kw in missing[:5] if kw.lower() not in summary_words]
        if inject:
            snippet = ", ".join(kw.title() if len(kw) > 3 else kw.upper() for kw in inject)
            m.summary = m.summary.rstrip(". ") + f". Skilled in {snippet}."
            changes.append(
                ChangeItem(
                    "summary",
                    "improved",
                    f"Injected keywords into summary: {', '.join(inject[:5])}",
                )
            )
            kw_added.extend(inject)

    # ── Step 4: Rewrite weak experience bullets ───────────────────────
    bullets_rewritten = 0
    for exp in m.experiences:
        new_bullets = []
        for bullet in exp.bullets:
            improved = _improve_bullet(bullet)
            if improved != bullet:
                bullets_rewritten += 1
            new_bullets.append(improved)
        exp.bullets = new_bullets

        # Inject weak keywords into bullets where contextually relevant
        if weak and exp.bullets:
            exp_text_lower = " ".join(exp.bullets).lower()
            for kw in weak[:3]:
                if kw.lower() in exp_text_lower:
                    # Already mentioned — try to strengthen by adding context
                    kw_strengthened.append(kw)

    if bullets_rewritten > 0:
        changes.append(
            ChangeItem(
                "experience",
                "rewritten",
                f"Improved {bullets_rewritten} bullet(s) with action verbs",
            )
        )

    # ── Step 5: Add missing structural components ─────────────────────
    if not m.education and not m.certifications:
        # Can't fabricate education, but note it
        pass

    if not m.languages:
        # Default: add the detected language
        lang_map = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French"}
        detected = lang_map.get(m.language, "")
        if detected:
            m.languages = [detected]
            changes.append(ChangeItem("structure", "added", f"Added language: {detected}"))

    # ── Score after ───────────────────────────────────────────────────
    after = score_cv(m)

    return RewriteResult(
        model=m,
        changes=changes,
        score_before=before.overall,
        score_after=after.overall,
        keywords_added=kw_added,
        keywords_strengthened=kw_strengthened,
    )


def _improve_bullet(bullet: str) -> str:
    """Improve a single experience bullet (rule-based).

    - Replace weak starters with action verbs
    - Ensure sentence starts with capital
    - Trim excessive whitespace
    """
    text = bullet.strip()
    if not text:
        return text

    # Remove leading bullet markers
    text = re.sub(r"^[-•*]\s*", "", text)

    # Replace weak starters
    if _WEAK_STARTERS.match(text):
        # Pick an action verb based on content hints
        verb = _pick_verb(text)
        text = _WEAK_STARTERS.sub("", text).strip()
        # Remove leading prepositions left over
        text = re.sub(r"^(the|a|an|of|for|in|to)\s+", "", text, flags=re.IGNORECASE)
        text = f"{verb} {text}"

    # Ensure first letter is capitalized
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text


def _pick_verb(bullet_text: str) -> str:
    """Heuristic: choose an appropriate action verb based on bullet content."""
    lower = bullet_text.lower()
    if any(w in lower for w in ("code", "software", "application", "system", "api")):
        return "Developed"
    if any(w in lower for w in ("team", "report", "manage", "lead", "oversee")):
        return "Led"
    if any(w in lower for w in ("test", "qa", "quality", "bug")):
        return "Validated"
    if any(w in lower for w in ("deploy", "server", "cloud", "infrastructure")):
        return "Deployed"
    if any(w in lower for w in ("design", "create", "build", "architect")):
        return "Designed"
    if any(w in lower for w in ("reduce", "cost", "save", "efficient", "optimiz")):
        return "Optimized"
    if any(w in lower for w in ("automat", "script", "pipeline", "ci", "cd")):
        return "Automated"
    if any(w in lower for w in ("analyz", "data", "report", "metric", "insight")):
        return "Analyzed"
    return "Delivered"


# ═══════════════════════════════════════════════════════════════════════════
# 2. KEYWORD OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════


def optimize_keywords(model: CVModel, job_text: str) -> KeywordOptResult:
    """Optimize CV keywords for a specific job description.

    Injects missing keywords into:
        1. Skills section (technical keywords)
        2. Summary (top 3 missing keywords)
        3. Experience bullets (contextually relevant keywords)

    Returns a new CVModel with the changes + before/after coverage.
    """
    if not (job_text or "").strip():
        return KeywordOptResult(
            model=model,
            coverage_before=0.0,
            coverage_after=0.0,
        )

    from services.job_match_service import _cv_text

    cv_txt = _cv_text(model)
    gap_before = keyword_compare(cv_txt, job_text)
    coverage_before = gap_before.get("keyword_coverage_pct", 0.0)

    missing = gap_before.get("missing_keywords", [])
    weak = gap_before.get("weak_keywords", [])

    if not missing and not weak:
        return KeywordOptResult(
            model=model,
            coverage_before=coverage_before,
            coverage_after=coverage_before,
        )

    m = model.model_copy(deep=True)
    added_skills: list[str] = []
    added_summary: list[str] = []
    added_bullets: list[str] = []

    # ── 1. Add to skills ──────────────────────────────────────────────
    existing_lower = {s.lower() for s in (m.skills or [])}
    for cat_skills in (m.skills_categorized or {}).values():
        existing_lower.update(s.lower() for s in cat_skills)

    to_add = [kw for kw in missing[:12] if kw.lower() not in existing_lower]
    if to_add:
        if not m.skills_categorized:
            m.skills_categorized = {}
        cat = "Technical Skills"
        if cat not in m.skills_categorized:
            m.skills_categorized[cat] = []
        formatted = [kw.title() if len(kw) > 3 else kw.upper() for kw in to_add]
        m.skills_categorized[cat].extend(formatted)
        m.skills = list(m.skills or []) + formatted
        added_skills.extend(to_add)

    # ── 2. Add to summary ─────────────────────────────────────────────
    if (m.summary or "").strip() and missing:
        summary_words = _extract_meaningful_words(m.summary)
        inject = [kw for kw in missing[:5] if kw.lower() not in summary_words][:3]
        if inject:
            snippet = ", ".join(kw.title() if len(kw) > 3 else kw.upper() for kw in inject)
            m.summary = m.summary.rstrip(". ") + f". Proficient in {snippet}."
            added_summary.extend(inject)

    # ── 3. Add to experience bullets ──────────────────────────────────
    # For each missing keyword, find the most relevant experience and
    # append a contextual mention.
    remaining = [kw for kw in missing if kw not in added_skills and kw not in added_summary][:5]
    if remaining and m.experiences:
        for kw in remaining:
            best_exp = _find_relevant_experience(m.experiences, kw)
            if best_exp is not None:
                # Append keyword mention to the most recent bullet
                if best_exp.bullets:
                    last = best_exp.bullets[-1]
                    kw_fmt = kw.title() if len(kw) > 3 else kw.upper()
                    if kw.lower() not in last.lower():
                        best_exp.bullets[-1] = last.rstrip(". ") + f", leveraging {kw_fmt}."
                        added_bullets.append(kw)

    # ── Measure coverage after ────────────────────────────────────────
    cv_txt_after = _cv_text(m)
    gap_after = keyword_compare(cv_txt_after, job_text)
    coverage_after = gap_after.get("keyword_coverage_pct", 0.0)

    total = len(added_skills) + len(added_summary) + len(added_bullets)

    return KeywordOptResult(
        model=m,
        added_to_skills=added_skills,
        added_to_summary=added_summary,
        added_to_bullets=added_bullets,
        total_added=total,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
    )


def _find_relevant_experience(experiences: list[Experience], keyword: str) -> Experience | None:
    """Find the experience entry most relevant to *keyword*.

    Simple heuristic: return the experience whose bullets/title mention
    the most related terms, or the first experience if no match.
    """
    kw_lower = keyword.lower()
    best = None
    best_score = -1

    for exp in experiences:
        text = " ".join([exp.title, exp.company] + exp.bullets).lower()
        score = text.count(kw_lower)
        # Partial word match bonus
        words = _extract_meaningful_words(text)
        if any(kw_lower in w or w in kw_lower for w in words):
            score += 1
        if score > best_score:
            best_score = score
            best = exp

    return best or (experiences[0] if experiences else None)


# Backward-compat alias
rewrite_cv = optimize_cv
