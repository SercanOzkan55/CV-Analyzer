"""Manual isolation test: calls /history with two different JWTs
and prints counts to verify users only see their own analyses.

Run: C:/Users/ozkan/cv-analyzer/venv/Scripts/python.exe manual_history_test.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_URL", "http://localhost:8001")

try:
	# Import helpers from the fast test file
	from test_saas_fast import create_mock_jwt, TEST_USER_1, TEST_USER_2
except Exception:
	# Fallback: try debug_jwt token creator
	from debug_jwt import token as DEBUG_TOKEN
	print("Could not import test helpers; exiting.")
	raise

def call_history(token):
	try:
		r = requests.get(f"{API}/api/v1/history", headers={"Authorization": f"Bearer {token}"}, timeout=5)
		return r.status_code, r.text
	except Exception as e:
		return None, str(e)

tok1 = create_mock_jwt(TEST_USER_1)
tok2 = create_mock_jwt(TEST_USER_2)

status1, body1 = call_history(tok1)
status2, body2 = call_history(tok2)

print("User1 token -> status:", status1)
print("User1 body ->", body1[:400])
print("---")
print("User2 token -> status:", status2)
print("User2 body ->", body2[:400])

# If JSON responses, try to show lengths
try:
	import json
	j1 = json.loads(body1) if body1 else []
	j2 = json.loads(body2) if body2 else []
	print(f"User1 records: {len(j1)}, User2 records: {len(j2)}")
except Exception:
	pass

print("Isolation check complete.")
