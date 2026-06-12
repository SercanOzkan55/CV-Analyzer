from auth import verify_supabase_jwt
from models import AuditLog, CandidateAction, CandidateComment, Notification, RolePermission, User, WorkerAnalysisResult
from services.owner_workflow_service import check_permission, decision_to_candidate_status
from tests.test_worker_mvp import _claim_one, _create_action, _create_worker_key, _submit_result, _worker_headers


def test_decision_status_mapping_defaults_to_manual_review():
    assert decision_to_candidate_status("recommended_accept") == "accepted"
    assert decision_to_candidate_status("recommended_reject") == "rejected"
    assert decision_to_candidate_status("something-new") == "needs_manual_review"


def test_role_permission_override_can_deny_default_access(db_session, recruiter_user):
    from models import User

    user = db_session.query(User).filter_by(id=recruiter_user["user_id"]).one()
    assert check_permission(db_session, user, "audit.view") is True

    db_session.add(
        RolePermission(
            organization_id=recruiter_user["organization_id"],
            role="recruiter",
            permission_key="audit.view",
            is_allowed=False,
        )
    )
    db_session.commit()

    assert check_permission(db_session, user, "audit.view") is False


def test_worker_result_creates_owner_audit_and_notification(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, name="Jane Owner", email="owner-flow@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)

    response = _submit_result(client, headers, test_job.id, item)
    assert response.status_code == 200, response.text

    db_session.expire_all()
    result = db_session.query(WorkerAnalysisResult).filter_by(job_id=test_job.id).one()
    assert result.candidate_status == "accepted"

    audit = db_session.query(AuditLog).filter_by(organization_id=recruiter_user["organization_id"]).one()
    assert audit.event_type == "candidate_accepted"
    assert audit.resource_type == "candidate"

    notification = db_session.query(Notification).filter_by(organization_id=recruiter_user["organization_id"]).one()
    assert notification.type == "candidate_accepted"
    assert notification.is_read is False
    assert notification.audit_log_id == audit.id


def test_owner_notification_endpoints(client, db_session, recruiter_user, test_job):
    _create_action(db_session, recruiter_user, test_job, name="Endpoint User", email="endpoint@example.com")
    created = _create_worker_key(client, job_id=test_job.id, quota_limit=2)
    headers = _worker_headers(client, created["api_key"])
    item = _claim_one(client, headers, test_job.id)
    assert _submit_result(client, headers, test_job.id, item).status_code == 200

    list_response = client.get("/api/v1/owner/notifications")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "candidate_accepted"

    read_response = client.post(f"/api/v1/owner/notifications/{items[0]['id']}/read")
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["is_read"] is True

    unread_response = client.get("/api/v1/owner/notifications", params={"unread_only": True})
    assert unread_response.status_code == 200, unread_response.text
    assert unread_response.json()["items"] == []


def test_owner_can_create_member_and_update_role(client, db_session, recruiter_user):
    create_response = client.post(
        "/api/v1/owner/users",
        json={"email": "hr.member@example.com", "role": "hr"},
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()["user"]
    assert created["email"] == "hr.member@example.com"
    assert created["role"] == "hr"
    assert created["supabase_id"].startswith("pending-owner-")

    row = db_session.query(User).filter_by(email="hr.member@example.com").one()
    assert row.organization_id == recruiter_user["organization_id"]

    update_response = client.put(
        f"/api/v1/owner/users/{row.id}/role",
        json={"role": "limited"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["user"]["role"] == "limited"

    db_session.expire_all()
    updated = db_session.query(User).filter_by(id=row.id).one()
    assert updated.role == "limited"
    events = [item.event_type for item in db_session.query(AuditLog).all()]
    assert "new_hr_user_added" in events
    assert "user_permission_changed" in events


def test_owner_member_invite_email_is_sent_when_enabled(client, recruiter_user, monkeypatch):
    sent_messages = []

    def fake_send_email(to_email, subject, body, recruiter_email=""):
        sent_messages.append(
            {
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "recruiter_email": recruiter_email,
            }
        )
        return True

    monkeypatch.setenv("OWNER_INVITE_EMAIL_ENABLED", "true")
    monkeypatch.setenv("OWNER_APP_URL", "https://app.example.test")
    monkeypatch.setattr("routes.owner_workflow._do_send_email", fake_send_email)

    response = client.post(
        "/api/v1/owner/users",
        json={"email": "email.invite@example.com", "role": "hr"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["invite_email"]["requested"] is True
    assert payload["invite_email"]["sent"] is True
    assert len(sent_messages) == 1
    assert sent_messages[0]["to_email"] == "email.invite@example.com"
    assert sent_messages[0]["subject"] == "CV Analyzer team access"
    assert "https://app.example.test" in sent_messages[0]["body"]
    assert "as hr" in sent_messages[0]["body"]


def test_pending_owner_member_is_adopted_on_first_login(client, db_session, recruiter_user):
    create_response = client.post(
        "/api/v1/owner/users",
        json={"email": "invited.member@example.com", "role": "limited"},
    )
    assert create_response.status_code == 200, create_response.text
    pending_user = create_response.json()["user"]
    assert pending_user["supabase_id"].startswith("pending-owner-")

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": "real-supabase-invited-member",
        "email": "invited.member@example.com",
    }

    permissions_response = client.get("/api/v1/owner/permissions")
    assert permissions_response.status_code == 200, permissions_response.text
    payload = permissions_response.json()
    assert payload["role"] == "limited"
    assert payload["organization_id"] == recruiter_user["organization_id"]

    db_session.expire_all()
    rows = db_session.query(User).filter_by(email="invited.member@example.com").all()
    assert len(rows) == 1
    assert rows[0].supabase_id == "real-supabase-invited-member"
    assert rows[0].role == "limited"
    assert rows[0].organization_id == recruiter_user["organization_id"]
    assert db_session.query(AuditLog).filter_by(event_type="hr_user_activated").count() == 1
    assert db_session.query(Notification).filter_by(type="hr_user_activated").count() == 1


def test_owner_can_override_role_permission(client, db_session, recruiter_user):
    response = client.put(
        "/api/v1/owner/role-permissions/hr/audit.view",
        json={"is_allowed": False},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["permission"]
    assert payload["role"] == "hr"
    assert payload["permission_key"] == "audit.view"
    assert payload["is_allowed"] is False

    listing = client.get("/api/v1/owner/role-permissions")
    assert listing.status_code == 200, listing.text
    assert listing.json()["defaults"]["hr"]["audit.view"] is True
    assert len(listing.json()["overrides"]) == 1

    override = db_session.query(RolePermission).filter_by(role="hr", permission_key="audit.view").one()
    assert override.is_allowed is False
    notification = db_session.query(Notification).filter_by(type="user_permission_changed").one()
    assert notification.audit_log_id is not None


def test_owner_candidate_action_controls_and_privacy(client, db_session, recruiter_user, test_job):
    action = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=test_job.id,
        recruiter_id=recruiter_user["user_id"],
        candidate_name="Private Candidate",
        candidate_email="private@example.com",
        cv_text="Private CV text",
        final_score=70,
        ats_score=65,
        action="pending",
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)

    score_response = client.put(
        f"/api/v1/owner/candidate-actions/{action.id}/score",
        json={"final_score": 82, "ats_score": 80},
    )
    assert score_response.status_code == 200, score_response.text
    assert score_response.json()["action"]["final_score"] == 82

    delete_response = client.delete(f"/api/v1/owner/candidate-actions/{action.id}")
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["action"]["deleted_at"] is not None

    visible_response = client.get("/api/v1/owner/candidate-actions")
    assert visible_response.status_code == 200, visible_response.text
    assert visible_response.json()["items"] == []

    deleted_response = client.get("/api/v1/owner/candidate-actions", params={"include_deleted": True})
    assert deleted_response.status_code == 200, deleted_response.text
    assert len(deleted_response.json()["items"]) == 1

    anonymize_response = client.post(f"/api/v1/owner/candidate-actions/{action.id}/anonymize")
    assert anonymize_response.status_code == 200, anonymize_response.text
    payload = anonymize_response.json()["action"]
    assert payload["candidate_email"] is None
    assert payload["candidate_name"].startswith("Anonymized Candidate")
    assert payload["anonymized_at"] is not None

    db_session.expire_all()
    stored = db_session.query(CandidateAction).filter_by(id=action.id).one()
    assert stored.candidate_email is None
    assert stored.cv_text is None
    events = [row.event_type for row in db_session.query(AuditLog).all()]
    assert "candidate_score_changed" in events
    assert "candidate_deleted" in events


def test_limited_user_sees_only_assigned_candidate_actions(client, db_session, recruiter_user, test_job):
    limited = User(
        supabase_id="limited-owner-user",
        email="limited@example.com",
        organization_id=recruiter_user["organization_id"],
        role="limited",
    )
    db_session.add(limited)
    db_session.commit()
    db_session.refresh(limited)

    assigned = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=test_job.id,
        recruiter_id=recruiter_user["user_id"],
        assigned_user_id=limited.id,
        candidate_name="Assigned Candidate",
        candidate_email="assigned@example.com",
        action="pending",
    )
    unassigned = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=test_job.id,
        recruiter_id=recruiter_user["user_id"],
        candidate_name="Unassigned Candidate",
        candidate_email="unassigned@example.com",
        action="pending",
    )
    db_session.add_all([assigned, unassigned])
    db_session.commit()

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": limited.supabase_id,
        "email": limited.email,
    }

    response = client.get("/api/v1/owner/candidate-actions")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_email"] == "assigned@example.com"


def test_limited_user_can_comment_only_on_assigned_candidate(client, db_session, recruiter_user, test_job):
    limited = User(
        supabase_id="limited-comment-user",
        email="limited-comment@example.com",
        organization_id=recruiter_user["organization_id"],
        role="limited",
    )
    db_session.add(limited)
    db_session.commit()
    db_session.refresh(limited)

    assigned = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=test_job.id,
        recruiter_id=recruiter_user["user_id"],
        assigned_user_id=limited.id,
        candidate_name="Assigned Comment Candidate",
        candidate_email="assigned-comment@example.com",
        action="pending",
    )
    unassigned = CandidateAction(
        organization_id=recruiter_user["organization_id"],
        job_id=test_job.id,
        recruiter_id=recruiter_user["user_id"],
        candidate_name="Blocked Comment Candidate",
        candidate_email="blocked-comment@example.com",
        action="pending",
    )
    db_session.add_all([assigned, unassigned])
    db_session.commit()
    db_session.refresh(assigned)
    db_session.refresh(unassigned)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": limited.supabase_id,
        "email": limited.email,
    }

    created = client.post(
        f"/api/v1/owner/candidate-actions/{assigned.id}/comments",
        json={"body": "Looks promising for manual review."},
    )
    assert created.status_code == 200, created.text
    assert created.json()["comment"]["body"] == "Looks promising for manual review."
    assert created.json()["action"]["comment_count"] == 1

    blocked = client.post(
        f"/api/v1/owner/candidate-actions/{unassigned.id}/comments",
        json={"body": "Should not be allowed."},
    )
    assert blocked.status_code == 404, blocked.text

    comments = client.get(f"/api/v1/owner/candidate-actions/{assigned.id}/comments")
    assert comments.status_code == 200, comments.text
    assert len(comments.json()["items"]) == 1

    db_session.expire_all()
    stored = db_session.query(CandidateComment).filter_by(candidate_action_id=assigned.id).one()
    assert stored.author_user_id == limited.id
    assert db_session.query(CandidateComment).count() == 1
    assert db_session.query(AuditLog).filter_by(event_type="candidate_comment_added").count() == 1
    assert db_session.query(Notification).filter_by(type="candidate_comment_added").count() == 1
