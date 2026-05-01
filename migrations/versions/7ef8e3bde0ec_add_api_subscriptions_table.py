"""add_api_subscriptions_table

Revision ID: 7ef8e3bde0ec
Revises: f452bb8cb12f
Create Date: 2026-04-20 14:13:13.426064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ef8e3bde0ec'
down_revision: Union[str, Sequence[str], None] = 'f452bb8cb12f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create api_subscriptions table
    op.create_table(
        'api_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False),
        sa.Column('monthly_limit', sa.Integer(), nullable=False, default=1000),
        sa.Column('monthly_usage', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('monthly_reset_day', sa.Integer(), nullable=False, default=1),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key')
    )
    # Create indexes
    op.create_index(op.f('ix_api_subscriptions_api_key'), 'api_subscriptions', ['api_key'], unique=False)
    op.create_index(op.f('ix_api_subscriptions_organization_id'), 'api_subscriptions', ['organization_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_api_subscriptions_organization_id'), table_name='api_subscriptions')
    op.drop_index(op.f('ix_api_subscriptions_api_key'), table_name='api_subscriptions')
    # Drop table
    op.drop_table('api_subscriptions')
