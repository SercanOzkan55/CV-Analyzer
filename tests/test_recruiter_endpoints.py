"""
Recruiter endpoint isolation tests.
Uses db_session and client fixtures from conftest.py (per-function isolation).
"""

from datetime import datetime, timedelta


from auth import verify_supabase_jwt
from models import Analysis, Organization, User

# ── Helpers ──


def _setup_two_orgs(db):
    """Create two orgs, a recruiter in A, candidates in both, analyses in both."""
    org_a = Organization(name="A", domain="a.test")
    org_b = Organization(name="B", domain="b.test")
    db.add_all([org_a, org_b])
    db.commit()
    db.refresh(org_a)
    db.refresh(org_b)

    recruiter = User(
        supabase_id="rec-a",
        email="rec@a.test",
        role="recruiter",
        organization_id=org_a.id,
    )
    cand_a = User(
        supabase_id="cand-a",
        email="cand@a.test",
        role="individual",
        organization_id=org_a.id,
    )
    cand_b = User(
        supabase_id="cand-b",
        email="cand@b.test",
        role="individual",
        organization_id=org_b.id,
    )
    db.add_all([recruiter, cand_a, cand_b])
    db.commit()
    db.refresh(recruiter)
    db.refresh(cand_a)
    db.refresh(cand_b)

    a_analysis = Analysis(
        user_id=cand_a.id,
        organization_id=org_a.id,
        similarity_score=80.0,
        interpretation="",
        confidence=0.0,
        risk_level="",
    )
    b_analysis = Analysis(
        user_id=cand_b.id,
        organization_id=org_b.id,
        similarity_score=60.0,
        interpretation="",
        confidence=0.0,
        risk_level="",
    )
    db.add_all([a_analysis, b_analysis])
    db.commit()

    return org_a, org_b, recruiter, cand_a, cand_b


# ── Tests ──


def test_recruiter_sees_own_org_candidates(client, db_session):
    org_a, org_b, recruiter, cand_a, cand_b = _setup_two_orgs(db_session)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get("/api/v1/recruiter/candidates")
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    ids = {c["user_id"] for c in data["candidates"]}
    assert cand_a.id in ids
    assert cand_b.id not in ids


def test_recruiter_cannot_access_other_org_analysis(client, db_session):
    org_a, org_b, recruiter, cand_a, cand_b = _setup_two_orgs(db_session)

    analysis_b = db_session.query(Analysis).filter_by(user_id=cand_b.id).first()
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get(f"/api/v1/recruiter/candidate/{analysis_b.id}")
    assert resp.status_code == 403


def test_list_endpoint_no_leak(client, db_session):
    """Org A recruiter should never see Org B candidates, even with 100 Org B records."""
    org_a, org_b, recruiter, _, _ = _setup_two_orgs(db_session)

    # Add 100 Org B candidates
    for i in range(100):
        c = User(
            supabase_id=f"cb-{i}",
            email=f"cb{i}@b.test",
            role="individual",
            organization_id=org_b.id,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        db_session.add(
            Analysis(
                user_id=c.id,
                organization_id=org_b.id,
                similarity_score=50.0,
                interpretation="",
                confidence=0.0,
                risk_level="",
            )
        )
        db_session.commit()

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get("/api/v1/recruiter/candidates?limit=200")
    assert resp.status_code == 200
    for c in resp.json()["candidates"]:
        user = db_session.query(User).filter_by(id=c["user_id"]).first()
        assert user.organization_id == org_a.id


def test_pagination_no_leak(client, db_session):
    """Pagination manipulation should not leak other org records."""
    org_a, org_b, recruiter, _, _ = _setup_two_orgs(db_session)

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get("/api/v1/recruiter/candidates?limit=1000")
    assert resp.status_code == 200
    for c in resp.json()["candidates"]:
        user = db_session.query(User).filter_by(id=c["user_id"]).first()
        assert user.organization_id == org_a.id


def test_id_guess_attack(client, db_session):
    """Org A recruiter should get 403 for Org B analysis_id."""
    org_a, org_b, recruiter, _, cand_b = _setup_two_orgs(db_session)

    analysis_b = db_session.query(Analysis).filter_by(user_id=cand_b.id).first()
    assert analysis_b is not None
    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get(f"/api/v1/recruiter/candidate/{analysis_b.id}")
    assert resp.status_code == 403


def test_top_candidates_org_scope(client, db_session):
    """Org A recruiter should not see Org B's high-score candidate."""
    org_a, org_b, recruiter, _, _ = _setup_two_orgs(db_session)

    # Org B high-score candidate
    cand_bh = User(
        supabase_id="cand-b-high",
        email="high@b.test",
        role="individual",
        organization_id=org_b.id,
    )
    db_session.add(cand_bh)
    db_session.commit()
    db_session.refresh(cand_bh)
    db_session.add(
        Analysis(
            user_id=cand_bh.id,
            organization_id=org_b.id,
            similarity_score=99.0,
            interpretation="",
            confidence=0.0,
            risk_level="",
        )
    )
    db_session.commit()

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }
    resp = client.get("/api/v1/recruiter/top_candidates?limit=10")
    assert resp.status_code == 200
    for c in resp.json()["top_candidates"]:
        user = db_session.query(User).filter_by(id=c["user_id"]).first()
        assert user.organization_id == org_a.id


def test_pagination_and_top_ordering(client, db_session):
    org_a, _, recruiter, cand_a, _ = _setup_two_orgs(db_session)

    times = [datetime.utcnow() - timedelta(days=i) for i in range(3)]
    scores = [10.0, 30.0, 20.0]
    for t, s in zip(times, scores):
        db_session.add(
            Analysis(
                user_id=cand_a.id,
                organization_id=org_a.id,
                similarity_score=s,
                interpretation="",
                confidence=0.0,
                risk_level="",
                created_at=t,
            )
        )
    db_session.commit()

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.get("/api/v1/recruiter/candidates?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["candidates"]) == 2

    resp2 = client.get("/api/v1/recruiter/top_candidates?limit=3")
    assert resp2.status_code == 200
    top = resp2.json()["top_candidates"]
    scores_returned = [c["final_score"] for c in top]
    assert scores_returned == sorted(scores_returned, reverse=True)


def test_top_candidates_filters(client, db_session):
    org_a, _, recruiter, cand_a, _ = _setup_two_orgs(db_session)

    # Add an analysis with known score
    db_session.add(
        Analysis(
            user_id=cand_a.id,
            organization_id=org_a.id,
            similarity_score=50.0,
            interpretation="",
            confidence=0.0,
            risk_level="",
        )
    )
    db_session.commit()

    client.app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "user_id": recruiter.supabase_id,
        "email": recruiter.email,
    }

    resp = client.get("/api/v1/recruiter/top_candidates?min_score=25")
    assert resp.status_code == 200
    for c in resp.json()["top_candidates"]:
        assert c["final_score"] >= 25

    now = datetime.utcnow()
    start = (now - timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=1)).isoformat()
    resp = client.get(
        f"/api/v1/recruiter/top_candidates?start_date={start}&end_date={end}"
    )
    assert resp.status_code == 200
