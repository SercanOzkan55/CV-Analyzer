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


def _clear_rate_limit_state():
    """Clear all in-memory rate limit buckets to avoid 429 cascade across tests."""
    from core import http_runtime
    http_runtime._user_global_counts.clear()
    http_runtime._ip_global_counts.clear()
    http_runtime._user_embed_counts.clear()
    http_runtime._search_counts.clear()
    http_runtime._dedup_cache.clear()
    http_runtime._LOCAL_ABUSE_BANS.clear()
    http_runtime._LOCAL_ABUSE_COUNTERS.clear()


def test_share_requires_analysis_ownership(client, db_session):
    _clear_rate_limit_state()
    _user(db_session, "test-user-123", "testuser@example.com", plan_type="pro")
    other = _user(db_session, "other-user", "other@example.com", plan_type="pro")
    foreign_analysis = _analysis(db_session, other)

    response = client.post("/api/v1/share", json={"analysis_id": foreign_analysis.id})

    assert response.status_code == 404


def test_public_share_rejects_mismatched_share_owner(client, db_session):
    _clear_rate_limit_state()
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
    _clear_rate_limit_state()
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
    _clear_rate_limit_state()
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
    from core import http_runtime

    monkeypatch.setattr(main, "_ADMIN_TOKEN", "x" * 40)
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [])
    http_runtime._admin_rate_hits.clear()

    headers = {"Authorization": f"Bearer {'x' * 40}"}
    first = client.get("/admin/status", headers=headers)
    second = client.get("/admin/status", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429


def test_admin_endpoint_rejects_ip_outside_allowlist(client, monkeypatch):
    import main
    from core import http_runtime

    monkeypatch.setattr(main, "_ADMIN_TOKEN", "x" * 40)
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 20)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [ipaddress.ip_network("203.0.113.10/32")])
    http_runtime._admin_rate_hits.clear()

    response = client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {'x' * 40}"},
    )

    assert response.status_code == 403


def test_billing_admin_uses_same_ip_allowlist(client, monkeypatch):
    import main
    from core import http_runtime

    monkeypatch.setenv("BILLING_ADMIN_TOKEN", "billing-secret")
    monkeypatch.setenv("BILLING_ADMIN_ALLOWED_EMAILS", "testuser@example.com")
    monkeypatch.setattr(main, "_ADMIN_RATE_LIMIT_PER_MIN", 20)
    monkeypatch.setattr(main, "_ADMIN_IP_ALLOWLIST", [ipaddress.ip_network("203.0.113.10/32")])
    http_runtime._admin_rate_hits.clear()

    response = client.get(
        "/api/v1/billing/admin/me",
        headers={"X-Billing-Admin-Token": "billing-secret"},
    )

    assert response.status_code == 403


def test_semantic_search_tenant_isolation(client, db_session, monkeypatch):
    _clear_rate_limit_state()
    from models import Organization, Candidate

    # Create two organizations
    org1 = Organization(name="Tenant 1", domain="tenant1.com")
    org2 = Organization(name="Tenant 2", domain="tenant2.com")
    db_session.add(org1)
    db_session.add(org2)
    db_session.commit()

    # The mock user returns 'test-user-123'. Assign it to org1.
    user1 = _user(db_session, "test-user-123", "testuser@example.com")
    user1.organization_id = org1.id
    db_session.add(user1)

    # Create candidate in org2 (Tenant 2)
    c2 = Candidate(
        organization_id=org2.id,
        name="Tenant2 Candidate",
        email="c2@org2.com",
        cv_text="Python FastAPI developer with experience in microservices",
    )
    db_session.add(c2)
    db_session.commit()

    # Mock the get_embedding to return a dummy vector
    monkeypatch.setattr("routes.ai_tools.get_embedding", lambda x: [0.1] * 1536)

    # Call semantic-search endpoint
    response = client.post(
        "/api/v1/semantic-search",
        json={"job_text": "Python developer", "k": 5},
    )

    # The result should not leakage Tenant 2's candidate
    assert response.status_code == 200
    data = response.json()
    matches = data.get("matches", [])
    candidate_ids = [m.get("id") for m in matches]
