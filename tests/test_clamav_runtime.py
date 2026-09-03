import sys
import types

import pytest
from fastapi import HTTPException

from services import pdf_runtime


class _Result:
    def __init__(self, status: str, reason: str | None = None):
        self.status = status
        self.reason = reason


def _enable_scanner(monkeypatch, result=None, error: Exception | None = None):
    monkeypatch.setattr(pdf_runtime, "main_value", lambda _name, _default: True)

    class FakeClient:
        def __init__(self, *, host, port, timeout):
            assert host == pdf_runtime.CLAMAV_HOST
            assert port == pdf_runtime.CLAMAV_PORT
            assert timeout == 15

        def instream(self, stream):
            assert stream.read() == b"test upload"
            if error is not None:
                raise error
            return result

    monkeypatch.setitem(sys.modules, "clamdpy", types.SimpleNamespace(ClamdNetworkSocket=FakeClient))


def test_clamav_accepts_clean_upload(monkeypatch):
    _enable_scanner(monkeypatch, _Result("OK"))
    pdf_runtime._scan_upload_for_viruses(b"test upload")


def test_clamav_rejects_detected_malware(monkeypatch):
    _enable_scanner(monkeypatch, _Result("FOUND", "Eicar-Signature"))

    with pytest.raises(HTTPException) as exc_info:
        pdf_runtime._scan_upload_for_viruses(b"test upload")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Malware detected: Eicar-Signature"


def test_clamav_fails_closed_when_daemon_is_unavailable(monkeypatch):
    _enable_scanner(monkeypatch, error=ConnectionError("unavailable"))

    with pytest.raises(HTTPException) as exc_info:
        pdf_runtime._scan_upload_for_viruses(b"test upload")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Virus scan failed"
