def test_cookie_auth_post_requires_csrf_token(client):
    response = client.post(
        "/api/v1/notes",
        headers={"Cookie": "csrf_token=abcdefghijklmnop"},
        json={"analysis_id": 1, "content": "blocked before endpoint"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"
