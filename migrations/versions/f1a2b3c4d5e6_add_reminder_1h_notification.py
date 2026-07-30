"""add 1-hour reminder notification timestamp

Revision ID: f1a2b3c4d5e6
Revises: e8a1b2c3d4f5
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8a1b2c3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "reminders" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("reminders")}
    if "notified_1h_at" not in columns:
        op.add_column("reminders", sa.Column("notified_1h_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "reminders" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("reminders")}
    if "notified_1h_at" in columns:
        op.drop_column("reminders", "notified_1h_at")
