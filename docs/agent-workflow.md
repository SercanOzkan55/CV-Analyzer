# Agent Workflow For Safe Product Changes

This workflow is for Codex, contributors, and any future automated agent working on CV Analyzer.

## Goal

Improve the product without reintroducing the old monolith problem.

Every meaningful change should leave the system more modular, more general, and easier to test.

## Roles

### 1. Product/UX Reviewer

Use this role for frontend and product behavior changes.

Checks:
- Does the change preserve existing user-facing features?
- Does it keep Blog, Cover Letter, Career Studio, Compare, CV Builder, Dashboard, Recruiter, Settings, Profile, and public pages discoverable?
- Does the navigation remain uncluttered?
- Are empty/loading/error states clear?
- Does the UI remain professional and consistent?
- Does the change work on desktop and mobile?

### 2. Backend Architecture Reviewer

Use this role for API, service, data, auth, billing, upload, parser, and AI changes.

Checks:
- Did any implementation code get added to `main.py`?
- Is the endpoint in a domain router?
- Are schemas in `schemas/`?
- Is behavior in `services/`?
- Does persistence use DB models and migrations when production data is involved?
- Are auth and organization scopes preserved?
- Are provider calls isolated behind services?

### 3. Generalization Reviewer

Use this role for CV parsing, scoring, rewrite, matching, recruiter ranking, and recommendations.

Checks:
- Does the logic work across languages?
- Does it assume one CV layout?
- Does it confuse certifications, education, experience, projects, and skills?
- Does it handle multi-page and multi-column documents?
- Does it handle PDF, DOCX, and TXT consistently?
- Is a regression test added for the specific failure mode?

### 4. Frontend Implementation Reviewer

Use this role for React/Vite changes.

Checks:
- Are API calls centralized in `frontend/src/api.js`?
- Are shared rules in utilities, not duplicated page-by-page?
- Are colors/tokens/status badges centralized?
- Are existing feature routes preserved?
- Are page-specific changes small and safe?
- Does build still pass?

### 5. QA/Security Reviewer

Use this role before final response.

Checks:
- Backend tests pass.
- Frontend tests pass.
- Build passes.
- No secret was printed or committed.
- No fake auth was added.
- Upload validation still rejects unsupported files.
- CORS is not broadened in production.
- Stripe webhook verification remains strict.

## Required Workflow

### Step 1: Classify The Change

Classify the request as one or more:
- Backend API.
- Backend service.
- Parser/upload.
- AI/rewrite.
- Billing/webhook.
- Recruiter.
- Dashboard/user data.
- Frontend UI.
- Documentation only.
- Test/CI only.

### Step 2: Locate Ownership

Before editing, identify:
- Route owner.
- Schema owner.
- Service owner.
- Model/migration owner.
- Frontend API owner.
- Tests owner.

If the only obvious place is `main.py`, create the missing module instead.

### Step 3: Search Before Writing

Use `rg` first:

```bash
rg "target_function_or_endpoint"
rg "/api/v1/some-path"
rg "class SomeSchema"
rg "someFrontendApiCall" frontend/src
```

Never duplicate a helper until existing helpers have been checked.

### Step 4: Implement Small Slices

Prefer small, production-safe improvements:
- Extract one domain at a time.
- Keep route contracts stable.
- Add tests around the behavior being moved.
- Preserve public API shape.
- Avoid broad rewrites unless the user explicitly requests one.

### Step 5: Verify

Run relevant checks:

```bash
python -m py_compile main.py services/rewrite_service.py
python -m pytest
cd frontend
npm test
npm run build
```

If authenticated browser QA is needed, use the safe test session only through the normal login UI and do not store credentials.

## `main.py` Guardrail

This is the most important repository-specific rule:

> Do not add feature code to `main.py`.

If a change touches `main.py`, classify it:

Allowed:
- `include_router(...)`.
- FastAPI app configuration.
- Middleware registration.
- Lifespan/bootstrap wiring.
- Emergency compatibility shim with immediate extraction plan.

Not allowed:
- Endpoint body.
- New schema.
- New service helper.
- New parser.
- New AI prompt builder.
- New persistence bucket.
- New recruiter/dashboard/business workflow.

## Good Backend Change Example

```text
Need: Add "saved JD templates".

Do:
  schemas/jd_template.py
  services/jd_template_service.py
  routes/jd_templates.py
  alembic migration for jd_templates table
  tests/test_jd_templates.py
  main.py gains only app.include_router(jd_templates_router)

Do not:
  Add a @app.get("/api/v1/jd-templates") function directly to main.py.
  Store templates in a JSON file for production behavior.
```

## Good Parser Change Example

```text
Need: Certifications are being parsed as experience.

Do:
  Add a regression fixture or minimal text sample.
  Update parser section boundary logic in service module.
  Test certifications, experience, education, projects separately.
  Verify non-English aliases.

Do not:
  Add a Turkish-only if statement.
  Hard-code one customer's certificate name.
  Patch the issue only in frontend display.
```

## Good Frontend Change Example

```text
Need: Upload UI should support DOCX/TXT.

Do:
  Create shared file type utility.
  Update all upload components to use it.
  Keep backend validation authoritative.
  Update translations and hints.
  Add/adjust tests where available.

Do not:
  Update only one page.
  Duplicate accepted file extensions in five components.
  Let frontend accept files backend rejects.
```

## Reporting Format

Final responses should include:
- What changed.
- Which files changed.
- Commands run and results.
- What was intentionally not changed.
- Remaining risks or recommended next refactor.

If `main.py` was changed:
- Say exactly why.
- Say whether lines were added or removed.
- Name the target module for follow-up extraction.

## Current High-Priority Backlog

1. Extract upload/parsing helpers from `main.py`.
2. Extract rewrite routes and schemas.
3. Extract dashboard/user feature endpoints.
4. Extract recruiter endpoints and services.
5. Move local feature store behavior into database-backed models.
6. Replace remaining `datetime.utcnow()` with timezone-aware UTC helpers.
7. Add route-level tests for all frontend-consumed endpoints.
8. Add browser QA coverage for authenticated routes.
9. Add CI checks that fail if new endpoint decorators are added directly to `main.py`.
