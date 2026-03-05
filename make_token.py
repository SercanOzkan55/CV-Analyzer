#!/usr/bin/env python3
"""Generate HS256 JWT compatible with backend's SUPABASE_JWT_SECRET.

Usage examples:
  SUPABASE_JWT_SECRET=... python make_token.py --sub test-user-1 --email you@example.com
  python make_token.py --sub test-user-1 --email you@example.com --exp 3600

If SUPABASE_JWT_SECRET is not in env, the script will look for a .env file
in the repo root and parse SUPABASE_JWT_SECRET from it.
"""

import argparse
import os
import time

from jose import jwt


def load_secret_from_dotenv(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "SUPABASE_JWT_SECRET":
                    return v.strip()
    except FileNotFoundError:
        return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sub", required=True, help="sub (user id) to embed in token")
    p.add_argument("--email", required=True, help="email")
    p.add_argument("--role", default="authenticated", help="role")
    p.add_argument("--org_id", type=int, default=1, help="org_id")
    p.add_argument("--exp", type=int, default=3600, help="seconds until expiry")
    args = p.parse_args()

    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        secret = load_secret_from_dotenv(".env")

    if not secret:
        print(
            "Error: SUPABASE_JWT_SECRET not set in environment and .env not found or missing the key"
        )
        raise SystemExit(1)

    now = int(time.time())
    payload = {
        "sub": args.sub,
        "email": args.email,
        "role": args.role,
        "org_id": args.org_id,
        "exp": now + args.exp,
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
