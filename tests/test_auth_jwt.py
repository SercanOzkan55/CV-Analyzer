import time

import pytest
from fastapi import HTTPException
from jose import jwt

import auth


def _token(secret: str, **claims):
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "exp": int(time.time()) + 300,
        "aud": "authenticated",
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_supabase_jwt_accepts_expected_audience(monkeypatch):
    secret = "test-secret"
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", secret)
    monkeypatch.setattr(auth, "SUPABASE_URL", None)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    monkeypatch.delenv("MOCK_SERVICES", raising=False)

    token = _token(secret)
    payload = auth.verify_supabase_jwt(f"Bearer {token}")

    assert payload["user_id"] == "user-123"
    assert payload["email"] == "user@example.com"


def test_verify_supabase_jwt_rejects_wrong_audience(monkeypatch):
    secret = "test-secret"
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", secret)
    monkeypatch.setattr(auth, "SUPABASE_URL", None)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    monkeypatch.delenv("MOCK_SERVICES", raising=False)

    token = _token(secret, aud="other-service")

    with pytest.raises(HTTPException) as exc:
        auth.verify_supabase_jwt(f"Bearer {token}")

    assert exc.value.status_code == 401


def test_verify_supabase_jwt_rejects_wrong_issuer(monkeypatch):
    secret = "test-secret"
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", secret)
    monkeypatch.setattr(auth, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    monkeypatch.delenv("MOCK_SERVICES", raising=False)

    token = _token(secret, iss="https://evil.example/auth/v1")

    with pytest.raises(HTTPException) as exc:
        auth.verify_supabase_jwt(f"Bearer {token}")

    assert exc.value.status_code == 401
