# Recruiter Batch Upload & WebSocket Progress Tracking

This document describes the batch CV upload feature with real-time WebSocket progress tracking for the Recruiter API.

## Overview

The batch upload feature allows recruiters to:
- Upload multiple CVs at once (up to 50 files per batch)
- Support PDF, TXT, and DOCX formats
- Track upload progress in real-time via WebSocket
- Automatically rank candidates against a job description

## Architecture

### Components

1. **Backend Endpoints**
   - `POST /api/v1/recruiter/dashboard/batch-upload` - Upload CVs
   - `WS /api/v1/recruiter/ws/batch-upload/{task_id}` - Real-time progress

2. **Frontend Components**
   - `BatchUploadModal.jsx` - Upload UI with file selection
   - `BatchUploadProgress.jsx` - Real-time progress tracker
   - `useWebSocketProgress.js` - WebSocket connection hook

3. **Task Processing**
   - Celery task `batch_recruiter_task` processes CVs asynchronously
   - AsyncResult polling via WebSocket for progress updates

## Usage

### Backend: Upload CVs

**Endpoint:** `POST /api/v1/recruiter/dashboard/batch-upload`

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "job_id=1" \
  -F "files=@cv1.pdf" \
  -F "files=@cv2.pdf" \
  http://localhost:8001/api/v1/recruiter/dashboard/batch-upload
```

**Form Parameters:**
- `job_id` (int, required) - Target job position ID
- `files` (list[UploadFile], required) - PDF/TXT/DOCX files

**Response:**
```json
{
  "task_id": "abc123def456",
  "count": 2,
  "message": "Batch processing started for 2 CVs",
  "job_id": 1
}
```

**Constraints:**
- Max 50 files per request
- Max 5MB per file
- Supported formats: PDF, TXT, DOCX
- Minimum 50 characters of extractable text per file
- Requires sufficient organization credits

**Error Responses:**
- `400` - Invalid files, format error, or insufficient text
- `404` - Job not found
- `429` - Insufficient credits
- `500` - Internal processing error

### Backend: Track Progress via WebSocket

**Endpoint:** `WS /api/v1/recruiter/ws/batch-upload/{task_id}`

**Example (JavaScript):**
```javascript
const taskId = 'abc123def456'; // from upload response
const ws = new WebSocket(
  `ws://localhost:8001/api/v1/recruiter/ws/batch-upload/${taskId}`,
  [],
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', {
    status: data.status,        // PENDING, PROGRESS, SUCCESS, FAILURE
    processed: data.processed,   // Number of CVs processed
    total: data.total,           // Total CVs in batch
    percent: data.percent,       // 0-100 percentage complete
    currentFile: data.current_file,  // Currently processing file
    error: data.error            // Error message if failed
  });
};

ws.onerror = (event) => {
  console.error('WebSocket error:', event);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

**Progress Message Structure:**
```json
{
  "status": "PROGRESS",
  "processed": 5,
  "total": 10,
  "percent": 50.0,
  "current_file": "cv_john_doe.pdf"
}
```

**Status Values:**
- `PENDING` - Task queued, not started
- `PROGRESS` - CVs being processed
- `SUCCESS` - All CVs processed successfully
- `FAILURE` - Error during processing

### Frontend: React Integration

**Component Usage:**
```jsx
import BatchUploadModal from './components/BatchUploadModal'
import { useState } from 'react'

function RecruiterDashboard() {
  const [showUpload, setShowUpload] = useState(false)
  const [jobs, setJobs] = useState([...]) // Fetch from API

  const handleUploadSuccess = (progress) => {
    console.log('Upload complete:', progress)
    // Refresh candidates list, show success message, etc.
  }

  return (
    <div>
      <button onClick={() => setShowUpload(true)}>
        Upload CVs
      </button>
      
      <BatchUploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onSuccess={handleUploadSuccess}
        jobs={jobs}
      />
    </div>
  )
}
```

**WebSocket Hook Usage:**
```jsx
import { useWebSocketProgress } from './hooks/useWebSocketProgress'

function ProgressTracker({ taskId }) {
  const { progress, status, error, isConnected } = 
    useWebSocketProgress(taskId)

  if (!progress) return <p>Connecting...</p>

  return (
    <div>
      <p>Status: {status}</p>
      <p>Progress: {progress.processed}/{progress.total} ({progress.percent}%)</p>
      {error && <p className="error">Error: {error}</p>}
      {!isConnected && <p className="warning">Connection lost</p>}
    </div>
  )
}
```

## Features

### File Validation
- PDF validation via magic number check
- Text extraction from PDF/TXT/DOCX
- Minimum text length requirement (50 characters)
- Maximum file size limit (5MB per file)

### Progress Tracking
- Real-time WebSocket updates every 1 second
- Current file name tracking
- Percentage calculation
- Error message propagation

### Error Handling
- Detailed error messages for each validation failure
- Automatic credit rollback on failure
- Graceful WebSocket disconnection
- Reconnection guidance in UI

### Rate Limiting
- 60 requests/minute per endpoint
- Rate limit headers in responses
- 429 Too Many Requests error when exceeded

### Organization Isolation
- Recruiter can only access own organization's jobs
- Cross-organization access prevented via org_id check
- Credits tracked per organization

## Testing

### Manual Testing via REST Client

See `test_recruiter_api.http` for REST client examples.

**Test Flow:**
1. Authenticate and get JWT token
2. List available jobs
3. Upload CV batch to specific job
4. Connect WebSocket to task ID
5. Monitor progress updates
6. Verify completion

### Automated Tests

Run integration tests:
```bash
pytest tests/test_batch_upload_integration.py -v -s
```

Key test scenarios:
- ✅ Successful batch upload
- ✅ Multiple file upload
- ✅ File limit validation (50 files max)
- ✅ Format validation
- ✅ Empty file rejection
- ✅ Insufficient credits
- ✅ WebSocket progress tracking
- ✅ Cross-organization isolation
- ✅ Rate limiting
- ✅ Export candidates (CSV/JSON)
- ✅ Export rankings (CSV/JSON)

## Performance Characteristics

- **Upload Latency:** < 5 seconds for 50 files (depends on file size)
- **Processing Speed:** 10-50 CVs per minute (depends on CV length and model)
- **WebSocket Updates:** Every 1 second during processing
- **Memory Usage:** Streaming file uploads (no buffering)

## Database Schema Changes

### Migration: 004_recruiter_constraints.py

Added PostgreSQL CHECK constraints:
- `check_future_date` - Reminder dates must be in future
- `check_email_format` - Valid email format validation
- `check_title_length` - Job title 5-200 characters
- `check_description_length` - Description 20-5000 characters

### Extended Candidate Model

New columns:
- `name` (String) - Candidate name from CV
- `email` (String) - Candidate email address
- `phone` (String) - Candidate phone number

## Error Scenarios

### Upload Fails - Insufficient Credits
```json
{
  "detail": "Insufficient credits. You need 5 CVs analyzed but only have 2 credits remaining this month."
}
```

### Job Not Found
```json
{
  "detail": "Job not found or you do not have permission to access it"
}
```

### WebSocket Connection Lost
```
[WebSocket] Connection lost
Attempting to reconnect...
```

## Future Enhancements

- [ ] Bulk import from LinkedIn
- [ ] Resume parsing with OCR
- [ ] Custom ranking criteria
- [ ] Automated email templates
- [ ] Scheduled batch processing
- [ ] Progress analytics dashboard
- [ ] CSV import with validation
- [ ] Candidate deduplication

## Troubleshooting

### WebSocket Connection Fails
- Verify task_id is correct
- Check authentication token is valid
- Ensure WebSocket port (8001) is accessible
- Check firewall/proxy settings

### Upload Progress Stuck at 0%
- Check Celery task queue status
- Verify Redis connection
- Check application logs for processing errors
- Try uploading with fewer files

### Files Rejected as Invalid Format
- Ensure files are actual PDF/TXT/DOCX (check magic numbers)
- Verify file extensions match content type
- For PDFs, ensure they contain text (not image-only scans)
- Use `file` command to verify format: `file cv.pdf`

## API Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/candidates` | 60 | 1 minute |
| `/search` | 60 | 1 minute |
| `/jobs` | 60 | 1 minute |
| `/send-email-bulk` | 30 | 1 minute |
| `/dashboard/batch-upload` | 20 | 1 minute |

Response headers include:
- `X-RateLimit-Limit` - Total requests allowed
- `X-RateLimit-Remaining` - Requests remaining
- `X-RateLimit-Reset` - Reset timestamp (Unix)

## Configuration

### Environment Variables

```bash
# Celery task configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File upload settings
MAX_FILE_SIZE=5242880  # 5MB
MAX_BATCH_SIZE=50
MIN_TEXT_LENGTH=50

# WebSocket settings
WS_POLL_INTERVAL=1  # seconds
WS_TIMEOUT=300  # 5 minutes
```

### Alembic Migration

Run migration to add database constraints:
```bash
alembic upgrade head
```

## Security Considerations

- All endpoints require JWT authentication
- Organization isolation prevents cross-org data access
- File uploads scanned for valid format/content
- WebSocket connections require valid JWT token
- Credit system prevents abuse via upload limits
- Request rate limiting prevents DDoS
- Sensitive data (tokens) not logged

## Support & Documentation

- API Documentation: `/docs` (Swagger UI)
- WebSocket Examples: See this document
- Test Examples: `tests/test_batch_upload_integration.py`
- REST Client: `test_recruiter_api.http`
