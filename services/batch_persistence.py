"""Persist batch processing results to the DB for recruiter dashboard.

This module provides a small helper used by batch processors to save
candidate analyses into the `candidate_actions` table via
`services.recruiter_service.save_candidate_action`.

The function is defensive: if DB is unavailable it will log and return
without raising to avoid breaking batch pipelines.
"""
import logging
from typing import List, Dict, Any

from database import SessionLocal
from services.recruiter_service import save_candidate_action

_log = logging.getLogger("app.batch_persist")


def persist_batch_results(
    results: List[Dict[str, Any]],
    org_id: int,
    job_id: int,
    recruiter_id: int,
) -> int:
    """Persist a list of processed candidate results.

    Each item in `results` is expected to contain at least:
      - filename or candidate_name
      - final_score
      - ats_score
      - details or analysis (full analysis snapshot)

    Returns number of records successfully written.
    """
    written = 0
    try:
        db = SessionLocal()
    except Exception as e:
        _log.error("persist_batch: failed to acquire DB session: %s", e)
        return 0

    try:
        for item in results:
            try:
                name = item.get("candidate_name") or item.get("filename") or "Unknown"
                email = item.get("candidate_email")
                cv_text = item.get("cv_text") or item.get("snippet") or None
                cv_file_key = item.get("cv_file_key") or item.get("file_key")
                cv_file_name = item.get("cv_file_name") or item.get("filename")
                cv_file_type = item.get("cv_file_type") or item.get("file_type")
                final_score = item.get("final_score")
                ats_score = item.get("ats_score") or item.get("ats") and item.get("ats").get("score")
                analysis_snapshot = item.get("details") or item.get("analysis") or item

                save_candidate_action(
                    db=db,
                    org_id=org_id,
                    job_id=job_id,
                    recruiter_id=recruiter_id,
                    candidate_name=name,
                    candidate_email=email,
                    cv_text=cv_text,
                    final_score=final_score,
                    ats_score=ats_score,
                    action="pending",
                    analysis_snapshot=analysis_snapshot,
                    cv_file_key=cv_file_key,
                    cv_file_name=cv_file_name,
                    cv_file_type=cv_file_type,
                )
                written += 1
            except Exception as e:
                _log.exception("persist_batch: failed to persist item %s: %s", item.get("filename"), e)
    finally:
        try:
            db.close()
        except Exception:
            pass

    _log.info("persist_batch: wrote %d/%d records for job=%s org=%s", written, len(results), job_id, org_id)
    return written
