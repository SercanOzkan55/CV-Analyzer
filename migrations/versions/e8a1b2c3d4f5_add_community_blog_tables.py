"""add community blog tables

Revision ID: e8a1b2c3d4f5
Revises: d7f8a9b0c1d2
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a1b2c3d4f5"
down_revision: Union[str, Sequence[str], None] = "d7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_supabase_id", sa.String(length=128), nullable=False),
        sa.Column("author_email", sa.String(length=320), nullable=False),
        sa.Column("author_name", sa.String(length=80), nullable=False),
        sa.Column("author_role", sa.String(length=32), nullable=False),
        sa.Column("author_plan", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=320), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('published', 'hidden')", name="check_blog_post_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blog_posts_author_supabase_id", "blog_posts", ["author_supabase_id"])
    op.create_index("ix_blog_posts_category", "blog_posts", ["category"])
    op.create_index("ix_blog_posts_created_at", "blog_posts", ["created_at"])
    op.create_index("ix_blog_posts_slug", "blog_posts", ["slug"], unique=True)
    op.create_index("ix_blog_posts_status", "blog_posts", ["status"])

    op.create_table(
        "blog_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("author_supabase_id", sa.String(length=128), nullable=False),
        sa.Column("author_email", sa.String(length=320), nullable=False),
        sa.Column("author_name", sa.String(length=80), nullable=False),
        sa.Column("author_role", sa.String(length=32), nullable=False),
        sa.Column("author_plan", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('published', 'hidden')", name="check_blog_comment_status"),
        sa.ForeignKeyConstraint(["parent_id"], ["blog_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["blog_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blog_comments_author_supabase_id", "blog_comments", ["author_supabase_id"])
    op.create_index("ix_blog_comments_created_at", "blog_comments", ["created_at"])
    op.create_index("ix_blog_comments_parent_id", "blog_comments", ["parent_id"])
    op.create_index("ix_blog_comments_post_id", "blog_comments", ["post_id"])
    op.create_index("ix_blog_comments_status", "blog_comments", ["status"])

    op.create_table(
        "blog_reactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_supabase_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("target_type IN ('post', 'comment')", name="check_blog_reaction_target_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_supabase_id", "target_type", "target_id", name="uq_blog_reaction_user_target"),
    )
    op.create_index("ix_blog_reactions_target_id", "blog_reactions", ["target_id"])
    op.create_index("ix_blog_reactions_target_type", "blog_reactions", ["target_type"])
    op.create_index("ix_blog_reactions_user_supabase_id", "blog_reactions", ["user_supabase_id"])


def downgrade() -> None:
    op.drop_table("blog_reactions")
    op.drop_table("blog_comments")
    op.drop_table("blog_posts")
