"""Request-size and upload helpers shared by app bootstrap and routes."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config.aws import MAX_UPLOAD_BYTES
from security.file_guard import read_upload_limited


def _format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} bytes"


def _get_max_request_body_bytes() -> int:
    import os

    default_limit = MAX_UPLOAD_BYTES + 1024 * 1024
    try:
        configured = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(default_limit)))
    except (TypeError, ValueError):
        configured = default_limit
    return max(configured, MAX_UPLOAD_BYTES)


async def _read_upload_or_400(
    file: UploadFile,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> bytes:
    try:
        return await read_upload_limited(file, max_bytes=max_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        max_body_size = _get_max_request_body_bytes()
        content_length = request.headers.get("content-length")
        try:
            declared_length = int(content_length or "0")
        except ValueError:
            declared_length = 0
        if declared_length and declared_length > max_body_size:
            return Response(
                f"Request too large. Max body size is {_format_bytes(max_body_size)}.",
                status_code=413,
            )
        return await call_next(request)
