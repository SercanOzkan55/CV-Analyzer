"""add_candidate_action_owner_controls

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidate_actions', sa.Column('assigned_user_id', sa.Integer(), nullable=True))
    op.add_column('candidate_actions', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('candidate_actions', sa.Column('anonymized_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'fk_candidate_actions_assigned_user_id_app_users',
        'candidate_actions',
        'app_users',
        ['assigned_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_candidate_actions_assigned_user_id'), 'candidate_actions', ['assigned_user_id'], unique=False)
    op.create_index(op.f('ix_candidate_actions_deleted_at'), 'candidate_actions', ['deleted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_candidate_actions_deleted_at'), table_name='candidate_actions')
    op.drop_index(op.f('ix_candidate_actions_assigned_user_id'), table_name='candidate_actions')
    op.drop_constraint('fk_candidate_actions_assigned_user_id_app_users', 'candidate_actions', type_='foreignkey')
    op.drop_column('candidate_actions', 'anonymized_at')
    op.drop_column('candidate_actions', 'deleted_at')
    op.drop_column('candidate_actions', 'assigned_user_id')
