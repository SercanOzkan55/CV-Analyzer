"""rename_api_key_to_api_key_hash_and_add_display

Revision ID: 82d43dbf7da4
Revises: c9d0e1f2a3b4
Create Date: 2026-06-21 22:10:02.461932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82d43dbf7da4'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename api_key to api_key_hash and add api_key_display
    with op.batch_alter_table('api_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('api_key', new_column_name='api_key_hash', existing_type=sa.String(length=255), nullable=False)
        batch_op.add_column(sa.Column('api_key_display', sa.String(length=50), nullable=True))
    
    # Drop old index and create new one
    try:
        op.drop_index('ix_api_subscriptions_api_key', table_name='api_subscriptions')
    except Exception:
        pass
        
    op.create_index(op.f('ix_api_subscriptions_api_key_hash'), 'api_subscriptions', ['api_key_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    try:
        op.drop_index('ix_api_subscriptions_api_key_hash', table_name='api_subscriptions')
    except Exception:
        pass
        
    op.create_index(op.f('ix_api_subscriptions_api_key'), 'api_subscriptions', ['api_key_hash'], unique=False)
    
    with op.batch_alter_table('api_subscriptions', schema=None) as batch_op:
        batch_op.drop_column('api_key_display')
        batch_op.alter_column('api_key_hash', new_column_name='api_key', existing_type=sa.String(length=255), nullable=False)
