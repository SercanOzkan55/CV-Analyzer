"""merge_multiple_heads

Revision ID: f452bb8cb12f
Revises: 0d06ef70c2dc, 1b9c8f7e6d5a, 9f1a2b3c4d5e, b7e4f1a2c3d9
Create Date: 2026-04-20 14:13:09.979354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f452bb8cb12f'
down_revision: Union[str, Sequence[str], None] = ('0d06ef70c2dc', '1b9c8f7e6d5a', '9f1a2b3c4d5e', 'b7e4f1a2c3d9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
