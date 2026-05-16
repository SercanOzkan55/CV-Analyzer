import pytest
from pathlib import Path
from utils.cv_processor import extract_text_fast


def test_extract_text_fast_on_sample_pdfs():
    p = Path("sample_cvs")
    files = [f for f in sorted(p.glob("*.pdf")) if f.is_file()]
    assert files, "No sample PDFs found in sample_cvs"

    for f in files:
        content = f.read_bytes()
        text = extract_text_fast(content, f.name)
        assert isinstance(text, str)
        assert len(text.strip()) > 30, f"Empty extraction for {f.name}"
