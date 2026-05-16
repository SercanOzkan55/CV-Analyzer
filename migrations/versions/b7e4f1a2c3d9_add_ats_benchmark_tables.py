"""add global ats benchmark tables

Revision ID: b7e4f1a2c3d9
Revises: merge_heads_20260305
Create Date: 2026-04-03

Adds three tables for the Global ATS Benchmark system:
- ats_benchmark_global: single-row global aggregate
- ats_benchmark_professions: per-profession aggregates
- ats_benchmark_scores: individual anonymised score records
"""

revision = "b7e4f1a2c3d9"
down_revision = "merge_heads_20260305"
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "ats_benchmark_global",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column("total_cvs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sum_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("median_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "ats_benchmark_professions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profession", sa.String(), nullable=False, unique=True),
        sa.Column("total_cvs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sum_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("median_ats", sa.Float(), nullable=False, server_default="0"),
        sa.Column("top_10_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ats_benchmark_professions_profession", "ats_benchmark_professions", ["profession"], unique=True)

    op.create_table(
        "ats_benchmark_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ats_score", sa.Float(), nullable=False),
        sa.Column("profession", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ats_benchmark_scores_ats_score", "ats_benchmark_scores", ["ats_score"])
    op.create_index("ix_ats_benchmark_scores_profession", "ats_benchmark_scores", ["profession"])
    op.create_index("ix_ats_benchmark_scores_created_at", "ats_benchmark_scores", ["created_at"])


def downgrade() -> None:
    op.drop_table("ats_benchmark_scores")
    op.drop_table("ats_benchmark_professions")
    op.drop_table("ats_benchmark_global")
