"""Merge multiple heads

Revision ID: merge_heads_20260305
Revises: e3f347de40ef, af3b9c_pgvector_embeddings
Create Date: 2026-03-05

This is an auto-generated merge revision to combine two heads so Alembic
can apply a single linear head. The revision intentionally performs no
schema changes; it only stitches the history together.
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "merge_heads_20260305"
down_revision: Union[str, Sequence[str], None] = (
    "e3f347de40ef",
    "af3b9c_pgvector_embeddings",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge revision."""
    pass


def downgrade() -> None:
    """Downgrade is a no-op for the merge glue revision."""
    pass
