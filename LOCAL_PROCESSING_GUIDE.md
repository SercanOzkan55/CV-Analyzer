# Local Processing Mode - Zero Data Retention

This document describes the local processing mode for CV analysis, which ensures **zero data retention** on our servers while providing full ranking and analysis capabilities.

## Overview

Local processing mode allows organizations to:
- Process CVs without storing them on our servers
- Receive analysis results as downloadable files
- Maintain full control over their data
- Use API keys for authentication and quota management

## Architecture

### Key Components

1. **APISubscription Model** - API key management with monthly quotas
2. **Local Processing Endpoints** - Process CVs without database storage
3. **Temporary Downloads** - Secure file downloads with auto-expiration
4. **Frontend Local Mode** - UI for local processing workflow

### Data Flow

```
[Organization]
     ↓
1. Generate API Key (POST /subscriptions/generate-key)
     ↓
2. Upload CVs (POST /process-local with X-API-Key)
     ↓
3. Server processes CVs in memory
     ↓
4. Returns results + download URLs
     ↓
5. Organization downloads JSON/CSV files
     ↓
6. Files auto-delete after 1 hour
```

## API Endpoints

### Generate API Key

**Endpoint:** `POST /api/v1/recruiter/subscriptions/generate-key`

**Authentication:** JWT Bearer token

**Response:**
```json
{
  "api_key": "<generated-api-key>",
  "monthly_limit": 1000,
  "monthly_usage": 0,
  "expires_at": "2024-12-31T23:59:59Z",
  "message": "New API key generated successfully"
}
```

### Get Usage

**Endpoint:** `GET /api/v1/recruiter/subscriptions/usage`

**Authentication:** `X-API-Key` header

**Response:**
```json
{
  "monthly_limit": 1000,
  "monthly_usage": 45,
  "remaining": 955,
  "expires_at": "2024-12-31T23:59:59Z",
  "is_active": true
}
```

### Process CVs Locally

**Endpoint:** `POST /api/v1/recruiter/process-local`

**Authentication:** `X-API-Key` header

**Form Data:**
- `job_id` (int, required) - Target job position ID
- `files` (list[UploadFile], required) - PDF/TXT files

**Response:**
```json
{
  "results": [
    {
      "filename": "john_doe.pdf",
      "status": "success",
      "final_score": 85.5,
      "ats_score": 78.2,
      "skills_match": ["Python", "FastAPI"],
      "experience_match": 0.9,
      "education_match": 0.8,
      "processed_at": "2024-04-20T10:30:00Z",
      "job_id": 1
    }
  ],
  "summary": {
    "total_cvs": 1,
    "job_id": 1,
    "job_title": "Senior Python Developer",
    "processed_at": "2024-04-20T10:30:00Z"
  },
  "downloads": {
    "json": "/api/v1/downloads/json_abc123...",
    "csv": "/api/v1/downloads/csv_def456..."
  },
  "usage": {
    "monthly_limit": 1000,
    "monthly_usage": 46,
    "remaining": 954
  }
}
```

### Download Results

**Endpoint:** `GET /api/v1/downloads/{download_id}`

**Authentication:** None required (temporary URLs)

**Response:** File download with appropriate headers

## Security Features

### API Key Security
- Secure random generation using `secrets.token_urlsafe(32)`
- Prefix validation (`cv_` format)
- Database indexing for fast lookups
- Expiration dates for automatic deactivation

### Data Protection
- **Zero Storage:** CVs processed in memory, never saved to disk
- **No Logs:** CV content not logged anywhere
- **Temporary Files:** Download files expire in 1 hour
- **Memory Cleanup:** Automatic cleanup of processing artifacts

### Quota Management
- Monthly limits per organization
- Real-time usage tracking
- Automatic quota validation
- Admin reset capabilities

## Usage Limits

| Feature | Limit | Notes |
|---------|-------|-------|
| Files per request | 50 | Max batch size |
| File size | 5MB | Per file limit |
| Monthly quota | 1000 CVs | Default, configurable |
| Download expiry | 1 hour | Auto-cleanup |
| API key expiry | 1 year | Renewable |

## Frontend Integration

### Component Usage

```jsx
import BatchUploadLocalMode from './components/BatchUploadLocalMode'

function LocalProcessingPage() {
  const [apiKey, setApiKey] = useState('')
  const [jobs, setJobs] = useState([])

  return (
    <BatchUploadLocalMode
      apiKey={apiKey}
      jobs={jobs}
      onSuccess={(results) => {
        console.log('Processing complete:', results)
        // Handle results locally
      }}
      onError={(error) => {
        console.error('Processing failed:', error)
      }}
    />
  )
}
```

### API Key Management

```jsx
// Generate new API key
const generateKey = async () => {
  const response = await api.post('/recruiter/subscriptions/generate-key')
  setApiKey(response.data.api_key)
}

// Check usage
const checkUsage = async () => {
  const response = await api.get('/recruiter/subscriptions/usage', {
    headers: { 'X-API-Key': apiKey }
  })
  console.log(`Used: ${response.data.monthly_usage}/${response.data.monthly_limit}`)
}
```

## Database Schema

### APISubscription Table

```sql
CREATE TABLE api_subscriptions (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    api_key VARCHAR(255) UNIQUE NOT NULL,
    monthly_limit INTEGER DEFAULT 1000,
    monthly_usage INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    monthly_reset_day INTEGER DEFAULT 1
);

CREATE INDEX ix_api_subscriptions_api_key ON api_subscriptions(api_key);
CREATE INDEX ix_api_subscriptions_organization_id ON api_subscriptions(organization_id);
```

## Error Handling

### Common Errors

**Invalid API Key:**
```json
{
  "detail": "Invalid API key format"
}
```

**Expired Key:**
```json
{
  "detail": "API key expired"
}
```

**Quota Exceeded:**
```json
{
  "detail": "Monthly quota exceeded. Remaining: 0, Requested: 5"
}
```

**Job Not Found:**
```json
{
  "detail": "Job not found or you do not have permission to access it"
}
```

**File Processing Failed:**
```json
{
  "detail": "Processing failed: PDF extraction error"
}
```

## Testing

### Run Tests

```bash
pytest tests/test_local_processing.py -v -s
```

### Test Coverage

- ✅ API key generation and validation
- ✅ Quota management and limits
- ✅ File processing without DB storage
- ✅ Download URL generation and expiry
- ✅ Error handling and edge cases
- ✅ Multi-file batch processing

## Compliance

### GDPR Compliance
- **Data Minimization:** Only process data, never store
- **Purpose Limitation:** Processing only for analysis
- **Storage Limitation:** No persistent storage
- **Data Subject Rights:** No data to access/delete

### Security Best Practices
- API keys hashed in logs (if any)
- HTTPS only communication
- Rate limiting on all endpoints
- Input validation and sanitization
- Automatic cleanup of temporary files

## Performance

### Processing Speed
- **Small batches (<10 CVs):** < 30 seconds
- **Medium batches (10-50 CVs):** < 2 minutes
- **Large batches:** Depends on CV complexity

### Memory Usage
- **Per CV:** ~50-200MB (PDF processing)
- **Concurrent requests:** Limited by server capacity
- **Cleanup:** Automatic garbage collection

### Scalability
- Horizontal scaling with load balancer
- Redis for temporary file storage (production)
- Background processing with Celery (optional)

## Monitoring

### Key Metrics
- API key usage per organization
- Processing success/failure rates
- File size and processing time distributions
- Download completion rates
- Temporary file cleanup effectiveness

### Alerts
- High error rates per organization
- Unusual file size patterns
- API key abuse attempts
- Storage capacity warnings

## Future Enhancements

### Phase 2: Advanced Features
- [ ] Custom ranking models per organization
- [ ] Bulk job processing
- [ ] Real-time processing status
- [ ] Integration with ATS systems
- [ ] Custom export formats

### Phase 3: Enterprise Features
- [ ] SAML/SSO integration
- [ ] Audit logs (metadata only)
- [ ] Custom quota tiers
- [ ] White-label options
- [ ] API rate limiting per key

## Troubleshooting

### Common Issues

**API Key Not Working:**
- Verify key format starts with `cv_`
- Check expiration date
- Confirm organization membership

**Processing Fails:**
- Check file format (PDF/TXT only)
- Verify file size < 5MB
- Ensure sufficient text content (>50 chars)

**Downloads Not Working:**
- Check URL expiry (1 hour limit)
- Verify network connectivity
- Try refreshing the page

**Quota Issues:**
- Check monthly usage vs limit
- Contact support for quota increase
- Wait for monthly reset

## Support

For issues with local processing mode:
1. Check this documentation
2. Run the test suite
3. Check server logs (anonymized)
4. Contact enterprise support

## Migration from Cloud Mode

Organizations can migrate from cloud to local mode:

1. Generate API key
2. Update client applications
3. Test with small batches
4. Migrate production traffic
5. Deactivate old cloud usage

---

**This feature provides enterprise-grade privacy while maintaining full functionality.**
