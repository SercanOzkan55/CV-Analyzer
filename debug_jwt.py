"""
Debug JWT token generation and validation
"""

from datetime import datetime, timedelta, timezone
from jose import jwt
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from current directory
env_path = Path(".env")
print(f"Current directory: {os.getcwd()}")
print(f".env file exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_JWT_SECRET:
    print("❌ SUPABASE_JWT_SECRET not set in .env")
    print(f"   Checked: {env_path.resolve()}")
    print(f"\n   Available environment variables:")
    print(f"   {list(os.environ.keys())[:5]}...")
    exit(1)

print(f"✅ JWT Secret loaded: {SUPABASE_JWT_SECRET[:20]}...")

# Create test user
test_user = {
    "sub": "user-123-aaa",
    "email": "user1@example.com",
    "aud": "authenticated"
}

# Create token with new datetime method
now = datetime.now(timezone.utc)
payload = {
    **test_user,
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(hours=1)).timestamp())
}

print("\n📝 Payload to encode:")
for k, v in payload.items():
    print(f"  {k}: {v}")

# Encode
try:
    token = jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")
    print(f"\n✅ Token created successfully!")
    print(f"   Token (first 50 chars): {token[:50]}...")
    print(f"   Full token length: {len(token)} chars")
except Exception as e:
    print(f"\n❌ Error encoding token: {e}")
    exit(1)

# Decode 
try:
    decoded = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False}  # Don't verify audience for this test
    )
    print(f"\n✅ Token decoded successfully!")
    print(f"   Decoded payload:")
    for k, v in decoded.items():
        print(f"     {k}: {v}")
except Exception as e:
    print(f"\n❌ Error decoding token: {e}")
    exit(1)

# Verify sub and email
if decoded.get("sub") == test_user["sub"] and decoded.get("email") == test_user["email"]:
    print(f"\n✅ Token validation PASSED - sub and email match")
else:
    print(f"\n❌ Token validation FAILED")
    print(f"   Expected sub: {test_user['sub']}, Got: {decoded.get('sub')}")
    print(f"   Expected email: {test_user['email']}, Got: {decoded.get('email')}")

print("\n🎯 If all above passed, JWT token generation is working correctly!")
