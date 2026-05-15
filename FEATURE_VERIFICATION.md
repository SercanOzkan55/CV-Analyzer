# 🧪 Özellik Doğrulama & Test Adımları

Bu doküman, yeni eklenen özellikleri ve iyileştirmeleri test etmek için adım adım rehber sağlar.

---

## 📋 Eklenen İyileştirmeler

1. **CSS Standardları** - line-clamp property eklendi
2. **Frontend Testing** - Vitest test suite oluşturuldu
3. **Structured Logging** - Request tracking ve JSON logs
4. **CI/CD Pipeline** - GitHub Actions workflow optimize edildi

---

## 🔍 Test Kontrol Adımları

### 1️⃣ CSS Standards Test

**Location:** [frontend/src/pages/BlogPage.css](frontend/src/pages/BlogPage.css)

**Verify in Browser:**

```bash
# Frontend'i başlat
cd frontend
npm run dev
```

**Test Steps:**
1. http://localhost:5174/blog URL'ine git
2. Blog kartlarını gözle
3. ✅ **Başlık metni** maksimum 2 satırda kesilerek gösterilmeli
4. ✅ **Özet metni** maksimum 3 satırda kesilerek gösterilmeli
5. ✅ Kesilen metinler "..." ile sonlanmalı
6. 🌐 **Tarayıcı Uyumluluğu Test Etme:**
   - Chrome/Edge: ✅ (modern browsers)
   - Firefox: ✅ (line-clamp desteği)
   - Safari: ✅ (-webkit fallback var)

**Code Verification:**
```bash
# CSS'de line-clamp property'sinin var olduğunu doğrula
grep -n "line-clamp:" frontend/src/pages/BlogPage.css
# Output: satır 302 ve 310'da line-clamp: 2; ve line-clamp: 3; olmalı
```

---

### 2️⃣ Frontend Testing Suite

**Location:** [frontend/src/__tests__](frontend/src/__tests__)

**Test Files Added:**
- ✅ `EnhancedCandidatePreview.test.jsx` - Component rendering tests
- ✅ `exportUtils.test.js` - Utility function tests
- ✅ `RecruiterSessionContext.test.jsx` - Session persistence tests

**Run Tests:**

```bash
cd frontend

# Tüm testleri çalıştır
npm test

# Coverage raporu ile çalıştır
npm test -- --coverage

# Belirli bir test dosyasını çalıştır
npm test -- EnhancedCandidatePreview.test.jsx

# Watch mode (geliştirme sırasında)
npm test -- --watch
```

**Expected Output:**

```
PASS  src/__tests__/EnhancedCandidatePreview.test.jsx
  EnhancedCandidatePreview
    ✓ renders candidate name and email (15ms)
    ✓ displays final score (8ms)
    ✓ shows detected skills (10ms)
    ✓ renders experience timeline (12ms)

PASS  src/__tests__/exportUtils.test.js
  exportUtils
    ✓ escapeCsv escapes quotes in CSV fields (5ms)
    ✓ escapeHtml escapes HTML special characters (3ms)
    ... [12 more tests]

PASS  src/__tests__/RecruiterSessionContext.test.jsx
  RecruiterSessionContext
    ✓ saves batch result to localStorage (20ms)
    ✓ updates usage quota (8ms)
    ... [8 more tests]

Test Files  3 passed (3)
Tests      27 passed (27)
```

**Coverage Expectations:**
```
-----------|----------|----------|----------|----------|
File      | % Stmts  | % Branch | % Funcs  | % Lines  |
-----------|----------|----------|----------|----------|
exportUtils.js    | 95.0   | 90.0     | 100      | 95.0     |
EnhancedCandidatePreview | 85.0   | 80.0     | 90       | 85.0     |
RecruiterSessionContext  | 90.0   | 85.0     | 100      | 90.0     |
-----------|----------|----------|----------|----------|
```

---

### 3️⃣ Structured Logging

**Location:** [main.py](main.py), [logging_config.py](logging_config.py)

**Backend'i Test Etme:**

```bash
# Backend'i başlat (log output'unu görmek için)
uvicorn main:app --reload --port 8001
```

**Test API Call:**

```bash
# Recruiter batch ranking endpoint'ini çağır
curl -X POST http://localhost:8001/api/v1/recruiter/batch_rank \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Senior Python Developer",
    "candidate_ids": ["candidate-1", "candidate-2"]
  }'
```

**Expected Logs (JSON format):**

```json
{
  "timestamp": "2026-04-16T12:34:56.789Z",
  "level": "INFO",
  "logger": "main",
  "message": "POST /api/v1/recruiter/batch_rank",
  "module": "main",
  "function": "logging_middleware",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/v1/recruiter/batch_rank",
  "status_code": 200,
  "duration_ms": 234.5
}
```

**Logging Verification:**

```bash
# Log output'unu JSON olarak doğrula
# Terminal'de backend logs'u gözle:
# ✅ Timestamp ISO format'ında olmalı
# ✅ Level INFO/ERROR olmalı
# ✅ request_id unique olmalı (X-Request-ID header'ında)
# ✅ duration_ms milisaniye cinsinden olmalı
```

**Özel Test Senaryosu - Error Logging:**

```bash
# 400 Bad Request tetikle
curl -X POST http://localhost:8001/api/v1/recruiter/batch_rank \
  -H "Authorization: Bearer invalid_token" \
  -d '{invalid json}'
```

**Expected Error Log:**
```json
{
  "timestamp": "2026-04-16T12:34:57.000Z",
  "level": "ERROR",
  "logger": "main",
  "message": "Request failed: POST /api/v1/recruiter/batch_rank",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "status_code": 401,
  "duration_ms": 12.3,
  "error": "Invalid token",
  "exception": {
    "type": "HTTPException",
    "message": "Invalid token",
    "traceback": [...]
  }
}
```

---

### 4️⃣ GitHub Actions CI Pipeline

**Location:** [.github/workflows/ci.yml](.github/workflows/ci.yml)

**CI Pipeline Features:**
- ✅ Lint & Static Analysis (ruff, mypy, bandit)
- ✅ Backend Tests (pytest with coverage)
- ✅ Frontend Tests (npm test)
- ✅ Docker Build Validation
- ✅ Security Scan (Trivy)

**Local olarak Trigger Etme (Push before merge):**

```bash
# Feature branch'i push et
git add .
git commit -m "feat: add improvements"
git push origin feature/branch-name

# GitHub'da PR aç → CI actions otomatik çalışacak
```

**CI Pipeline Kontrol Adımları:**

1. **GitHub'da Actions Tab'ını Aç**
   - URL: https://github.com/YOUR_REPO/actions
   - En son workflow'u aç

2. **Lint Job Kontrol Et**
   - ✅ Ruff check passed
   - ✅ Ruff format check passed
   - ✅ Bandit scan completed
   - ✅ Mypy type check completed

3. **Test Job Kontrol Et**
   - ✅ Database migrations executed
   - ✅ PostgreSQL extension created
   - ✅ Tests passed: `N passed`
   - ✅ Coverage: `60% of required` or higher
   - ✅ Artifact: coverage.xml uploaded

4. **Frontend Job Kontrol Et**
   - ✅ npm ci succeeded
   - ✅ Build completed
   - ✅ Tests ran (or skipped if not configured)
   - ✅ Coverage uploaded to Codecov

5. **Docker Job Kontrol Et**
   - ✅ Docker image built
   - ✅ Container health check passed
   - ✅ No build errors

6. **Security Job Kontrol Et**
   - ✅ Trivy scan completed
   - ✅ CRITICAL vulnerabilities: 0
   - ✅ HIGH vulnerabilities: < 5
   - ✅ SARIF report uploaded

**Örnek Başarılı Output:**
```
✓ Lint (3m 45s) - PASSED
✓ Test (5m 20s) - PASSED (98/103 tests)
✓ Frontend (2m 15s) - PASSED
✓ Docker (4m 10s) - PASSED
✓ Security (1m 30s) - PASSED (0 critical issues)

Overall Status: ✅ ALL CHECKS PASSED
```

---

## 🚀 Fiziksel Site Üzerinde Kontrol

### Pre-Deployment Checklist

Üretim ortamına deploy etmeden önce:

- [ ] Tüm local tests pass et: `npm test` + `pytest`
- [ ] Coverage sonuçlarını kontrol et (min 60%)
- [ ] Git push yap ve CI pipeline başarıyla tamamlansın
- [ ] Code review al
- [ ] Staging ortamında manual test et

### Staging Deployment Test

```bash
# 1. Staging branch'ını oluştur
git checkout -b staging-test
git push origin staging-test

# 2. GitHub Actions'ı izle
# URL: https://github.com/YOUR_REPO/actions

# 3. Staging ortamında manual test et
# URL: https://staging.your-domain.com/

# 4. Özelikleri test et:
```

**Test Scenarios:**

1. **Blog Page (CSS Fix)**
   - [ ] Blog sayfasını aç
   - [ ] Blog kartlarının başlık ve özet metinleri düzgün kesiliyor mu?
   - [ ] Different screen sizes'da test et (mobile, tablet, desktop)

2. **Recruiter Features (Persistence & Export)**
   - [ ] Recruiter Dashboard'a gir
   - [ ] Batch ranking çalıştır
   - [ ] CSV export'ı indir ve aç → Veri doğru mu?
   - [ ] HTML export'ı aç → Formatting düzgün mü?
   - [ ] JSON export'ı aç → Structure valid mi?
   - [ ] Page'i refresh et → Veriler kayıp mı? (localStorage check)

3. **Logging & Monitoring**
   - [ ] Backend logs'u izle: `docker logs <container_id>`
   - [ ] JSON formatted logs görünüyor mu?
   - [ ] Error logs'a bakılan API call fail edince error capture ediliyor mu?

### Production Deployment

```bash
# 1. Main branch'a merge et (after PR approval & CI pass)
git checkout main
git merge --no-ff feature/improvements
git push origin main

# 2. CI pipeline tamamlandığını bekle
# 3. Docker image otomatik built ve pushed olur

# 4. Production'a deploy et (manual or automatic):
# - Kubernetes: kubectl apply -f deployment.yaml
# - Docker Compose: docker-compose up -d

# 5. Health check kontrol et
curl https://your-domain.com/api/v1/health
# Expected: {"status": "ok"}

# 6. Smoke tests çalıştır:
```

**Production Validation:**
```bash
# API Health Check
curl -s https://api.your-domain.com/health | jq .

# Frontend Load Check
curl -s https://your-domain.com/ | head -c 1000 | grep -q "<!DOCTYPE" && echo "✅ Frontend served" || echo "❌ Frontend error"

# Recruiter API Check
curl -s -H "Authorization: Bearer $JWT_TOKEN" \
  https://api.your-domain.com/api/v1/recruiter/search \
  | jq '.status' | grep -q "success" && echo "✅ Recruiter API OK" || echo "❌ Recruiter API Error"
```

---

## 📊 Monitoring & Verification After Deployment

### Logs Monitoring

```bash
# Backend logs'u real-time izle
docker logs -f cv-analyzer-backend

# Belirli saat aralığında logs'u ara
docker logs --since "30m" cv-analyzer-backend | grep ERROR

# JSON logs'u parse et
docker logs cv-analyzer-backend 2>&1 | jq 'select(.level == "ERROR")'
```

### Performance Metrics

```bash
# Response time check
time curl -s https://api.your-domain.com/api/v1/recruiter/search -H "Authorization: Bearer $TOKEN"

# Load test (optional)
# ab -n 100 -c 10 https://api.your-domain.com/health
```

### Error Rate Monitoring

```bash
# Error ratio in logs
docker logs cv-analyzer-backend 2>&1 | jq 'select(.level == "ERROR")' | wc -l
# vs total logs
docker logs cv-analyzer-backend 2>&1 | jq '.' | wc -l
```

---

## 🔄 Rollback Plan

Eğer sorun yaşanırsa:

```bash
# 1. Önceki version'a switch et
git revert <commit_hash>
git push origin main

# 2. CI pipeline'ı bekle (automatic re-deploy)

# 3. Health check kontrol et
curl https://your-domain.com/health

# 4. Logs'u izle
docker logs -f cv-analyzer-backend
```

---

## 📞 Troubleshooting

### Tests Fail Locally

```bash
# Clear cache and reinstall
npm ci --force
npm test -- --no-cache

# Python tests
pip install -e . --force-reinstall
pytest --cache-clear
```

### CI Pipeline Fails

1. GitHub Actions'ın logs'unu aç
2. Error message'i oku
3. Local'da reproduce et
4. Fix yap ve push et

### Production Deployment Issues

```bash
# Container logs'u kontrol et
docker logs cv-analyzer-backend

# Database connection kontrol et
docker exec cv-analyzer-backend psql $DATABASE_URL -c "SELECT 1"

# Redis connection kontrol et
docker exec cv-analyzer-redis redis-cli ping
```

---

## ✅ Final Verification Checklist

Tüm değişiklikleri deploy ettikten sonra:

- [ ] All tests pass locally
- [ ] CI pipeline green
- [ ] Staging works correctly
- [ ] Production deployed
- [ ] Health check returns 200
- [ ] Logs format correct (JSON)
- [ ] No critical errors in logs
- [ ] Blog page displays correctly
- [ ] Recruiter export works
- [ ] Session persistence works (page refresh test)
- [ ] Performance acceptable (< 500ms response time)
- [ ] Security scan: 0 critical vulnerabilities

---

**Version:** 1.0  
**Last Updated:** 2026-04-16  
**Author:** Development Team
