import os
from fastapi import Header, HTTPException
from jose import jwt

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"


def verify_supabase_jwt(authorization: str = Header(None)):
    """
    Verify Supabase JWT token from Authorization header.
    Expected format: Authorization: Bearer <token>
    
    Returns: dict with user_id (sub) and email from JWT payload
    """
    # In development/testing mode, return a mock user when MOCK_SERVICES is set
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return {"user_id": "mock-user", "email": "dev@example.com", "plan_type": "free"}

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")

        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[ALGORITHM],
            options={"verify_aud": False}  # Allow any audience
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "user_id": user_id,
        "email": email,
        "payload": payload
    }