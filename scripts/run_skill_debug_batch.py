"""Quick runner to inspect skill extraction on a batch of CV files.

Usage:
  python scripts/run_skill_debug_batch.py --cvdir sample_cvs --jd "Senior Python Developer..."

This tool is for local debugging: it loads each CV, extracts skills using
`services.skill_service`, computes coverage against a provided job
description, and prints structured output. It does not modify project state.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so imports like `services.*` work when
# running this script directly (e.g. `python scripts/run_skill_debug_batch.py`).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import pdfplumber
except Exception:
    pdfplumber = None

from services.skill_service import extract_skills, skill_coverage_score


def extract_text_from_file(path: Path) -> str:
    # Prefer the fast/robust extractor from utils.cv_processor when available.
    try:
        from utils.cv_processor import extract_text_fast
    except Exception:
        extract_text_fast = None

    try:
        content = path.read_bytes()
    except Exception:
        return ""

    if extract_text_fast:
        try:
            return extract_text_fast(content, path.name)
        except Exception:
            # Fall through to simpler extraction on error
            pass

    # Fallback behaviours (preserve original script semantics)
    if path.suffix.lower() in (".txt", ".md"):
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    if path.suffix.lower() == ".pdf" and pdfplumber is not None:
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
                return "\n".join(pages)
        except Exception:
            return ""

    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cvdir", default="sample_cvs", help="Directory with CV files")
    p.add_argument("--jd", default="", help="Job description text to match against")
    p.add_argument("--jd-file", default="", help="Path to job description file")
    p.add_argument("--out", default="skill_debug_output.json", help="Output JSON file")
    args = p.parse_args()

    cvdir = Path(args.cvdir)
    if args.jd_file:
        jd_text = Path(args.jd_file).read_text(encoding="utf-8", errors="ignore")
    else:
        jd_text = args.jd or ""

    results = []
    if not cvdir.exists():
        print(f"CV directory not found: {cvdir}")
        return

    for path in sorted(cvdir.glob("**/*")):
        if path.is_dir():
            continue
        if path.suffix.lower() not in (".txt", ".md", ".pdf", ".docx"):
            continue

        text = extract_text_from_file(path)
        if not text:
            print(f"{path.name}: empty or unreadable")
            continue

        skill_data = extract_skills(text)
        score, missing = skill_coverage_score(text, jd_text) if jd_text else (None, None)

        entry = {
            "file": str(path),
            "detected_skills": sorted(skill_data.get("found", [])),
            "by_category": {k: sorted(list(v)) for k, v in skill_data.get("by_category", {}).items()},
            "skill_coverage": score,
            "missing": missing,
            "snippet": (text or "")[:800].replace("\n", " ")[:800],
        }
        results.append(entry)
        # Print safely to avoid Windows console encoding errors (e.g. cp1254)
        try:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        except UnicodeEncodeError:
            # Fallback to ASCII-safe output when console cannot print Unicode
            print(json.dumps(entry, ensure_ascii=True, indent=2))

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} results to {args.out}")


if __name__ == "__main__":
    main()
