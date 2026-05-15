/**
 * Documentation and best practices guide for Recruiter API improvements
 * 
 * This file documents the improvements made to ensure better error handling,
 * validation, and consistency across recruiter endpoints.
 */

# Recruiter API Improvements Guide

## Backend Improvements (routes/recruiter.py)

### 1. Response Format Standardization

**Problem**: Endpoints returned inconsistent response structures
- Some: `{candidates: []}`
- Some: `{results: []}`
- Some: `{jobs: []}`

**Solution**: Created unified Pydantic response models

```python
# Created response models:
class CandidatesResponse(BaseModel):
    candidates: list[CandidatePreview]
    total: int | None = None

class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int | None = None
    query: str | None = None

class JobsResponse(BaseModel):
    jobs: list[JobResponse]
    total: int | None = None
```

**Implementation**: All endpoints now return consistent `{data_array, total}` format

### 2. Input Validation

**Improvements**:
- GET /candidates: `limit` parameter bounded to 1-100 (Query validator)
- GET /search: `q` parameter 1-500 chars with min_length/max_length
- POST /batch-upload: File type validation, size limits per file
- POST /reminders: Date validation (must be future), title length caps

**Example**:
```python
@router.get("/candidates")
def recruiter_candidates(
    limit: int = Query(20, ge=1, le=100),  # Bounds enforced
    ...
) -> CandidatesResponse:
```

### 3. Error Handling

**Improvements**:
- Standardized HTTP status codes:
  - 400: Invalid input/validation error
  - 404: Resource not found
  - 429: Rate limit / insufficient credits
  - 500: Server/provider error
- Detailed error messages with context
- Structured logging for debugging

**Before**:
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Search error: {e}")
```

**After**:
```python
except HTTPException:
    raise  # Re-raise known errors
except Exception as e:
    logger.error("search_unexpected_error q=%s org_id=%s error=%s", query, org_id, e)
    raise HTTPException(
        status_code=500,
        detail="An unexpected error occurred during search"
    )
```

### 4. File Upload Validation

**New validations for POST /batch-upload**:
- ✅ File type checking (PDF/TXT/DOCX only)
- ✅ File size validation (max 5MB per file)
- ✅ Minimum file count and maximum (1-50)
- ✅ Extracted text validation (min 50 chars)
- ✅ Credit deduction with rollback on failure
- ✅ Detailed error messages per failure point

### 5. Email Sending Improvements

**New error handling for POST /send-email**:
- ✅ Email validation before sending
- ✅ Try-catch around template rendering
- ✅ Try-catch around email send
- ✅ Logging of all attempts and failures
- ✅ Helpful error messages for configuration issues

### 6. Reminder Improvements

**New validation for POST /reminders**:
- ✅ Title required and length-capped (500 chars)
- ✅ Event date must be in future
- ✅ Email validation
- ✅ Try-catch around database operations
- ✅ Transaction rollback on failure

### 7. Docstrings and Type Hints

**Added to all endpoints**:
- Clear description of endpoint purpose
- Parameter documentation
- Return value documentation
- Possible error codes and causes
- Type hints on return values

**Example**:
```python
@router.post("/send-email")
def recruiter_send_email(...) -> dict:
    """
    Send email to candidate using email template.
    
    **Parameters:**
    - `action_id` or `candidate_email`: Email recipient (one required)
    - `template_id`: Email template to use
    
    **Returns:**
    - Confirmation of sent email with timestamp
    
    **Raises:**
    - 400: Invalid email or missing fields
    - 404: Template or action not found
    - 500: Email sending failed
    """
```

## Frontend Improvements (frontend/src/utils/recruiterErrorHandling.js)

### New Utility Functions

1. **extractApiData(data, key, defaultVal)**
   - Safely extract nested data from inconsistent API responses
   - Handles arrays, objects, and missing data

2. **formatErrorMessage(error, defaultMsg)**
   - Format various error types for user display
   - Handles Response objects, Error objects, and strings

3. **safeApiCall(apiFn, operationName, options)**
   - Wrapper for API calls with proper error handling
   - Includes performance timing and logging
   - Returns `{success, data, error}` object

4. **validateEmail(email)**
   - Email format validation
   - Handles length limits
   - Returns `{valid, error}`

5. **validateCVText(cvText, minChars)**
   - CV text validation
   - Minimum and maximum length checks
   - Returns `{valid, error}`

6. **validateFileUploads(files, options)**
   - Multi-file validation
   - File type, size, and count checks
   - Returns `{valid, error, validFiles}`

7. **Error Detection Helpers**
   - `isRateLimitError(error)`: Detects rate limit errors
   - `isValidationError(error)`: Detects validation errors
   - `isPermissionError(error)`: Detects permission errors

### Usage Example

```javascript
import { validateEmail, validateFileUploads, safeApiCall, extractApiData } from '@/utils/recruiterErrorHandling'

// Validate before API call
const emailValidation = validateEmail(email)
if (!emailValidation.valid) {
  toast.error(emailValidation.error)
  return
}

// Safe API call with error handling
const { success, data, error } = await safeApiCall(
  () => recruiterSendEmail(token, payload),
  'Send Email',
  { verbose: true }
)

if (!success) {
  toast.error(error || 'Failed to send email')
  return
}

// Safely extract data from response
const candidates = extractApiData(data, 'candidates', [])
const total = data?.total || 0
```

## Test Coverage (tests/test_recruiter_improvements.py)

### New Test Scenarios

1. **Response Format Tests**
   - ✅ Verify all endpoints return `total` field
   - ✅ Verify response model consistency

2. **Input Validation Tests**
   - ✅ Limit bounds enforcement (1-100)
   - ✅ Query length validation
   - ✅ File type and size validation
   - ✅ Email format validation

3. **Error Handling Tests**
   - ✅ Missing required parameters
   - ✅ Invalid data formats
   - ✅ Resource not found scenarios
   - ✅ Permission denied scenarios

4. **Edge Cases**
   - ✅ Empty files rejection
   - ✅ Oversized files rejection
   - ✅ Too many files rejection
   - ✅ Past date rejection (reminders)

## API Response Examples

### Before (Inconsistent)
```json
GET /api/v1/recruiter/candidates
{
  "candidates": [...]  // No total field
}

GET /api/v1/recruiter/search
{
  "results": [...]  // No total or query field
}
```

### After (Consistent)
```json
GET /api/v1/recruiter/candidates
{
  "candidates": [...],
  "total": 5
}

GET /api/v1/recruiter/search?q=python
{
  "results": [...],
  "total": 3,
  "query": "python"
}

POST /api/v1/recruiter/send-email
{
  "sent": true,
  "to": "candidate@example.com",
  "subject": "Your Application",
  "timestamp": "2026-04-20T12:34:56.789123"
}
```

## Migration Guide for Frontend

### Step 1: Update API response handling

**Before**:
```javascript
const jobs = data?.jobs || []  // May fail if format changes
```

**After**:
```javascript
const jobs = extractApiData(data, 'jobs', [])  // Handles variations
```

### Step 2: Add input validation

**Before**:
```javascript
handleSendEmail() {
  // Direct API call, no pre-validation
  recruiterSendEmail(token, payload)
}
```

**After**:
```javascript
handleSendEmail() {
  const validation = validateEmail(email)
  if (!validation.valid) {
    toast.error(validation.error)
    return
  }
  
  const { success, error } = await safeApiCall(
    () => recruiterSendEmail(token, payload),
    'Send Email'
  )
  if (!success) toast.error(error)
}
```

### Step 3: Update error handling

**Before**:
```javascript
.catch(() => { /* ignore */ })
```

**After**:
```javascript
.catch(err => {
  const msg = extractDetailFromError(err)
  if (isRateLimitError(err)) {
    toast.warn('Too many requests. Please wait a moment.')
  } else if (isValidationError(err)) {
    toast.error('Invalid input: ' + msg)
  } else {
    toast.error(msg)
  }
})
```

## Status and Next Steps

### ✅ Completed
- Backend response format standardization
- Input validation on all endpoints
- Error handling improvements
- Docstrings and type hints
- Comprehensive test coverage
- Frontend error handling utilities

### ⏳ Recommended Next Steps
1. Update RecruiterDashboardPage.jsx to use new error handling utilities
2. Add retry logic for transient errors
3. Implement optimistic UI updates
4. Add analytics tracking for user-facing errors
5. Create user-facing error documentation

## Performance Impact

- ✅ No negative impact (validation happens early)
- ✅ Better error messages reduce user confusion and support tickets
- ✅ Structured logging improves debugging time
- ✅ Type hints improve IDE autocomplete and catch bugs earlier
