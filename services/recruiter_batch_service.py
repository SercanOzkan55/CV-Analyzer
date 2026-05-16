from __future__ import annotations

from collections.abc import Callable, Iterable


def rank_cv_texts(
    cv_items: Iterable[dict],
    jd_text: str,
    *,
    run_pipeline: Callable[[str, str], dict],
    include_cv_text: bool = False,
) -> dict:
    """Rank extracted CV texts against one job description."""

    ranked = []
    skill_counts: dict[str, int] = {}

    for idx, item in enumerate(cv_items):
        cv_text = str(item.get("cv_text") or "")
        file_name = str(item.get("file_name") or f"candidate_{idx + 1}.pdf")
        candidate_name = str(item.get("candidate_name") or file_name or f"candidate_{idx + 1}")

        result = run_pipeline(cv_text, jd_text)
        detected_skills = result.get("detected_skills") or []
        for skill in detected_skills:
            key = str(skill or "").strip().lower()
            if key:
                skill_counts[key] = skill_counts.get(key, 0) + 1

        row = {
            "candidate_name": candidate_name,
            "file_name": file_name,
            "final_score": float(result.get("final_score") or 0.0),
            "ats_score": float(result.get("ats_score") or 0.0),
            "skill_score": float(result.get("skill_score") or 0.0),
            "missing_skills": result.get("missing_skills") or [],
            "keyword_gap": result.get("keyword_gap") or {},
            "score_breakdown": result.get("score_breakdown") or {},
            "recommendations": result.get("recommendations") or [],
        }
        if include_cv_text:
            row["cv_text"] = cv_text
        ranked.append(row)

    ranked.sort(key=lambda row: row["final_score"], reverse=True)
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx

    total = len(ranked)
    avg_score = round(sum(row["final_score"] for row in ranked) / max(1, total), 2)
    distribution = {
        "high": sum(1 for row in ranked if row["final_score"] >= 75),
        "medium": sum(1 for row in ranked if 50 <= row["final_score"] < 75),
        "low": sum(1 for row in ranked if row["final_score"] < 50),
    }
    top_skills = sorted(skill_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total_candidates": total,
        "ranking": ranked,
        "analytics": {
            "avg_score": avg_score,
            "top_skills": [{"skill": skill, "count": count} for skill, count in top_skills],
            "candidate_distribution": distribution,
        },
    }
