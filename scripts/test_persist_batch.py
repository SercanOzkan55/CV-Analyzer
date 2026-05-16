import logging
from services.batch_persistence import persist_batch_results

logging.basicConfig(level=logging.INFO)

sample_results = [
    {
        "filename": "sample_cv.pdf",
        "candidate_name": "John Doe",
        "candidate_email": "john@example.com",
        "cv_text": "Experienced Python developer...",
        "final_score": 78.5,
        "ats_score": 74.0,
        "details": {"detected_skills": ["python", "sql"]}
    }
]

written = persist_batch_results(sample_results, org_id=1, job_id=1, recruiter_id=1)
print("persist_batch_results returned:", written)
