"""Capture pre-main startup failures for packaged-app CI smoke tests."""

import os
import sys
import traceback
from pathlib import Path


_REPORT_PATH = os.environ.get("CV_WORKER_SMOKE_REPORT", "").strip()


if _REPORT_PATH:

    def _write_unhandled_exception(exception_type, exception, exception_traceback):
        details = "".join(traceback.format_exception(exception_type, exception, exception_traceback))
        try:
            Path(_REPORT_PATH).write_text(
                f"FAILED: unhandled exception before application startup\n{details}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    sys.excepthook = _write_unhandled_exception
