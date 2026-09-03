"""enable row-level security on application tables

Revision ID: a3c4d5e6f7a8
Revises: f1a2b3c4d5e6
Create Date: 2026-09-03

RLS is deliberately enabled without ``FORCE ROW LEVEL SECURITY``. PostgreSQL
table owners (the role used by the server-side SQLAlchemy connection) continue
to bypass policies, while PostgREST roles receive deny-by-default protection
unless an explicit policy and grant are added later.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Explicitly list application-owned tables. Keeping this list static prevents
# accidental changes to extension, Supabase-managed, or future public tables.
_APPLICATION_TABLES = (
    "analysis",
    "analysis_notes",
    "analysis_shares",
    "api_subscriptions",
    "app_users",
    "async_task_owners",
    "ats_benchmark_global",
    "ats_benchmark_professions",
    "ats_benchmark_scores",
    "audit_logs",
    "blog_comments",
    "blog_posts",
    "blog_reactions",
    "candidate_actions",
    "candidate_comments",
    "candidates",
    "cv_versions",
    "email_templates",
    "failed_tasks",
    "favorites",
    "job_applications",
    "job_templates",
    "jobs",
    "notification_rules",
    "notifications",
    "organizations",
    "quota_events",
    "recruiter_jobs",
    "reminders",
    "role_permissions",
    "usage_daily",
    "worker_analysis_results",
    "worker_claims",
    "worker_keys",
    "worker_sessions",
)


def _postgres_application_tables() -> tuple[str, ...]:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return ()
    existing = set(sa.inspect(bind).get_table_names(schema="public"))
    return tuple(table for table in _APPLICATION_TABLES if table in existing)


def upgrade() -> None:
    for table in _postgres_application_tables():
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    for table in _postgres_application_tables():
        op.execute(sa.text(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY'))
