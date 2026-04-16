from datetime import datetime

from sqlalchemy import (TIMESTAMP, Column, DateTime, Enum, Float, ForeignKey,
                        Integer, String, Text)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
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
