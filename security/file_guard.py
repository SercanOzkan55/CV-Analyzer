"""File upload security guard.

Validates file size, extension, MIME type, and magic bytes before
any processing or storage happens.
"""

import logging

logger = logging.getLogger("security.file_guard")

# ── Magic byte signatures ───────────────────────────────────────────
MAGIC_PDF = b"%PDF-"
MAGIC_DOCX = b"PK\x03\x04"  # ZIP (OOXML is ZIP-based)

# ── Limits ──────────────────────────────────────────────────────────
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MIN_FILE_SIZE = 100              # too small = empty/garbage

ALLOWED_EXTENSIONS = frozenset({"pdf", "docx"})

ALLOWED_CONTENT_TYPES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})

# PDF complexity limits
MAX_PDF_OBJECTS = 5_000
MAX_PDF_PAGES = 10


def validate_file_upload(
    file_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> str:
    """Full file validation.  Returns the validated content type.

    Checks in order:
    1. File size (min/max)
    2. Extension whitelist
    3. Content-Type whitelist
    4. Magic bytes
    5. PDF complexity (object count, page count)

    Raises ValueError on any failure.
    """

    # ── 1. Size ─────────────────────────────────────────────────────
    size = len(file_bytes)
    if size < MIN_FILE_SIZE:
        logger.warning("file_guard:too_small size=%d", size)
        raise ValueError("File is too small or empty")
    if size > MAX_FILE_SIZE:
        logger.warning("file_guard:too_large size=%d limit=%d", size, MAX_FILE_SIZE)
        raise ValueError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit")

    # ── 2. Extension ────────────────────────────────────────────────
    ext = _extract_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("file_guard:bad_extension ext=%s filename=%s", ext, filename)
        raise ValueError(f"File type .{ext} is not allowed (only PDF and DOCX)")

    # ── 3. Content-Type ─────────────────────────────────────────────
    ct = (content_type or "").lower().strip()
    if ct not in ALLOWED_CONTENT_TYPES:
        logger.warning("file_guard:bad_content_type ct=%s", ct)
        raise ValueError("Unsupported content type")

    # ── 4. Magic bytes ──────────────────────────────────────────────
    if ext == "pdf":
        if not file_bytes[:5].startswith(MAGIC_PDF):
            logger.warning("file_guard:bad_magic expected=PDF got=%s", file_bytes[:8])
            raise ValueError("File content does not match PDF format")
    elif ext == "docx":
        if not file_bytes[:4].startswith(MAGIC_DOCX):
            logger.warning("file_guard:bad_magic expected=DOCX(ZIP) got=%s", file_bytes[:8])
            raise ValueError("File content does not match DOCX format")

    # ── 5. PDF complexity ───────────────────────────────────────────
    if ext == "pdf":
        _check_pdf_complexity(file_bytes)

    logger.info("file_guard:ok size=%d ext=%s ct=%s", size, ext, ct)
    return ct


def _extract_extension(filename: str | None) -> str:
    """Extract and normalise extension from filename."""
    if not filename:
        return ""
    parts = filename.rsplit(".", 1)
    if len(parts) < 2:
        return ""
    return parts[-1].lower().strip()


def _check_pdf_complexity(data: bytes) -> None:
    """Reject PDFs with too many objects or pages (bomb protection)."""
    obj_count = data.count(b" obj")
    if obj_count > MAX_PDF_OBJECTS:
        logger.warning("file_guard:pdf_bomb objects=%d limit=%d", obj_count, MAX_PDF_OBJECTS)
        raise ValueError("PDF is too complex (too many objects)")

    page_count = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    if page_count > MAX_PDF_PAGES:
        logger.warning("file_guard:pdf_too_long pages=%d limit=%d", page_count, MAX_PDF_PAGES)
        raise ValueError(f"PDF has too many pages (max {MAX_PDF_PAGES})")


def validate_text_payload(text: str, max_length: int = 200_000) -> None:
    """Guard against oversized text payloads (memory/CPU protection)."""
    if len(text) > max_length:
        raise ValueError(f"Text exceeds {max_length} character limit")
