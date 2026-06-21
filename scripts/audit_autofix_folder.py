"""Audit CV auto-fix behavior across a local folder of CV files.

This script is intentionally read-only: it extracts text, runs the current
auto-fix pipeline, and writes a report showing score deltas and protected
section preservation. Use it before enabling AI for a large corpus so the
expensive pass can focus only on flagged CVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.cv_autofix_service import (  # noqa: E402
    PROTECTED_SECTION_KEYS,
    _non_empty_section_lines,
    _parse_sections,
    auto_fix_cv_text,
)
from utils.cv_processor import extract_text_fast  # noqa: E402


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


def iter_cv_files(folder: Path) -> Iterable[Path]:
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def section_counts(text: str) -> dict[str, int]:
    _, sections, _ = _parse_sections(text or "")
    return {key: len(_non_empty_section_lines(sections, key)) for key in sorted(PROTECTED_SECTION_KEYS)}


def shrunk_sections(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return [key for key, before_count in before.items() if before_count > 0 and after.get(key, 0) < before_count]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8", errors="ignore")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit auto-fix output quality for a folder of CV files.")
    parser.add_argument("folder", type=Path, help="Folder containing PDF/DOCX/TXT CVs")
    parser.add_argument(
        "--job-description",
        default="",
        help="Optional job description used by ATS scoring.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("autofix_audit_results"),
        help="Output directory for CSV/JSONL and flagged text snapshots.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max files to process")
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Allow AI rewrite if REWRITE_PROVIDER and OPENAI_API_KEY are configured.",
    )
    args = parser.parse_args()

    folder = args.folder
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "autofix_audit.csv"
    jsonl_path = out_dir / "autofix_audit.jsonl"
    flagged_dir = out_dir / "flagged_outputs"

    rows: list[dict] = []
    files = list(iter_cv_files(folder))
    if args.limit > 0:
        files = files[: args.limit]

    for index, path in enumerate(files, start=1):
        rel = str(path.relative_to(folder))
        row = {
            "file": rel,
            "status": "ok",
            "before_score": "",
            "after_score": "",
            "score_delta": "",
            "shrunk_sections": "",
            "warnings": "",
            "error": "",
        }
        try:
            content = path.read_bytes()
            text = extract_text_fast(content, path.name)
            if not text.strip():
                row["status"] = "extract_empty"
                rows.append(row)
                continue

            before_counts = section_counts(text)
            result = auto_fix_cv_text(
                text,
                job_description=args.job_description,
                use_ai=args.use_ai,
            )
            optimized = str(result.get("optimized_cv_text") or result.get("optimized_text") or "")
            after_counts = section_counts(optimized)
            shrunk = shrunk_sections(before_counts, after_counts)

            before_ats = result.get("before_ats") or {}
            after_ats = result.get("after_ats") or {}
            delta = float(result.get("score_delta") or 0)
            warnings = result.get("warnings") or []

            row.update(
                {
                    "before_score": before_ats.get("overall_score", ""),
                    "after_score": after_ats.get("overall_score", ""),
                    "score_delta": delta,
                    "shrunk_sections": ",".join(shrunk),
                    "warnings": " | ".join(str(w) for w in warnings),
                }
            )

            if delta < 0 or shrunk or warnings:
                row["status"] = "flagged"
                safe_name = f"{index:05d}_{path.stem[:80]}"
                write_text(flagged_dir / f"{safe_name}_before.txt", text)
                write_text(flagged_dir / f"{safe_name}_after.txt", optimized)

        except Exception as exc:  # pragma: no cover - local diagnostic script
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"

        rows.append(row)
        print(f"[{index}/{len(files)}] {row['status']}: {rel}")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "total": len(rows),
        "ok": sum(1 for r in rows if r["status"] == "ok"),
        "flagged": sum(1 for r in rows if r["status"] == "flagged"),
        "extract_empty": sum(1 for r in rows if r["status"] == "extract_empty"),
        "error": sum(1 for r in rows if r["status"] == "error"),
        "csv": str(csv_path),
        "jsonl": str(jsonl_path),
        "flagged_outputs": str(flagged_dir),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
