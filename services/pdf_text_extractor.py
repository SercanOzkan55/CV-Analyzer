"""PDF text extraction helpers with page-level column reconstruction."""

from __future__ import annotations

import io
import logging
import re
from statistics import median
from typing import Callable

from fastapi import HTTPException


_SECTION_HEADING_RE = re.compile(
    r"\b(profile|summary|objective|about|skills?|proficient|experience|employment|work|history"
    r"|projects?|education|academic|certifications?|languages?|personal|executive"
    r"|deneyim|egitim|e\u011fitim|yetenek|beceri|projeler|diller|profil|ozet|\u00f6zet)\b",
    re.I,
)

_MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "â€™", "â€œ", "â€", "Â")

# Word-boundary tolerance as a fraction of font size, rather than a fixed
# point value. pdfplumber's default fixed x_tolerance=3 glues words together
# in PDFs that position glyphs tightly and omit explicit space characters
# (common with some resume templates and CMYK/print-oriented exporters). A
# font-relative tolerance self-adapts: tight layouts split correctly while
# normally-spaced layouts are unaffected (verified to leave word counts
# identical across well-behaved CVs).
_X_TOLERANCE_RATIO = 0.16


# Repeating page furniture (footers/headers) that PDF exporters stamp on every
# page and that otherwise leak into the last section on each page — e.g.
# "Created by UC Davis Career Center | careercenter.ucdavis.edu 22",
# "Smith Page 2 of 3". Patterns are deliberately narrow and only applied to
# short lines so real content is never removed.
_PAGE_FURNITURE_RES = (
    re.compile(r"^\s*created by\b.*$", re.I),  # template attribution line
    re.compile(r"^\s*page\s+\d+(?:\s+of\s+\d+)?\s*$", re.I),  # "Page 2 of 3"
    re.compile(r"^.{0,40}?\bpage\s+\d+(?:\s+of\s+\d+)?\s*$", re.I),  # "Name Page 2"
    # Bare page count like "1 of 3" / "12 of 20" only. The prefixed variant
    # ("Aduba 1 of 3") is intentionally NOT matched: it is structurally
    # indistinguishable from real content such as "Rated top 2 of 50" or
    # "Ranked 1 of 500", so matching it silently dropped achievement lines.
    re.compile(r"^\s*\d{1,3}\s+of\s+\d{1,2}\s*$", re.I),  # "1 of 3"
    re.compile(r"^\s*\S+\.(?:edu|com|org|net)\S*\s*[|\-–]?\s*\d{1,3}\s*$", re.I),  # "site.edu 22"
)


def _strip_page_furniture(text: str) -> str:
    """Drop repeating footer/header lines (page numbers, template credits)."""
    if not text:
        return text
    kept = []
    for line in text.split("\n"):
        probe = line.strip()
        if probe and len(probe) <= 70 and any(rx.match(probe) for rx in _PAGE_FURNITURE_RES):
            continue
        kept.append(line)
    return "\n".join(kept)


# Symbol fonts (Wingdings/Webdings) extract as Unicode private-use codepoints
# (e.g. U+F076, U+F0B7). Downstream classifiers treat them as opaque letters,
# which breaks bullet detection and pollutes skills/languages.
_PRIVATE_USE_RE = re.compile("[\ue000-\uf8ff]+")


def _normalize_private_use_glyphs(text: str) -> str:
    """Turn leading symbol-font glyphs into real bullets; drop the rest."""
    if not text or not _PRIVATE_USE_RE.search(text):
        return text
    out = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped and _PRIVATE_USE_RE.match(stripped):
            indent = line[: len(line) - len(stripped)]
            line = indent + "• " + _PRIVATE_USE_RE.sub(" ", stripped).strip()
        else:
            line = _PRIVATE_USE_RE.sub(" ", line)
        out.append(line)
    return "\n".join(out)


def _mojibake_score(text: str) -> int:
    return sum((text or "").count(marker) for marker in _MOJIBAKE_MARKERS)


def _fix_common_mojibake(text: str) -> str:
    """Repair common UTF-8-as-Windows-1252 extraction artifacts when obvious."""
    if not text or _mojibake_score(text) == 0:
        return text
    try:
        repaired = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if _mojibake_score(repaired) < _mojibake_score(text) else text


def _word_center(word: dict) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2.0


def _line_tolerance(words: list[dict]) -> float:
    heights = [
        float(w.get("bottom", 0)) - float(w.get("top", 0))
        for w in words
        if float(w.get("bottom", 0)) > float(w.get("top", 0))
    ]
    if not heights:
        return 3.5
    return max(3.0, min(6.0, median(heights) * 0.35))


def _words_to_lines(words: list[dict]) -> list[str]:
    if not words:
        return []

    tolerance = _line_tolerance(words)
    ordered = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))
    lines: list[str] = []
    current_top = float(ordered[0]["top"])
    current: list[dict] = []

    for word in ordered:
        top = float(word["top"])
        if current and abs(top - current_top) > tolerance:
            lines.append(" ".join(str(w["text"]) for w in sorted(current, key=lambda w: float(w["x0"]))))
            current = [word]
            current_top = top
        else:
            current.append(word)
            current_top = (current_top + top) / 2.0

    if current:
        lines.append(" ".join(str(w["text"]) for w in sorted(current, key=lambda w: float(w["x0"]))))
    return [line.strip() for line in lines if line.strip()]


def _detect_columns(words: list[dict], page_width: float) -> list[tuple[float, float]]:
    """Detect stable visual columns from word-center projection.

    The old extractor looked for one large gap on each text row. That misses
    templates whose columns are vertically staggered, and it can falsely split
    normal single-column lines that simply contain wide spaces. Word-center
    projection is more stable for CV templates because real columns form dense
    horizontal bands across the page.
    """

    if len(words) < 35 or page_width <= 0:
        return []

    centers = sorted(_word_center(w) for w in words)
    gap_threshold = max(36.0, page_width * 0.06)
    clusters: list[list[float]] = []

    for center in centers:
        if not clusters or center - clusters[-1][-1] > gap_threshold:
            clusters.append([center])
        else:
            clusters[-1].append(center)

    min_words = max(8, int(len(words) * 0.08))
    min_width = max(28.0, page_width * 0.04)
    ranges: list[tuple[float, float, int]] = []
    for cluster in clusters:
        if len(cluster) < min_words:
            continue
        left = min(cluster)
        right = max(cluster)
        if right - left < min_width:
            continue
        ranges.append((max(0.0, left - 12.0), min(page_width, right + 12.0), len(cluster)))

    if len(ranges) < 2:
        return _detect_columns_from_heading_rows(words, page_width)

    ranges.sort(key=lambda item: item[0])
    merged: list[tuple[float, float, int]] = []
    for left, right, count in ranges:
        if merged and left - merged[-1][1] < gap_threshold * 0.65:
            old_left, old_right, old_count = merged[-1]
            merged[-1] = (old_left, max(old_right, right), old_count + count)
        else:
            merged.append((left, right, count))

    if len(merged) >= 2:
        covered_words = sum(item[2] for item in merged)
        if covered_words >= len(words) * 0.45:
            return [(left, right) for left, right, _ in merged[:3]]

    return _detect_columns_from_heading_rows(words, page_width)


def _looks_like_section_heading(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text or "").strip(" :-|")
    if not compact or len(compact) > 46:
        return False
    if not _SECTION_HEADING_RE.search(compact):
        return False
    words = compact.split()
    if len(words) > 4:
        return False
    alpha = re.sub(r"[^A-Za-z\u00c0-\u024f]", "", compact)
    if not alpha:
        return False
    upper_count = sum(1 for ch in alpha if ch.isupper())
    return upper_count / max(len(alpha), 1) >= 0.55 or all(word[:1].isupper() for word in words if word[:1].isalpha())


def _detect_columns_from_heading_rows(
    words: list[dict],
    page_width: float,
) -> list[tuple[float, float]]:
    rows: dict[float, list[dict]] = {}
    for word in words:
        row_key = round(float(word["top"]) / 3.0) * 3.0
        rows.setdefault(row_key, []).append(word)

    candidate_positions: list[float] = []
    gap_threshold = max(24.0, page_width * 0.045)

    for row_words in rows.values():
        ordered = sorted(row_words, key=lambda word: float(word["x0"]))
        if len(ordered) < 2:
            continue
        row_span = float(ordered[-1]["x1"]) - float(ordered[0]["x0"])
        if row_span < page_width * 0.18:
            continue

        best_gap = 0.0
        best_index = -1
        best_pos = 0.0
        for idx in range(len(ordered) - 1):
            gap = float(ordered[idx + 1]["x0"]) - float(ordered[idx]["x1"])
            pos = (float(ordered[idx]["x1"]) + float(ordered[idx + 1]["x0"])) / 2.0
            if gap > best_gap:
                best_gap = gap
                best_index = idx
                best_pos = pos

        if best_gap < gap_threshold:
            continue
        if not (page_width * 0.18 < best_pos < page_width * 0.82):
            continue

        left_text = " ".join(str(word["text"]) for word in ordered[: best_index + 1])
        right_text = " ".join(str(word["text"]) for word in ordered[best_index + 1 :])
        if _looks_like_section_heading(left_text) and _looks_like_section_heading(right_text):
            candidate_positions.append(best_pos)

    if not candidate_positions:
        return []

    candidate_positions.sort()
    clusters: list[list[float]] = []
    tolerance = page_width * 0.08
    for pos in candidate_positions:
        if not clusters or pos - clusters[-1][-1] > tolerance:
            clusters.append([pos])
        else:
            clusters[-1].append(pos)

    boundaries = sorted(median(cluster) for cluster in clusters)[:2]
    min_x = min(float(word["x0"]) for word in words)
    max_x = max(float(word["x1"]) for word in words)

    columns: list[tuple[float, float]] = []
    start = min_x
    for boundary in boundaries:
        if boundary - start < page_width * 0.12:
            continue
        columns.append((max(0.0, start - 8.0), max(start, boundary - 6.0)))
        start = boundary + 6.0
    if max_x - start >= page_width * 0.12:
        columns.append((min(page_width, start), min(page_width, max_x + 8.0)))

    return columns if len(columns) >= 2 else []


def _assign_words_to_columns(words: list[dict], columns: list[tuple[float, float]]) -> list[list[dict]]:
    buckets: list[list[dict]] = [[] for _ in columns]
    if not buckets:
        return buckets

    for word in words:
        center = _word_center(word)
        chosen = 0
        best_distance = float("inf")
        for idx, (left, right) in enumerate(columns):
            if left <= center <= right:
                chosen = idx
                best_distance = 0.0
                break
            distance = min(abs(center - left), abs(center - right))
            if distance < best_distance:
                best_distance = distance
                chosen = idx
        buckets[chosen].append(word)
    return buckets


def _first_parallel_heading_top(
    words: list[dict],
    columns: list[tuple[float, float]],
) -> float | None:
    rows: dict[float, list[dict]] = {}
    for word in words:
        row_key = round(float(word["top"]) / 3.0) * 3.0
        rows.setdefault(row_key, []).append(word)

    for row_top in sorted(rows):
        buckets = _assign_words_to_columns(rows[row_top], columns)
        heading_columns = 0
        for bucket in buckets:
            text = " ".join(str(word["text"]) for word in sorted(bucket, key=lambda w: float(w["x0"])))
            if _looks_like_section_heading(text):
                heading_columns += 1
        if heading_columns >= 2:
            return row_top
    return None


def _extract_pdfplumber_page(
    page,
    *,
    ocr_extract_text: Callable[[bytes], str] | None = None,
) -> tuple[list[str], bool]:
    words = page.extract_words(use_text_flow=False, x_tolerance_ratio=_X_TOLERANCE_RATIO) or []
    if not words:
        try:
            extracted = page.extract_text(x_tolerance_ratio=_X_TOLERANCE_RATIO) or ""
        except Exception:
            extracted = ""
        if extracted.strip():
            return [line.strip() for line in extracted.splitlines() if line.strip()], False

        if ocr_extract_text is not None:
            try:
                page_image = page.to_image(resolution=150).original
                buf = io.BytesIO()
                page_image.save(buf, format="JPEG")
                ocr_text = ocr_extract_text(buf.getvalue()) or ""
                if ocr_text.strip():
                    return [line.strip() for line in ocr_text.splitlines() if line.strip()], False
            except Exception:
                pass
        return [], False

    columns = _detect_columns(words, float(page.width))
    if len(columns) < 2:
        return _words_to_lines(words), False

    page_lines: list[str] = []
    heading_top = _first_parallel_heading_top(words, columns)
    if heading_top is not None:
        header_words = [word for word in words if float(word["top"]) < heading_top - 2.0]
        words = [word for word in words if float(word["top"]) >= heading_top - 2.0]
        header_lines = _words_to_lines(header_words)
        if header_lines:
            page_lines.extend(header_lines)
            page_lines.append("")

    for column_words in _assign_words_to_columns(words, columns):
        column_lines = _words_to_lines(column_words)
        if column_lines:
            if page_lines:
                page_lines.append("")
            page_lines.extend(column_lines)
    return page_lines, True


def extract_pdf_text(
    contents: bytes,
    *,
    max_pages: int,
    max_chars: int,
    ocr_extract_text: Callable[[bytes], str] | None = None,
) -> tuple[str, bool]:
    """Extract PDF text, preserving 1/2/3-column CV layouts."""

    from renderers.blocks import fix_decomposed_diacritics

    try:
        import pdfplumber

        pages_text: list[str] = []
        any_multi_column = False

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            if len(pdf.pages) > max_pages:
                logging.getLogger("app.security").warning("pdf_pages_limit: %d > %d", len(pdf.pages), max_pages)
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF too large (max {max_pages} pages)",
                )

            for page in pdf.pages:
                page_lines, is_multi_column = _extract_pdfplumber_page(
                    page,
                    ocr_extract_text=ocr_extract_text,
                )
                any_multi_column = any_multi_column or is_multi_column
                if page_lines:
                    if pages_text:
                        pages_text.append("")
                    pages_text.extend(page_lines)

        raw = "\n".join(pages_text).strip()
        if raw:
            if any_multi_column:
                raw = "multi_col_fixed\n" + raw
            truncated = len(raw) > max_chars
            if truncated:
                raw = raw[:max_chars]
            return fix_decomposed_diacritics(
                _strip_page_furniture(_normalize_private_use_glyphs(_fix_common_mojibake(raw)))
            ), truncated
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    pages = pdf_reader.pages
    if len(pages) > max_pages:
        pages = pages[:max_pages]

    text_parts = []
    for page in pages:
        extracted = page.extract_text()
        if extracted:
            text_parts.append(extracted)

    raw = "\n".join(text_parts).strip()
    truncated = len(raw) > max_chars
    if truncated:
        logging.getLogger("app.security").warning("pdf_text_truncated: %d > %d", len(raw), max_chars)
        raw = raw[:max_chars]
    return fix_decomposed_diacritics(
        _strip_page_furniture(_normalize_private_use_glyphs(_fix_common_mojibake(raw)))
    ), truncated
