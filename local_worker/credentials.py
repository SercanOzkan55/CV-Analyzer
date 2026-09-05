SERVICE_NAME = "cv-analyzer-local-worker"
USERNAME = "worker-api-key"
SMTP_USERNAME = "smtp-app-password"
WEBSITE_REFRESH_TOKEN_USERNAME = "website-refresh-token"


def load_worker_api_key() -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICE_NAME, USERNAME)
    except Exception:
        return None


def save_worker_api_key(api_key: str) -> bool:
    if not api_key:
        return False
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, USERNAME, api_key)
        return True
    except Exception:
        return False


def load_website_refresh_token() -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICE_NAME, WEBSITE_REFRESH_TOKEN_USERNAME)
    except Exception:
        return None


def save_website_refresh_token(refresh_token: str) -> bool:
    if not refresh_token:
        return False
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, WEBSITE_REFRESH_TOKEN_USERNAME, refresh_token)
        return True
    except Exception:
        return False


def clear_website_refresh_token() -> bool:
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, WEBSITE_REFRESH_TOKEN_USERNAME)
        return True
    except Exception:
        return False


def load_smtp_password() -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICE_NAME, SMTP_USERNAME)
    except Exception:
        return None


def save_smtp_password(password: str) -> bool:
    if not password:
        return False
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, SMTP_USERNAME, password)
        return True
    except Exception:
        return False
