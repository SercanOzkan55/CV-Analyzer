from services.recruiter_batch_service import rank_cv_texts


def test_rank_cv_texts_sorts_candidates_and_builds_distribution():
    def fake_pipeline(cv_text, jd_text):
        scores = {"A": 82, "B": 47, "C": 65}
        return {
            "final_score": scores[cv_text],
            "ats_score": scores[cv_text] - 5,
            "skill_score": scores[cv_text] - 10,
            "detected_skills": ["python", "sql"] if cv_text != "B" else ["sql"],
            "missing_skills": ["kubernetes"],
            "keyword_gap": {"missing_words": ["cloud"]},
            "score_breakdown": {"skills": scores[cv_text]},
            "recommendations": ["Tighten impact statements"],
        }

    result = rank_cv_texts(
        [
            {"candidate_name": "Candidate B", "file_name": "b.pdf", "cv_text": "B"},
            {"candidate_name": "Candidate A", "file_name": "a.pdf", "cv_text": "A"},
            {"candidate_name": "Candidate C", "file_name": "c.pdf", "cv_text": "C"},
        ],
        "Backend engineer",
        run_pipeline=fake_pipeline,
    )

    assert [row["candidate_name"] for row in result["ranking"]] == [
        "Candidate A",
        "Candidate C",
        "Candidate B",
    ]
    assert [row["rank"] for row in result["ranking"]] == [1, 2, 3]
    assert result["analytics"]["candidate_distribution"] == {"high": 1, "medium": 1, "low": 1}
    assert result["analytics"]["top_skills"][0] == {"skill": "sql", "count": 3}


def test_rank_cv_texts_can_include_cv_text_for_dashboard_batch_upload():
    result = rank_cv_texts(
        [{"candidate_name": "A", "file_name": "a.txt", "cv_text": "CV"}],
        "JD",
        run_pipeline=lambda _cv, _jd: {"final_score": 90},
        include_cv_text=True,
    )

    assert result["ranking"][0]["cv_text"] == "CV"
