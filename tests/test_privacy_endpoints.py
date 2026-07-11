"""Privacy-critical endpoint tests: account deletion and org-wide data scoping."""

from models import (
    Analysis,
    AnalysisNote,
    Candidate,
    CandidateAction,
    CandidateComment,
    CVVersion,
    EmailTemplate,
    Favorite,
    JobApplication,
    Organization,
    RecruiterJob,
    User,
    WorkerAnalysisResult,
)


def _clear_rate_limit_state():
    from core import http_runtime

    http_runtime._user_global_counts.clear()
    http_runtime._ip_global_counts.clear()
    http_runtime._user_embed_counts.clear()
    http_runtime._search_counts.clear()
    http_runtime._dedup_cache.clear()
    http_runtime._LOCAL_ABUSE_BANS.clear()
    http_runtime._LOCAL_ABUSE_COUNTERS.clear()


def _org(db) -> Organization:
    org = Organization(
        name="Privacy Test Org",
        domain="privacy-test.example.com",
        plan_type="pro",
        billing_status="active",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _current_user(db, *, role: str = "individual", organization_id=None) -> User:
    """Create the user matching conftest's mocked JWT subject."""
    user = User(
        supabase_id="test-user-123",
        email="testuser@example.com",
        plan_type="pro",
        billing_status="active",
        role=role,
        organization_id=organization_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_org_candidate_data(db, org_id: int, user_id: int):
    job = RecruiterJob(
        title="Backend Engineer",
        description="Python role",
        organization_id=org_id,
        created_by=user_id,
    )
    db.add(job)
    db.commit()
    candidate = Candidate(organization_id=org_id, name="Jane Doe", cv_text="raw cv text")
    db.add(candidate)
    db.commit()
    result = WorkerAnalysisResult(
        organization_id=org_id,
        job_id=job.id,
        candidate_id=candidate.id,
        score=80.0,
        decision="accept",
    )
    db.add(result)
    db.commit()
    return job, candidate, result


def test_account_delete_requires_confirm_token(client, db_session):
    _clear_rate_limit_state()
    _current_user(db_session)

    response = client.delete("/api/v1/me/account?confirm=NOPE12")

    assert response.status_code == 400


def test_account_delete_removes_all_user_data(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    user = _current_user(db_session, role="recruiter", organization_id=org.id)

    analysis = Analysis(
        user_id=user.id,
        organization_id=org.id,
        similarity_score=70.0,
        interpretation="ok",
    )
    cv_version = CVVersion(user_id=user.id, cv_text="stored cv text", version_label="v1")
    job_app = JobApplication(user_id=user.id, company="Acme", role="Engineer")
    email_template = EmailTemplate(
        organization_id=org.id,
        created_by=user.id,
        name="Offer",
        subject="Offer",
        body="Hello",
    )
    db_session.add_all([analysis, cv_version, job_app, email_template])
    db_session.commit()
    db_session.add_all(
        [
            Favorite(user_id=user.id, analysis_id=analysis.id),
            AnalysisNote(user_id=user.id, analysis_id=analysis.id, content="note"),
        ]
    )
    db_session.commit()
    job, _candidate, _result = _seed_org_candidate_data(db_session, org.id, user.id)
    action = CandidateAction(
        organization_id=org.id,
        job_id=job.id,
        recruiter_id=user.id,
        candidate_name="Jane Doe",
        cv_text="raw candidate cv",
        action="pending",
    )
    db_session.add(action)
    db_session.commit()
    db_session.add(
        CandidateComment(
            organization_id=org.id,
            candidate_action_id=action.id,
            author_user_id=user.id,
            body="looks strong",
        )
    )
    db_session.commit()
    user_id = user.id

    response = client.delete("/api/v1/me/account?confirm=DELETE")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    db_session.expire_all()
    assert db_session.query(User).filter(User.id == user_id).count() == 0
    assert db_session.query(CVVersion).filter(CVVersion.user_id == user_id).count() == 0
    assert db_session.query(Analysis).filter(Analysis.user_id == user_id).count() == 0
    assert db_session.query(Favorite).filter(Favorite.user_id == user_id).count() == 0
    assert db_session.query(AnalysisNote).filter(AnalysisNote.user_id == user_id).count() == 0
    assert db_session.query(JobApplication).filter(JobApplication.user_id == user_id).count() == 0
    assert db_session.query(EmailTemplate).filter(EmailTemplate.created_by == user_id).count() == 0
    assert db_session.query(RecruiterJob).filter(RecruiterJob.created_by == user_id).count() == 0
    assert db_session.query(CandidateAction).filter(CandidateAction.recruiter_id == user_id).count() == 0
    assert db_session.query(CandidateComment).filter(CandidateComment.author_user_id == user_id).count() == 0


def test_account_delete_blocks_when_storage_delete_fails(client, db_session, monkeypatch):
    _clear_rate_limit_state()
    user = _current_user(db_session)
    db_session.add(
        CVVersion(
            user_id=user.id,
            cv_text="stored cv text",
            version_label="v1",
            original_s3_key=f"cv/{user.supabase_id}/original.pdf",
        )
    )
    db_session.commit()
    user_id = user.id

    def _boom(key, supabase_id):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr("services.storage_service.delete_cv", _boom)

    response = client.delete("/api/v1/me/account?confirm=DELETE")

    assert response.status_code == 502
    db_session.expire_all()
    assert db_session.query(User).filter(User.id == user_id).count() == 1
    assert db_session.query(CVVersion).filter(CVVersion.user_id == user_id).count() == 1


def test_analyze_skips_candidate_row_for_individual_user(client, db_session):
    _clear_rate_limit_state()
    _current_user(db_session)

    response = client.post(
        "/api/v1/analyze",
        json={
            "cv_text": "Managed a team that increased revenue by 20%. Skills: Python, SQL.",
            "job_description": "Looking for a software engineer with Python and SQL experience.",
        },
    )

    assert response.status_code == 200
    assert db_session.query(Candidate).count() == 0


def test_analyze_saves_candidate_row_for_org_member(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    _current_user(db_session, role="recruiter", organization_id=org.id)

    response = client.post(
        "/api/v1/analyze",
        json={
            "cv_text": "Managed a team that increased revenue by 20%. Skills: Python, SQL.",
            "job_description": "Looking for a software engineer with Python and SQL experience.",
        },
    )

    assert response.status_code == 200
    candidates = db_session.query(Candidate).all()
    assert len(candidates) == 1
    assert candidates[0].organization_id == org.id


def test_workspace_delete_keeps_org_data_for_non_admin_member(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    user = _current_user(db_session, role="hr", organization_id=org.id)
    _seed_org_candidate_data(db_session, org.id, user.id)

    response = client.delete("/api/v1/me/data?scope=workspace&confirm=DELETE")

    assert response.status_code == 200
    body = response.json()
    assert body["organization_data_skipped"] == "owner_or_admin_role_required"
    assert body["deleted_candidates"] == 0
    assert body["deleted_worker_analysis_results"] == 0
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.organization_id == org.id).count() == 1
    assert db_session.query(WorkerAnalysisResult).filter(WorkerAnalysisResult.organization_id == org.id).count() == 1


def test_workspace_delete_wipes_org_data_for_owner(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    user = _current_user(db_session, role="owner", organization_id=org.id)
    _seed_org_candidate_data(db_session, org.id, user.id)

    response = client.delete("/api/v1/me/data?scope=workspace&confirm=DELETE")

    assert response.status_code == 200
    body = response.json()
    assert "organization_data_skipped" not in body
    assert body["deleted_candidates"] == 1
    assert body["deleted_worker_analysis_results"] == 1
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.organization_id == org.id).count() == 0


def test_data_export_hides_org_data_from_non_admin_member(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    user = _current_user(db_session, role="hr", organization_id=org.id)
    _seed_org_candidate_data(db_session, org.id, user.id)

    response = client.get("/api/v1/me/data-export?include_raw=true")

    assert response.status_code == 200
    body = response.json()
    assert body["organization_data_included"] is False
    assert body["candidates"] == []
    assert body["worker_analysis_results"] == []


def test_data_export_includes_org_data_for_owner(client, db_session):
    _clear_rate_limit_state()
    org = _org(db_session)
    user = _current_user(db_session, role="owner", organization_id=org.id)
    _seed_org_candidate_data(db_session, org.id, user.id)

    response = client.get("/api/v1/me/data-export?include_raw=true")

    assert response.status_code == 200
    body = response.json()
    assert body["organization_data_included"] is True
    assert len(body["candidates"]) == 1
    assert len(body["worker_analysis_results"]) == 1
