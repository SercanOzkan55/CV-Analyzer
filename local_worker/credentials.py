SERVICE_NAME = "cv-analyzer-local-worker"
USERNAME = "worker-api-key"


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
