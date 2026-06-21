"""Gunicorn production configuration.

Usage:
    gunicorn main:app -c gunicorn_config.py
"""

import multiprocessing
import os

# ── Bind ────────────────────────────────────────────────────────────
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8001")

# ── Workers ─────────────────────────────────────────────────────────
workers = int(os.getenv("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 8)))
worker_class = "uvicorn.workers.UvicornWorker"

# ── Timeouts ────────────────────────────────────────────────────────
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 15
keepalive = 5

# ── Worker recycling (prevent memory leaks) ─────────────────────────
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 100

# ── Logging ─────────────────────────────────────────────────────────
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"

# ── Process naming ──────────────────────────────────────────────────
proc_name = "cv-analyzer"

# ── Graceful shutdown ───────────────────────────────────────────────
# SIGTERM → workers get graceful_timeout seconds to finish
# Already handled by gunicorn defaults; explicit for clarity.

# ── Preload ─────────────────────────────────────────────────────────
preload_app = False  # Required for uvicorn workers to fork properly

# ── Security ────────────────────────────────────────────────────────
# Limit header size to prevent header-based attacks
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190


# ── Server hooks ────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("Gunicorn master starting (workers=%d, timeout=%d)", workers, timeout)


def worker_exit(server, worker):
    server.log.info("Worker %s exited (pid=%d)", worker.pid, worker.pid)
    # Flush all log handlers on worker exit
    import logging

    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass
