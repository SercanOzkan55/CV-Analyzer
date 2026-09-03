"""Regression checks for public server-error response details."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ERROR_CODES = {500, 503}


def _http_exception_calls():
    sources = [PROJECT_ROOT / "main.py"]
    sources.extend((PROJECT_ROOT / "core").rglob("*.py"))
    sources.extend((PROJECT_ROOT / "routes").rglob("*.py"))
    sources.extend((PROJECT_ROOT / "services").rglob("*.py"))

    for path in sources:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name != "HTTPException":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            status = keywords.get("status_code")
            detail = keywords.get("detail")
            if isinstance(status, ast.Constant) and status.value in SERVER_ERROR_CODES:
                yield path, node.lineno, detail


def test_500_and_503_details_are_static_strings():
    """Internal exceptions must stay in logs, never in public 500/503 payloads."""
    unsafe = []
    for path, line, detail in _http_exception_calls():
        if not (isinstance(detail, ast.Constant) and isinstance(detail.value, str)):
            unsafe.append(f"{path.relative_to(PROJECT_ROOT)}:{line}")

    assert unsafe == [], "Dynamic public server-error details found: " + ", ".join(unsafe)
