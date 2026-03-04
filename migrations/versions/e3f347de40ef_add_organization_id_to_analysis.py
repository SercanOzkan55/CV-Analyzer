"""add organization_id to analysis

Revision ID: e3f347de40ef
Revises: 342de95416fc
Create Date: 2026-03-04 00:01:07.704129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e3f347de40ef'
down_revision: Union[str, Sequence[str], None] = '342de95416fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('analysis', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_index('ix_analysis_organization_id', 'analysis', ['organization_id'], unique=False)
    op.create_foreign_key('fk_analysis_organization', 'analysis', 'organizations', ['organization_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_analysis_organization', 'analysis', type_='foreignkey')
    op.drop_index('ix_analysis_organization_id', table_name='analysis')
    op.drop_column('analysis', 'organization_id')
