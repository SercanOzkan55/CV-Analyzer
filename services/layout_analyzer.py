"""Layout analyzer — structural analysis of raw CV text.

Detects layout properties (columns, indentation, bullet patterns, header
styles) without any CV-domain knowledge.  Returns a ``LayoutInfo`` that
downstream stages (classifier, resolver) consume.

Pipeline position:  extract_agent → **layout_analyzer** → section_classifier
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Set, Tuple

# ── Column-gap detection ──────────────────────────────────────────────────
_GAP_RE = re.compile(r"^(\S.+?)\s{4,}(\S.+)$")

# ── Bullet patterns (domain-agnostic) ────────────────────────────────────
_BULLET_PATTERNS: Dict[str, re.Pattern] = {
    "dash": re.compile(r"^\s*[-–—]\s"),
    "dot": re.compile(r"^\s*[•·∙▪▸►]\s"),
    "star": re.compile(r"^\s*\*\s"),
    "number": re.compile(r"^\s*\d+[.)]\s"),
    "letter": re.compile(r"^\s*[a-zA-Z][.)]\s"),
}

# ── Underline / separator markers ─────────────────────────────────────────
_UNDERLINE_RE = re.compile(r"^[-=_]{3,}\s*$")

# ── Types ─────────────────────────────────────────────────────────────────
LayoutType = Literal[
    "default", "sidebar", "academic", "developer",
    "skills_heavy", "no_header", "ats_clean",
]
HeaderStyle = Literal["allcaps", "titlecase", "underline", "mixed", "none"]

# ── Structural signal patterns (domain-agnostic) ─────────────────────────
_DATE_LIKE_RE = re.compile(
    r"\b\d{4}\s*[-–—/]\s*(?:\d{4}|present|current|ongoing|halen|devam)"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
    r"|oca|şub|mar|nis|may|haz|tem|ağu|eyl|eki|kas|ara)[a-zıöüşçğ]*\s+\d{4}",
    re.I,
)
_URL_LIKE_RE = re.compile(r"https?://|github\.com|gitlab\.com|linkedin\.com|bitbucket\.org", re.I)
_COMMA_RE = re.compile(r",")


@dataclass
class LayoutInfo:
    """Structural layout descriptor — no CV-domain knowledge."""

    layout_type: LayoutType = "default"
    linearized_text: str = ""
    indent_levels: Set[int] = field(default_factory=set)
    bullet_styles: Dict[str, int] = field(default_factory=dict)
    header_style: HeaderStyle = "none"
    avg_line_length: float = 0.0
    blank_line_ratio: float = 0.0
    line_count: int = 0
    has_underline_markers: bool = False
    is_multi_column: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def analyze_layout(text: str) -> LayoutInfo:
    """Analyze structural layout of *text*.

    Returns a ``LayoutInfo`` whose ``.linearized_text`` is guaranteed to
    be single-column (multi-column text is reconstructed).
    """
    info = LayoutInfo()
    if not text or not text.strip():
        info.linearized_text = text or ""
        return info

    lines = text.split("\n")
    info.line_count = len(lines)

    # 1. Multi-column detection and linearization
    linearized = _detect_and_linearize_columns(text, lines)
    info.is_multi_column = linearized != text
    info.linearized_text = linearized

    # Remaining analysis uses the linearized text
    work_lines = linearized.split("\n")

    # 2. Indentation analysis
    info.indent_levels = _detect_indent_levels(work_lines)

    # 3. Bullet style analysis
    info.bullet_styles = _detect_bullet_styles(work_lines)

    # 4. Header style detection
    info.header_style, info.has_underline_markers = _detect_header_style(work_lines)

    # 5. Line statistics
    non_empty = [l for l in work_lines if l.strip()]
    if non_empty:
        info.avg_line_length = sum(len(l.strip()) for l in non_empty) / len(non_empty)
    total = len(work_lines)
    blank = sum(1 for l in work_lines if not l.strip())
    info.blank_line_ratio = blank / max(total, 1)

    # 6. Classify layout type using structural signals
    info.layout_type = _classify_layout(work_lines, non_empty, info)

    return info


def _classify_layout(
    work_lines: List[str],
    non_empty: List[str],
    info: "LayoutInfo",
) -> LayoutType:
    """Determine layout type using structural signals only.

    Rules (checked in order):
    - sidebar: multi-column OR many short lines
    - academic: many date-like patterns
    - developer: many urls
    - skills_heavy: many commas (comma-separated token lists)
    - no_header: few detected headers
    - ats_clean: underline markers + allcaps headers + moderate structure
    - default: everything else
    """
    n = max(len(non_empty), 1)

    # Count structural signals
    date_count = sum(1 for l in non_empty if _DATE_LIKE_RE.search(l))
    url_count = sum(1 for l in non_empty if _URL_LIKE_RE.search(l))
    comma_count = sum(len(_COMMA_RE.findall(l)) for l in non_empty)
    short_lines = sum(1 for l in non_empty if len(l.strip()) < 30)

    # Count header-like lines (short, uppercase or titlecase, no digits/urls)
    header_count = 0
    for l in non_empty:
        s = l.strip()
        words = s.split()
        if 1 <= len(words) <= 4 and len(s) <= 40:
            alpha = "".join(c for c in s if c.isalpha())
            if alpha and (alpha == alpha.upper() or all(w[0].isupper() for w in words if w[0].isalpha())):
                header_count += 1

    # sidebar: multi-column OR >40% short lines with many indentation levels
    if info.is_multi_column:
        return "sidebar"
    if short_lines > n * 0.4 and len(info.indent_levels) >= 3:
        return "sidebar"

    # academic: >15% of lines have date patterns
    if date_count > n * 0.15 and date_count >= 4:
        return "academic"

    # developer: >10% of lines have urls
    if url_count > n * 0.10 and url_count >= 3:
        return "developer"

    # skills_heavy: >2 commas per non-empty line on average
    if n >= 3 and comma_count / n > 2.0:
        return "skills_heavy"

    # no_header: fewer than 2 detected headers in a reasonably sized document
    if n >= 10 and header_count < 2:
        return "no_header"

    # ats_clean: underline markers + allcaps/underline headers + moderate line length
    if info.has_underline_markers and info.header_style in ("allcaps", "underline"):
        return "ats_clean"

    return "default"


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _detect_and_linearize_columns(text: str, lines: List[str]) -> str:
    """Detect interleaved multi-column text and linearize into single column.

    PDF extractors sometimes read columns left-to-right per row instead of
    reading each column top-to-bottom.  This produces interleaved text where
    left-column and right-column content alternate on each line separated by
    large whitespace gaps.

    Heuristic: if >=3 non-empty lines and >20% contain a gap of 4+ spaces,
    treat them as two columns and reconstruct left-col then right-col.
    """
    left_parts: List[str] = []
    right_parts: List[str] = []
    gap_count = 0
    total_nonempty = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            left_parts.append("")
            right_parts.append("")
            continue
        total_nonempty += 1
        m = _GAP_RE.match(stripped)
        if m:
            gap_count += 1
            left_parts.append(m.group(1).strip())
            right_parts.append(m.group(2).strip())
        else:
            left_parts.append(stripped)

    if total_nonempty > 0 and gap_count >= 3 and gap_count > total_nonempty * 0.2:
        while left_parts and not left_parts[-1]:
            left_parts.pop()
        while right_parts and not right_parts[-1]:
            right_parts.pop()
        return "\n".join(left_parts) + "\n\n" + "\n".join(right_parts)

    return text


def _detect_indent_levels(lines: List[str]) -> Set[int]:
    """Return the set of unique leading-space counts observed."""
    levels: Set[int] = set()
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        levels.add(indent)
    return levels


def _detect_bullet_styles(lines: List[str]) -> Dict[str, int]:
    """Count occurrences of each bullet style."""
    counts: Dict[str, int] = {}
    for line in lines:
        for style, pattern in _BULLET_PATTERNS.items():
            if pattern.match(line):
                counts[style] = counts.get(style, 0) + 1
                break
    return counts


def _detect_header_style(lines: List[str]) -> Tuple[HeaderStyle, bool]:
    """Detect dominant header formatting style."""
    allcaps_count = 0
    titlecase_count = 0
    has_underline = False

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 2:
            continue

        if _UNDERLINE_RE.match(stripped):
            has_underline = True
            continue

        words = stripped.split()
        if 1 <= len(words) <= 5 and len(stripped) <= 40:
            alpha_only = "".join(c for c in stripped if c.isalpha())
            if alpha_only and alpha_only == alpha_only.upper() and len(alpha_only) >= 2:
                allcaps_count += 1
            elif all(w[0].isupper() for w in words if w and w[0].isalpha()):
                titlecase_count += 1

    if has_underline:
        style: HeaderStyle = "underline"
    elif allcaps_count >= 3 and allcaps_count > titlecase_count:
        style = "allcaps"
    elif titlecase_count >= 3 and titlecase_count > allcaps_count:
        style = "titlecase"
    elif allcaps_count >= 1 and titlecase_count >= 1:
        style = "mixed"
    else:
        style = "none"

    return style, has_underline
