import pytest


@pytest.mark.skip(reason="requires PostgreSQL with pgvector; SQLite test DB lacks ::vector cast support")
def test_semantic_search_endpoint(client, db_session):
    # Use analyze endpoint to create a candidate and persist embedding
    cv = "Alice\nSkills: Python, SQL\nManaged teams"
    job = "Looking for Python developer with SQL experience"

    res = client.post("/api/v1/analyze", json={"cv_text": cv, "job_description": job})
    assert res.status_code == 200

    # Now call semantic search with job_text
    res2 = client.post("/api/v1/semantic-search", json={"job_text": job, "k": 5})
    assert res2.status_code == 200
    data = res2.json()
    assert "matches" in data
    assert isinstance(data["matches"], list)
    # At least one candidate should be returned (the one we just added)
    assert len(data["matches"]) >= 1
