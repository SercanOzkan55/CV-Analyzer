import json

from models import User


def test_cv_version_metadata_only_mode_does_not_store_raw_text(client, db_session, monkeypatch):
    monkeypatch.setenv("CV_VERSION_TEXT_STORAGE_MODE", "metadata_only")
    user = User(
        supabase_id="test-user-123",
        email="testuser@example.com",
        plan_type="pro",
        billing_status="active",
    )
    db_session.add(user)
    db_session.commit()

    raw_cv = "Jane Doe\nEmail: jane@example.com\nSecret project details"
    response = client.post(
        "/api/v1/cv/versions",
        json={
            "cv_text": raw_cv,
            "optimized_cv_text": "Optimized Jane Doe CV",
            "job_description": "Python backend role",
            "version_label": "privacy",
            "source": "test",
            "lang": "en",
        },
    )

    assert response.status_code == 200
    row = client.get(f"/api/v1/cv/versions/{response.json()['id']}").json()
    stored_cv = json.loads(row["cv_text"])
    assert stored_cv["storage"] == "metadata_only"
    assert stored_cv["chars"] == len(raw_cv)
    assert "Jane Doe" not in row["cv_text"]
    assert "jane@example.com" not in row["cv_text"]
