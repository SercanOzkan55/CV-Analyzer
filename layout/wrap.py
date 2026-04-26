from __future__ import annotations

from textwrap import wrap


def wrap_text(text: str, max_width: int) -> list[str]:
    clean = str(text or "").strip()
    if not clean:
        return []
    width = max(8, int(max_width or 80))
    return wrap(clean, width=width, break_long_words=False, break_on_hyphens=False)
