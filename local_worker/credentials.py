SERVICE_NAME = "cv-analyzer-local-worker"
USERNAME = "worker-api-key"
SMTP_USERNAME = "smtp-app-password"


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
