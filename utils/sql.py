"""Small SQL query helpers shared by route modules."""

from __future__ import annotations

LIKE_ESCAPE_CHAR = "\\"


def escape_like_wildcards(value: str, escape_char: str = LIKE_ESCAPE_CHAR) -> str:
    """Escape LIKE wildcard characters in user-provided search text."""
    text = str(value)
    return (
        text.replace(escape_char, escape_char + escape_char)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


def contains_like_pattern(value: str, escape_char: str = LIKE_ESCAPE_CHAR) -> str:
    return f"%{escape_like_wildcards(value, escape_char=escape_char)}%"
