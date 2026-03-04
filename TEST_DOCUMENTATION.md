## 📋 Database Migration and Testing

### PGVector integration
 
 - Install dependency:
 
 ```bash
 pip install -r requirements.txt
 ```
 
 - Ensure your `DATABASE_URL` points to a Postgres instance and run migrations:
 
 ```bash
 # run alembic migrations
 .\venv\Scripts\python.exe -m alembic upgrade heads
 ```
 
 - Quick DB check script (validates `vector` extension and columns):
 
 ```bash
 .\venv\Scripts\python.exe scripts\check_db.py
 ```
 
 - Run the small pgvector integration test (requires Postgres):
 
 ```bash
 .\venv\Scripts\python.exe -m pytest -q tests/test_pgvector_integration.py::test_pgvector_similarity
 ```
# 🔥 SaaS Backend Test Documentation

## Overview

This document covers the critical tests for the JWT authentication and multi-user isolation system. Run these tests **before any production deployment**.

---

## 🚀 Quick Start

### Option 1: Python Test Suite (Automated)

```bash
# Install dependencies
pip install python-jose requests

# Run all tests
python test_saas.py
```

**Expected Output:**
```
✓ PASS: Test 1 - No Auth
✓ PASS: Test 2 - Invalid Token
✓ PASS: Test 3 - Valid Token
✓ PASS: Test 4 - User Auto-Creation
✓ PASS: Test 5 - User Isolation
✓ PASS: Test 6 - Rate Limiting
✓ PASS: Test 7 - Foreign Key
✓ PASS: Test 8 - PDF Protection
✓ PASS: Test 9 - Auth Scheme
✓ PASS: Test 10 - Missing Email

Total: 10/10 tests passed
🎉 ALL TESTS PASSED
```

### Option 2: Manual Curl Tests

```bash
bash test_saas.sh
```

### Option 3: Postman Collection

See the **Postman Setup** section at end of `test_saas.sh`

---

## 📋 Detailed Test Breakdown

### Test 1: NO AUTH (🔴 Critical)

**What:** Send request without Authorization header  
**Command:** `curl -X POST http://localhost:8000/api/v1/analyze -d {...}`  
**Expected:** `401 Unauthorized`  
**Failure Impact:** 🔴 **CRITICAL** - API is completely exposed

```json
{
  "detail": "Missing Authorization header"
}
```

---

### Test 2: INVALID TOKEN (🔴 Critical)

**What:** Send request with tampered/invalid JWT  
**Command:** `curl -H "Authorization: Bearer TAMPERED_TOKEN" ...`  
**Expected:** `401 Unauthorized`  
**Failure Impact:** 🔴 **CRITICAL** - Anyone can fake authentication

```json
{
  "detail": "Invalid or expired token"
}
```

**How to test manually:**
```bash
# Get valid token first
TOKEN="your_real_jwt_token"
FAKE="${TOKEN:0:-5}xxxxx"  # Change last 5 chars

curl -H "Authorization: Bearer $FAKE" \
  -X POST http://localhost:8000/api/v1/analyze
```

---

### Test 3: VALID TOKEN (🟢 Expected Success)

**What:** Send request with correct JWT  
**Command:** `curl -H "Authorization: Bearer VALID_TOKEN" ...`  
**Expected:** `200 OK` with analysis results  
**Failure Impact:** ⚠️ All legitimate users blocked

**Response includes:**
- `final_score` - Match percentage
- `interpretation` - Quality assessment
- `user_id` - Linked to authenticated user

---

### Test 4: USER AUTO-CREATION (🟢 Important)

**What:** First request should create user in database  
**Verification:**
```sql
SELECT * FROM users WHERE email = 'your_email@example.com';  # (app_users)
```

**Check for:**
- ✅ `supabase_id` - Set from JWT `sub` claim
- ✅ `email` - Set from JWT `email` claim
- ✅ `plan_type` - Defaults to "free"
- ✅ `created_at` - Current timestamp

**Failure symptoms:**
- ❌ No user created → Later user isolation fails
- ❌ Wrong supabase_id → Can't identify user
- ❌ NULL email → Problems for billing/notifications

---

### Test 5: USER ISOLATION (🔴 MOST CRITICAL)

**What:** User A should ONLY see User A's analyses  
**Why:** Customer data privacy - legal and security requirement

**Test Steps:**
1. Create 2 different Supabase accounts
2. User A logs in → Does `/api/v1/analyze`
3. User B logs in → Does `/api/v1/analyze`
4. User A calls `/api/v1/history` → Should ONLY see their own records
5. User B calls `/api/v1/history` → Should ONLY see their own records

**Database verification:**
```sql
-- User A should only see their analyses
SELECT COUNT(*) FROM analysis a
WHERE a.user_id = (SELECT id FROM users WHERE email = 'user_a@example.com');

-- User B should only see their analyses
SELECT COUNT(*) FROM analysis a
WHERE a.user_id = (SELECT id FROM users WHERE email = 'user_b@example.com');

-- Check no cross-contamination
SELECT DISTINCT(user_id) FROM analysis
ORDER BY user_id;
```

**Failure Impact:** 🔴 **CRITICAL SECURITY BREACH**
- Customer A can see Customer B's CVs/job analyses
- GDPR/privacy violations
- Breach of trust, lawsuits

**Common failure:** `@app.get("/api/v1/history")` returns ALL analyses instead of filtering by user_id

---

### Test 6: RATE LIMITING (🟡 Important)

**What:** Max 10 requests per minute per user  
**Command:** Send 11 requests rapidly

```bash
for i in {1..11}; do
  curl -H "Authorization: Bearer $TOKEN" \
    -X POST http://localhost:8000/api/v1/analyze \
    -d '...'
done
```

**Expected:**
- Requests 1-10: `200 OK`
- Request 11: `429 Too Many Requests`

**Failure symptoms:**
- ❌ All 11 return 200 → Rate limiter broken
- ❌ Requests keep succeeding → Users can DOS your API

**Response on limit:**
```json
{
  "detail": "10 per 1 minute"
}
```

---

### Test 7: FOREIGN KEY INTEGRITY (🟢 Important)

**What:** Every Analysis record MUST have `user_id` set

**Database check:**
```sql
-- This should return 0
SELECT COUNT(*) FROM analysis WHERE user_id IS NULL;

-- This should return 0 (no orphaned records)
SELECT COUNT(*) FROM analysis a
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = a.user_id);
```

**Failure impact:**
- ❌ Can't attribute analyses to users
- ❌ User isolation fails
- ❌ Analytics/billing broken

---

### Test 8: PDF ENDPOINT PROTECTION (🟡 Important)

**What:** `/api/v1/analyze-pdf` also requires JWT  
**Command without auth:** `curl -X POST http://localhost:8000/api/v1/analyze-pdf -F "file=@cv.pdf"`  
**Expected:** `401 Unauthorized`

**Common mistake:** Only protecting `/analyze`, forgetting about `/analyze-pdf`

---

### Test 9: AUTH SCHEME VALIDATION (🟡 Important)

**What:** Only "Bearer" scheme is accepted  
**Invalid schemes that should fail:**
- `Authorization: Basic TOKEN` → 401
- `Authorization: Token TOKEN` → 401
- `Authorization: JWT TOKEN` → 401
- `Authorization: ${TOKEN}` → 401

**Correct format:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

### Test 10: MISSING EMAIL IN TOKEN (🟢 Edge Case)

**What:** Token without email field should still work  
**Why:** Not all JWT tokens may include email

**Expected:** 200 (works with email=None)  
**Not expected:** 401 error due to missing email

---

## 🗄️ Database Inspection Commands

### Check User Creation

```sql
-- Count users
SELECT COUNT(*) FROM users;

-- List recent users
SELECT id, supabase_id, email, plan_type, created_at
FROM users
ORDER BY created_at DESC
LIMIT 10;

-- Check specific user
SELECT * FROM users WHERE email = 'youremail@example.com';
```

### Check Analysis Records

```sql
-- All analyses with user info
SELECT 
  a.id,
  a.similarity_score,
  a.interpretation,
  u.email,
  u.supabase_id,
  a.created_at
FROM analysis a
LEFT JOIN users u ON a.user_id = u.id
ORDER BY a.created_at DESC
LIMIT 10;

-- Analyses by user
SELECT 
  u.email,
  COUNT(*) as analysis_count,
  MIN(a.created_at) as first_analysis,
  MAX(a.created_at) as last_analysis
FROM users u
LEFT JOIN analysis a ON u.id = a.user_id
GROUP BY u.id, u.email
ORDER BY analysis_count DESC;
```

### Verify Data Integrity

```sql
-- Check for NULL user_ids (SHOULD BE 0)
SELECT COUNT(*) as orphaned_analyses
FROM analysis
WHERE user_id IS NULL;

-- Check for broken foreign keys (SHOULD BE 0)
SELECT COUNT(*) as invalid_references
FROM analysis a
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = a.user_id);

-- Verify each analysis has user_id
SELECT COUNT(*) as total_analyses, 
       COUNT(DISTINCT user_id) as users_with_analyses
FROM analysis;
```

---

## 🔐 Security Checklist

Before production, verify:

- [ ] Test 1 passes - API rejects requests without JWT
- [ ] Test 2 passes - API rejects tampered tokens
- [ ] Test 3 passes - Valid tokens work (200 OK)
- [ ] Test 4 passes - Users auto-created on first request
  - [ ] Test 6 passes - Free tier capped at 5 analyses per UTC day (quota enforcement)
- [ ] Test 5 passes - User A CANNOT see User B's data
- [ ] Test 6 passes - Rate limiting enforced (429 after 10)
- [ ] Test 7 passes - No NULL user_id in database
- [ ] Test 8 passes - PDF endpoint also requires JWT
- [ ] Test 9 passes - Wrong auth scheme rejected
- [ ] Test 10 passes - Handles missing email gracefully
- [ ] Database has no orphaned analyses
- [ ] All endpoints use `Depends(verify_supabase_jwt)`

---

## 🧪 Testing Workflow

### Day 1: Local Testing

```bash
# Start server
python -m uvicorn main:app --reload

# In another terminal
python test_saas.py
```

### Day 2: Frontend Integration

1. Update `test-login.html` to add `/api/v1/analyze` calls
2. Get token from Supabase session
3. Send to API with Authorization header
4. Verify 200 response

### Day 3: Multi-User Testing

1. Test with 2+ actual Supabase accounts
2. Each user does multiple requests
3. `/history` endpoint returns only that user's data
4. User isolation verified ✅

### Day 4: Production Readiness

1. All database validations pass
2. Rate limiting tested under load
3. Error handling verified (timeouts, crashes)
4. Backup/restore procedure tested

---

## 🐛 Troubleshooting

---

## **IVFFlat Tuning & CI Ops**

**Purpose:** Document practical tuning advice for `ivfflat` indexes used by `pgvector`, and CI/runtime operational recommendations so tests and CI pipelines can run reliably with `pgvector` enabled.

- **Index type used:** `ivfflat` with `vector_cosine_ops`. This is a trade-off between search speed and recall.

- **When to use `ivfflat`:**
  - Good for large collections (tens of thousands+ vectors).
  - When you need sub-linear query latency and can tolerate slightly lower recall compared to exact search.

- **Key parameter — `lists` (nlist):**
  - The `lists` parameter controls the number of Voronoi cells. Larger `lists` → higher index size and longer index build time but better recall.
  - Rule of thumb:
    - small corpora (<10k vectors): `lists=100` or use exact search (`vector_l2_ops`/brute-force)
    - medium (10k–200k): `lists=512` → `1024`
    - large (>200k): `lists=2048` or higher, tune by benchmarking

- **Rebuilding / Reindexing:**
  - When `lists` is changed you must `REINDEX` or drop/create the index again:

```sql
DROP INDEX IF EXISTS idx_candidates_cv_embedding_ivfflat;
CREATE INDEX idx_candidates_cv_embedding_ivfflat ON candidates USING ivfflat (cv_embedding vector_cosine_ops) WITH (lists = 512);
```

  - After batch inserts, run `ANALYZE` on the table to update planner statistics.

- **Warmup & tuning workflow:**
  1. Start with a conservative `lists` value (e.g. 512).
  2. Run representative queries and measure recall/latency.
  3. Increase `lists` until latency/recall meet SLOs.
  4. Use larger `nprobe` at query time for higher recall at cost of latency (if supported by your pgvector build).

- **Example: create ivfflat index with lists=100 (sensible default for small/medium test DBs):**

```sql
-- create extension if needed
CREATE EXTENSION IF NOT EXISTS vector;

-- create ivfflat index (adjust lists for production)
CREATE INDEX IF NOT EXISTS idx_candidates_cv_embedding_ivfflat
ON candidates USING ivfflat (cv_embedding vector_cosine_ops) WITH (lists = 100);
```

- **CI/Dev Ops recommendations:**
  - CI must provide a Postgres instance with the `pgvector` extension available.
  - Two common approaches for GitHub Actions / CI:
    1. Use a Docker service image that has `pgvector` pre-installed (recommended):

```yaml
services:
  postgres:
    image: ankane/pgvector:postgres-15
    ports: [5432]
    env:
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpass
      POSTGRES_DB: testdb
    options: >-
      --health-cmd "pg_isready -U testuser" --health-interval 10s --health-timeout 5s --health-retries 5
```

    2. Use `postgres:15` and install `pgvector` in CI startup script (slower):

```bash
apt-get update && apt-get install -y postgresql-server-dev-all build-essential git
git clone https://github.com/pgvector/pgvector.git && cd pgvector && make && make install
```

  - After DB is available in CI, run migrations and create indexes before tests:

```bash
# set DATABASE_URL for CI
export DATABASE_URL=postgresql+psycopg2://testuser:testpass@localhost:5432/testdb
python -m alembic upgrade heads
# optionally create ivfflat index with a small lists value for CI
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;" \
  && psql $DATABASE_URL -c "CREATE INDEX IF NOT EXISTS idx_candidates_cv_embedding_ivfflat ON candidates USING ivfflat (cv_embedding vector_cosine_ops) WITH (lists = 100);"
```

- **Testing tips:**
  - CI should run the pgvector integration tests conditionally (skip if extension missing). The repo's tests already skip when `DATABASE_URL` is not a Postgres URL.
  - Use a low `lists` value in CI to keep index build times short.
  - For deterministic unit tests, stub `find_similar_candidates` to avoid flakiness caused by approximate indexes.

- **Monitoring & production ops:**
  - Monitor query latency and index size (table bloat). If latency grows, consider increasing `lists` or sharding by tenant.
  - Schedule periodic `VACUUM`/`ANALYZE` for large tables and reindex after massive data loads.

---

End of `ivfflat` tuning & CI ops notes.

### "401 on valid token"

**Possible causes:**
1. `SUPABASE_JWT_SECRET` wrong in `.env`
2. Token expired (check exp claim)
3. Wrong audience claim (should be "authenticated")
4. Token from different Supabase project

**Fix:**
```bash
# Get secret from Supabase Project Settings → API
# In .env:
SUPABASE_JWT_SECRET=your_actual_secret_here

# Restart server
python -m uvicorn main:app --reload
```

### "User not created in database"

**Possible causes:**
1. Database connection broken
2. Migrations not run
3. User already existed but different email

**Fix:**
```bash
# Reset database (⚠️ DELETES DATA)
pip install sqlalchemy
python
>>> from database import engine
>>> from models import Base
>>> Base.metadata.drop_all(engine)
>>> Base.metadata.create_all(engine)
```

### "User A can see User B's data"

**Critical issue - check:**

1. `/history` endpoint filtering:
```python
# ✅ CORRECT
records = db.query(Analysis).filter(
    Analysis.user_id == db_user.id  # Filter by current user
).all()

# ❌ WRONG
records = db.query(Analysis).all()  # No filter - ALL data!
```

2. Verify `user_id` is set for all analyses:
```sql
SELECT COUNT(*) FROM analysis WHERE user_id IS NULL;
-- Result must be 0
```

### "Rate limit not working"

**Check:**
1. Is `@limiter.limit("10/minute")` decorator present?
2. Is `app.state.limiter = limiter` set?
3. Are old analyses from before rate limit still in DB?

---

## 📊 Test Results Interpretation

| Test | Pass | Fail Severity |
|------|------|---------------|
| No Auth | ✅ Should see 401 | 🔴 CRITICAL - API exposed |
| Invalid Token | ✅ Should reject | 🔴 CRITICAL - Auth broken |
| Valid Token | ✅ Should work | ⚠️ Users can't use app |
| User Creation | ✅ User created | ⚠️ Can't track users |
| User Isolation | ✅ Separated | 🔴 CRITICAL - Privacy breach |
| Rate Limit | ✅ Enforced | 🟡 Medium - DOS risk |
| Foreign Key | ✅ All linked | ⚠️ Data integrity issue |
| PDF Protection | ✅ Requires JWT | 🟡 Medium - Endpoint exposed |
| Auth Scheme | ✅ Bearer only | 🟡 Medium - Weak security |
| Missing Email | ✅ Handles | ❌ Minor - Edge case |

---

## 🚀 Next Steps After Tests Pass

1. **Phase 3**: Usage Tracking (track daily/monthly counts)
2. **Phase 4**: Quota System (enforce limits per plan)
3. **Phase 5**: Stripe Integration (payment processing)

See `/api/v1/history` endpoint - ready for usage analytics.

---

## Debug Mode

To get detailed error logs:

```python
# In main.py
import logging
logging.basicConfig(level=logging.DEBUG)

# In auth.py - add at top
import sys
sys.stderr = sys.stdout  # See all errors
```

---

## Questions?

Check:
1. `auth.py` - JWT verification logic
2. `main.py` - Endpoint protection with `Depends(verify_supabase_jwt)`
3. `models.py` - User and Analysis schema
4. Database logs for connection issues

