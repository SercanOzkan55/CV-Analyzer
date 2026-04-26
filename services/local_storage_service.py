"""Local Disk storage service for On-Premise / Private deployments."""

import os
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("app.storage.local")

# Root directory for local storage, relative to the app root
LOCAL_STORAGE_ROOT = os.getenv("LOCAL_STORAGE_PATH", "storage")

def _ensure_dir(path: str):
    """Ensure the directory for a given file path exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

def upload(file_bytes: bytes, key: str, content_type: str = None) -> None:
    """Save bytes to local disk using the key as relative path."""
    full_path = os.path.join(LOCAL_STORAGE_ROOT, key)
    _ensure_dir(full_path)
    with open(full_path, "wb") as f:
        f.write(file_bytes)
    logger.debug("local_storage:saved key=%s size=%d", key, len(file_bytes))

def download(key: str) -> bytes:
    """Read bytes from local disk."""
    full_path = os.path.join(LOCAL_STORAGE_ROOT, key)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Key not found: {key}")
    with open(full_path, "rb") as f:
        return f.read()

def delete(key: str) -> None:
    """Remove file from local disk."""
    full_path = os.path.join(LOCAL_STORAGE_ROOT, key)
    if os.path.exists(full_path):
        os.remove(full_path)
        logger.debug("local_storage:deleted key=%s", key)

def head(key: str) -> dict | None:
    """Check if file exists and return metadata (simulated)."""
    full_path = os.path.join(LOCAL_STORAGE_ROOT, key)
    if os.path.exists(full_path):
        stats = os.stat(full_path)
        return {
            "size": stats.st_size,
            "updated": stats.st_mtime
        }
    return None

def get_local_path(key: str) -> str:
    """Return the absolute path on disk for a given key."""
    return os.path.abspath(os.path.join(LOCAL_STORAGE_ROOT, key))

def validate_storage() -> bool:
    """Check if storage root is writable."""
    try:
        os.makedirs(LOCAL_STORAGE_ROOT, exist_ok=True)
        test_file = os.path.join(LOCAL_STORAGE_ROOT, ".healthcheck")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception as e:
        logger.error("local_storage:health_check_failed error=%s", e)
        return False
