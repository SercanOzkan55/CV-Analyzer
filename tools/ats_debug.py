"""Simple CLI to debug ATS final score breakdown for a single CV + JD.

Usage:
  python tools/ats_debug.py --cv path/to/cv.txt --jd path/to/jd.txt

If `--jd` omitted, runs standalone CV analysis.
"""

import argparse
import json
from services.ats_service import analyze_cv, compute_final_score


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cv", required=True, help="Path to CV text file")
    p.add_argument("--jd", required=False, help="Path to job description text file")
    args = p.parse_args()

    cv_text = load_text(args.cv)
    jd_text = load_text(args.jd) if args.jd else ""

    ats = analyze_cv(cv_text, jd_text)

    # assemble inputs for compute_final_score
    keyword = float(ats.get("content", {}).get("keyword_score", 0.0))
    section = float(ats.get("layout", {}).get("section_presence_score", 0.0))
    # Extract experience and skills from section_scores (not section_presence!)
    section_map = {s["name"]: s.get("score", 0) for s in ats.get("section_scores", [])}
    exp = float(section_map.get("experience", 60.0))
    skills = float(section_map.get("skills", 60.0))
    layout = float(ats.get("layout", {}).get("formatting_score", 0.0))
    contact = float(ats.get("layout", {}).get("contact_score", 0.0))

    # ML score: attempt to import family's ml predict bridge from main pipeline
    try:
        from main import ml_predict_score

        ml_score = float(ml_predict_score([]))
    except Exception:
        ml_score = 50.0

    breakdown = compute_final_score(
        keyword=keyword,
        section=section,
        exp=exp,
        skills=skills,
        layout=layout,
        contact=contact,
        ml_score=ml_score,
        debug=True,
    )

    out = {
        "ats_details": ats,
        "breakdown": breakdown,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
