"""Non-secret SMTP configuration (host/port/from-email).

The password is never stored here -- it lives in the OS credential store via
`credentials.load_smtp_password`/`save_smtp_password`. This module mirrors
`qml_gui.py`'s `load_mail_templates`/`save_mail_templates` pattern exactly
(a JSON file in the same per-user app data directory) so the two settings
files are read/written the same way, without qml_gui.py and this module
importing each other.
"""

import json
import os
import tempfile
from pathlib import Path

SETTINGS_FILENAME = "smtp_settings.json"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_smtp_settings() -> dict:
    path = app_data_dir() / SETTINGS_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"host": "", "port": 587, "email": ""}


def save_smtp_settings(host: str, port: int, email: str) -> None:
    path = app_data_dir() / SETTINGS_FILENAME
    try:
        port_value = int(port)
    except (TypeError, ValueError):
        port_value = 587
    data = {
        "host": (host or "").strip(),
        "port": port_value,
        "email": (email or "").strip(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
