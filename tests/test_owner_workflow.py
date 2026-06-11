from models import AuditLog, Notification, RolePermission, User, WorkerAnalysisResult
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
