from datetime import datetime, timedelta
import io
import zipfile

from models import (
    CandidateAction,
    Organization,
    QuotaEvent,
    RecruiterJob,
    User,
    WorkerAnalysisResult,
    WorkerClaim,
    WorkerKey,
    WorkerSession,
)


def _create_action(db, recruiter_user, job, *, name="Jane Candidate", email="jane@example.com", cv_text=None):
    action = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=job.id,
        recruiter_id=recruiter_user["user_id"],
        candidate_name=name,
        candidate_email=email,
        cv_text=cv_text or "Jane Candidate\nSkills: Python FastAPI SQL Docker\nExperience: Built APIs.",
        action="pending",
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def _create_worker_key(client, job_id=None, quota_limit=5, expires_at=None):
    payload = {
        "name": "Office laptop worker",
        "job_id": job_id,
        "quota_limit": quota_limit,
    }
    if expires_at:
        payload["expires_at"] = expires_at.isoformat()
    response = client.post("/api/worker-keys", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _worker_headers(client, api_key):
    response = client.post("/api/worker/auth", json={
        "api_key": api_key,
        "device_name": "pytest",
        "worker_version": "test",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _claim_one(client, headers, job_id, limit=1):
    response = client.post(f"/api/worker/jobs/{job_id}/claim", headers=headers, json={"limit": limit})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["items"]
    return data["items"][0]


def _submit_result(client, headers, job_id, item, score=84):
    return client.post(
        f"/api/worker/jobs/{job_id}/results",
        headers=headers,
        json={
            "cv_id": item["cv_id"],
            "candidate_id": item["candidate_id"],
            "score": score,
            "decision": "recommended_accept",
            "confidence": "high",
            "summary": "Matched required skills.",
            "matched_skills": ["Python"],
            "missing_skills": [],
            "risk_flags": [],
            "explanation": "Rule based MVP result.",
            "worker_version": "test",
            "engine_version": "rule_based_test",
        },
    )


def test_worker_key_create_returns_plaintext_once(client, db_session, recruiter_user, test_job):
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=10)
    assert created["api_key"].startswith("sk_worker_live_")
    assert created["key_prefix"] in created["api_key"]

    listed = client.get("/api/worker-keys").json()
    assert listed
    assert "api_key" not in listed[0]

    row = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert row.key_hash != created["api_key"]
    assert row.key_prefix == created["api_key"][:20]


def test_worker_key_create_enforces_premium_monthly_limit(client, db_session, recruiter_user, test_job):
    assert _create_worker_key(client, job_id=test_job.id, quota_limit=1000)["quota_remaining"] == 1000
    _create_worker_key(client, job_id=test_job.id, quota_limit=1000)
    _create_worker_key(client, job_id=test_job.id, quota_limit=2000)

    quota = client.get("/api/worker/quota")
    assert quota.status_code == 200, quota.text
    assert quota.json()["monthly_limit"] == 4000
    assert quota.json()["quota_remaining"] == 0

    response = client.post("/api/worker-keys", json={
        "name": "overflow",
        "job_id": test_job.id,
        "quota_limit": 1,
    })
    assert response.status_code == 403
    assert "Monthly Local Worker quota exceeded" in response.json()["detail"]


def test_worker_key_create_rejects_single_key_over_premium_monthly_limit(client, recruiter_user, test_job):
    response = client.post("/api/worker-keys", json={
        "name": "too large",
        "job_id": test_job.id,
        "quota_limit": 4001,
    })
    assert response.status_code == 403
    assert "Monthly Local Worker quota exceeded" in response.json()["detail"]


def test_revoked_unused_worker_quota_is_reusable(client, recruiter_user, test_job):
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=4000)
    assert client.post(f"/api/worker-keys/{created['id']}/revoke").status_code == 200

    replacement = _create_worker_key(client, job_id=test_job.id, quota_limit=4000)
    assert replacement["quota_limit"] == 4000


def test_revoked_used_worker_quota_counts_for_month(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)
    assert _submit_result(client, headers, test_job.id, item).status_code == 200
    assert client.post(f"/api/worker-keys/{created['id']}/revoke").status_code == 200

    response = client.post("/api/worker-keys", json={
        "name": "replacement-too-large",
        "job_id": test_job.id,
        "quota_limit": 4000,
    })
    assert response.status_code == 403
    assert _create_worker_key(client, job_id=test_job.id, quota_limit=3999)["quota_limit"] == 3999


def test_worker_package_download_contains_cli_without_plaintext_key(client, recruiter_user):
    response = client.get("/api/worker/download-package")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "worker.py",
            "qml_gui.py",
            "workspace.py",
            "credentials.py",
            "requirements.txt",
            "README.md",
            "start_here.cmd",
            "install_windows.cmd",
            "run_gui.cmd",
            "build_windows_exe.cmd",
            "CV Analyzer Local Worker.spec",
            "assets/cv_analyzer_worker.ico",
            "run-worker.ps1",
            ".env.example",
            "config.example.json",
        } <= names
        assert "qt_gui.py" not in names
        assert "gui.py" not in names
        assert any(name.startswith("qml/") for name in names)
        readme = archive.read("README.md").decode("utf-8")
        env_example = archive.read(".env.example").decode("utf-8")
        config_example = archive.read("config.example.json").decode("utf-8")
        worker_py = archive.read("worker.py").decode("utf-8")

    assert "sk_worker_live_xxx" in readme
    assert "start_here.cmd" in readme
    assert "crash.log" in readme
    assert "sk_worker_live_xxx" in env_example
    assert "CV_WORKER_AI_MAX_REVIEWS=25" in env_example
    assert "paste-created-worker-key-at-runtime" in config_example
    assert '"ai_max_reviews": 25' in config_example
    assert "sk_worker_live_" not in worker_py
    assert "http://testserver/api/worker" in readme


def test_worker_executable_download_returns_single_exe(client, recruiter_user, tmp_path, monkeypatch):
    import routes.worker as worker_routes

    exe_dir = tmp_path / "dist"
    exe_dir.mkdir()
    exe_path = exe_dir / "CV Analyzer Local Worker.exe"
    exe_path.write_bytes(b"MZqt-worker")

    monkeypatch.setattr(worker_routes, "_LOCAL_WORKER_DIR", tmp_path)

    response = client.get("/api/worker/download-exe")
    assert response.status_code == 200, response.text
    assert response.content == b"MZqt-worker"
    assert response.headers["content-type"] == "application/vnd.microsoft.portable-executable"
    content_disposition = response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "CV%20Analyzer%20Local%20Worker.exe" in content_disposition


def test_worker_auth_success_fail_revoked_and_expired(client, db_session, recruiter_user, test_job):
    created = _create_worker_key(client, job_id=test_job.id)
    assert client.post("/api/worker/auth", json={"api_key": created["api_key"]}).status_code == 200
    assert client.post("/api/worker/auth", json={"api_key": "sk_worker_live_bad"}).status_code == 401

    assert client.post(f"/api/worker-keys/{created['id']}/revoke").status_code == 200
    assert client.post("/api/worker/auth", json={"api_key": created["api_key"]}).status_code == 401

    expired = _create_worker_key(
        client,
        job_id=test_job.id,
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    assert client.post("/api/worker/auth", json={"api_key": expired["api_key"]}).status_code == 401


def test_worker_cannot_use_other_company_job(client, db_session, recruiter_user, test_job):
    other_org = Organization(name="Other Org", domain="other-worker.example.com")
    db_session.add(other_org)
    db_session.flush()
    other_user = User(
        supabase_id="other-worker-user",
        email="other@example.com",
        organization_id=other_org.id,
        role="recruiter",
        plan_type="pro",
        billing_status="active",
    )
    db_session.add(other_user)
    db_session.flush()
    other_job = RecruiterJob(
        organization_id=other_org.id,
        created_by=other_user.id,
        title="Other job",
        description="Other job description",
    )
    db_session.add(other_job)
    db_session.commit()

    created = _create_worker_key(client, quota_limit=10)
    headers = _worker_headers(client, created["api_key"])
    response = client.get(f"/api/worker/jobs/{other_job.id}/config", headers=headers)
    assert response.status_code in {403, 404}


def test_claim_uses_job_specific_pool_and_signed_download(client, db_session, recruiter_user, test_job):
    target = _create_action(db_session, recruiter_user, test_job, email="target@example.com")
    other_job = RecruiterJob(
        organization_id=recruiter_user["organization_id"],
        created_by=recruiter_user["user_id"],
        title="Other same-org job",
        description="Java role",
    )
    db_session.add(other_job)
    db_session.commit()
    _create_action(db_session, recruiter_user, other_job, email="other-job@example.com")

    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    assert item["candidate_action_id"] == target.id
    assert "s3.example.com" not in item["download_url"]
    download = client.get(item["download_url"])
    assert download.status_code == 200
    assert "Python FastAPI" in download.text


def test_claim_uses_storage_signed_url_when_file_key_exists(client, db_session, recruiter_user, test_job, monkeypatch):
    _create_action(
        db_session,
        recruiter_user,
        test_job,
        email="stored@example.com",
        cv_text=None,
    )
    action = db_session.query(CandidateAction).filter_by(candidate_email="stored@example.com").one()
    action.cv_file_key = f"user_{recruiter_user['user_id']}/original/stored.pdf"
    action.cv_file_name = "stored.pdf"
    action.cv_file_type = "pdf"
    db_session.commit()

    import services.storage_service as storage_service
    monkeypatch.setattr(storage_service, "get_download_url", lambda key, user_id, expires=600: "https://storage.example.com/stored.pdf?sig=test")

    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    assert item["download_url"].startswith("https://storage.example.com/")
    assert item["file_name"] == "stored.pdf"
    assert item["file_type"] == "pdf"


def test_claim_reserves_and_result_moves_quota_to_used(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 1
    assert key.quota_used == 0

    response = _submit_result(client, headers, test_job.id, item)
    assert response.status_code == 200, response.text

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 0
    assert key.quota_used == 1


def test_duplicate_result_is_idempotent_and_does_not_double_charge(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    assert _submit_result(client, headers, test_job.id, item).status_code == 200
    duplicate = _submit_result(client, headers, test_job.id, item)
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "already_processed"

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_used == 1
    assert key.quota_reserved == 0
    assert db_session.query(WorkerAnalysisResult).filter_by(job_id=test_job.id).count() == 1


def test_other_session_cannot_submit_claim(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    first_headers = _worker_headers(client, created["api_key"])
    second_headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, first_headers, test_job.id)

    response = _submit_result(client, second_headers, test_job.id, item)
    assert response.status_code == 400

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 1
    assert key.quota_used == 0


def test_expired_claim_submit_refunds_and_rejects(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    claim = db_session.query(WorkerClaim).filter_by(id=item["claim_id"]).one()
    claim.claim_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    response = _submit_result(client, headers, test_job.id, item)
    assert response.status_code == 409

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    claim = db_session.query(WorkerClaim).filter_by(id=item["claim_id"]).one()
    assert key.quota_reserved == 0
    assert key.quota_used == 0
    assert claim.status == "expired"


def test_revoked_key_cannot_submit_or_download_fallback(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    assert client.post(f"/api/worker-keys/{created['id']}/revoke").status_code == 200

    submit_response = _submit_result(client, headers, test_job.id, item)
    assert submit_response.status_code == 401
    download_response = client.get(item["download_url"])
    assert download_response.status_code == 401


def test_revoked_session_cannot_submit_result(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    session = db_session.query(WorkerSession).filter_by(worker_key_id=created["id"]).one()
    session.revoked_at = datetime.utcnow()
    db_session.commit()

    response = _submit_result(client, headers, test_job.id, item)
    assert response.status_code == 401


def test_two_sessions_claim_distinct_candidates_without_over_reserving(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, email="first-concurrency@example.com")
    _create_action(db_session, recruiter_user, test_job, email="second-concurrency@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    first_headers = _worker_headers(client, created["api_key"])
    second_headers = _worker_headers(client, created["api_key"])

    first_item = _claim_one(client, first_headers, test_job.id)
    second_item = _claim_one(client, second_headers, test_job.id)

    assert first_item["candidate_action_id"] != second_item["candidate_action_id"]
    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 2
    assert key.quota_used == 0
    assert key.quota_reserved + key.quota_used <= key.quota_limit


def test_second_session_cannot_over_claim_quota(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, email="quota-one@example.com")
    _create_action(db_session, recruiter_user, test_job, email="quota-two@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    first_headers = _worker_headers(client, created["api_key"])
    second_headers = _worker_headers(client, created["api_key"])

    _claim_one(client, first_headers, test_job.id)
    response = client.post(f"/api/worker/jobs/{test_job.id}/claim", headers=second_headers, json={"limit": 1})

    assert response.status_code == 402
    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 1
    assert key.quota_used == 0


def test_expired_claim_refund_runs_on_next_claim(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, email="first@example.com")
    _create_action(db_session, recruiter_user, test_job, email="second@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    claim = db_session.query(WorkerClaim).filter_by(id=item["claim_id"]).one()
    claim.claim_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    response = client.post(f"/api/worker/jobs/{test_job.id}/claim", headers=headers, json={"limit": 1})
    assert response.status_code == 200, response.text

    db_session.expire_all()
    key = db_session.query(WorkerKey).filter_by(id=created["id"]).one()
    assert key.quota_reserved == 1
    assert db_session.query(QuotaEvent).filter_by(event_type="expired").count() >= 1


def test_quota_limit_prevents_over_claim(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, email="one@example.com")
    _create_action(db_session, recruiter_user, test_job, email="two@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    response = client.post(f"/api/worker/jobs/{test_job.id}/claim", headers=headers, json={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1

    response = client.post(f"/api/worker/jobs/{test_job.id}/claim", headers=headers, json={"limit": 1})
    assert response.status_code == 402


def test_score_validation_rejects_out_of_range(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job)
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=1)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)
    response = _submit_result(client, headers, test_job.id, item, score=101)
    assert response.status_code == 422
