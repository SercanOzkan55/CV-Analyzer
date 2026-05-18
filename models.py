from datetime import datetime

from sqlalchemy import (TIMESTAMP, Boolean, Column, DateTime, Enum, Float, ForeignKey,
                        Integer, JSON, String, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base

try:
    from pgvector.sqlalchemy import Vector
except Exception:
    # pgvector optional import; migrations will create extension in DB
    Vector = None


class User(Base):
    __tablename__ = "app_users"
    PLAN_TYPES = ("free", "pro", "enterprise")
    BILLING_STATUSES = ("active", "past_due", "canceled", "trialing")

    id = Column(Integer, primary_key=True, index=True)
    supabase_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    plan_type = Column(
        Enum(*PLAN_TYPES, name="plan_type_enum"), default="free", nullable=False
    )
    billing_status = Column(
        Enum(*BILLING_STATUSES, name="billing_status_enum"),
        default="trialing",
        nullable=False,
    )
    stripe_customer_id = Column(String, nullable=True, index=True)
    daily_usage = Column(Integer, default=0)
    monthly_usage = Column(Integer, default=0)
    last_reset = Column(DateTime, nullable=True)
    role = Column(String, default="individual")
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    organization = relationship("Organization", back_populates="users")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APISubscription(Base):
    """API subscription for local processing mode - zero data retention."""
    __tablename__ = "api_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    organization = relationship("Organization", back_populates="api_subscriptions")

    # API key for authentication
    api_key = Column(String(255), unique=True, nullable=False, index=True)

    # Monthly limits and usage
    monthly_limit = Column(Integer, default=1000, nullable=False)
    monthly_usage = Column(Integer, default=0, nullable=False)

    # Subscription status
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    # Reset monthly usage on the 1st of each month
    monthly_reset_day = Column(Integer, default=1, nullable=False)


class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Link to User table
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)

    similarity_score = Column(Float, nullable=False)
    interpretation = Column(Text, nullable=False)
    confidence = Column(Float)
    risk_level = Column(Text)

    domain_id = Column(Integer)
    industry_id = Column(Integer)
    specialization_id = Column(Integer)
    job_title = Column(String, nullable=True, index=True)
    result = Column(JSON, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=False), server_default=func.now(), index=True
    )


class Organization(Base):
    __tablename__ = "organizations"

    PLAN_TYPES = ("free", "pro", "enterprise")
    BILLING_STATUSES = ("active", "past_due", "canceled", "trialing")

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, unique=True, index=True)
    plan_type = Column(
        Enum(*PLAN_TYPES, name="org_plan_type_enum"), default="free", nullable=False
    )
    billing_status = Column(
        Enum(*BILLING_STATUSES, name="org_billing_status_enum"),
        default="trialing",
        nullable=False,
    )
    stripe_customer_id = Column(String, nullable=True, index=True)
    daily_usage = Column(Integer, default=0)
    monthly_usage = Column(Integer, default=0)
    cv_credit_limit = Column(Integer, default=100) # Varsayılan aylık 100 CV kotası
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    api_subscriptions = relationship("APISubscription", back_populates="organization")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    cv_text = Column(Text, nullable=True)
    # cv_embedding will be `vector(1536)` in Postgres when pgvector is installed
    if Vector is not None:
        cv_embedding = Column(Vector(1536), nullable=True)
    else:
        cv_embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    raw_text = Column(Text, nullable=True)
    if Vector is not None:
        job_embedding = Column(Vector(1536), nullable=True)
    else:
        job_embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FailedTask(Base):
    """Dead-letter table for failed async tasks.

    Records Celery task failures after retries are exhausted so that
    operations can inspect and replay or debug problematic jobs.
    """

    __tablename__ = "failed_tasks"

    id = Column(Integer, primary_key=True)
    task_name = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CVVersion(Base):
    __tablename__ = "cv_versions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    version_label = Column(String, nullable=False, default="v1")
    source = Column(String, nullable=False, default="manual")
    lang = Column(String, nullable=False, default="en")
    cv_text = Column(Text, nullable=False)
    optimized_cv_text = Column(Text, nullable=True)
    job_description = Column(Text, nullable=True)
    match_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    original_s3_key = Column(String, nullable=True)
    optimized_s3_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ── Recruiter Dashboard Models ──────────────────────────────────


class RecruiterJob(Base):
    """A job posting that a recruiter is hiring for."""

    __tablename__ = "recruiter_jobs"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    actions = relationship("CandidateAction", back_populates="job", lazy="dynamic")


class EmailTemplate(Base):
    """Reusable email templates with variable placeholders."""

    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    name = Column(String, nullable=False)
    template_type = Column(String, nullable=False, default="accept")  # accept | reject | custom
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Backward-compatible alias for recruiter email template tests
RecruiterEmailTemplate = EmailTemplate


class CandidateAction(Base):
    """Tracks recruiter accept/reject decisions per candidate-job pair."""

    __tablename__ = "candidate_actions"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_name = Column(String, nullable=False)
    candidate_email = Column(String, nullable=True)
    cv_text = Column(Text, nullable=True)
    cv_file_key = Column(String, nullable=True)
    cv_file_name = Column(String, nullable=True)
    cv_file_type = Column(String, nullable=True)
    final_score = Column(Float, nullable=True)
    ats_score = Column(Float, nullable=True)
    action = Column(String, nullable=False)  # accepted | rejected | pending
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)  # JSON blob of full analysis
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    job = relationship("RecruiterJob", back_populates="actions")


class Reminder(Base):
    """Organization-level interview / application reminders."""

    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    reminder_type = Column(String, nullable=False, default="interview")
    target_email = Column(String, nullable=False)
    event_date = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    notified_3d_at = Column(DateTime, nullable=True)
    notified_1d_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Global ATS Benchmark Models ─────────────────────────────────


class JobApplication(Base):
    """User-owned job application tracker entries."""

    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    company = Column(String(200), nullable=False)
    role = Column(String(200), nullable=False)
    status = Column(String(40), nullable=False, default="wishlist", index=True)
    location = Column(String(200), nullable=True)
    url = Column(Text, nullable=True)
    salary = Column(String(120), nullable=True)
    priority = Column(String(20), nullable=False, default="medium")
    notes = Column(Text, nullable=True)
    applied_date = Column(DateTime, nullable=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True)
    board_order = Column(Integer, nullable=False, default=0)
    source = Column(String(80), nullable=False, default="manual")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ATSBenchmarkGlobal(Base):
    """Single-row aggregate: global ATS statistics across all CVs."""

    __tablename__ = "ats_benchmark_global"

    id = Column(Integer, primary_key=True, default=1)
    total_cvs = Column(Integer, nullable=False, default=0)
    sum_ats = Column(Float, nullable=False, default=0.0)
    avg_ats = Column(Float, nullable=False, default=0.0)
    median_ats = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ATSBenchmarkProfession(Base):
    """Aggregate ATS statistics per profession group."""

    __tablename__ = "ats_benchmark_professions"

    id = Column(Integer, primary_key=True)
    profession = Column(String, nullable=False, unique=True, index=True)
    total_cvs = Column(Integer, nullable=False, default=0)
    sum_ats = Column(Float, nullable=False, default=0.0)
    avg_ats = Column(Float, nullable=False, default=0.0)
    median_ats = Column(Float, nullable=False, default=0.0)
    top_10_pct = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ATSBenchmarkScore(Base):
    """Individual anonymised ATS score record for percentile calculation."""

    __tablename__ = "ats_benchmark_scores"

    id = Column(Integer, primary_key=True)
    ats_score = Column(Float, nullable=False, index=True)
    profession = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ── User Usage History ──────────────────────────────────────────


class UsageDaily(Base):
    """Tracks daily usage counts per user for usage history charts."""

    __tablename__ = "usage_daily"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date = Column(DateTime, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


# ── Favorites ───────────────────────────────────────────────────


class Favorite(Base):
    """User-bookmarked analyses for quick access."""

    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id = Column(
        Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ── Saved Job Description Templates ─────────────────────────────


class JobTemplate(Base):
    """Saved job description templates for quick reuse."""

    __tablename__ = "job_templates"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Analysis Share Links ────────────────────────────────────────


class AnalysisShare(Base):
    """Public share links for analysis results (Pro feature)."""

    __tablename__ = "analysis_shares"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id = Column(
        Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    share_token = Column(String(64), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Analysis Notes ──────────────────────────────────────────────


class AnalysisNote(Base):
    """User notes/annotations on analysis results."""

    __tablename__ = "analysis_notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id = Column(
        Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Local Worker Models ─────────────────────────────────────────

class WorkerKey(Base):
    __tablename__ = "worker_keys"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    key_prefix = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, unique=True, index=True)
    quota_limit = Column(Integer, nullable=False, default=0)
    quota_used = Column(Integer, nullable=False, default=0)
    quota_reserved = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    permissions = Column(JSON, nullable=True)


class WorkerSession(Base):
    __tablename__ = "worker_sessions"

    id = Column(Integer, primary_key=True)
    worker_key_id = Column(Integer, ForeignKey("worker_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String, nullable=True)
    worker_version = Column(String, nullable=True)
    access_token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)


class WorkerClaim(Base):
    __tablename__ = "worker_claims"

    id = Column(Integer, primary_key=True)
    worker_key_id = Column(Integer, ForeignKey("worker_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_session_id = Column(Integer, ForeignKey("worker_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    cv_id = Column(Integer, nullable=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_action_id = Column(Integer, ForeignKey("candidate_actions.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String, nullable=False, default="claimed") # claimed | completed | failed | expired
    claim_expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class WorkerAnalysisResult(Base):
    __tablename__ = "worker_analysis_results"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_action_id = Column(Integer, ForeignKey("candidate_actions.id", ondelete="SET NULL"), nullable=True, index=True)
    cv_id = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    decision = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    matched_skills = Column(JSON, nullable=True)
    missing_skills = Column(JSON, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="local_worker")
    worker_key_id = Column(Integer, ForeignKey("worker_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    worker_version = Column(String, nullable=True)
    engine_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuotaEvent(Base):
    __tablename__ = "quota_events"

    id = Column(Integer, primary_key=True)
    worker_key_id = Column(Integer, ForeignKey("worker_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, nullable=True)
    cv_id = Column(Integer, nullable=True)
    event_type = Column(String, nullable=False) # reserved | completed | refunded | expired
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True)
