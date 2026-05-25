import pytest
from datetime import datetime
from models import (
    WorkerKey,
    Candidate,
    CandidateAction,
    WorkerAnalysisResult,
    QuotaEvent,
)
from tests.test_worker_mvp import _create_worker_key, _worker_headers


def test_offline_sync_success(client, db_session, recruiter_user, test_job):
    # 1. Create a worker key with quota limit 5
    created_key = _create_worker_key(client, job_id=test_job.id, quota_limit=5)
    headers = _worker_headers(client, created_key["api_key"])

    # 2. Sync 2 candidates offline
    payload = {
        "job_id": test_job.id,
        "results": [
            {
                "file_name": "resume1.pdf",
                "file_type": "pdf",
                "file_hash": "hash123",
                "duplicate_of": None,
                "score": 85.0,
                "decision": "recommended_accept",
                "confidence": "high",
                "summary": "Excellent Python dev",
                "matched_skills": ["Python", "FastAPI"],
                "missing_skills": [],
                "risk_flags": [],
                "explanation": "Local offline run match",
                "cv_text": "John Doe Resume Python FastAPI",
                "candidate_name": "John Doe",
                "candidate_email": "john.doe@example.com",
                "worker_version": "1.0.0",
                "engine_version": "1.0.0"
            },
            {
                "file_name": "resume2.pdf",
                "file_type": "pdf",
                "file_hash": "hash456",
                "duplicate_of": None,
                "score": 45.0,
                "decision": "recommended_reject",
                "confidence": "medium",
                "summary": "Junior dev",
                "matched_skills": [],
                "missing_skills": ["Python"],
                "risk_flags": ["missing_experience"],
                "explanation": "No Python match",
                "cv_text": "Jane Smith Resume Junior Dev",
                "candidate_name": "Jane Smith",
                "candidate_email": "jane.smith@example.com",
                "worker_version": "1.0.0",
                "engine_version": "1.0.0"
            }
        ]
    }

    response = client.post("/api/worker/offline-sync", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ok"
    assert data["synced_count"] == 2

    # 3. Verify DB records
    # Verify candidates
    candidates = db_session.query(Candidate).filter(Candidate.email.in_(["john.doe@example.com", "jane.smith@example.com"])).all()
    assert len(candidates) == 2
    assert {c.name for c in candidates} == {"John Doe", "Jane Smith"}

    # Verify candidate actions
    actions = db_session.query(CandidateAction).filter_by(job_id=test_job.id).all()
    assert len(actions) == 2
    assert {a.action for a in actions} == {"shortlist", "rejected"}  # recommended_accept -> shortlist, recommended_reject -> rejected

    # Verify worker analysis results
    results = db_session.query(WorkerAnalysisResult).filter_by(job_id=test_job.id).all()
    assert len(results) == 2
    assert {r.score for r in results} == {85.0, 45.0}

    # Verify quota used
    wk = db_session.query(WorkerKey).filter_by(id=created_key["id"]).first()
    assert wk.quota_used == 2
    assert wk.quota_reserved == 0


def test_offline_sync_quota_limit_exceeded(client, db_session, recruiter_user, test_job):
    # Create key with quota limit 1
    created_key = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created_key["api_key"])

    payload = {
        "job_id": test_job.id,
        "results": [
            {
                "file_name": "resume1.pdf",
                "file_type": "pdf",
                "file_hash": "hash1",
                "score": 80.0,
                "decision": "recommended_accept",
                "confidence": "high",
                "summary": "test",
                "explanation": "test",
                "candidate_name": "Cand 1",
                "candidate_email": "cand1@example.com",
            },
            {
                "file_name": "resume2.pdf",
                "file_type": "pdf",
                "file_hash": "hash2",
                "score": 90.0,
                "decision": "recommended_accept",
                "confidence": "high",
                "summary": "test",
                "explanation": "test",
                "candidate_name": "Cand 2",
                "candidate_email": "cand2@example.com",
            }
        ]
    }

    # Should return 402 quota exceeded
    response = client.post("/api/worker/offline-sync", json=payload, headers=headers)
    assert response.status_code == 402
    assert "Quota limit exceeded" in response.text
