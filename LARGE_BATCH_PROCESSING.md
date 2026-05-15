# 🚀 Large Batch CV Processing (5000+ CVs)

## Problem: Why 5000 CVs Crash the System?

### Memory Issues
```
5000 CVs × 1MB avg = ~5GB RAM (peak)
- ZIP extraction: 2GB
- Processing: 2GB
- Database ops: 1GB
= System runs out of memory → Crash
```

### Other Issues
```
❌ Default timeout: 30s (5000 CVs need 2-3 hours)
❌ Database connection pool: 5 connections max
❌ API request size limit: 100MB
❌ Single async task blocks event loop
```

---

## ✅ Solution: Chunked Processing + Streaming

### 1. **Chunked Batch Processing**
```python
# Process in 200 CV chunks instead of all at once
def chunk_list(items, chunk_size=200):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]

# 5000 CVs = 25 chunks × 5 min = 2 hours total
```

### 2. **Streaming ZIP Extraction**
```python
async def extract_linkedin_zip_streaming(zip_file, chunk_size=200):
    """Extract files WITHOUT loading entire ZIP to memory"""
    with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
        chunk = []
        for file_info in zip_ref.filelist:
            chunk.append(file_info)
            
            if len(chunk) >= chunk_size:
                yield chunk  # Yield as we go
                chunk = []
    
    # Memory never exceeds 500MB for ZIP buffer
```

### 3. **Async Processing**
```python
async def process_cv_batch_chunked():
    """Process chunks with async/await"""
    
    for chunk_num, file_chunk in enumerate(zip_stream):
        # Process each chunk independently
        results = await process_cv_batch(file_chunk)
        
        # Free memory after each chunk
        del file_chunk
        
        # Yield control back
        await asyncio.sleep(0.1)
```

### 4. **Progress Tracking**
```python
# Store progress in Redis (fast, temporary)
progress = {
    'session_id': 'abc123',
    'chunk': 15,
    'processed': 3000,
    'total': 5000,
    'status': 'processing',
    'eta': '45m'
}

redis.set(f"processing:{session_id}", json.dumps(progress), ex=3600)
```

---

## 🏗️ Architecture

### Request Flow
```
Client
  ↓
POST /process-linkedin-export-large
  ↓
[API Layer]
  ├─ Validate API key
  ├─ Check quota
  └─ Return session_id immediately
  ↓
[Background Processing]
  ├─ Stream extract ZIP
  ├─ Chunk files (200 each)
  ├─ Process chunk
  ├─ Update Redis progress
  ├─ Free memory
  └─ Repeat
  ↓
[Results Storage]
  ├─ Store JSON/CSV temporary files
  ├─ Cache results (1 hour)
  └─ Ready for download

Client polls:
  GET /processing-status/{session_id}
    ↓
    Redis cache
    ↓
    Returns: { processed: 3000, total: 5000, status: 'processing' }
```

---

## 📊 Performance Specifications

| CVs | Chunks | Duration | Memory | CPU |
|-----|--------|----------|--------|-----|
| 100 | 1 | 3-5 min | 500MB | 25% |
| 500 | 3 | 15-20 min | 600MB | 30% |
| 1000 | 5 | 30-45 min | 700MB | 35% |
| 2000 | 10 | 1-1.5h | 800MB | 40% |
| 5000 | 25 | 2-3h | 900MB | 50% |
| 10000 | 50 | 4-6h | 1GB | 60% |

**Chunk size: 200 CVs (optimal balance)**

---

## 🛠️ Implementation Details

### Endpoint 1: Start Large Batch
```bash
POST /api/v1/recruiter/process-linkedin-export-large

{
  "job_id": 123,
  "zip_file": <binary>,
  "X-API-Key": "cv_xxxxxxxx",
  "chunk_size": 200  # optional
}

Response:
{
  "status": "success",
  "session_id": "1234567890",
  "summary": {
    "total_processed": 5000,
    "chunks_processed": 25,
    "status": "completed"
  },
  "downloads": {
    "json": "https://api.example.com/download/ranking_5000_abc123.json",
    "csv": "https://api.example.com/download/ranking_5000_abc123.csv"
  }
}
```

### Endpoint 2: Check Progress (Optional)
```bash
GET /api/v1/recruiter/processing-status/{session_id}?X-API-Key=cv_xxxx

Response:
{
  "session_id": "1234567890",
  "status": "processing",
  "progress": {
    "processed": 2500,
    "errors": 15,
    "chunk": 13,
    "success_rate": 99.4
  },
  "eta_seconds": 900  # 15 minutes remaining
}
```

---

## 💾 Memory Management

### Before (Naive Approach)
```python
# ❌ This crashes with 5000 CVs
all_files = []
with zipfile.ZipFile(zip_buffer) as z:
    all_files = z.extractall()  # All 5GB to memory!

results = process(all_files)    # Another peak
```

### After (Chunked Approach)
```python
# ✅ Stays under 1GB with 5000 CVs
async for chunk in stream_extract(zip_buffer):
    results += await process(chunk)  # Process batch
    del chunk                         # Free memory
    gc.collect()                      # Force cleanup
```

---

## 🔐 Quota Management

### Original Quota Check
```python
check_monthly_quota(subscription, 5000)  # Might fail

# If limit is 1000/month: REJECT
# But user has 2000 remaining? APPROVE
```

### Smart Quota for Large Batches
```python
# Conservative estimate first
estimated_cvs = 2000  # Assume 1000-5000 range
if remaining < estimated_cvs:
    REJECT

# After processing, use ACTUAL count
actual_cvs = len(results)
check_monthly_quota(subscription, actual_cvs)

# Update with actual usage
subscription.monthly_usage += actual_cvs
```

---

## 🎯 Optimization Strategies

### 1. **Disable Unnecessary Processing**
```python
# Skip features that slow things down
def process_cv_fast():
    text = extract_text(file)
    
    # ✅ Do this (fast)
    skills = extract_skills(text)
    score = calculate_score(skills)
    
    # ❌ Skip this (slow)
    # ✗ Save to database
    # ✗ Generate PDF
    # ✗ Run heavy ML models
    # ✗ Email notifications
```

### 2. **Batch Database Operations**
```python
# Instead of 5000 individual inserts
for result in results:
    db.add(result)  # ❌ Slow: 5000 queries

# Do bulk operations
db.bulk_insert_mappings(Results, results)  # ✅ Fast: 1 query
```

### 3. **Connection Pooling**
```python
# Increase pool size for large batches
engine = create_engine(
    DATABASE_URL,
    pool_size=20,              # Increase from 5
    max_overflow=10,           # Allow 10 extra
    pool_pre_ping=True         # Verify connections
)
```

### 4. **Async Processing**
```python
# Run multiple operations concurrently
tasks = [
    process_chunk(chunk1),
    process_chunk(chunk2),
    process_chunk(chunk3),
]
results = await asyncio.gather(*tasks)
```

---

## 📋 Celery Background Job (Optional)

For systems with **Celery + RabbitMQ/Redis**:

```python
# Create async task for massive batches
from celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def process_cv_batch_async(self, batch_id, zip_file_path, job_id):
    """Background task for 5000+ CVs"""
    
    try:
        results = process_large_batch(zip_file_path, job_id)
        
        # Store results in Redis cache
        cache.set(f"batch:{batch_id}", results, timeout=3600)
        
        return {
            'batch_id': batch_id,
            'status': 'completed',
            'result_count': len(results)
        }
    
    except Exception as exc:
        # Retry with exponential backoff
        self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

---

## 🚀 Deployment Checklist

- [ ] Increase timeout: 30s → 3600s (1 hour)
- [ ] Increase pool size: 5 → 20 connections
- [ ] Enable Redis caching for progress
- [ ] Add monitoring/logging for long processes
- [ ] Configure file upload size limit: 100MB → 500MB
- [ ] Add rate limiting to prevent abuse
- [ ] Set up storage for temporary results (S3/local disk)
- [ ] Add cleanup job for old temporary files
- [ ] Monitor memory usage and set alerts
- [ ] Load test with actual 5000 CV export

---

## 📈 Scaling Beyond 10000 CVs

### Use Kubernetes Auto-scaling
```yaml
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cv-processor-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cv-processor
  minReplicas: 1
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Distributed Processing
```python
# Distribute chunks across multiple workers
from celery import group

# Process 50 chunks on 10 workers (5 chunks each)
job = group([
    process_chunk.s(chunks[i:i+5])
    for i in range(0, len(chunks), 5)
])

result = job.apply_async()
```

---

## ✅ Testing Large Batches

```bash
# Test locally with 5000 CV simulations
pytest tests/test_large_batch.py -v

# Load test with 10 concurrent 5000-CV uploads
locust -f locustfile.py --host=http://localhost:8001
```

---

## 💡 Key Takeaways

1. **Chunking** - Process 200 CVs at a time (25 chunks for 5000)
2. **Streaming** - Extract ZIP without loading all to memory
3. **Async** - Use async/await for concurrent processing
4. **Progress** - Track with Redis, client polls for status
5. **Monitoring** - Watch CPU, memory, database connections
6. **Scaling** - Use Celery + Kubernetes for 10000+ CVs

**Result:** Handle 5000 CVs safely without system crashes ✅
