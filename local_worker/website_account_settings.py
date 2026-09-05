"""Non-secret Website Sync account setting (just the remembered email).

The password is never stored anywhere; only a Supabase refresh token is
persisted, in the OS credential store via
`credentials.load_website_refresh_token`/`save_website_refresh_token`.
Mirrors smtp_settings.py's JSON-file pattern exactly.
"""

import json

from smtp_settings import app_data_dir

SETTINGS_FILENAME = "website_account_settings.json"


def load_website_account_settings() -> dict:
    path = app_data_dir() / SETTINGS_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"email": ""}


def save_website_account_settings(email: str) -> None:
    path = app_data_dir() / SETTINGS_FILENAME
    data = {"email": (email or "").strip()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
