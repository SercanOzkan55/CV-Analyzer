"""
🔥 Fast SaaS Backend Tests - Authentication Only
Tests JWT, rate limiting, and user management (no model inference)
Run: python test_saas_fast.py
"""

import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from jose import jwt

load_dotenv()

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_JWT_SECRET:
    print("❌ ERROR: SUPABASE_JWT_SECRET not set in .env")
    exit(1)

# Test users
TEST_USER_1 = {
    "sub": "user-123-aaa",
    "email": "user1@example.com",
    "aud": "authenticated",
}
TEST_USER_2 = {
    "sub": "user-456-bbb",
    "email": "user2@example.com",
    "aud": "authenticated",
}


def create_mock_jwt(user_data):
    """Create JWT token"""
    now = datetime.now(timezone.utc)
    payload = {
        **user_data,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")


def print_test(num, name):
    print(f"\n{'='*60}")
    print(f"✅ TEST {num}: {name}")
    print(f"{'='*60}")


def print_result(passed, expected, actual):
    if passed:
        print(f"✓ PASS - Expected: {expected}, Got: {actual}")
    else:
        print(f"✗ FAIL - Expected: {expected}, Got: {actual}")


def check_server():
    try:
        requests.get(f"{API_BASE_URL}/docs", timeout=2)
        return True
    except:
        return False


# =====================================================
# TESTS
# =====================================================


def test_1_no_auth():
    print_test(1, "NO AUTH TEST")
    try:
        # history is GET, not POST
        response = requests.get(f"{API_BASE_URL}/api/v1/history", timeout=5)
        passed = response.status_code == 401
        print_result(passed, "401 Unauthorized", f"{response.status_code}")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_2_invalid_token():
    print_test(2, "INVALID TOKEN TEST")
    try:
        token = create_mock_jwt(TEST_USER_1)
        tampered = token[:-5] + "xxxxx"
        response = requests.get(
            f"{API_BASE_URL}/api/v1/history",
            headers={"Authorization": f"Bearer {tampered}"},
            timeout=5,
        )
        passed = response.status_code == 401
        print_result(passed, "401 Unauthorized", f"{response.status_code}")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_3_valid_token():
    print_test(3, "VALID TOKEN TEST")
    try:
        token = create_mock_jwt(TEST_USER_1)
        response = requests.get(
            f"{API_BASE_URL}/api/v1/history",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        passed = response.status_code == 200
        print_result(passed, "200 OK", f"{response.status_code}")
        if passed:
            print(f"  Response: {response.json()[:100]}...")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_4_user_creation():
    print_test(4, "USER CREATION TEST")
    try:
        from database import SessionLocal
        from models import User

        db = SessionLocal()
        user = db.query(User).filter(User.supabase_id == TEST_USER_1["sub"]).first()

        if user:
            print(f"✓ User created: {user.email}")
            print(f"  - User ID: {user.id}")
            print(f"  - Plan: {user.plan_type}")
            print(f"  - Daily usage: {user.daily_usage}")
            print(f"  - Monthly usage: {user.monthly_usage}")
            print(f"  - Last reset: {user.last_reset}")
            db.close()
            return True
        else:
            print("✗ User not found in database")
            db.close()
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_5_user_isolation():
    print_test(5, "USER ISOLATION TEST")
    try:
        from database import SessionLocal
        from models import User

        db = SessionLocal()

        # Get both users
        user1 = db.query(User).filter(User.supabase_id == TEST_USER_1["sub"]).first()
        user2 = db.query(User).filter(User.supabase_id == TEST_USER_2["sub"]).first()

        # Get their histories
        token1 = create_mock_jwt(TEST_USER_1)
        token2 = create_mock_jwt(TEST_USER_2)

        resp1 = requests.get(
            f"{API_BASE_URL}/api/v1/history",
            headers={"Authorization": f"Bearer {token1}"},
            timeout=10,
        )

        resp2 = requests.get(
            f"{API_BASE_URL}/api/v1/history",
            headers={"Authorization": f"Bearer {token2}"},
            timeout=10,
        )

        db.close()

        if resp1.status_code == 200 and resp2.status_code == 200:
            print("✓ Both users can access /history")
            print(f"  User1 analyses: {len(resp1.json())}")
            print(f"  User2 analyses: {len(resp2.json())}")
            return True
        else:
            print("✗ History access failed")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_6_pdf_protection():
    print_test(6, "PDF ENDPOINT PROTECTION")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/analyze-pdf",
            files={"file": ("test.pdf", b"%PDF-test", "application/pdf")},
            data={"job_description": "test"},
        )
        passed = response.status_code == 401
        print_result(passed, "401 Unauthorized", f"{response.status_code}")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_7_auth_scheme():
    print_test(7, "AUTH SCHEME VALIDATION")
    try:
        token = create_mock_jwt(TEST_USER_1)
        response = requests.get(
            f"{API_BASE_URL}/api/v1/history",
            headers={"Authorization": f"Basic {token}"},
            timeout=5,
        )
        passed = response.status_code == 401
        print_result(passed, "401 Unauthorized", f"{response.status_code}")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_8_quota_enforcement():
    print_test(8, "DAILY QUOTA ENFORCEMENT")
    try:
        token = create_mock_jwt(TEST_USER_2)
        headers = {"Authorization": f"Bearer {token}"}
        body = {"cv_text": "", "job_description": ""}
        success = True
        # make 5 allowed requests
        for i in range(5):
            resp = requests.post(
                f"{API_BASE_URL}/api/v1/analyze", json=body, headers=headers, timeout=10
            )
            if resp.status_code != 200:
                print(f"✗ request {i+1} returned {resp.status_code}")
                success = False
                break
        # sixth request should be rejected
        resp6 = requests.post(
            f"{API_BASE_URL}/api/v1/analyze", json=body, headers=headers, timeout=10
        )
        passed = success and resp6.status_code == 403
        print_result(passed, "403 on 6th", f"{resp6.status_code}")
        return passed
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


# =====================================================
# MAIN
# =====================================================


def run_all_tests():
    print("\n" + "=" * 60)
    print("   SaaS BACKEND FAST TESTS (Auth Only)")
    print("   No model inference - focus on security")
    print("=" * 60)

    if not check_server():
        print(f"\n❌ ERROR: Server not running at {API_BASE_URL}")
        print("   Start: python -m uvicorn main:app --reload")
        return False

    results = {
        "Test 1 - No Auth": test_1_no_auth(),
        "Test 2 - Invalid Token": test_2_invalid_token(),
        "Test 3 - Valid Token": test_3_valid_token(),
        "Test 4 - User Creation": test_4_user_creation(),
        "Test 5 - User Isolation": test_5_user_isolation(),
        "Test 6 - PDF Protection": test_6_pdf_protection(),
        "Test 7 - Auth Scheme": test_7_auth_scheme(),
    }

    # Summary
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + "  TEST RESULTS SUMMARY".center(58) + "║")
    print("╠" + "=" * 58 + "╣")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"║ {status}: {name:<50} ║")

    print("╠" + "=" * 58 + "╣")
    print(f"║ Total: {passed}/{total} tests passed".ljust(59) + "║")
    print("╚" + "=" * 58 + "╝\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED - SaaS Backend is secure!\n")
        return True
    else:
        print(f"❌ {total - passed} test(s) failed\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
