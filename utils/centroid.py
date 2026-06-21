"""Shared centroid update helper — avoids duplication across domain/industry/specialization."""

from __future__ import annotations

import json

_ALLOWED_CENTROID_TABLES = {"domains", "industries", "specializations"}


def update_centroid(cur, table: str, row_id: int, embedding: list[float]) -> None:
    """Incrementally update the centroid of *row_id* in *table* with *embedding*."""
    if table not in _ALLOWED_CENTROID_TABLES:
        raise ValueError(f"Unsupported centroid table: {table}")

    cur.execute(f"SELECT centroid, sample_count FROM {table} WHERE id = %s;", (row_id,))  # nosec B608
    row = cur.fetchone()
    if not row:
        return

    centroid, count = row
    if isinstance(centroid, str):
        centroid = json.loads(centroid)
    centroid = list(centroid)

    updated = [(float(c) * count + float(e)) / (count + 1) for c, e in zip(centroid, embedding)]

    cur.execute(
        f"""
        UPDATE {table}
        SET centroid = %s,
            sample_count = sample_count + 1
        WHERE id = %s;
        """,  # nosec B608
        (updated, row_id),
    )
