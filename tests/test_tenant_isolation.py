import ipaddress

from models import Analysis, AnalysisShare, User


def _user(db, supabase_id: str, email: str, plan_type: str = "free") -> User:
    row = User(
        supabase_id=supabase_id,
        email=email,
        plan_type=plan_type,
        billing_status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _analysis(db, owner: User, score: float = 72.0) -> Analysis:
    row = Analysis(
        user_id=owner.id,
        organization_id=owner.organization_id,
        similarity_score=score,
        interpretation="ok",
        confidence=0.8,
        risk_level="low",
        job_title="Software Engineer",
        result={"ats_score": score},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_share_requires_analysis_ownership(client, db_session):
    _user(db_session, "test-user-123", "testuser@example.com", plan_type="pro")
    other = _user(db_session, "other-user", "other@example.com", plan_type="pro")
    foreign_analysis = _analysis(db_session, other)

    response = client.post("/api/v1/share", json={"analysis_id": foreign_analysis.id})

    assert response.status_code == 404


def test_public_share_rejects_mismatched_share_owner(client, db_session):
    owner = _user(db_session, "owner-user", "owner@example.com", plan_type="pro")
    other = _user(db_session, "other-user", "other@example.com", plan_type="pro")
    foreign_analysis = _analysis(db_session, other)
    share = AnalysisShare(
        user_id=owner.id,
        analysis_id=foreign_analysis.id,
        share_token="mismatched-share",
        is_active=True,
    )
    db_session.add(share)
    db_session.commit()

    response = client.get("/api/v1/shared/mismatched-share")

    assert response.status_code == 404


def test_notes_require_analysis_ownership(client, db_session):
    _user(db_session, "test-user-123", "testuser@example.com", plan_type="pro")
    other = _user(db_session, "other-user", "other@example.com", plan_type="pro")
    foreign_analysis = _analysis(db_session, other)

    create_response = client.post(
        "/api/v1/notes",
        json={"analysis_id": foreign_analysis.id, "content": "private note"},
    )
    get_response = client.get(f"/api/v1/notes/{foreign_analysis.id}")
    delete_response = client.delete(f"/api/v1/notes/{foreign_analysis.id}")

    assert create_response.status_code == 404
    assert get_response.status_code == 404
    assert delete_response.status_code == 404


def test_favorites_require_analysis_ownership(client, db_session):
    _user(db_session, "test-user-123", "testuser@example.com", plan_type="pro")
    other = _user(db_session, "other-user", "other@example.com", plan_type="pro")
    foreign_analysis = _analysis(db_session, other)

    response = client.post(
        "/api/v1/favorites/toggle",
        json={"analysis_id": foreign_analysis.id, "note": "not mine"},
    )

    assert response.status_code == 404


def test_admin_endpoint_rate_limits_after_token_check(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "_ADMIN_TOKEN", "x" * 40)
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [])
    main._admin_rate_hits.clear()

    headers = {"Authorization": f"Bearer {'x' * 40}"}
    first = client.get("/admin/status", headers=headers)
    second = client.get("/admin/status", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429


def test_admin_endpoint_rejects_ip_outside_allowlist(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "_ADMIN_TOKEN", "x" * 40)
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 20)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [ipaddress.ip_network("203.0.113.10/32")])
    main._admin_rate_hits.clear()

    response = client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {'x' * 40}"},
    )

    assert response.status_code == 403


def test_billing_admin_uses_same_ip_allowlist(client, monkeypatch):
    import main

    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "billing-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 20)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [ipaddress.ip_network("203.0.113.10/32")])
    main._admin_rate_hits.clear()

    response = client.get(
        "/api/v1/billing/admin/me",
        headers={"X-Billing-Admin-Token": "billing-secret"},
    )

    assert response.status_code == 403
