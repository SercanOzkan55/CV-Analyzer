from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    CheckConstraint,
    UniqueConstraint,
)
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
    plan_type = Column(Enum(*PLAN_TYPES, name="plan_type_enum"), default="free", nullable=False)
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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    organization = relationship("Organization", back_populates="users")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APISubscription(Base):
    """API subscription for local processing mode - zero data retention."""

    __tablename__ = "api_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", back_populates="api_subscriptions")

    # API key for authentication (hashed for security)
    api_key_hash = Column(String(255), unique=True, nullable=False, index=True)
    api_key_display = Column(String(50), nullable=True)  # Last 8 chars for UX, shown once

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

    def set_api_key(self, plain_key: str):
        """Hash and store API key securely."""
        try:
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            self.api_key_hash = pwd_context.hash(plain_key)
            self.api_key_display = plain_key[-8:] if len(plain_key) > 8 else "****"
        except ImportError:
            # Fallback if passlib not available (should not happen in production)
            import hashlib

            self.api_key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
            self.api_key_display = plain_key[-8:] if len(plain_key) > 8 else "****"

    def verify_api_key(self, plain_key: str) -> bool:
        """Verify plain text key against hash."""
        try:
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_key, self.api_key_hash)
        except ImportError:
            # Fallback for missing passlib
            import hashlib

            return hashlib.sha256(plain_key.encode()).hexdigest() == self.api_key_hash


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

    created_at = Column(TIMESTAMP(timezone=False), server_default=func.now(), index=True)


class Organization(Base):
    __tablename__ = "organizations"

    PLAN_TYPES = ("free", "pro", "enterprise")
    BILLING_STATUSES = ("active", "past_due", "canceled", "trialing")

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, unique=True, index=True)
    plan_type = Column(Enum(*PLAN_TYPES, name="org_plan_type_enum"), default="free", nullable=False)
    billing_status = Column(
        Enum(*BILLING_STATUSES, name="org_billing_status_enum"),
        default="trialing",
        nullable=False,
    )
    stripe_customer_id = Column(String, nullable=True, index=True)
    daily_usage = Column(Integer, default=0)
    monthly_usage = Column(Integer, default=0)
    cv_credit_limit = Column(Integer, default=100)  # Varsayılan aylık 100 CV kotası
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    api_subscriptions = relationship("APISubscription", back_populates="organization")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
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


class AsyncTaskOwner(Base):
    """Durable ownership mapping for async task result polling."""

    __tablename__ = "async_task_owners"

    id = Column(Integer, primary_key=True)
    task_id = Column(String, nullable=False, unique=True, index=True)
    task_type = Column(String, nullable=False, default="analysis", index=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)


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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    actions = relationship("CandidateAction", back_populates="job", lazy="dynamic")


class EmailTemplate(Base):
    """Reusable email templates with variable placeholders."""

    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    recruiter_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_name = Column(String, nullable=False)
    candidate_email = Column(String, nullable=True)
    cv_text = Column(Text, nullable=True)
    cv_file_key = Column(String, nullable=True)
    cv_file_name = Column(String, nullable=True)
    cv_file_type = Column(String, nullable=True)
    final_score = Column(Float, nullable=True)
    ats_score = Column(Float, nullable=True)
    action = Column(String, nullable=False)  # accepted | rejected | pending
    assigned_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)  # JSON blob of full analysis
    deleted_at = Column(DateTime, nullable=True, index=True)
    anonymized_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    job = relationship("RecruiterJob", back_populates="actions")


class CandidateComment(Base):
    """User comments on candidate actions for limited/HR review workflows."""

    __tablename__ = "candidate_comments"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_action_id = Column(
        Integer, ForeignKey("candidate_actions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    action = relationship("CandidateAction")
    author = relationship("User")


class Reminder(Base):
    """Organization-level interview / application reminders."""

    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint("event_date > created_at", name="check_future_date"),
        CheckConstraint("length(title) >= 1 AND length(title) <= 500", name="check_title_length"),
        CheckConstraint("target_email LIKE '%@%.%'", name="check_email_format"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
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
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
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
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


# ── Favorites ───────────────────────────────────────────────────


class Favorite(Base):
    """User-bookmarked analyses for quick access."""

    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ── Saved Job Description Templates ─────────────────────────────


class JobTemplate(Base):
    """Saved job description templates for quick reuse."""

    __tablename__ = "job_templates"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Analysis Share Links ────────────────────────────────────────


class AnalysisShare(Base):
    """Public share links for analysis results (Pro feature)."""

    __tablename__ = "analysis_shares"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    share_token = Column(String(64), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Analysis Notes ──────────────────────────────────────────────


class AnalysisNote(Base):
    """User notes/annotations on analysis results."""

    __tablename__ = "analysis_notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis.id", ondelete="CASCADE"), nullable=False, index=True)
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
    worker_session_id = Column(
        Integer, ForeignKey("worker_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    cv_id = Column(Integer, nullable=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_action_id = Column(
        Integer, ForeignKey("candidate_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status = Column(String, nullable=False, default="claimed")  # claimed | completed | failed | expired
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
    candidate_action_id = Column(
        Integer, ForeignKey("candidate_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cv_id = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    decision = Column(String, nullable=True)
    candidate_status = Column(String, nullable=True, index=True)
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
    event_type = Column(String, nullable=False)  # reserved | completed | refunded | expired
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True)


# --- Owner Workflow Models -------------------------------------------------


class RolePermission(Base):
    """Per-organization role permission overrides for owner/HR workflows."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "role",
            "permission_key",
            name="uq_role_permissions_org_role_permission",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, index=True)
    permission_key = Column(String, nullable=False, index=True)
    is_allowed = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Durable audit trail for owner-visible recruitment actions."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True, index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    description = Column(Text, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=False, default="success", index=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NotificationRule(Base):
    """Organization-level notification preferences for important owner events."""

    __tablename__ = "notification_rules"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "event_type",
            "channel",
            name="uq_notification_rules_org_event_channel",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, default="in_app")
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    """Owner-visible in-app notifications generated from audit-worthy events."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_action_id = Column(
        Integer, ForeignKey("candidate_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    analysis_result_id = Column(
        Integer, ForeignKey("worker_analysis_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(String, nullable=False, default="in_app")
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
