"""Logging configuration for production deployment.

Call ``setup_logging()`` early in application startup to configure
rotating file handlers and structured JSON output.

Usage (in main.py or gunicorn_config.py)::

    from logging_config import setup_logging
    setup_logging()
"""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone

try:
    from security.redaction import redact_for_log, redact_sensitive_text
except Exception:  # pragma: no cover - logging must keep working during boot

    def redact_sensitive_text(value: str, max_length: int = 2000) -> str:
        return value

    def redact_for_log(value, key: str | None = None, max_depth: int = 4):
        return value


_LOG_DIR = os.getenv("LOG_DIR", "/app/logs")
_LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(50 * 1024 * 1024)))  # 50 MB
_LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # "json" or "text"


class RedactingFilter(logging.Filter):
    """Best-effort secret and PII redaction before records hit handlers."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str) and not record.args:
                record.msg = redact_sensitive_text(record.msg)
            if isinstance(record.args, dict):
                record.args = {key: redact_for_log(value, key=str(key)) for key, value in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_for_log(value) for value in record.args)
            elif record.args:
                record.args = redact_for_log(record.args)
        except Exception:
            pass
        return True


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production observability (ELK, Datadog, CloudWatch)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": redact_sensitive_text(str(record.exc_info[1])),
                "traceback": [
                    redact_sensitive_text(line, max_length=4000)
                    for line in traceback.format_exception(*record.exc_info)
                ],
            }
        # Merge any extra fields passed via `extra={}` kwarg
        for key in ("user_id", "request_id", "path", "method", "status_code", "duration_ms"):
            if hasattr(record, key):
                log_entry[key] = redact_for_log(getattr(record, key), key=key)
        return json.dumps(log_entry, default=str, ensure_ascii=False)


def _make_formatter() -> logging.Formatter:
    """Return JSON or text formatter based on LOG_FORMAT env var."""
    if _LOG_FORMAT == "json":
        return JSONFormatter()
    return logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def setup_logging() -> None:
    """Configure root + application loggers with rotating file handlers."""

    # Ensure log directory exists (no-op if using stdout only)
    if _LOG_DIR and _LOG_DIR != "-":
        os.makedirs(_LOG_DIR, exist_ok=True)

    fmt = _make_formatter()

    root = logging.getLogger()
    root.setLevel(_LOG_LEVEL)
    root.addFilter(RedactingFilter())

    # ── Always add stderr handler ──
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    stderr_handler.setLevel(_LOG_LEVEL)
    stderr_handler.addFilter(RedactingFilter())
    root.addHandler(stderr_handler)

    # ── Add rotating file handlers if LOG_DIR is set ──
    if _LOG_DIR and _LOG_DIR != "-":
        _files = {
            "app.log": logging.getLogger(),
            "audit.log": logging.getLogger("app.audit"),
            "security.log": logging.getLogger("app.security"),
            "access.log": logging.getLogger("app.access"),
            "guard.log": logging.getLogger("app.guard"),
        }
        for filename, target_logger in _files.items():
            path = os.path.join(_LOG_DIR, filename)
            handler = logging.handlers.RotatingFileHandler(
                path,
                maxBytes=_LOG_MAX_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(fmt)
            handler.setLevel(_LOG_LEVEL)
            handler.addFilter(RedactingFilter())
            target_logger.addHandler(handler)
