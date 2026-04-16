import os

from fastapi import Header, HTTPException
from jose import jwt


def _read_secret_file(path: str | None) -> str | None:
    """Best-effort helper to read a secret from a Docker/OS-level file.

    Returns None if the file can't be read. This allows production
    deployments to mount Supabase secrets via Docker/Kubernetes secrets
    while keeping local .env workflows unchanged.
    """

    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    SUPABASE_JWT_SECRET = _read_secret_file(os.getenv("SUPABASE_JWT_SECRET_FILE"))

SUPABASE_URL = os.getenv("SUPABASE_URL")


def _fetch_jwks(supabase_url: str):
    """Fetch JWKS from Supabase (tries a couple common paths)."""
    try:
        import requests
    except Exception:
        return None

    candidates = []
    if supabase_url:
        candidates.append(supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json")
        candidates.append(supabase_url.rstrip("/") + "/.well-known/jwks.json")

    for url in candidates:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


def verify_supabase_jwt(authorization: str = Header(None)):
    """
    Verify Supabase JWT token from Authorization header.
    Supports HS256 (legacy secret) and RS/ES algorithms via JWKS fetched
    from SUPABASE_URL.

    Returns: dict with user_id (sub) and email from JWT payload
    """
    # In development/testing mode, return a mock user when MOCK_SERVICES is set.
    # GUARD: never allow mock auth when ENV is production.
    _env_mode = os.getenv("ENV", "development").lower()
    if (
        os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
        and _env_mode not in ("production", "prod")
    ):
        # Try to preserve per-user identity in mock mode by reading unverified
        # claims from the bearer token. This keeps quota/rate-limit behavior
        # meaningful across different accounts during local testing.
        if authorization:
            try:
                scheme, token = authorization.split()
                if scheme.lower() == "bearer":
                    claims = jwt.get_unverified_claims(token)
                    user_id = claims.get("sub") or "mock-user"
                    email = claims.get("email") or "dev@example.com"
                    return {
                        "user_id": user_id,
                        "email": email,
                        "plan_type": "free",
                        "payload": claims,
                    }
            except Exception:
                pass
        return {
            "user_id": "mock-user",
            "email": "dev@example.com",
            "plan_type": "free",
        }

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )

    # Inspect header to determine algorithm/kid
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token header")

    # If algorithm is HMAC (HS*), use SUPABASE_JWT_SECRET
    if alg and alg.upper().startswith("HS"):
        if not SUPABASE_JWT_SECRET:
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration: SUPABASE_JWT_SECRET not set",
            )
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    else:
        # Asymmetric algorithm (RS/ES) - fetch JWKS and verify using the key with matching kid
        jwks = _fetch_jwks(SUPABASE_URL)
        if not jwks or "keys" not in jwks:
            raise HTTPException(
                status_code=500,
                detail="Unable to fetch JWKS for token verification; set SUPABASE_URL and install requests",
            )

        kid = header.get("kid")
        key_obj = None
        for k in jwks["keys"]:
            if kid and k.get("kid") == kid:
                key_obj = k
                break
        if not key_obj:
            key_obj = jwks["keys"][0]

        # Convert JWK to PEM using jwcrypto if available
        try:
            from jwcrypto import jwk as jwk_mod

            # jwcrypto accepts JSON string; ensure key is serializable
            jwk_key = jwk_mod.JWK(**key_obj)
            pem = jwk_key.export_to_pem(public_key=True, password=None)
            payload = jwt.decode(
                token, pem, algorithms=[alg], options={"verify_aud": False}
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Server missing jwcrypto dependency to verify Supabase JWT (pip install jwcrypto)",
            )

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"user_id": user_id, "email": email, "payload": payload}
