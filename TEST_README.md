# 🔥 SaaS Backend Testing Suite

## 📚 Testing Documentation

Three comprehensive test files have been created to validate your SaaS backend:

| File | Purpose | Use When |
|------|---------|----------|
| **tests/test_validate_saas.py** | Automated pytest validation suite | Validating pre-production checks locally and in CI |
| **TEST_WINDOWS.md** | Manual PowerShell commands | Testing individual endpoints on Windows |
| **TEST_DOCUMENTATION.md** | Detailed test guide | Understanding what each test does |
| **TEST_WINDOWS.md** | Windows PowerShell guide | Running on Windows |
| **validate_saas.py** | Pre-deployment checklist | Before going to production |

---

## 🚀 Quick Start (Pick One)

### Option 1: Full Automated Test (Recommended)

```bash
# Terminal 1: Start server
cd c:\Users\ozkan\cv-analyzer
python -m uvicorn main:app --reload

# Terminal 2: Run validation tests
python -m pytest tests/test_validate_saas.py
```

**Expected Output:** pytest exits successfully

### Option 2: Manual Testing (Windows PowerShell)

```powershell
# See TEST_WINDOWS.md for step-by-step guide
# Includes pre-built PowerShell commands
```

### Option 3: Manual Endpoint Tests

```bash
# See TEST_WINDOWS.md for step-by-step PowerShell endpoint checks.
```

---

## 🧪 What Gets Tested

### Core Security Tests
- ✅ **JWT Protection** - Endpoints reject requests without valid token
- ✅ **Token Validation** - Tampered tokens are rejected
- ✅ **Bearer Scheme** - Only "Bearer" auth method accepted

### User Isolation Tests (CRITICAL)
- ✅ **Auto-Creation** - Users created in DB on first request
- ✅ **Data Separation** - User A CANNOT see User B's analyses
- ✅ **History Isolation** - Each user only sees their own history

### Data Integrity Tests
- ✅ **Foreign Keys** - All analyses linked to users (no NULLs)
- ✅ **Orphaned Records** - No analyses without owners

### API Rate Limiting
- ✅ **Rate Limit** - Enforces 10 requests/minute per user

### Edge Cases
- ✅ **PDF Protection** - PDF endpoint also requires JWT
- ✅ **Missing Fields** - Handles tokens without optional fields

---

## 🎯 Test Sequence

**Phase 1: Pre-Flight Check (5 min)**
```bash
python validate_saas.py  # Validates config, files, code
```

**Phase 2: Automated Tests (10 min)**
```bash
python -m pytest tests/test_validate_saas.py
```

**Phase 3: Manual User Testing (30 min)**
- Create 2 different Supabase accounts
- User A makes requests
- User B makes requests
- Verify data isolation
- Check database

**Phase 4: Production Deployment**
- All tests passing ✅
- Staging environment tested ✅
- Ready to deploy

---

## 🔐 Critical Tests Explained

### Test 5: User Isolation (Most Important)

```python
# This is what we verify:

# User A's token → Only sees User A's analyses
GET /api/v1/history (with token A)
Response: [analysis1, analysis2]  # Only A's data

# User B's token → Only sees User B's analyses  
GET /api/v1/history (with token B)
Response: [analysis3, analysis4]  # Only B's data

# Never should happen:
Response: [analysis1, analysis2, analysis3, analysis4]  # 🔴 SECURITY BREACH
```

**If this fails:** 🔴 **DO NOT DEPLOY** - Customer data privacy violation

### Test 1: JWT Protection

```python
# Without token → 401
POST /api/v1/analyze
Response: 401 Unauthorized

# With token → 200 OK
POST /api/v1/analyze (with Authorization header)
Response: 200 OK + analysis results
```

**If this fails:** 🔴 **CRITICAL** - API is completely exposed

---

## 📊 Test Results Examples

### ✅ Perfect Run (All Tests Pass)

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
🎉 ALL TESTS PASSED - SaaS Backend is secure!
```

### ❌ Common Failures

**Test 1 Failed: No Auth (404 instead of 401)**
```
Issue: Endpoints not found
Check: API is running on port 8000
Fix: python -m uvicorn main:app --reload
```

**Test 3 Failed: Valid Token (401)**
```
Issue: Invalid JWT secret
Check: SUPABASE_JWT_SECRET in .env
Fix: Get secret from Supabase Project Settings
```

**Test 5 Failed: User Isolation (Data Overlap)**
```
Issue: CRITICAL - User A seeing User B's data
Check: /api/v1/history endpoint filtering
Fix: Add filter(Analysis.user_id == db_user.id) to query
```

---

## 🗄️ Database Validation

After tests pass, verify database integrity:

```sql
-- Check users created
SELECT COUNT(*) FROM users;

-- Check analyses linked to users
SELECT COUNT(*) FROM analysis 
WHERE user_id IS NOT NULL;

-- Check for orphaned records (should be 0)
SELECT COUNT(*) FROM analysis 
WHERE user_id IS NULL;

-- Check per-user data
SELECT u.email, COUNT(a.id) as analyses
FROM users u
LEFT JOIN analysis a ON u.id = a.user_id
GROUP BY u.id;
```

---

## 🐛 Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ConnectionRefusedError` | Server not running | `python -m uvicorn main:app --reload` |
| `401 on valid token` | Wrong JWT secret | Check `SUPABASE_JWT_SECRET` in .env |
| `404 on /api/v1/analyze` | Wrong endpoint path | Check main.py endpoint routes |
| `Test 5 fails (data overlap)` | User isolation broken | **DO NOT DEPLOY** - Fix filtering in /history |
| `Rate limit not working` | Limiter not configured | Check `@limiter.limit("10/minute")` |

---

## 📋 Pre-Production Checklist

Before deploying to production:

- [ ] Run `python validate_saas.py` → All pass
- [ ] Run `python -m pytest tests/test_validate_saas.py` → Pass
- [ ] Database checks return expected results
- [ ] Created 2 test accounts, data isolation verified
- [ ] Rate limiting tested (11 requests return 429)
- [ ] Backup/restore procedure tested
- [ ] Environment variables set correctly
- [ ] Error logging configured
- [ ] Monitoring set up (API response times, errors)
- [ ] Load testing done on staging

---

## 🚀 Next Phase: Usage Tracking

Once all tests pass, implement:

1. **Usage Tracking** - Count requests per user/day/month
2. **Quota System** - Enforce limits per plan (free/pro/enterprise)
3. **Stripe Integration** - Payment processing
4. **Analytics Dashboard** - User stats and revenue

The system is ready - all groundwork is in place.

---

## 📞 Support

For issues:

1. Check [TEST_DOCUMENTATION.md](TEST_DOCUMENTATION.md) for detailed test explanations
2. Check [TEST_WINDOWS.md](TEST_WINDOWS.md) for Windows-specific guidance
3. Run `python validate_saas.py` to identify missing configuration
4. Check database directly using SQL queries provided

---

## Files Created

```
✅ tests/test_validate_saas.py - Automated pytest validation suite
✅ tests/run_tests.py          - Lightweight API smoke-test helper
✅ validate_saas.py          - Pre-production validation checklist
✅ TEST_DOCUMENTATION.md     - Detailed test guide (comprehensive)
✅ TEST_WINDOWS.md           - Windows PowerShell quick start
✅ TEST_README.md            - This file
```

---

**Status: Ready for Testing** ✅
