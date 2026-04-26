from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEMES_DIR = ROOT / "themes"

# ── Allowed fonts for CV generation ──────────────────────────────────────
# Keys are the canonical font identifiers sent by the frontend.
# Values are display labels.
ALLOWED_FONTS: dict[str, str] = {
    "Arial":            "Arial",
    "Calibri":          "Calibri",
    "Times New Roman":  "Times New Roman",
    "Georgia":          "Georgia",
    "Cambria":          "Cambria",
    "Garamond":         "Garamond",
    "Tahoma":           "Tahoma",
    "Segoe UI":         "Segoe UI",
    "Consolas":         "Consolas",
    "Helvetica":        "Helvetica",
    "Palatino":         "Palatino",
    "Verdana":          "Verdana",
}

DEFAULT_FONT = "Arial"


def load_theme(template: str, font_override: str = "") -> dict:
    template_name = (template or "classic").strip().lower() or "classic"
    path = THEMES_DIR / f"{template_name}.json"
    if not path.exists():
        path = THEMES_DIR / "classic.json"

    try:
        theme = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        theme = {
            "font": DEFAULT_FONT,
            "size": 11,
            "header_size": 14,
            "spacing": 4,
            "accent": "#333",
        }

    # Apply user font override if valid
    if font_override and font_override in ALLOWED_FONTS:
        theme["font"] = font_override

    return theme
