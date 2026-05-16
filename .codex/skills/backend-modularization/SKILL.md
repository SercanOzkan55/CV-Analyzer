# Backend Modularization Skill

Use this skill whenever a task touches backend API routes, schemas, services, parsing, uploads, billing, recruiter workflows, dashboard/user data, webhooks, or `main.py`.

## Mission

Keep CV Analyzer modular. Do not add new feature code to `main.py`.

## Hard Rule

`main.py` may only be used for:
- App creation.
- Middleware registration.
- Router registration.
- Global exception handlers.
- Metrics/lifespan/bootstrap wiring.
- Health checks.

Do not add:
- New endpoint implementations.
- New schemas.
- New parsing helpers.
- New AI prompt builders.
- New persistence helpers.
- New business workflows.

If the needed module does not exist, create it.

## Target Placement

Use these locations:

```text
routes/<domain>.py      # FastAPI APIRouter endpoints
schemas/<domain>.py     # Pydantic request/response contracts
services/<domain>.py    # business behavior
core/<topic>.py         # config/security/dependencies/errors
middleware/<topic>.py   # request/response middleware
tests/test_<domain>.py  # regression and contract tests
```

## Backend Workflow

1. Search first:
   ```bash
   rg "APIRouter|@app\\.|include_router" .
   rg "/api/v1/path" .
   rg "class .*Request|class .*Response" schemas main.py
   ```

2. Identify ownership:
   - Domain route file.
   - Domain schema file.
   - Domain service file.
   - Model/migration file if persistence is needed.
   - Test file.

3. Implement in layers:
   - Schema.
   - Service.
   - Route.
   - Router registration in `main.py`.
   - Tests.

4. Preserve API contracts:
   - Existing URL.
   - Existing method.
   - Existing response keys.
   - Existing auth behavior.
   - Existing frontend empty state behavior.

5. Verify:
   ```bash
   python -m py_compile main.py
   python -m pytest
   ```

## Extraction Workflow

When moving code out of `main.py`:

1. Copy the smallest cohesive block to a domain module.
2. Keep function names stable where tests/imports rely on them.
3. Replace direct globals with explicit parameters or dependencies.
4. Keep route paths unchanged.
5. Add router registration.
6. Run focused tests, then full tests.
7. Remove the old block from `main.py`.

## Parser And Upload Rules

Upload and parsing behavior must be shared across:
- Analyze.
- Auto-fix.
- Recruiter batch rank.
- Recruiter dashboard batch upload.
- JD upload.

Do not create separate file validation logic per endpoint.

Supported files:
- PDF.
- DOCX.
- TXT.

Always test:
- Unsupported file rejection.
- Oversized file rejection.
- Empty text extraction.
- Multi-page/multi-column parsing.
- Certification vs experience separation.
- Non-English section aliases.

## AI Rules

Provider calls belong in services, never route bodies.

AI prompts must:
- Preserve facts.
- Avoid invention.
- Match requested language.
- Use configurable provider/model settings.
- Have mock fallback for tests.

## Output Requirement

When using this skill, final response must state:
- Whether `main.py` was touched.
- If touched, exactly why.
- Which module owns the behavior now.
- What tests/builds were run.
