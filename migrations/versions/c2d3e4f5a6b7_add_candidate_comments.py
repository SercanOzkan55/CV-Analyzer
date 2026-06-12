"""add_candidate_comments

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidate_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('candidate_action_id', sa.Integer(), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_user_id'], ['app_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['candidate_action_id'], ['candidate_actions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_candidate_comments_author_user_id'), 'candidate_comments', ['author_user_id'], unique=False)
    op.create_index(op.f('ix_candidate_comments_candidate_action_id'), 'candidate_comments', ['candidate_action_id'], unique=False)
    op.create_index(op.f('ix_candidate_comments_created_at'), 'candidate_comments', ['created_at'], unique=False)
    op.create_index(op.f('ix_candidate_comments_organization_id'), 'candidate_comments', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_candidate_comments_organization_id'), table_name='candidate_comments')
    op.drop_index(op.f('ix_candidate_comments_created_at'), table_name='candidate_comments')
    op.drop_index(op.f('ix_candidate_comments_candidate_action_id'), table_name='candidate_comments')
    op.drop_index(op.f('ix_candidate_comments_author_user_id'), table_name='candidate_comments')
    op.drop_table('candidate_comments')
