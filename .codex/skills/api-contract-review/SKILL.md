# API Contract Review Skill

Use this skill when fixing frontend/backend mismatches, missing endpoints, API 404/500 errors, route shape changes, response shape changes, or local/prod API base issues.

## Mission

Fix API contracts without scattering logic or hiding failures.

## Contract Checklist

Before editing:

```bash
rg "/api/v1" frontend/src
rg "fetch[A-Z]|api\\." frontend/src
rg "@app\\.|APIRouter|include_router" .
```

Identify:
- Frontend caller.
- HTTP method.
- URL path.
- Request body/query/form shape.
- Auth requirement.
- Success response shape.
- Empty state response shape.
- Error response behavior.

## Implementation Rules

Backend endpoint bodies belong in `routes/<domain>.py`.

Schemas belong in `schemas/<domain>.py`.

Behavior belongs in `services/<domain>.py`.

`main.py` should only register routers.

## Response Rules

Prefer stable, frontend-safe responses:

```json
{ "items": [] }
{ "favorites": [] }
{ "templates": [] }
{ "stats": { ... } }
```

Do not return 500 for normal empty states.

Use:
- `400` for invalid input.
- `401` for missing/invalid auth.
- `403` for role/plan/organization denial.
- `404` for missing resource.
- `409` for conflict/idempotency issues.
- `422` for schema validation.
- `503` for unavailable provider/service.

## Compatibility Rules

Do not casually rename JSON keys consumed by the frontend.

If a response must change:
- Update frontend API wrapper.
- Update consuming pages/components.
- Update tests.
- Document the breaking change.

## Local Development API Base

For local static frontend served on `127.0.0.1:5173`, API calls should go to the local backend on `127.0.0.1:8001`.

Do not hardcode production hosts in frontend source.

Use environment variables first:
- `VITE_API_BASE_URL`
- local fallback only for localhost/127.0.0.1

## Verification

Use route registration checks:

```python
import main
paths = {getattr(route, "path", "") for route in main.app.routes}
assert "/api/v1/some-path" in paths
```

Then run:

```bash
python -m pytest
cd frontend && npm test && npm run build
```

If browser QA is available:
- Log in through the normal UI with safe test credentials.
- Visit affected routes.
- Check network tab for 404/500.
- Check console errors.
- Check empty states.

## Output Requirement

Final response must include:
- Which API contracts were fixed.
- Which frontend screens were affected.
- Whether route paths stayed stable.
- Commands run and results.
- Remaining contracts that still need database-backed implementation.
