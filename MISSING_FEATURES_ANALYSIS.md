# 📋 Eksik Özellikler & İyileştirme Alanları

## 🔴 KRİTİK - Hemen Yapılması Gereken

### 1. Frontend Integration - Utility Functions Kullanılmıyor ⚠️
**Status**: Hazırlandı ama entegre edilmedi
**Dosya**: `frontend/src/utils/recruiterErrorHandling.js` (250 lines)
**Sorun**: 
- ✅ Utility functions oluşturuldu
- ❌ RecruiterDashboardPage.jsx'e entegre edilmemiş
- ❌ validateEmail(), validateFileUploads() kullanılmıyor
- ❌ safeApiCall() wrapper kullanılmıyor

**Çözüm**: 
```javascript
// RecruiterDashboardPage.jsx
import { 
  validateEmail, 
  validateFileUploads, 
  safeApiCall,
  formatErrorMessage 
} from '../utils/recruiterErrorHandling'

// handleSendEmail() içinde
if (!validateEmail(emailAddr)) {
  toast.error('Invalid email format')
  return
}

// handleRank() içinde
const result = await safeApiCall(
  () => recruiterDashboardRank(token, {...}),
  'Candidate Ranking',
  { logContext: { jobId: selectedJob.id } }
)
```

---

### 2. Authorization/Access Control - Recruiter'lar Başkasının Verilerine Erişebiliyor
**Status**: Eksik
**Endpoints**: GET /candidates, GET /search, GET /jobs, POST /jobs

**Sorun**:
```python
# routes/recruiter.py - line 275
# Hiçbir organization_id kontrolü yok!
stmt = select(Candidate).where(...)
# → Tüm candidates'e erişim olabilir
```

**Çözüm**:
```python
@router.get("/candidates")
def recruiter_candidates(
    token: str = Header(...),
    org_id: int | None = None,
    db = Depends(get_db)
) -> CandidatesResponse:
    user_obj = verify_supabase_jwt(token)
    user = _get_user(db, user_obj.sub, user_obj.email)
    org = db.query(Organization).filter(
        Organization.id == user.organization_id
    ).first()
    if not org:
        raise HTTPException(401, "Not in organization")
    
    # org_id check
    stmt = select(Candidate).where(
        Candidate.organization_id == org.id  # ← Critical
    ).limit(limit)
    return CandidatesResponse(
        candidates=db.execute(stmt).scalars().all(),
        total=db.execute(select(func.count()).select_from(Candidate)).scalar()
    )
```

**Impact**: 🔴 SECURITY CRITICAL
- Recruiter A can see Recruiter B's data
- Need org-level isolation on ALL endpoints

---

### 3. Pagination with Offset - Büyük Veri Setleri için
**Status**: Kısmi (limit var, offset yok)
**Endpoints**: GET /candidates, GET /search, GET /jobs

**Sorun**:
```python
# Şu an
limit: int = Query(20, ge=1, le=100),
stmt = select(Candidate).limit(limit)  # ← Only first 20

# 500+ candidate olursa? Sayfa geçişi imkansız
```

**Çözüm**:
```python
@router.get("/candidates")
def recruiter_candidates(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
) -> CandidatesResponse:
    stmt = select(Candidate).limit(limit).offset(offset)
    candidates = db.execute(stmt).scalars().all()
    total = db.query(Candidate).count()
    
    return CandidatesResponse(
        candidates=candidates,
        total=total,
        limit=limit,
        offset=offset,
        hasMore=offset + limit < total
    )
```

**Impact**: Büyük veri seti'nde navigation imkansız

---

## 🟠 YÜKSEK ÖNEMLİ - Kısa Vadede Yapılması Gereken

### 4. Database Constraints - Future Date Validation
**Status**: Frontend'de yapılıyor, DB'de yok
**Model**: Reminder.event_date

**Sorun**:
```python
# models.py
event_date = Column(DateTime, nullable=False)  # ← No constraint!

# Tarih validation sadece backend endpoint'te:
if reminder_date_obj <= datetime.utcnow():
    raise HTTPException(400, "Date must be in future")
```

**Çözüm** (Alembic migration):
```sql
ALTER TABLE reminders 
ADD CONSTRAINT check_future_date 
CHECK (event_date > NOW());

ALTER TABLE reminders 
ADD CONSTRAINT check_email_format 
CHECK (target_email ~ '^[^@]+@[^@]+\.[^@]+$');

ALTER TABLE reminders 
ADD CONSTRAINT check_title_length 
CHECK (length(title) BETWEEN 1 AND 500);
```

**Impact**: DB integrity without app logic

---

### 5. Bulk Operations - Multi-Candidate Email Sending
**Status**: Eksik
**Current**: Single candidate email send only

**Sorun**:
```javascript
// RecruiterDashboardPage.jsx - handleSendEmail
// Sadece 1 candidate'e email gönderilip duruyor
await recruiterSendEmail(token, {
  candidate_name: emailTarget.name,
  candidate_email: emailAddr,
  // ← Tek recipient
})
```

**Çözüm** - New Endpoint:
```python
# routes/recruiter.py
@router.post("/send-email-bulk")
async def recruiter_send_email_bulk(
    payload: BulkEmailPayload,
    token: str = Header(...),
    db = Depends(get_db)
):
    """Send email to multiple candidates with progress tracking"""
    results = {
        "total": len(payload.candidate_emails),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for recipient in payload.candidate_emails:
        try:
            await _do_send_email(
                to=recipient,
                subject=subject,
                body=body
            )
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "email": recipient,
                "error": str(e)
            })
    
    return results

# Frontend wrapper
export async function recruiterSendEmailBulk(token, {
  templateId,
  candidateEmails = [],
  jobId = null
}) {
  const res = await fetch(`${BASE}/api/v1/recruiter/send-email-bulk`, {
    method: 'POST',
    headers: { 
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      template_id: templateId,
      candidate_emails: candidateEmails,
      job_id: jobId
    })
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

**Impact**: Users can't email multiple candidates at once

---

### 6. Export Features - CSV/PDF Export
**Status**: Eksik
**Current**: Web only, no export

**Sorun**:
- Ranking sonuçları export edilemiyor
- Candidate list export yok
- Email history export yok

**Çözüm** - New Endpoints:
```python
# routes/recruiter.py

@router.get("/export/rankings")
def recruiter_export_rankings(
    job_id: int,
    format: str = Query("csv", regex="^(csv|json)$"),
    db = Depends(get_db)
) -> StreamingResponse:
    """Export ranked candidates as CSV or JSON"""
    job = db.query(RecruiterJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    
    actions = db.query(CandidateAction).filter(
        CandidateAction.job_id == job_id
    ).all()
    
    if format == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'name', 'email', 'final_score', 'ats_score', 'action'
        ])
        writer.writeheader()
        for action in actions:
            writer.writerow({
                'name': action.candidate_name,
                'email': action.candidate_email,
                'final_score': action.final_score,
                'ats_score': action.ats_score,
                'action': action.action
            })
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=rankings_{job_id}.csv"}
        )
    else:  # JSON
        return [dict(row) for row in actions]

@router.get("/export/candidates")
def recruiter_export_candidates(
    format: str = Query("csv", regex="^(csv|json)$"),
    db = Depends(get_db)
):
    """Export candidates list"""
    # Similar to above
```

---

### 7. Rate Limiting on All Recruiter Endpoints
**Status**: Kısmi (sadece /search'de)
**Current**: 
```python
# routes/recruiter.py - line 392
_search_guard: None = Depends(require_search_rate)  # ← Sadece search
```

**Sorun**: Batch upload, email send'de limit yok

**Çözüm**:
```python
def require_recruiter_rate(
    request: Request,
    user=Depends(verify_supabase_jwt)
):
    """Rate limiter for all recruiter endpoints"""
    return _main().require_recruiter_rate(request, user=user)

# Apply to all endpoints
@router.post("/batch-upload")
async def recruiter_batch_upload(
    _rate_guard: None = Depends(require_recruiter_rate),
    db = Depends(get_db)
):
    # ...

@router.post("/send-email")
async def recruiter_send_email(
    _rate_guard: None = Depends(require_recruiter_rate),
    db = Depends(get_db)
):
    # ...
```

---

### 8. Audit Logging - Critical Operations
**Status**: Hazır ama kullanılmıyor
**Available**: `_log_event(event_type, **fields)`

**Sorun**:
```python
# routes/recruiter.py
async def recruiter_send_email(...):
    # Email sent successfully
    # BUT: No audit log!
    await _do_send_email(...)
    # Should log:
    # _log_event("recruiter.email_sent", 
    #           recruiter_id=org_id,
    #           recipient=email,
    #           template_id=template_id)
```

**Çözüm** - Add audit logs:
```python
@router.post("/send-email")
async def recruiter_send_email(...):
    _log_event("recruiter.email_send_attempt", 
               org_id=org_id,
               recipient=emailAddr,
               template_id=template_id)
    
    try:
        await _do_send_email(...)
        _log_event("recruiter.email_sent",
                   org_id=org_id,
                   recipient=emailAddr,
                   status="success")
    except Exception as e:
        _log_event("recruiter.email_failed",
                   org_id=org_id,
                   recipient=emailAddr,
                   error=str(e))

@router.post("/batch-upload")
async def recruiter_batch_upload(...):
    _log_event("recruiter.batch_upload_start",
               org_id=org_id,
               file_count=len(files))
    # ... process
    _log_event("recruiter.batch_upload_complete",
               org_id=org_id,
               success_count=len(successful),
               failed_count=len(failed))
```

---

## 🟡 ORTA ÖNEMLİ - Ufak Optimizasyonlar

### 9. Response Model Updates - Pagination Fields Ekle
**Status**: Kısmi eksik
**Current Response Models**:
```python
class CandidatesResponse(BaseModel):
    candidates: list[CandidatePreview]
    total: int | None = None
    # ❌ Missing: offset, limit, hasMore
```

**Çözüm**:
```python
class PaginationMeta(BaseModel):
    total: int
    limit: int = 20
    offset: int = 0
    hasMore: bool

class CandidatesResponse(BaseModel):
    candidates: list[CandidatePreview]
    pagination: PaginationMeta

class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str | None = None
    pagination: PaginationMeta

class JobsResponse(BaseModel):
    jobs: list[JobResponse]
    pagination: PaginationMeta
```

---

### 10. Caching for GET Endpoints
**Status**: Eksik
**Current**: No caching

**Çözüm** - Add Redis/Memcached:
```python
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend
from fastapi_cache2.decorator import cache

@router.get("/jobs")
@cache(expire=300)  # Cache for 5 minutes
def recruiter_jobs(
    token: str = Header(...),
    db = Depends(get_db)
) -> JobsResponse:
    # ...
```

---

### 11. Database Cascade Delete
**Status**: Eksik
**Problem**: Silinen job/candidate'ler orphan records bırakıyor

**Çözüm**:
```python
# models.py - RecruiterJob
created_by = Column(
    Integer, 
    ForeignKey("app_users.id", ondelete="CASCADE"),
    nullable=False
)

# models.py - Reminder
created_by = Column(
    Integer,
    ForeignKey("app_users.id", ondelete="CASCADE"),
    nullable=False
)

# models.py - CandidateAction
job_id = Column(
    Integer,
    ForeignKey("recruiter_jobs.id", ondelete="CASCADE"),
    nullable=False
)
```

---

### 12. Retry Logic for Email Send
**Status**: Eksik
**Current**: Single attempt, no retry

**Çözüm** - Celery Task:
```python
from celery import shared_task
from tenacity import retry, stop_after_attempt, wait_exponential

@shared_task
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def send_email_with_retry(to_email, subject, body):
    """Send email with automatic retry (3 attempts)"""
    try:
        return _do_send_email(to_email, subject, body)
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise

@router.post("/send-email")
async def recruiter_send_email(...):
    # Queue background task instead of sync send
    send_email_with_retry.delay(
        to_email=emailAddr,
        subject=subject,
        body=body
    )
    return {"status": "queued", "message": "Email scheduled for delivery"}
```

---

### 13. Progress Tracking for Batch Upload
**Status**: Eksik
**Current**: Upload completes, then results

**Çözüm** - WebSocket Progress:
```python
# routes/recruiter.py
from fastapi import WebSocketDisconnect

@router.websocket("/ws/batch-upload/{upload_id}")
async def websocket_batch_upload(websocket: WebSocket, upload_id: str):
    """Real-time batch upload progress tracking"""
    await websocket.accept()
    try:
        while True:
            # Poll job status
            job_status = get_batch_upload_status(upload_id)
            await websocket.send_json({
                "processed": job_status["processed"],
                "total": job_status["total"],
                "percent": (job_status["processed"] / job_status["total"]) * 100,
                "current": job_status["current_file"],
                "status": job_status["status"]
            })
            if job_status["status"] == "completed":
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

# Frontend
const ws = new WebSocket(`ws://localhost:8001/api/v1/recruiter/ws/batch-upload/${uploadId}`)
ws.onmessage = (e) => {
    const progress = JSON.parse(e.data)
    setUploadProgress(progress)  // Update UI
}
```

---

## 📊 Özet Tablosu

| Özellik | Priority | Effort | Impact | Status |
|---------|----------|--------|--------|--------|
| Frontend Integration | 🔴 High | 2h | High | Not Started |
| Authorization/Access Control | 🔴 High | 3h | Critical | Not Started |
| Pagination with Offset | 🔴 High | 2h | High | Partial |
| DB Constraints (Future Date) | 🟠 Medium | 1h | Medium | Not Started |
| Bulk Email Send | 🟠 Medium | 3h | High | Not Started |
| Export (CSV/JSON) | 🟠 Medium | 3h | Medium | Not Started |
| Rate Limiting (All Endpoints) | 🟠 Medium | 1h | Medium | Partial |
| Audit Logging | 🟠 Medium | 2h | Medium | Ready, Unused |
| Pagination Model Updates | 🟡 Low | 1h | Low | Not Started |
| Caching for GET | 🟡 Low | 1h | Low | Not Started |
| Cascade Delete | 🟡 Low | 0.5h | Low | Not Started |
| Email Retry Logic | 🟡 Low | 2h | Low | Not Started |
| Progress Tracking | 🟡 Low | 3h | Low | Not Started |

---

## 🎯 Önerilen Çalışma Sırası

### **Faz 1: Critical Security (1 gün)**
1. Authorization/Access Control (org_id check) - **SECURITY**
2. Frontend Integration (error handling utils) - **UX**
3. Database Constraints (future dates) - **INTEGRITY**

### **Faz 2: Core Features (2 gün)**
4. Pagination with Offset - **FUNCTIONALITY**
5. Bulk Email Send - **PRODUCTIVITY**
6. Rate Limiting on All Endpoints - **PROTECTION**
7. Audit Logging Integration - **OBSERVABILITY**

### **Faz 3: Polish (1 gün)**
8. Export Features (CSV/JSON) - **UX**
9. Response Model Updates - **CONSISTENCY**
10. Caching for Performance - **PERFORMANCE**
11. Other optimizations - **REFINEMENT**

---

## 📝 Notlar

- ✅ **Frontend utilities ready**: `recruiterErrorHandling.js` hazır ama kullanılmıyor
- ⚠️ **Security risk**: org_id kontrolü eksik = data leakage riski
- 📦 **Alembic migration gerekli**: DB constraints için
- 🔄 **Celery tasks ready**: Batch upload, email retry için infrastructure var
- 📊 **Monitoring ready**: Structured logging infrastructure var, sadece integration yapılmamış
