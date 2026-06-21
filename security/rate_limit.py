"""Upload-specific rate limiting.

Provides per-user upload counting layered on top of the existing
IP-based rate limiter in main.py.
"""

import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger("security.rate_limit")

# ── Per-user upload rate (uploads per window) ───────────────────────
_MAX_UPLOADS_PER_WINDOW = 10
_WINDOW_SECONDS = 60

_lock = threading.Lock()
_upload_tracker: dict[str, list[float]] = defaultdict(list)


def check_upload_rate(user_id: str) -> None:
    """Reject if user exceeds upload rate within the window.

    Thread-safe.  Raises ValueError on limit breach.
    """
    now = time.monotonic()
    with _lock:
        timestamps = _upload_tracker[user_id]
        # Prune expired entries
        cutoff = now - _WINDOW_SECONDS
        timestamps[:] = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= _MAX_UPLOADS_PER_WINDOW:
            logger.warning(
                "rate_limit:upload_exceeded user=%s count=%d",
                user_id,
                len(timestamps),
            )
            raise ValueError(f"Upload rate limit exceeded ({_MAX_UPLOADS_PER_WINDOW} per minute)")
        timestamps.append(now)
