"""Recruiter dashboard service — ranking, strength/weakness analysis, email."""

import json
import re
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import CandidateAction, EmailTemplate, RecruiterJob

logger = logging.getLogger("app.recruiter")

# ── Variable pattern for email templates ─────────────────────────
_VAR_RE = re.compile(r"\{(\w+)\}")

# ── Section quality weights ──────────────────────────────────────
_REQUIRED_SECTIONS = {"summary", "experience", "education", "skills"}
_BONUS_SECTIONS = {"projects", "certifications", "languages", "publications"}


# =====================================================================
#  FEATURE 1 — Candidate Ranking
# =====================================================================


def rank_candidates(analyses: list[dict]) -> list[dict]:
    """Sort analysed candidates by composite score.

    Primary: final_score (or ats_score)
    Secondary: experience entry count
    Tertiary: detected skills count
    """
    for item in analyses:
        exp_entries = 0
        ats = item.get("ats") or {}
        if isinstance(ats, dict):
            exp_block = ats.get("experience") or {}
            exp_entries = exp_block.get("entry_count", 0) if isinstance(exp_block, dict) else 0

        skills_count = len(item.get("detected_skills") or [])

        item["_sort_key"] = (
            float(item.get("final_score") or item.get("ats_score") or 0),
            exp_entries,
            skills_count,
        )

    analyses.sort(key=lambda x: x["_sort_key"], reverse=True)

    ranked = []
    for i, item in enumerate(analyses, 1):
        summary_text = ""
        ats = item.get("ats") or {}
        if isinstance(ats, dict):
            summary_text = (ats.get("summary") or {}).get("text", "")
        if not summary_text:
            cv_text = item.get("cv_text") or ""
            summary_text = cv_text[:200].strip()

        ranked.append({
            "rank": i,
            "candidate_name": item.get("candidate_name", f"Candidate {i}"),
            "candidate_email": item.get("candidate_email", ""),
            "final_score": round(float(item.get("final_score") or 0), 2),
            "ats_score": round(float(item.get("ats_score") or 0), 2),
            "skill_score": round(float(item.get("skill_score") or 0), 2),
            "experience_count": item["_sort_key"][1],
            "skills_count": item["_sort_key"][2],
            "preview": summary_text[:200],
            "detected_skills": (item.get("detected_skills") or [])[:15],
            "missing_skills": (item.get("missing_skills") or [])[:10],
            "score_breakdown": item.get("score_breakdown") or {},
            "job_description_quality": item.get("job_description_quality") or {},
            "warnings": item.get("warnings") or [],
            "score_version": item.get("score_version") or "",
            "file_name": item.get("file_name", ""),
            "cv_text": item.get("cv_text", ""),
        })
        del item["_sort_key"]

    return ranked


# =====================================================================
#  FEATURE 2 — Strength / Weakness Analysis
# =====================================================================


def analyze_strengths_weaknesses(analysis: dict) -> dict:
    """Generate structured strength/weakness report from pipeline result."""
    strengths = []
    weaknesses = []

    # ── Score-based ──────────────────────────────────────────────
    final_score = float(analysis.get("final_score") or analysis.get("ats_score") or 0)
    if final_score >= 75:
        strengths.append("High overall match score")
    elif final_score < 50:
        weaknesses.append("Low overall match score")

    skill_score = float(analysis.get("skill_score") or 0)
    if skill_score >= 70:
        strengths.append("Strong skills alignment with job description")
    elif skill_score < 40:
        weaknesses.append("Weak skills match — many required skills missing")

    # ── Skills detail ────────────────────────────────────────────
    detected = analysis.get("detected_skills") or []
    missing = analysis.get("missing_skills") or []

    if len(detected) >= 8:
        strengths.append(f"Rich skill set ({len(detected)} skills detected)")
    elif len(detected) < 3:
        weaknesses.append(f"Very few skills listed ({len(detected)})")

    if missing:
        weaknesses.append(f"Missing {len(missing)} required skills: {', '.join(missing[:5])}")

    # ── Experience ───────────────────────────────────────────────
    ats = analysis.get("ats") or {}
    exp_data = ats.get("experience") or {} if isinstance(ats, dict) else {}
    exp_count = exp_data.get("entry_count", 0) if isinstance(exp_data, dict) else 0

    if exp_count >= 3:
        strengths.append(f"Solid experience section ({exp_count} entries)")
    elif exp_count == 0:
        weaknesses.append("No experience entries detected")
    else:
        weaknesses.append(f"Limited experience ({exp_count} entry)")

    # ── Sections present ─────────────────────────────────────────
    sections = set()
    if isinstance(ats, dict):
        for key in ats:
            if isinstance(ats[key], dict) and ats[key]:
                sections.add(key.lower())

    missing_sections = _REQUIRED_SECTIONS - sections
    if not missing_sections:
        strengths.append("All core sections present (summary, experience, education, skills)")
    else:
        weaknesses.append(f"Missing sections: {', '.join(sorted(missing_sections))}")

    bonus_present = _BONUS_SECTIONS & sections
    if bonus_present:
        strengths.append(f"Bonus sections: {', '.join(sorted(bonus_present))}")

    # ── Education ────────────────────────────────────────────────
    edu_data = ats.get("education") or {} if isinstance(ats, dict) else {}
    if isinstance(edu_data, dict) and edu_data.get("text"):
        strengths.append("Education section present")
    else:
        weaknesses.append("Education section missing or empty")

    # ── Structure / Format ───────────────────────────────────────
    breakdown = analysis.get("score_breakdown") or {}
    format_score = float(breakdown.get("format", 0))
    if format_score >= 70:
        strengths.append("Good CV structure and formatting")
    elif format_score < 40:
        weaknesses.append("Poor CV formatting / structure")

    return {"strengths": strengths, "weaknesses": weaknesses}


# =====================================================================
#  FEATURE 3 — Preview Panel Data
# =====================================================================


def build_preview(analysis: dict) -> dict:
    """Extract preview-friendly subset from analysis result."""
    ats = analysis.get("ats") or {}
    summary_text = ""
    last_experience = ""
    education_text = ""

    if isinstance(ats, dict):
        summary_text = (ats.get("summary") or {}).get("text", "")
        # Last experience
        exp = ats.get("experience") or {}
        if isinstance(exp, dict):
            entries = exp.get("entries") or []
            if entries and isinstance(entries, list):
                last_experience = str(entries[0])[:300]
            elif exp.get("text"):
                last_experience = str(exp["text"])[:300]
        # Education
        edu = ats.get("education") or {}
        if isinstance(edu, dict):
            education_text = edu.get("text", "")[:300]

    return {
        "name": analysis.get("candidate_name", ""),
        "email": analysis.get("candidate_email", ""),
        "final_score": round(float(analysis.get("final_score") or 0), 2),
        "ats_score": round(float(analysis.get("ats_score") or 0), 2),
        "summary": summary_text[:500],
        "top_skills": (analysis.get("detected_skills") or [])[:10],
        "missing_skills": (analysis.get("missing_skills") or [])[:10],
        "last_experience": last_experience,
        "education": education_text,
        "score_breakdown": analysis.get("score_breakdown") or {},
        "job_description_quality": analysis.get("job_description_quality") or {},
        "warnings": analysis.get("warnings") or [],
    }


# =====================================================================
#  FEATURE 5 & 6 — Email Template System
# =====================================================================


def render_template(template_body: str, template_subject: str, variables: dict) -> dict:
    """Replace {var} placeholders in template with actual values.

    Returns {"subject": str, "body": str, "missing_vars": [str]}
    """
    missing = []

    def _replace(match):
        key = match.group(1)
        val = variables.get(key)
        if val is None:
            missing.append(key)
            return match.group(0)  # leave placeholder
        return str(val)

    rendered_body = _VAR_RE.sub(_replace, template_body)
    rendered_subject = _VAR_RE.sub(_replace, template_subject)

    return {
        "subject": rendered_subject,
        "body": rendered_body,
        "missing_vars": missing,
    }


def extract_variables(analysis: dict) -> dict:
    """Extract template variables from analysis result.

    Extracts: name, email, position, company, score, skills
    """
    ats = analysis.get("ats") or {}
    name = analysis.get("candidate_name", "")
    email = analysis.get("candidate_email", "")

    # Try extracting position/company from experience
    position = ""
    company = ""
    if isinstance(ats, dict):
        exp = ats.get("experience") or {}
        if isinstance(exp, dict):
            entries = exp.get("entries") or []
            if entries and isinstance(entries, list) and isinstance(entries[0], dict):
                position = entries[0].get("title", "")
                company = entries[0].get("company", "")

    skills = ", ".join((analysis.get("detected_skills") or [])[:5])

    return {
        "name": name,
        "email": email,
        "position": position,
        "company": company,
        "score": str(round(float(analysis.get("final_score") or 0), 1)),
        "skills": skills,
    }


# =====================================================================
#  FEATURE 8 — Safety Validation
# =====================================================================


def validate_email_send(candidate_name: str, candidate_email: str) -> str | None:
    """Return error message if email cannot be sent, else None."""
    if not candidate_email or not candidate_email.strip():
        return "Cannot send email: candidate email is missing"
    if not candidate_name or not candidate_name.strip():
        return "Cannot send email: candidate name is missing"
    if "@" not in candidate_email:
        return "Cannot send email: invalid email address"
    return None


# =====================================================================
#  DB Operations
# =====================================================================


def create_job(db: Session, org_id: int, user_id: int, title: str, description: str) -> RecruiterJob:
    job = RecruiterJob(
        organization_id=org_id,
        created_by=user_id,
        title=title,
        description=description,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_jobs(db: Session, org_id: int) -> list[RecruiterJob]:
    return (
        db.query(RecruiterJob)
        .filter(RecruiterJob.organization_id == org_id, RecruiterJob.is_active.is_(True))
        .order_by(RecruiterJob.created_at.desc())
        .all()
    )


def save_candidate_action(
    db: Session,
    org_id: int,
    job_id: int,
    recruiter_id: int,
    candidate_name: str,
    candidate_email: str | None,
    cv_text: str | None,
    final_score: float | None,
    ats_score: float | None,
    action: str,
    analysis_snapshot: dict | None = None,
) -> CandidateAction:
    record = CandidateAction(
        organization_id=org_id,
        job_id=job_id,
        recruiter_id=recruiter_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        cv_text=cv_text,
        final_score=final_score,
        ats_score=ats_score,
        action=action,
        analysis_snapshot=json.dumps(analysis_snapshot, default=str) if analysis_snapshot else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def mark_email_sent(db: Session, action_id: int) -> None:
    record = db.query(CandidateAction).filter(CandidateAction.id == action_id).first()
    if record:
        record.email_sent = True
        record.email_sent_at = datetime.now(timezone.utc)
        db.commit()


def get_actions_for_job(db: Session, job_id: int, org_id: int) -> list[CandidateAction]:
    return (
        db.query(CandidateAction)
        .filter(
            CandidateAction.job_id == job_id,
            CandidateAction.organization_id == org_id,
        )
        .order_by(CandidateAction.created_at.desc())
        .all()
    )


def create_email_template(
    db: Session,
    org_id: int,
    user_id: int,
    name: str,
    template_type: str,
    subject: str,
    body: str,
) -> EmailTemplate:
    tpl = EmailTemplate(
        organization_id=org_id,
        created_by=user_id,
        name=name,
        template_type=template_type,
        subject=subject,
        body=body,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def get_email_templates(db: Session, org_id: int) -> list[EmailTemplate]:
    return (
        db.query(EmailTemplate)
        .filter(EmailTemplate.organization_id == org_id)
        .order_by(EmailTemplate.created_at.desc())
        .all()
    )


def get_email_template(db: Session, template_id: int, org_id: int) -> EmailTemplate | None:
    return (
        db.query(EmailTemplate)
        .filter(EmailTemplate.id == template_id, EmailTemplate.organization_id == org_id)
        .first()
    )


def delete_email_template(db: Session, template_id: int, org_id: int) -> bool:
    tpl = get_email_template(db, template_id, org_id)
    if not tpl:
        return False
    db.delete(tpl)
    db.commit()
    return True
