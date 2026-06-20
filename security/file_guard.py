"""File upload security guard.

Validates file size, extension, MIME type, and magic bytes before
any processing or storage happens.
"""

import io
import logging
import zipfile

from config.aws import (
    ALLOWED_CONTENT_TYPES,
    MAX_DOCX_COMPRESSION_RATIO,
    MAX_DOCX_FILES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_PDF_OBJECTS,
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
)

logger = logging.getLogger("security.file_guard")

# ── Magic byte signatures ───────────────────────────────────────────
MAGIC_PDF = b"%PDF-"
MAGIC_DOCX = b"PK\x03\x04"  # ZIP (OOXML is ZIP-based)

# ── Limits ──────────────────────────────────────────────────────────
MAX_FILE_SIZE = MAX_UPLOAD_BYTES
MIN_FILE_SIZE = 100              # too small = empty/garbage

ALLOWED_EXTENSIONS = frozenset({"pdf", "docx", "txt"})


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
        raise ValueError(f"File too large; exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit")

    # ── 2. Extension ────────────────────────────────────────────────
    ext = _extract_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("file_guard:bad_extension ext=%s filename=%s", ext, filename)
        raise ValueError(f"File type .{ext} is not allowed (only PDF, DOCX, and TXT)")

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
    elif ext == "txt":
        if b"\x00" in file_bytes:
            logger.warning("file_guard:bad_magic expected=TXT got null bytes")
            raise ValueError("File content does not match plain text format")

    # ── 5. PDF complexity ───────────────────────────────────────────
    if ext == "pdf":
        _check_pdf_complexity(file_bytes)
    elif ext == "docx":
        _check_docx_archive(file_bytes)

    logger.info("file_guard:ok size=%d ext=%s ct=%s", size, ext, ct)
    return ct


async def read_upload_limited(upload_file, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an UploadFile in chunks and stop once it exceeds max_bytes."""
    data = bytearray()
    while True:
        chunk = await upload_file.read(1024 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            logger.warning(
                "file_guard:stream_too_large filename=%s size>%d",
                getattr(upload_file, "filename", None),
                max_bytes,
            )
            raise ValueError(f"File too large; exceeds {max_bytes // (1024 * 1024)} MB limit")
    return bytes(data)


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


def _check_docx_archive(data: bytes) -> None:
    """Reject malformed or abusive DOCX ZIP archives."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_FILES:
                logger.warning("file_guard:docx_too_many_files count=%d", len(entries))
                raise ValueError("DOCX is too complex")

            names = {item.filename for item in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                logger.warning("file_guard:docx_missing_required_parts")
                raise ValueError("File content does not match DOCX format")

            uncompressed_total = 0
            compressed_total = 0
            for item in entries:
                name = item.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    logger.warning("file_guard:docx_path_traversal name=%s", item.filename[:80])
                    raise ValueError("Unsafe DOCX archive path")
                if item.flag_bits & 0x1:
                    logger.warning("file_guard:docx_encrypted name=%s", item.filename[:80])
                    raise ValueError("Encrypted DOCX files are not supported")
                uncompressed_total += int(item.file_size or 0)
                compressed_total += int(item.compress_size or 0)

            if uncompressed_total > MAX_DOCX_UNCOMPRESSED_BYTES:
                logger.warning(
                    "file_guard:docx_too_large_uncompressed size=%d limit=%d",
                    uncompressed_total,
                    MAX_DOCX_UNCOMPRESSED_BYTES,
                )
                raise ValueError("DOCX is too large after decompression")

            if compressed_total > 0:
                ratio = uncompressed_total / max(compressed_total, 1)
                if ratio > MAX_DOCX_COMPRESSION_RATIO:
                    logger.warning(
                        "file_guard:docx_zip_bomb_ratio ratio=%.2f limit=%d",
                        ratio,
                        MAX_DOCX_COMPRESSION_RATIO,
                    )
                    raise ValueError("DOCX compression ratio is unsafe")
    except zipfile.BadZipFile as exc:
        logger.warning("file_guard:bad_docx_zip")
        raise ValueError("File content does not match DOCX format") from exc


def validate_text_payload(text: str, max_length: int = 200_000) -> None:
    """Guard against oversized text payloads (memory/CPU protection)."""
    if len(text) > max_length:
        raise ValueError(f"Text exceeds {max_length} character limit")


def validate_zip_archive(file_path: str) -> None:
    """Validate ZIP archive for safety before processing.

    Checks:
    - Max uncompressed files: 200
    - Max uncompressed total bytes: 100MB
    - Max single file uncompressed size: 10MB
    - Unsafe path traversals (.. or starting with /)
    - Unsafe compression ratio (> 50.0 for files > 10KB)
    - Encrypted zip entries
    """
    MAX_ZIP_FILES = 200
    MAX_ZIP_UNCOMPRESSED_BYTES = 100_000_000
    MAX_ZIP_SINGLE_FILE_UNCOMPRESSED = 10_000_000
    MAX_ZIP_COMPRESSION_RATIO = 50.0

    try:
        with zipfile.ZipFile(file_path, 'r') as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_FILES:
                logger.warning("file_guard:zip_too_many_files count=%d limit=%d", len(entries), MAX_ZIP_FILES)
                raise ValueError("ZIP archive contains too many files")

            uncompressed_total = 0
            for item in entries:
                if item.is_dir():
                    continue

                # Path traversal check
                name = item.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    logger.warning("file_guard:zip_path_traversal name=%s", item.filename[:80])
                    raise ValueError("ZIP archive contains unsafe file path")

                # Encryption check
                if item.flag_bits & 0x1:
                    logger.warning("file_guard:zip_encrypted name=%s", item.filename[:80])
                    raise ValueError("Encrypted files in ZIP are not supported")

                # Size checks
                file_size = int(item.file_size or 0)
                if file_size > MAX_ZIP_SINGLE_FILE_UNCOMPRESSED:
                    logger.warning("file_guard:zip_file_too_large name=%s size=%d limit=%d", item.filename[:80], file_size, MAX_ZIP_SINGLE_FILE_UNCOMPRESSED)
                    raise ValueError("File inside ZIP is too large")

                # Compression ratio check
                compress_size = int(item.compress_size or 0)
                if file_size > 10240 and compress_size > 0:
                    ratio = file_size / max(compress_size, 1)
                    if ratio > MAX_ZIP_COMPRESSION_RATIO:
                        logger.warning("file_guard:zip_bomb_ratio name=%s ratio=%.2f limit=%d", item.filename[:80], ratio, MAX_ZIP_COMPRESSION_RATIO)
                        raise ValueError("ZIP archive compression ratio is unsafe")

                uncompressed_total += file_size

            if uncompressed_total > MAX_ZIP_UNCOMPRESSED_BYTES:
                logger.warning("file_guard:zip_too_large_uncompressed size=%d limit=%d", uncompressed_total, MAX_ZIP_UNCOMPRESSED_BYTES)
                raise ValueError("ZIP archive uncompressed size too large")

    except zipfile.BadZipFile as exc:
        logger.warning("file_guard:bad_zip")
        raise ValueError("File content does not match ZIP format") from exc
