"""add_check_constraints_to_reminders

Revision ID: fbfa3b84d7c1
Revises: e63b476f4381
Create Date: 2026-05-24 14:23:05.129979

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbfa3b84d7c1'
down_revision: Union[str, Sequence[str], None] = 'e63b476f4381'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add check constraints to reminders table."""
    op.create_check_constraint('check_email_format', 'reminders', "target_email LIKE '%@%.%'")
    op.create_check_constraint('check_future_date', 'reminders', 'event_date > created_at')
    op.create_check_constraint('check_title_length', 'reminders', 'length(title) >= 1 AND length(title) <= 500')


def downgrade() -> None:
    """Downgrade schema: Drop check constraints from reminders table."""
    op.drop_constraint('check_email_format', 'reminders', type_='check')
    op.drop_constraint('check_future_date', 'reminders', type_='check')
    op.drop_constraint('check_title_length', 'reminders', type_='check')
