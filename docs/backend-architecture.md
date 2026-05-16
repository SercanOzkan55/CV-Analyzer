# Backend Architecture And Modularization Guide

This document defines the backend direction for CV Analyzer. It exists because the application has historically accumulated too much code in `main.py`. New work must reduce that pressure, not add to it.

## Non-Negotiable Rule

`main.py` is not a feature implementation file.

It should become a composition root:

```text
main.py
  create FastAPI app
  configure middleware
  configure metrics
  register exception handlers
  include routers
  expose health endpoints
  run startup/shutdown wiring
```

Everything else should live in domain modules.

## Target Directory Ownership

```text
routes/
  analyze.py
  billing.py
  cv_builder.py
  dashboard.py
  data_privacy.py
  feedback.py
  recruiter.py
  rewrite.py
  sharing.py
  user.py
  webhook.py

schemas/
  analyze.py
  billing.py
  cv_builder.py
  dashboard.py
  recruiter.py
  rewrite.py
  user.py

services/
  upload_service.py
  parsing_service.py
  analyze_service.py
  dashboard_service.py
  recruiter_service.py
  rewrite_service.py
  billing_service.py
  sharing_service.py
  privacy_service.py

core/
  config.py
  dependencies.py
  errors.py
  logging.py
  security.py

middleware/
  abuse_protection.py
  security_headers.py
  request_context.py
```

## Layer Responsibilities

### `routes/`

Routes are thin HTTP adapters.

They may:
- Define `APIRouter`.
- Attach dependencies and rate limits.
- Accept request schemas.
- Call services.
- Convert known domain errors into `HTTPException`.
- Return response schemas.

They may not:
- Parse PDFs/DOCX/TXT directly.
- Call OpenAI/Stripe/Supabase SDKs directly unless the route is an auth/webhook adapter and the behavior is tiny.
- Contain multi-step business workflows.
- Define long helper functions.
- Store user data in local files.
- Duplicate quota, audit, or authorization logic.

### `schemas/`

Schemas define API contracts.

Rules:
- Every non-trivial endpoint should have request and response models.
- Keep schemas grouped by feature.
- Keep models stable; changing a response shape needs frontend review.
- Do not place new Pydantic models in `main.py`.

### `services/`

Services own behavior and should be unit-testable without FastAPI.

Examples:
- `upload_service.extract_upload_text(...)`
- `parsing_service.parse_cv_sections(...)`
- `recruiter_service.rank_candidates(...)`
- `dashboard_service.get_usage_summary(...)`
- `rewrite_service.generate_cover_letter(...)`
- `billing_service.handle_stripe_event(...)`

Services may depend on database sessions, provider clients, and environment settings, but those dependencies should be explicit.

### `core/`

Core modules contain cross-cutting configuration and dependencies:
- Settings/env parsing.
- CORS policy.
- Security helpers.
- Shared dependency factories.
- Error types.
- Logger setup.

### `middleware/`

Middleware modules contain request/response cross-cutting behavior:
- Security headers.
- Abuse protection.
- Request IDs.
- Cache headers.

## Router Pattern

Use this shape for new routers:

```python
from fastapi import APIRouter, Depends

from database import get_db
from auth import verify_supabase_jwt
from schemas.rewrite import RewriteRequest, RewriteResponse
from services.rewrite_service import rewrite_cv

router = APIRouter(prefix="/api/v1/rewrite", tags=["rewrite"])


@router.post("/cv", response_model=RewriteResponse)
def rewrite_cv_endpoint(
    body: RewriteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    result = rewrite_cv(db=db, user=user, request=body)
    return RewriteResponse(result=result.text, plan=result.plan)
```

Then register it in `main.py`:

```python
from routes.rewrite import router as rewrite_router

app.include_router(rewrite_router)
```

`main.py` should gain only the import and `include_router` line.

## Extraction Strategy For Existing `main.py`

Do not attempt one huge refactor. Extract in safe slices.

### Slice 1: Upload And Parsing

Move:
- `_scan_upload_for_viruses`
- `_extract_pdf_text`
- `_extract_docx_text`
- `_extract_plain_text`
- `_extract_upload_text`
- `_resolve_job_description_text`

Into:
- `services/upload_service.py`
- `services/parsing_service.py`

Tests:
- PDF success.
- DOCX success.
- TXT success.
- Unsupported file rejection.
- Too-large rejection.
- Empty extraction rejection.
- Multi-page/multi-column regression.
- Certification/experience section separation regression.

### Slice 2: Rewrite/AI Endpoints

Move route functions into:
- `routes/rewrite.py`
- `schemas/rewrite.py`

Keep provider logic in:
- `services/rewrite_service.py`

Tests:
- Mock provider fallback.
- OpenAI provider selection when `OPENAI_API_KEY` exists.
- Empty provider response handling.
- Fact-preservation prompt rules.
- Plan entitlement behavior.

### Slice 3: Dashboard/User Utilities

Move dashboard-style endpoints into:
- `routes/dashboard.py`
- `routes/user.py`
- `schemas/dashboard.py`
- `services/dashboard_service.py`

Endpoints include:
- usage history
- usage streak
- favorites
- insights
- JD templates
- history export
- notes
- reminders
- data summary/export/delete

Production data should move to database tables with Alembic migrations. Local JSON fallback must be dev-only.

### Slice 4: Recruiter

Move recruiter endpoints into:
- `routes/recruiter.py`
- `schemas/recruiter.py`
- `services/recruiter_service.py`

Important:
- Organization scoping must remain enforced.
- Recruiter role checks must remain explicit.
- Batch upload must reuse the same upload parser as analyze/auto-fix.
- Ranking should avoid recomputing JD embeddings per candidate.

### Slice 5: Billing And Webhooks

Move:
- Stripe checkout/portal/admin plan endpoints to `routes/billing.py`.
- Stripe webhook endpoint to `routes/webhook.py`.
- Signature verification and event handling to `services/billing_service.py`.

Tests:
- Valid Stripe signature.
- Missing signature.
- Expired timestamp.
- Wrong signature.
- Idempotency behavior.
- Plan update behavior.

## Feature Implementation Checklist

For every backend feature, answer these before editing:

1. What domain owns this feature?
2. Which route module should expose it?
3. Which schema module defines the contract?
4. Which service owns the behavior?
5. Does it need a database model or migration?
6. Which frontend API call consumes it?
7. Which tests prove it is general, secure, and compatible?
8. Does this require touching `main.py`, or only registering a router?

If the answer to item 8 is "touching `main.py` with implementation code", redesign the change.

## Generalization Requirements

CV Analyzer must not be built for a single resume style, language, country, or customer.

Parsing and scoring should handle:
- Turkish, English, German, Spanish, French, Arabic and unknown/neutral text.
- Multi-column PDFs.
- Multi-page PDFs.
- DOCX tables.
- TXT exports.
- Non-standard section headings.
- Different orderings of education, experience, certifications, skills, projects, awards, and languages.

Add regression tests whenever a specific CV sample reveals a parsing issue.

## API Stability Requirements

The frontend currently depends on many route contracts. Before changing backend shape:

```bash
rg "api\\.|fetch\\(|axios|/api/v1" frontend/src
rg "@app\\.|APIRouter|include_router" .
```

Route changes should preserve:
- URL path.
- HTTP method.
- Auth behavior.
- JSON key names.
- Empty state shape.
- Error status class.

Breaking changes must be versioned or coordinated with frontend updates in the same change.

## Security Requirements

Use explicit, tested security behavior.

Must preserve:
- JWT validation.
- User ownership checks.
- Organization scoping.
- Recruiter role checks.
- Upload validation.
- File size limits.
- CORS production restrictions.
- Stripe webhook signature verification.
- Rate limits and abuse protection.

Security fixes are allowed to be slightly larger than normal changes, but they still must land in the correct module.

## Testing Matrix

Minimum backend verification:

```bash
python -m py_compile main.py services/rewrite_service.py
python -m pytest
```

Targeted tests for modular work:

```bash
python -m pytest tests/test_api.py
python -m pytest tests/test_recruiter_endpoints.py
python -m pytest tests/test_cv_autofix_parser_generalization.py
python -m pytest tests/test_security_file_upload.py tests/test_security_file_type.py
```

Minimum frontend verification:

```bash
cd frontend
npm test
npm run build
```

## Definition Of Done

A backend feature is done only when:
- No new implementation logic was added to `main.py`.
- Route, schema, service, and tests are in domain-owned files.
- Existing route contracts still work.
- Unsupported inputs fail clearly.
- Empty states do not produce 500s.
- Auth and organization scoping are tested.
- The final response lists remaining migration or refactor risk.
