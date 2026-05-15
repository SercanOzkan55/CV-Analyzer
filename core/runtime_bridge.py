"""Small compatibility bridge for runtime values owned by the FastAPI app.

Most services should import their dependencies directly. A few values are still
owned by ``main`` during application bootstrap, and tests monkeypatch those
attributes on ``main``. Keeping that lookup here prevents route/service modules
from each defining their own ad-hoc ``_main_module`` helper.
"""

from __future__ import annotations

import sys
from typing import Any


def main_module():
    module = sys.modules.get("main") or sys.modules.get("__main__")
    if module is None:
        import main as module  # pragma: no cover - fallback for direct imports
    return module


def main_value(name: str, default: Any = None) -> Any:
    return getattr(main_module(), name, default)


def redis_rate_client():
    return main_value("redis_rate", None)


def is_mock_services_on() -> bool:
    return bool(main_value("MOCK_SERVICES_ON", False))
