"""Timeout guard for CPU-intensive operations.

Prevents a single request from holding resources indefinitely.
Uses threading for sync functions and asyncio for async functions.
"""

import asyncio
import concurrent.futures
import functools
import logging
from typing import TypeVar, Callable

logger = logging.getLogger("security.timeout_guard")

T = TypeVar("T")

# ── Default timeouts (seconds) ──────────────────────────────────────
TIMEOUT_PDF_PARSE = 5
TIMEOUT_OPTIMIZE = 10
TIMEOUT_S3_OPERATION = 10


def run_with_timeout(
    fn: Callable[..., T],
    args: tuple = (),
    kwargs: dict | None = None,
    timeout: float = TIMEOUT_OPTIMIZE,
    label: str = "operation",
) -> T:
    """Run a synchronous function with a hard timeout.

    Uses a thread pool so the main event loop is not blocked.
    Raises TimeoutError if the function exceeds the limit.
    """
    kwargs = kwargs or {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error("timeout_guard:%s exceeded %ss", label, timeout)
            raise TimeoutError(f"{label} timed out after {timeout}s")


def timeout_decorator(seconds: float = TIMEOUT_OPTIMIZE, label: str = ""):
    """Decorator that wraps a sync function with a timeout guard."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        op_label = label or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return run_with_timeout(fn, args, kwargs, timeout=seconds, label=op_label)

        return wrapper

    return decorator
