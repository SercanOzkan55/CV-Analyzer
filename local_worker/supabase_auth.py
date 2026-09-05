"""Direct Supabase GoTrue login for Local Worker's Website Sync.

Local Worker never sends the recruiter's password to our own backend --
it exchanges it for a Supabase session here, exactly like the website's
own frontend does, then hands only the resulting JWT to
POST /api/worker/login. The URL and key below are the same public
values already embedded in the shipped frontend bundle
(frontend/.env.production: VITE_SUPABASE_URL / VITE_SUPABASE_KEY) --
publishable/anon keys are meant to be embedded in client apps.
"""

import requests

SUPABASE_URL = "https://oanidolrgdukiqxvvbzd.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_jtUrR1fRO7YbWwecyeGcVQ_00jbDGfo"


class SupabaseAuthError(RuntimeError):
    pass


def _token_request(payload: dict, grant_type: str) -> dict:
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/auth/v1/token",
            params={"grant_type": grant_type},
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise SupabaseAuthError(f"Could not reach the login server: {exc}") from exc

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error_description") or resp.json().get("msg") or resp.text
        except ValueError:
            detail = resp.text
        if resp.status_code in (400, 401):
            raise SupabaseAuthError("Incorrect email or password.")
        raise SupabaseAuthError(f"Login failed: {detail}")

    return resp.json()


def login_with_password(email: str, password: str) -> dict:
    """Returns {"access_token", "refresh_token", ...} on success."""
    if not email or not password:
        raise SupabaseAuthError("Enter your email and password.")
    return _token_request({"email": email, "password": password}, "password")


def refresh_session(refresh_token: str) -> dict:
    """Exchanges a stored refresh token for a fresh access token, without
    the user re-entering their password."""
    if not refresh_token:
        raise SupabaseAuthError("No stored session to refresh.")
    return _token_request({"refresh_token": refresh_token}, "refresh_token")
