"""PDF upload, extraction, OCR, and scanned-PDF helpers."""

import io
import logging
import os
import re

from fastapi import HTTPException, Request, UploadFile

from config.aws import MAX_PDF_OBJECTS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES
from core.request_utils import _format_bytes
from core.runtime_bridge import main_value
from security.file_guard import read_upload_limited
from services.cv_builder_service import build_cv

CLAMAV_ENABLED = os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes")
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "localhost")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310") or "3310")
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "auto").lower()
OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "").strip()
OCR_SERVICE_KEY = os.getenv("OCR_SERVICE_KEY", "").strip()
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip() or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_LANG_TO_TESSERACT: dict[str, str] = {
    "en": "eng",
    "tr": "tur",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "ar": "ara",
    "pt": "por",
    "it": "ita",
    "nl": "nld",
    "ru": "rus",
    "ja": "jpn",
    "ko": "kor",
    "zh": "chi_sim",
}


def _scan_upload_for_viruses(contents: bytes) -> None:
    """Scan uploaded file bytes with ClamAV when enabled.

    This uses the clamd network daemon if available. In environments
    without CLAMAV_ENABLED, the function is a no-op.
    """

    if not bool(main_value("CLAMAV_ENABLED", CLAMAV_ENABLED)):
        return

    try:
        import clamd  # type: ignore[import-untyped, import-not-found]
    except Exception:
        raise HTTPException(status_code=500, detail="Virus scanning backend unavailable")

    try:
        client = clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT)
        result = client.instream(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=500, detail="Virus scan failed")

    try:
        _name, (status, signature) = next(iter(result.items()))
    except Exception:
        status, signature = None, None

    if status != "OK":
        detail = "File failed virus scan"
        if signature:
            detail = f"Malware detected: {signature}"
        raise HTTPException(status_code=400, detail=detail)


def _extract_pdf_text(contents: bytes) -> tuple[str, bool]:
    """Extract plain text from PDF bytes using coordinate-based layout analysis.

    Uses pdfplumber word positions to detect and properly reconstruct
    multi-column layouts. Falls back to PyPDF2 if pdfplumber fails.

    Returns (text, truncated) where truncated is True if content was capped.
    """
    from services.pdf_text_extractor import extract_pdf_text

    return extract_pdf_text(
        contents,
        max_pages=_MAX_PDF_PAGES,
        max_chars=_MAX_PDF_EXTRACTED_CHARS,
        ocr_extract_text=_ocr_extract_text,
    )

    from renderers.blocks import fix_decomposed_diacritics

    # ── Primary: pdfplumber with coordinate-based column detection ──
    try:
        import pdfplumber

        left_lines: list[str] = []
        right_lines: list[str] = []
        is_multi_col = False
        col_boundary = 0.0

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            # ── Security: reject PDFs with too many pages ──
            if len(pdf.pages) > _MAX_PDF_PAGES:
                logging.getLogger("app.security").warning("pdf_pages_limit: %d > %d", len(pdf.pages), _MAX_PDF_PAGES)
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)",
                )
            # ── First pass: detect column layout across ALL pages ──
            all_page_gaps: list[float] = []
            total_both = 0
            total_content = 0
            page_widths: list[float] = []

            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue
                page_w = page.width
                page_widths.append(page_w)

                rows: dict[float, list] = {}
                for w in words:
                    row_key = round(w["top"] / 3) * 3
                    rows.setdefault(row_key, []).append(w)

                for row_words in rows.values():
                    sorted_rw = sorted(row_words, key=lambda w: w["x0"])
                    row_span = sorted_rw[-1]["x1"] - sorted_rw[0]["x0"] if len(sorted_rw) > 1 else 0
                    # Skip rows that span less than 30% — likely single-column header rows
                    if row_span < page_w * 0.30:
                        continue
                    total_content += 1
                    max_gap = 0
                    max_gap_pos = page_w / 2
                    for i in range(len(sorted_rw) - 1):
                        gap = sorted_rw[i + 1]["x0"] - sorted_rw[i]["x1"]
                        if gap > max_gap:
                            max_gap = gap
                            max_gap_pos = (sorted_rw[i]["x1"] + sorted_rw[i + 1]["x0"]) / 2
                    if max_gap > 20:
                        all_page_gaps.append(max_gap_pos)
                        total_both += 1

            total_content = max(total_content, 1)
            # Relax thresholds: 2 gap rows and >15% of content rows
            if total_both >= 2 and total_both > total_content * 0.15:
                is_multi_col = True
                all_page_gaps.sort()
                col_boundary = all_page_gaps[len(all_page_gaps) // 2]

            # ── Second pass: extract text using detected layout ──
            for page in pdf.pages:
                words = page.extract_words()

                # If pdfplumber finds no word objects on this page, try a few
                # fallbacks before skipping: (1) page.extract_text() and
                # (2) per-page OCR via Tesseract / remote OCR service.
                if not words:
                    # Quick plain-text fallback
                    try:
                        extracted = page.extract_text() or ""
                    except Exception:
                        extracted = ""

                    if extracted and extracted.strip():
                        if is_multi_col:
                            # treat whole-page extracted text as a left-column block
                            left_lines.append(extracted.strip())
                            left_lines.append("")
                        else:
                            left_lines.extend([ln for ln in extracted.splitlines() if ln.strip()])
                        # page processed via text fallback
                        continue

                    # If configured, attempt OCR on the page image
                    try:
                        # Use pdfplumber's image renderer to get a PIL image
                        pag_img = page.to_image(resolution=150).original
                        buf = io.BytesIO()
                        pag_img.save(buf, format="JPEG")
                        img_bytes = buf.getvalue()
                        ocr_text = _ocr_extract_text(img_bytes)
                        if ocr_text and ocr_text.strip():
                            if is_multi_col:
                                left_lines.append(ocr_text.strip())
                                left_lines.append("")
                            else:
                                left_lines.extend([ln for ln in ocr_text.splitlines() if ln.strip()])
                            continue
                    except Exception:
                        # OCR best-effort: ignore failures and skip page
                        pass

                    # Nothing useful found on this page — skip it
                    continue

                page_w = page.width
                mid = col_boundary if is_multi_col else page_w / 2

                if is_multi_col:
                    # Separate wide-header rows (span both columns) from column rows
                    header_rows_lines: list[str] = []
                    page_left: list[str] = []
                    page_right: list[str] = []

                    rows_by_top: dict[float, list] = {}
                    for w in words:
                        row_key = round(w["top"] / 3) * 3
                        rows_by_top.setdefault(row_key, []).append(w)

                    for row_key in sorted(rows_by_top.keys()):
                        row_words = sorted(rows_by_top[row_key], key=lambda w: w["x0"])
                        # Check if row spans both columns (wide header)
                        has_left = any(w["x0"] < mid - 5 for w in row_words)
                        has_right = any(w["x1"] > mid + 5 for w in row_words)
                        # Measure gap at column boundary
                        max_gap_at_mid = 0
                        for i in range(len(row_words) - 1):
                            gap = row_words[i + 1]["x0"] - row_words[i]["x1"]
                            gap_pos = (row_words[i]["x1"] + row_words[i + 1]["x0"]) / 2
                            if abs(gap_pos - mid) < page_w * 0.15 and gap > max_gap_at_mid:
                                max_gap_at_mid = gap

                        if has_left and has_right and max_gap_at_mid < 15:
                            # Wide row spanning both columns — treat as header/full-width
                            header_rows_lines.append(" ".join(w["text"] for w in row_words))
                        else:
                            # Split into left/right columns
                            left_words = [w for w in row_words if w["x0"] < mid]
                            right_words = [w for w in row_words if w["x0"] >= mid]
                            if left_words:
                                page_left.append(" ".join(w["text"] for w in left_words))
                            if right_words:
                                page_right.append(" ".join(w["text"] for w in right_words))

                    # Prepend wide-header lines (name, contact) before columns
                    if header_rows_lines:
                        left_lines.extend(header_rows_lines)
                        left_lines.append("")  # blank separator

                    # Accumulate column lines per page
                    if page_left:
                        left_lines.extend(page_left)
                    if page_right:
                        right_lines.extend(page_right)

                    # Blank line as page separator
                    left_lines.append("")
                else:
                    # Single column: extract normally
                    all_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
                    cur_top = all_words[0]["top"]
                    cur_line: list[str] = []
                    for w in all_words:
                        if w["top"] - cur_top > 3:
                            if cur_line:
                                left_lines.append(" ".join(cur_line))
                            cur_line = [w["text"]]
                            cur_top = w["top"]
                        else:
                            cur_line.append(w["text"])
                    if cur_line:
                        left_lines.append(" ".join(cur_line))

        if is_multi_col:
            # Determine sidebar vs main: the column with more content is "main" and goes first.
            # This ensures experience/education (main) appear before skills/languages (sidebar).
            left_text = "\n".join(left_lines).strip()
            right_text = "\n".join(right_lines).strip()
            left_len = len(left_text.replace("\n", "").replace(" ", ""))
            right_len = len(right_text.replace("\n", "").replace(" ", ""))

            if left_len >= right_len:
                raw = left_text + "\n\n" + right_text
            else:
                raw = right_text + "\n\n" + left_text
            raw = "multi_col_fixed\n" + raw
        else:
            raw = "\n".join(left_lines)

        raw = raw.strip()
        if raw:
            # Security: cap extracted text length
            truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
            if truncated:
                raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
            return fix_decomposed_diacritics(raw), truncated

    except Exception:
        pass  # Fall through to PyPDF2

    # ── Fallback: PyPDF2 ──
    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Security: cap page count in fallback path
    pages = pdf_reader.pages
    if len(pages) > _MAX_PDF_PAGES:
        pages = pages[:_MAX_PDF_PAGES]

    text_parts = []
    for page in pages:
        extracted = page.extract_text()
        if extracted:
            text_parts.append(extracted)
    raw = "\n".join(text_parts).strip()
    # Security: cap extracted text length
    truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
    if truncated:
        logging.getLogger("app.security").warning("pdf_text_truncated: %d > %d", len(raw), _MAX_PDF_EXTRACTED_CHARS)
        raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
    return fix_decomposed_diacritics(raw), truncated


# ── PDF safety constants ──
_MAX_PDF_PAGES = MAX_PDF_PAGES
_MAX_PDF_OBJECTS = MAX_PDF_OBJECTS
_MAX_PDF_EXTRACTED_CHARS = 100_000


def _validate_pdf_upload(contents: bytes, content_type: str | None) -> None:
    """Apply upload security checks for PDF files."""

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {_format_bytes(MAX_UPLOAD_BYTES)})",
        )
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Malicious PDF: too many internal objects
    obj_count = contents.count(b" obj")
    if obj_count > _MAX_PDF_OBJECTS:
        logging.getLogger("app.security").warning("pdf_rejected: too many objects %d > %d", obj_count, _MAX_PDF_OBJECTS)
        raise HTTPException(status_code=400, detail="PDF too complex (too many objects)")

    # Malicious PDF: too many pages (quick heuristic via cross-ref)
    page_count = contents.count(b"/Type /Page") - contents.count(b"/Type /Pages")
    if page_count > _MAX_PDF_PAGES:
        logging.getLogger("app.security").warning("pdf_rejected: too many pages %d > %d", page_count, _MAX_PDF_PAGES)
        raise HTTPException(status_code=400, detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)")

    try:
        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise
    except Exception:
        if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail="Virus scanner error")


async def _resolve_job_description_text(job_description: str = "", jd_file: UploadFile | None = None) -> str:
    """Resolve JD text from direct input or uploaded file (txt/pdf)."""

    direct = (job_description or "").strip()
    if direct:
        return direct

    if jd_file is None:
        raise HTTPException(status_code=400, detail="Job description is required")

    try:
        contents = await read_upload_limited(jd_file, max_bytes=1_000_000)
    except ValueError:
        raise HTTPException(status_code=400, detail="Job description file too large")
    if len(contents) > 1_000_000:
        raise HTTPException(status_code=400, detail="Job description file too large")

    ctype = (jd_file.content_type or "").lower()
    if ctype == "application/pdf":
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid JD PDF file")
        text, _ = _extract_pdf_text(contents)
        return text

    if ctype in ("text/plain", "application/octet-stream", ""):
        return contents.decode("utf-8", errors="ignore").strip()

    raise HTTPException(
        status_code=400,
        detail="Unsupported JD file type (use text/plain or application/pdf)",
    )


CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "0").lower() in ("1", "true", "yes")
CAPTCHA_PROVIDER = os.getenv("CAPTCHA_PROVIDER", "").strip().lower()
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET", "").strip()


def require_captcha(request: Request):
    """Optional CAPTCHA enforcement for abuse-sensitive endpoints.

    When CAPTCHA_ENABLED is true, expects a CAPTCHA token in the
    X-Captcha-Token header and verifies it against reCAPTCHA or
    hCaptcha depending on CAPTCHA_PROVIDER.
    """

    if not bool(main_value("CAPTCHA_ENABLED", CAPTCHA_ENABLED)):
        return None

    token = request.headers.get("X-Captcha-Token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing CAPTCHA token")

    captcha_provider = main_value("CAPTCHA_PROVIDER", CAPTCHA_PROVIDER)
    captcha_secret = main_value("CAPTCHA_SECRET", CAPTCHA_SECRET)
    if not captcha_provider or not captcha_secret:
        raise HTTPException(status_code=500, detail="CAPTCHA misconfigured on server")

    try:
        import requests
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="CAPTCHA verification backend unavailable (install requests)",
        )

    if captcha_provider == "recaptcha":
        verify_url = "https://www.google.com/recaptcha/api/siteverify"
        data = {"secret": captcha_secret, "response": token}
    elif captcha_provider == "hcaptcha":
        verify_url = "https://hcaptcha.com/siteverify"
        data = {"secret": captcha_secret, "response": token}
    else:
        raise HTTPException(status_code=500, detail="Unsupported CAPTCHA provider")

    try:
        resp = requests.post(verify_url, data=data, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")
        payload = resp.json() if hasattr(resp, "json") else {}
        if not payload or not payload.get("success"):
            raise HTTPException(status_code=400, detail="Invalid CAPTCHA token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="CAPTCHA verification error")

    return None


def _is_tesseract_available() -> bool:
    try:
        import os
        import pytesseract

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            if not os.path.exists(TESSERACT_CMD):
                return False

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_extract_text_remote(image_bytes: bytes, lang: str = "en") -> str:
    if not OCR_SERVICE_URL:
        raise HTTPException(
            status_code=503,
            detail=("OCR service not configured. Set OCR_SERVICE_URL or install Tesseract-OCR on the server."),
        )

    import requests

    headers = {}
    if OCR_SERVICE_KEY:
        headers["Authorization"] = f"Bearer {OCR_SERVICE_KEY}"

    files = {
        "file": ("scan.jpg", image_bytes, "application/octet-stream"),
    }
    data = {"lang": lang}

    try:
        response = requests.post(OCR_SERVICE_URL, headers=headers, files=files, data=data, timeout=30)
        response.raise_for_status()
        payload = response.json()
        text = payload.get("text") or payload.get("ocr_text") or ""
        if not text:
            raise ValueError("OCR service returned empty text")
        return text.strip()
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Remote OCR service unavailable: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Remote OCR service error: {exc}",
        )


def _build_tesseract_lang(lang: str) -> str:
    """Build Tesseract lang string: always include eng + requested lang."""
    parts: list[str] = ["eng"]
    tess = _LANG_TO_TESSERACT.get(lang)
    if tess and tess != "eng":
        parts.append(tess)
    return "+".join(parts)


def _ocr_extract_text(image_bytes: bytes, lang: str = "en") -> str:
    """Extract text from image bytes using Tesseract OCR.

    Falls back to a descriptive error when Tesseract is not installed.
    Supports all app languages via Tesseract language packs.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA/palette to RGB for OCR compatibility
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Pre-processing: resize if very small (improves OCR accuracy)
    w, h = img.size
    if max(w, h) < 600:
        scale = 1200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    tess_lang = _build_tesseract_lang(lang)

    # If the server is configured to use remote OCR or local Tesseract is unavailable,
    # fallback to a remote OCR endpoint when possible.
    tesseract_ready = _is_tesseract_available()
    if OCR_PROVIDER == "remote" or (OCR_PROVIDER == "auto" and not tesseract_ready):
        return _ocr_extract_text_remote(image_bytes, lang)
    if OCR_PROVIDER == "local" and not tesseract_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR service not available. Install pytesseract and Tesseract-OCR "
                "on the server, or set OCR_PROVIDER=remote with OCR_SERVICE_URL."
            ),
        )

    try:
        import pytesseract

        if TESSERACT_CMD:
            try:
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            except Exception:
                pass

        text = pytesseract.image_to_string(img, lang=tess_lang, config="--psm 6")
        return text.strip()
    except ImportError:
        if OCR_PROVIDER in ("auto", "remote"):
            return _ocr_extract_text_remote(image_bytes, lang)
        raise HTTPException(
            status_code=503,
            detail="OCR service not available. Install pytesseract and Tesseract-OCR.",
        )
    except Exception as e:
        _log = logging.getLogger("app.scan")
        # If requested lang pack is missing, fall back to eng-only
        if "Failed loading language" in str(e) and tess_lang != "eng":
            _log.warning("tesseract_lang_fallback requested=%s falling_back=eng", tess_lang)
            try:
                text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
                return text.strip()
            except Exception as e2:
                _log.error("ocr_fallback_failed error=%s", e2)
                raise HTTPException(status_code=500, detail=f"OCR processing failed: {e2}")
        _log.error("ocr_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")


def _reflow_ocr_lines(text: str) -> str:
    lines = text.split("\n")
    merged: list[str] = []
    prev: str | None = None

    def is_bullet_line(line: str) -> bool:
        return bool(re.match(r"^\s*[-*•\u2022\u2023\u25aa\u25a0\u25cf\u25cb\u25e6]\s+", line))

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if prev is not None:
                merged.append(prev)
                prev = None
            merged.append("")
            continue

        if prev is None:
            prev = stripped
            continue

        if is_bullet_line(stripped) or is_bullet_line(prev):
            merged.append(prev)
            prev = stripped
            continue

        if prev.rstrip().endswith("-"):
            prev = prev.rstrip()[:-1] + stripped
            continue

        if re.search(r"[a-z0-9]$", prev) and re.match(r"^[a-z]", stripped):
            prev = prev + " " + stripped
            continue

        merged.append(prev)
        prev = stripped

    if prev is not None:
        merged.append(prev)

    return "\n".join(merged)


def _normalize_ocr_text_for_cv_processing(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(
        r"(?m)^[ \t]*([•\u2022\u2023\u25aa\u25a0\u25cf\u25cb\u25e6\*\-·])\s*",
        "- ",
        text,
    )
    text = re.sub(r"(?m)^([ \t]*[-*])(?=\S)", r"- ", text)
    text = re.sub(r"(?m)-\n([a-z])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _reflow_ocr_lines(text)

    try:
        from agents.extract_agent import extract_structured
        from agents.normalize_agent import normalize
        from services.cv_autofix_service import _pipeline_to_structured_text

        extracted = extract_structured(text)
        normalized = normalize(extracted)
        repaired_text, _, _, _ = _pipeline_to_structured_text(
            normalized,
            job_description="",
            mode="balanced",
        )
        if repaired_text:
            text = repaired_text
    except Exception:
        pass

    return text.strip()


def _generate_scanned_pdf_from_text(text: str, source_images: list[bytes] | None = None) -> bytes:
    """Generate a PDF from scanned text with optional source images."""
    from fpdf import FPDF
    import textwrap

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Try to load DejaVuSans for full Unicode support
    _font_loaded = False
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                pdf.add_font("ScanFont", "", fpath, uni=True)
                pdf.set_font("ScanFont", size=10)
                _font_loaded = True
                break
            except Exception:
                continue
    if not _font_loaded:
        pdf.set_font("Helvetica", size=10)

    # Page 1: Extracted text
    pdf.add_page()
    pdf.set_font_size(14)
    pdf.cell(0, 10, "CV - Camera Scan", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font_size(10)

    for line in text.split("\n"):
        if not line.strip():
            pdf.ln(3)
            continue
        # Wrap long lines
        wrapped = textwrap.wrap(line, width=95) or [""]
        for wl in wrapped:
            pdf.cell(0, 5, wl, ln=True)

    # Append source images as additional pages if provided
    if source_images:
        from PIL import Image
        import tempfile

        for idx, img_bytes in enumerate(source_images):
            try:
                img = Image.open(io.BytesIO(img_bytes))
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    img.save(tmp, format="JPEG", quality=85)
                    tmp_path = tmp.name
                pdf.add_page()
                pdf.set_font_size(10)
                pdf.cell(0, 8, f"Original Scan - Page {idx + 1}", ln=True, align="C")
                pdf.ln(3)
                # Fit image within page margins
                page_w = pdf.w - 2 * pdf.l_margin
                page_h = pdf.h - pdf.t_margin - 30
                iw, ih = img.size
                ratio = min(page_w / iw, page_h / ih)
                pdf.image(tmp_path, x=pdf.l_margin, w=iw * ratio, h=ih * ratio)
                os.unlink(tmp_path)
            except Exception:
                continue

    return pdf.output()


def _generate_scanned_pdf(
    builder_payload: dict | None,
    job_description: str,
    lang: str,
    fallback_text: str,
    source_images: list[bytes] | None = None,
) -> bytes:
    """Generate a formatted CV PDF from structured payload or fallback to raw OCR text."""
    if builder_payload:
        try:
            cv_document = build_cv(
                builder_payload,
                job_description=job_description,
                template="classic",
                output_format="pdf",
                lang=lang,
                plan="free",
            )
            buf = cv_document.get("buffer")
            if buf is not None:
                if hasattr(buf, "getvalue"):
                    return buf.getvalue()
                if isinstance(buf, (bytes, bytearray)):
                    return bytes(buf)
        except Exception as exc:
            logging.getLogger("app.scan").warning(
                "build_cv_pdf_failed error=%s",
                exc,
                exc_info=True,
            )
    return _generate_scanned_pdf_from_text(fallback_text, source_images)
