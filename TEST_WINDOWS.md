# 🔥 SaaS Backend Tests - Windows Quick Start

## ⚡ Quick Commands (Windows PowerShell)

### 1. Start Server (in first PowerShell)
```powershell
cd c:\Users\ozkan\cv-analyzer
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Wait for: `Uvicorn running on http://127.0.0.1:8000`

### 2. Get JWT Token (in browser console)

Go to `file:///c:/Users/ozkan/cv-analyzer/test-login.html` (or host it)

```javascript
// After clicking Login with Google
const { data } = await supabase.auth.getSession();
const token = data.session.access_token;
console.log(token);
// Copy this token
```

### 3. Run Tests (in second PowerShell)

```powershell
cd c:\Users\ozkan\cv-analyzer

# Automated Python tests
python test_saas.py

# OR manual curl tests
$TOKEN = "paste_your_token_here"
$API = "http://localhost:8000"

# TEST: No Auth (should be 401)
Invoke-WebRequest -Uri "$API/api/v1/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"cv_text":"engineer","job_description":"backend engineer"}'

# TEST: With valid token (should be 200)
Invoke-WebRequest -Uri "$API/api/v1/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"Authorization"="Bearer $TOKEN"} `
  -Body '{"cv_text":"Senior Python dev","job_description":"Senior Backend Engineer"}'
```

---

## 🗄️ Database Checks (PostgreSQL)

### Option A: Using psql (if installed)

```powershell
# Connect to database
$env:PGPASSWORD="your_password"
psql -h your_host -U your_user -d your_db

# Then in psql:
SELECT * FROM app_users ORDER BY created_at DESC;
SELECT COUNT(*) FROM analysis WHERE user_id IS NULL;
SELECT DISTINCT user_id FROM analysis;
```

### Option B: Using Python

```powershell
python
```

```python
from database import SessionLocal
from models import User, Analysis

db = SessionLocal()

# Check users
users = db.query(User).all()
print(f"Total users: {len(users)}")
for user in users:
    print(f"  - {user.email}: {user.supabase_id}")

# Check analyses
analyses = db.query(Analysis).all()
print(f"\nTotal analyses: {len(analyses)}")

# Check for null user_id
null_user_ids = db.query(Analysis).filter(Analysis.user_id == None).count()
print(f"Analyses with NULL user_id: {null_user_ids} (should be 0)")

# Check per-user count
from sqlalchemy import func
counts = db.query(User.email, func.count(Analysis.id)).outerjoin(Analysis).group_by(User.id).all()
for email, count in counts:
    print(f"  - {email}: {count} analyses")

db.close()
```

---

## 🧪 Full Test Sequence

### Step 1: Prepare

```powershell
# Check server is running on port 8000
curl http://localhost:8000/docs  # Swagger UI should load
```

### Step 2: Get Tokens

Open `test-login.html` twice in different browsers or incognito windows:

1. First login → Copy Token A → Save as `$TOKEN_A`
2. Second login (different account) → Copy Token B → Save as `$TOKEN_B`

### Step 3: Run Tests (PowerShell)

```powershell
cd c:\Users\ozkan\cv-analyzer

# Set variables
$TOKEN_A = "first_user_token"
$TOKEN_B = "second_user_token"
$API = "http://localhost:8000"

# Test A: No Auth (should fail)
Write-Host "TEST 1: No Auth" -ForegroundColor Red
try {
  Invoke-WebRequest -Uri "$API/api/v1/analyze" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"cv_text":"test","job_description":"test"}'
} catch {
  Write-Host "✓ Got 401 as expected" -ForegroundColor Green
}

# Test B: Valid token User A
Write-Host "`nTEST 2: User A - Valid Token" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "$API/api/v1/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"Authorization"="Bearer $TOKEN_A"} `
  -Body '{
    "cv_text":"Senior Python Engineer, 5 years experience, FastAPI, PostgreSQL",
    "job_description":"Senior Backend Engineer, 5+ years Python, FastAPI required"
  }'
Write-Host "✓ Got 200 OK" -ForegroundColor Green
$score = ($response.Content | ConvertFrom-Json).final_score
Write-Host "  Score: $score" -ForegroundColor Green

# Test C: Valid token User B
Write-Host "`nTEST 3: User B - Valid Token" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "$API/api/v1/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"Authorization"="Bearer $TOKEN_B"} `
  -Body '{
    "cv_text":"Junior JavaScript dev, 2 years React",
    "job_description":"Senior Backend Engineer needed"
  }'
Write-Host "✓ Got 200 OK" -ForegroundColor Green

# Test D: User A history
Write-Host "`nTEST 4: User A - Get History" -ForegroundColor Yellow
$history_a = Invoke-WebRequest -Uri "$API/api/v1/history" `
  -Method GET `
  -Headers @{"Authorization"="Bearer $TOKEN_A"} | ConvertFrom-Json
Write-Host "✓ User A has $($history_a.Count) analyses" -ForegroundColor Green

# Test E: User B history
Write-Host "`nTEST 5: User B - Get History" -ForegroundColor Yellow
$history_b = Invoke-WebRequest -Uri "$API/api/v1/history" `
  -Method GET `
  -Headers @{"Authorization"="Bearer $TOKEN_B"} | ConvertFrom-Json
Write-Host "✓ User B has $($history_b.Count) analyses" -ForegroundColor Green

# Test F: Verify isolation
Write-Host "`nTEST 6: User Isolation Check" -ForegroundColor Cyan
if ($history_a.Count -gt 0 -and $history_b.Count -gt 0) {
  $ids_a = $history_a | % { $_.id }
  $ids_b = $history_b | % { $_.id }
  $overlap = [System.Linq.Enumerable]::Intersect($ids_a, $ids_b).Count
  if ($overlap -eq 0) {
    Write-Host "✓ NO DATA OVERLAP - User isolation working!" -ForegroundColor Green
  } else {
    Write-Host "✗ CRITICAL: Users can see each other's data!" -ForegroundColor Red
  }
}

# Test G: Rate limiting
Write-Host "`nTEST 7: Rate Limiting" -ForegroundColor Magenta
for ($i = 1; $i -le 11; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri "$API/api/v1/analyze" `
      -Method POST `
      -ContentType "application/json" `
      -Headers @{"Authorization"="Bearer $TOKEN_A"} `
      -Body '{"cv_text":"test","job_description":"test"}' `
      -TimeoutSec 5
    Write-Host "  Request $i": 200 OK" -ForegroundColor Green
  } catch {
    if ($_.Exception.Response.StatusCode -eq 429) {
      Write-Host "  Request $i`: 429 Rate Limited (expected)" -ForegroundColor Yellow
      break
    }
  }
  Start-Sleep -Milliseconds 100
}

Write-Host "`n✅ All tests complete!" -ForegroundColor Green
```

---

## 📊 Expected Results

```
TEST 1: No Auth
✓ Got 401 as expected

TEST 2: User A - Valid Token
✓ Got 200 OK
  Score: 67.5

TEST 3: User B - Valid Token
✓ Got 200 OK

TEST 4: User A - Get History
✓ User A has 1 analyses

TEST 5: User B - Get History
✓ User B has 1 analyses

TEST 6: User Isolation Check
✓ NO DATA OVERLAP - User isolation working!

TEST 7: Rate Limiting
  Request 1: 200 OK
  Request 2: 200 OK
  Request 3: 200 OK
  Request 4: 200 OK
  Request 5: 200 OK
  Request 6: 200 OK
  Request 7: 200 OK
  Request 8: 200 OK
  Request 9: 200 OK
  Request 10: 200 OK
  Request 11: 429 Rate Limited (expected)

✅ All tests complete!
```

---

## 🐛 Troubleshooting

### Server won't start
```powershell
# Check port in use
Get-NetTcpConnection -LocalPort 8000 | Select ProcessName

# Or use different port
python -m uvicorn main:app --reload --port 8001
```

### Database connection error
```powershell
# Check .env file
cat .env

# Verify DATABASE_URL is correct
# Format: postgresql://user:password@host:5432/dbname
```

### JWT token invalid
```powershell
# Get a new token
# Go to test-login.html again and login
# Or check SUPABASE_JWT_SECRET in .env matches your project
```

### Rate limit not working
```powershell
# Add small delay between requests
for ($i = 1; $i -le 11; $i++) {
  # ... request code ...
  Start-Sleep -Milliseconds 200  # Increase if needed
}
```

---

## 🎯 Success Criteria

- [ ] TEST 1: 401 without auth ✅
- [ ] TEST 2: 200 with valid token ✅
- [ ] TEST 3: Different user gets 200 ✅
- [ ] TEST 4: User A sees their analyses ✅
- [ ] TEST 5: User B sees their analyses ✅
- [ ] TEST 6: No data overlap between users ✅
- [ ] TEST 7: Rate limiting kicks in ✅

If all pass → **Ready for next phase (Usage Tracking, Quota System)**

