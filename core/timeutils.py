"""Time helpers.

``datetime.utcnow()`` is deprecated from Python 3.12 onward. ``utcnow()`` is a
drop-in replacement that preserves the codebase's existing naive-UTC convention
(every ``DateTime`` column is timezone-naive), so stored values, comparisons and
ISO serialization behave exactly as before — only the deprecation goes away.

If the project later moves to timezone-aware datetimes, this is the single place
to change.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive ``datetime`` (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
