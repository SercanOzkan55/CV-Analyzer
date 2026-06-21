import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))

from worker import extract_text, LocalWorkerError


def test_ocr_fallback_success():
    # Mock PIL, fitz (PyMuPDF), and pytesseract to simulate a successful OCR extraction
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_doc.__iter__.return_value = [mock_page]
    mock_page.get_pixmap.return_value = MagicMock(width=100, height=100, samples=b"\x00" * 30000)

    with (
        patch("PIL.Image.frombytes") as mock_frombytes,
        patch("fitz.open", return_value=mock_doc) as mock_fitz_open,
        patch("pytesseract.image_to_string", return_value="OCR Text Extracted") as mock_ocr,
    ):
        text = extract_text(b"scanned_pdf_bytes", "pdf", "cv.pdf")
        assert text == "OCR Text Extracted"
        mock_fitz_open.assert_called_once()
        mock_ocr.assert_called_once()


def test_ocr_fallback_failure_raises_original_error():
    # When OCR raises an exception or PyMuPDF is not installed, it should raise the original extraction error
    # since we bypass pdfplumber and pypdf (by passing empty/dummy bytes that return empty text)
    with patch("fitz.open", side_effect=ImportError("No module named fitz")):
        with pytest.raises(LocalWorkerError) as exc_info:
            extract_text(b"scanned_pdf_bytes_empty", "pdf", "cv.pdf")
        assert "PDF extraction failed" in str(exc_info.value)
