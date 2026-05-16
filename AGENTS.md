# Repository Agent Instructions

This repository is a production CV intelligence SaaS application. Treat every change as production-facing unless the user explicitly says it is throwaway work.

## Prime Directive

Do not grow `main.py`.

`main.py` is a legacy composition file. It currently contains too much routing and business logic, so new work must move the codebase toward modular ownership instead of adding more logic there.

Allowed edits in `main.py`:
- FastAPI app construction and global middleware registration.
- `include_router(...)` registration for routers.
- Global exception handlers, CORS setup, metrics setup, health checks, and lifespan/bootstrap wiring.
- Small compatibility shims only when they are immediately paired with extraction into a domain module.
- Emergency one-line fixes when the system is broken and no safer module exists yet. These must be followed by a cleanup task in the same response.

Disallowed edits in `main.py`:
- New API endpoint implementations.
- New Pydantic request/response schemas.
- New business logic helpers.
- New file parsing logic.
- New billing, recruiter, rewrite, CV builder, dashboard, favorites, reminders, notes, or analytics logic.
- New local persistence structures.
- Large copy-pasted blocks from experiments or previous backups.

If a task appears to require adding more than a few lines to `main.py`, stop and create/extract the correct module first.

## Backend Architecture Rules

Use this target structure for all new backend work:

```text
routes/
  analyze.py
  billing.py
  cv_builder.py
  data_privacy.py
  dashboard.py
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
  parsing_service.py
  upload_service.py
  rewrite_service.py
  recruiter_service.py
  dashboard_service.py
  billing_service.py
  sharing_service.py

core/
  config.py
  logging.py
  security.py
  dependencies.py
  errors.py

middleware/
  security_headers.py
  abuse_protection.py
  request_context.py
```

### Route Modules

Route modules should contain thin HTTP adapters only:
- Parse request data through Pydantic schemas.
- Call service functions.
- Translate domain errors into `HTTPException`.
- Apply dependencies and rate limits.
- Return response schemas or plain serializable DTOs.

Route modules should not:
- Implement parsing algorithms.
- Query several tables directly unless the endpoint is genuinely trivial.
- Build prompts inline.
- Contain provider SDK calls.
- Store data in ad hoc JSON files.
- Duplicate quota, auth, or audit patterns.

### Service Modules

Service modules own behavior:
- CV/JD text extraction and validation.
- AI provider calls and fallback behavior.
- Recruiter ranking and batch analysis orchestration.
- Dashboard aggregation.
- Billing and entitlement decisions.
- Sharing, favorites, reminders, and notes.

Services should be deterministic where possible, typed, and directly unit-testable without FastAPI.

### Schema Modules

All new request/response models belong under `schemas/`.

Rules:
- Use explicit models for public API contracts.
- Keep domain schemas grouped by feature.
- Do not define new Pydantic models in `main.py`.
- Include both request and response models for endpoints that the frontend consumes.

### Persistence Rules

Production feature data belongs in the database with migrations.

Allowed local files:
- Test fixtures.
- Developer-only temporary data under `_dev_scratch/`.
- Explicit local demo mode files that cannot be used in production.

Disallowed:
- Silent production feature stores in JSONL/JSON files.
- User data stores outside the database unless the feature is documented as local-only.

If a quick local fallback is needed, guard it with environment checks and document the migration path in the final response.

## API Compatibility Rules

Before adding or changing an endpoint:
- Search frontend calls in `frontend/src/api.js` and route usage in `frontend/src/pages` and `frontend/src/components`.
- Search existing backend route paths with `rg "@app\\.|APIRouter|include_router"`.
- Prefer implementing missing backend contracts in a domain router instead of changing frontend behavior blindly.
- Preserve existing request/response shapes unless there is a strong reason to version them.
- Return stable empty states instead of 500s for empty user data.
- Use `401/403` for auth/plan failures, `400/422` for invalid input, and `503` for unavailable providers.

All new endpoints need tests:
- Unit tests for service behavior.
- API tests for route contract and auth behavior.
- Regression tests for any frontend/backend contract mismatch being fixed.

## CV Parsing And Upload Rules

The product must be general-purpose.

Do not implement parsing logic that only works for:
- One language.
- One country.
- One CV template.
- One section heading.
- One visual layout.
- One specific customer or sample file.

Supported upload behavior must stay consistent across:
- Analyze.
- Auto-fix.
- Recruiter batch rank.
- Recruiter dashboard batch upload.
- Job description uploads.

Supported formats:
- PDF.
- DOCX.
- TXT.

Security rules:
- Enforce file size limits before parsing.
- Validate file signatures when possible.
- Keep virus scanning hooks intact.
- Do not trust file names for storage paths.
- Reject unsupported executable/archive-like uploads.

Parsing quality rules:
- Multi-page and multi-column CVs must not merge unrelated sections.
- Certifications must not leak into experience.
- Education, experience, projects, skills, certifications, languages, publications, and awards must remain distinct where possible.
- Section aliases must be language-general and tested.
- Empty extraction should return a clear validation error, not a misleading score.

## AI And Cost Rules

The user accepts slightly higher cost when it materially improves result quality.

Use AI where it improves correctness:
- CV rewrite.
- Cover letter generation.
- Interview question generation.
- Keyword optimization.
- Ambiguous section normalization.

Do not use AI where deterministic logic is better:
- File type validation.
- Auth.
- Entitlement checks.
- Basic quota calculation.
- Simple CRUD.
- CSV export.

AI calls must:
- Preserve source facts.
- Never invent employers, dates, degrees, certifications, skills, metrics, or contact information.
- Match the requested language.
- Use configurable provider/model settings.
- Have deterministic fallback behavior for tests and local development.
- Avoid logging prompts that contain user CV content.

## Frontend Architecture Rules

Frontend behavior should follow existing React/Vite patterns.

Rules:
- Keep API calls centralized in `frontend/src/api.js`.
- Keep shared upload type rules in shared utilities, not duplicated across pages.
- Keep status colors and score colors in shared utilities/tokens.
- Prefer shared components before page-specific styling.
- Preserve restored public pages and product pages: Blog, Cover Letter, Career Studio, Compare, CV Builder, Recruiter, Dashboard, Settings, Profile.
- Do not overcrowd the top navbar; use grouped menus or secondary navigation for less frequent tools.
- Never remove an existing user-facing feature to simplify layout unless the user explicitly approves.

## UI Quality Rules

The app should feel professional, modern, readable, and production-grade.

Prefer:
- Consistent spacing.
- Soft light surfaces.
- Clear typography hierarchy.
- Accessible contrast.
- Visible focus states.
- Predictable empty/loading/error states.
- Subtle motion that respects `prefers-reduced-motion`.

Avoid:
- One-off hard-coded colors.
- Overuse of gradients, shadows, blur, or decorative effects.
- Marketing-style hero layouts inside authenticated product screens.
- Nested cards.
- Text overflow in buttons, cards, nav items, or filters.
- Large visual rewrites when a shared token/component fix would solve it.

## Security Rules

Security-sensitive code must be explicit and tested.

Areas requiring extra care:
- Supabase JWT verification.
- Role and organization scoping.
- Recruiter candidate access.
- Stripe webhook verification.
- File upload validation.
- CORS.
- Rate limiting and abuse prevention.
- User data export/delete.

Do not:
- Print secrets.
- Store credentials in files.
- Disable auth for convenience.
- Add fake auth in production paths.
- Broaden CORS in production.
- Swallow security errors into successful responses.

## Testing And Verification

Run the most relevant checks for every change.

Backend:
```bash
python -m py_compile main.py services/rewrite_service.py
python -m pytest
```

Frontend:
```bash
cd frontend
npm test
npm run build
```

When type checking is available:
```bash
npx tsc --noEmit
```

If a command is unavailable because dependencies are not installed or network is blocked, say that clearly and run the closest local check.

For browser QA:
- Start backend on `127.0.0.1:8001`.
- Build or serve frontend on `127.0.0.1:5173`.
- Check public pages and authenticated pages when a safe test login exists.
- Check desktop and mobile widths for changed UI.
- Check console errors and network failures.

## Required Change Checklist

Before editing:
- Identify the feature domain.
- Identify the correct route, schema, service, model, and test files.
- Confirm whether `main.py` needs only router registration.
- Search for existing shared helpers before creating new ones.

During editing:
- Keep diffs scoped.
- Extract shared logic instead of duplicating it.
- Preserve business logic and data flows.
- Do not revert unrelated user changes.

Before final response:
- Run relevant tests/builds.
- Summarize changed files.
- Call out limitations and remaining risks.
- If `main.py` grew, explain why and list the extraction follow-up. In normal work, `main.py` should not grow.

## Current Refactor Priority

The next backend cleanup should extract existing `main.py` blocks in this order:

1. Upload/parsing helpers into `services/upload_service.py` and `services/parsing_service.py`.
2. Rewrite and AI endpoints into `routes/rewrite.py` and `schemas/rewrite.py`.
3. Dashboard/user/favorites/notes/reminders endpoints into `routes/dashboard.py`, `routes/user.py`, and matching services.
4. Recruiter endpoints into `routes/recruiter.py`, `schemas/recruiter.py`, and `services/recruiter_service.py`.
5. Stripe webhook into `routes/webhook.py` plus a small billing webhook service.
6. CORS/config/security helpers into `core/config.py` and `core/security.py`.

Each extraction must preserve route paths and response shapes unless intentionally versioned.
