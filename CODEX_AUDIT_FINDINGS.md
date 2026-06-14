# Codex Audit Findings

Date: 2026-06-13

Scope: Full-project security, bug, frontend QA, and validation pass using the repository UI agent workflow as guidance. No code changes were made during this audit.

## Summary

The project is fairly mature and already has many security controls: JWT auth, per-user and per-IP rate limits, upload validation, S3 ownership checks, security headers, admin token gates, and many security tests in the repo.

The highest-priority issues I found are around tenant isolation, server-side URL fetching, task ownership, unauthenticated progress/download surfaces, admin token handling, and dependency vulnerabilities.

## Critical / High Priority

### P1: Recruiter Tenant Isolation Risk

File: `routes/recruiter.py`

References:
- `routes/recruiter.py:452`
- `routes/recruiter.py:456`
- `routes/recruiter.py:459`
- `routes/recruiter.py:462`

Recruiter users with no `organization_id` are automatically assigned to an organization derived from their email domain. For generic providers such as Gmail, Outlook, Yahoo, etc., multiple unrelated recruiter accounts can be placed into the same auto-created organization.

Risk:
- Cross-tenant visibility of candidates, jobs, reminders, pipeline actions, and recruiter exports.
- A user with recruiter role and a common email domain may accidentally share a tenant with unrelated users.

Recommended fix:
- Do not auto-provision recruiter organizations from email domain in production.
- Require explicit organization invite, owner-created membership, or verified organization domain.
- For generic email providers, create a unique personal org per user or block recruiter auto-provisioning.

### P1: SSRF Risk in Job Import

File: `routes/analysis.py`

References:
- `routes/analysis.py:1208`
- `routes/analysis.py:1224`

`/api/v1/integrations/import-jobs` accepts a user-controlled `url` and calls `requests.get(url, timeout=10)` from the backend.

Risk:
- Server-side request forgery against `localhost`, internal services, cloud metadata endpoints, private network resources, or admin panels.
- Error messages may reveal internal connectivity details.

Recommended fix:
- Remove this mock endpoint from production or gate it behind admin/internal-only auth.
- Add strict allowlist of trusted domains.
- Reject private, loopback, link-local, multicast, and metadata IP ranges after DNS resolution.
- Use a hardened outbound HTTP helper with DNS/IP checks and redirect validation.

### P1/P2: Async Analysis Task Ownership Missing

File: `routes/analysis.py`

References:
- `routes/analysis.py:968`
- `routes/analysis.py:980`

`/api/v1/analysis/{job_id}` requires a valid JWT but does not verify that the Celery task belongs to the requesting user.

Risk:
- If a task ID is leaked or guessed, another authenticated user may retrieve analysis results.
- CV analysis results may contain sensitive extracted CV/job information.

Recommended fix:
- Persist task ownership when queueing async jobs.
- On polling, verify `job_id` belongs to `db_user.id` or `organization_id`.
- Avoid returning raw task results unless ownership is confirmed.

### P2: Unauthenticated Recruiter Batch Progress WebSocket

File: `routes/recruiter_extended.py`

References:
- `routes/recruiter_extended.py:360`
- `routes/recruiter_extended.py:386`
- `routes/recruiter_extended.py:401`

`/api/v1/recruiter/ws/batch-upload/{task_id}` accepts a WebSocket connection without JWT/session validation and polls task progress by `task_id`.

Risk:
- Anyone with a task ID can observe progress, filenames, status, or error details.
- Potential information leak across recruiter organizations.

Recommended fix:
- Require JWT auth for WebSocket connection.
- Store task ownership and verify organization/user access before streaming updates.
- Avoid including sensitive filenames or raw errors in unauthenticated progress messages.

## Medium Priority

### P2: Public Temporary Download Links

File: `routes/downloads.py`

References:
- `routes/downloads.py:16`
- `routes/downloads.py:48`

`/api/v1/downloads/{download_id}` and `/api/v1/downloads/cleanup/expired` are public. Download IDs are UUID-based and hard to guess, but links are bearer-equivalent and unauthenticated.

Risk:
- Anyone with the link can download exported recruiter/candidate ranking data until expiry.
- Cleanup endpoint is public and should not be externally callable.

Recommended fix:
- Require auth and verify ownership for temporary downloads.
- Store user/org ID with each temp download.
- Make cleanup internal/admin-only.
- Consider signed short-lived URLs with HMAC.

### P2: Billing Checkout / Portal Open Redirect Surface

File: `routes/billing.py`

References:
- `routes/billing.py:801`
- `routes/billing.py:805`
- `routes/billing.py:916`

Checkout and portal endpoints accept `success_url`, `cancel_url`, and `return_url` from the client without visible allowlist validation.

Risk:
- Open redirect/phishing surface through trusted billing flows.
- Users may be sent to attacker-controlled domains after billing actions.

Recommended fix:
- Only allow same-origin URLs or configured trusted frontend origins.
- Reject protocol-relative URLs and non-HTTPS production URLs.
- Prefer server-configured defaults over client-provided redirect targets.

### P2: Admin Token Stored in `localStorage`

Files:
- `frontend/src/pages/AdminBillingPage.jsx`
- `frontend/src/pages/OpsCenterPage.jsx`

References:
- `frontend/src/pages/AdminBillingPage.jsx:169`
- `frontend/src/pages/OpsCenterPage.jsx:77`

Billing/Ops admin token is saved in browser `localStorage`.

Risk:
- XSS, malicious extensions, or shared-browser access can exfiltrate a persistent admin token.

Recommended fix:
- Do not persist admin tokens in `localStorage`.
- Keep token in memory only, or use short-lived server-issued admin sessions.
- Add explicit "remember for this session" behavior only if necessary, using `sessionStorage` as a lesser fallback.

### P2: JWT Verification Gaps

File: `auth.py`

References:
- `auth.py:12`
- `auth.py:13`
- `auth.py:193`
- `auth.py:199`

JWT decoding disables audience verification with `verify_aud: False`. Some asymmetric verification failures may produce 500 responses instead of 401.

Risk:
- Tokens minted for a different audience may be accepted if the signature is valid.
- Invalid tokens can surface as server errors, making auth behavior noisy and harder to monitor.

Recommended fix:
- Verify expected issuer and audience for Supabase tokens.
- Return 401 for invalid token/key/verification failures.
- Cache JWKS and handle missing `kid` conservatively.

### P2: Frontend Dependency Vulnerabilities

File: `frontend/package.json`

References:
- `frontend/package.json:20`
- `frontend/package.json:31`
- `frontend/package.json:33`
- `frontend/package.json:37`

`npm audit` results:
- High: `esbuild <=0.28.0` via Vite/dev tooling.
- Moderate: `postcss <8.5.10`.
- Moderate: `react-router` / `react-router-dom` open redirect advisory.
- Moderate: `ws` uninitialized memory disclosure.

Recommended fix:
- Run `npm audit fix` for non-breaking updates.
- Plan Vite/esbuild upgrade carefully because audit suggests a breaking Vite major upgrade for full remediation.
- Update React Router to a non-vulnerable version.

### P3: Proxy IP Extraction Can Be Misconfigured

File: `core/ops_runtime.py`

References:
- `core/ops_runtime.py:333`
- `core/ops_runtime.py:337`
- `core/ops_runtime.py:342`

When `TRUSTED_PROXY_COUNT > 0`, `_extract_client_ip` returns the first `X-Forwarded-For` entry. If proxy trust is not enforced by infrastructure, clients may spoof their IP.

Risk:
- Rate limits, abuse bans, and admin IP allowlists can be bypassed or polluted.

Recommended fix:
- Only honor `X-Forwarded-For` when the immediate peer is a trusted proxy.
- Use the correct client IP from the right side of the trusted proxy chain.
- Document deployment-specific proxy requirements.

## Validation Notes

Initial audit commands run:

```powershell
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd run test
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd run build
python -m compileall -q auth.py main.py routes services core security utils models.py database.py
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd audit --omit=dev --cache C:\Users\ASUS\Desktop\cv-analyzer\.npm-cache
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd audit --cache C:\Users\ASUS\Desktop\cv-analyzer\.npm-cache
```

Current remediation validation commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --strict --progress-spinner off
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_security_advanced.py tests/test_auth_jwt.py tests/test_analysis_task_ownership.py tests/test_local_processing.py tests/test_exporters.py tests/test_security_dependency_check.py -q --tb=short
.\.venv\Scripts\python.exe -m compileall -q auth.py main.py routes services core security utils models.py database.py migrations tests
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd run test
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd run typecheck
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd run build
C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd audit --cache C:\Users\ASUS\Desktop\cv-analyzer\.npm-cache
```

Current results:
- Python dependency audit passed: `No known vulnerabilities found`.
- Python dependency resolver check passed: `No broken requirements found`.
- Backend targeted security/regression pytest passed: 32 passed, 1 skipped. The skipped test is the in-test `pip-audit` subprocess when the local sandbox cannot reach the vulnerability service; the same audit was run directly with network approval and passed.
- Frontend tests passed: 6 test files, 51 tests. The `Test error` console output is from the intentional ErrorBoundary test case.
- Frontend TypeScript validation passed via `npm run typecheck`.
- Frontend production build passed.
- Frontend `npm audit` passed: 0 vulnerabilities.
- Python `compileall` passed.

Remaining validation limitation:
- Browser/UI QA is intentionally deferred to the next UI-focused pass.

## Suggested Fix Order

1. Fix recruiter organization auto-provisioning and tenant isolation.
2. Remove or harden server-side job import URL fetching.
3. Add ownership checks to async task polling and recruiter progress WebSocket.
4. Add auth/ownership to temporary downloads and make cleanup admin-only.
5. Add redirect URL allowlist for billing flows.
6. Stop persisting admin tokens in `localStorage`.
7. Tighten JWT issuer/audience/error handling.
8. Upgrade vulnerable frontend dependencies.
9. Add `typescript` as a dev dependency or remove `npx tsc --noEmit` from required validation.
10. Restore local backend test tooling so security tests can run consistently.

## Remediation Status

Updated: 2026-06-13

Completed in branch `codex/security-audit-fixes`:

- P1 recruiter tenant isolation: disabled domain-based auto-provision by default and made the opt-in fallback create a personal org per recruiter.
- P1 SSRF in job import: added URL scheme, credentials, host allowlist, DNS/IP range, and redirect checks before outbound fetch.
- P1/P2 async task access: recorded analysis task owners and rejected polling by other users.
- P2 recruiter batch WebSocket: added JWT token verification and organization ownership checks before accepting progress streams.
- P2 temporary downloads: added HMAC-signed short-lived download URLs and protected cleanup with admin access checks.
- P2 billing redirects: added allowlist validation for checkout success/cancel and portal return URLs.
- P2 admin token storage: moved billing admin token persistence from `localStorage` to `sessionStorage` and clears the legacy key.
- P2 JWT validation: enabled audience validation, issuer validation when configured via `SUPABASE_URL`/`SUPABASE_JWT_ISSUER`, and normalized invalid asymmetric token failures to 401.
- P2 frontend dependency vulnerabilities: upgraded React Router, `ws`, PostCSS, Vite, Vite React plugin, and Tailwind Vite tooling; `npm audit` now reports 0 vulnerabilities.
- P3 proxy IP extraction: only trusts `X-Forwarded-For` when the immediate peer is trusted via `TRUSTED_PROXY_IPS` or loopback dev proxy.
- Python dependency vulnerabilities: upgraded vulnerable pins in `requirements.txt`, including `urllib3`, `cryptography`, `ecdsa`, `idna`, `jwcrypto`, `pytest`, `lxml`, `Mako`, `Pillow`, `Pygments`, `python-dotenv`, `python-multipart`, `requests`, and `starlette`. `prometheus-fastapi-instrumentator` was upgraded to keep Starlette 1.x compatibility.

Current status before UI pass:

- Async analysis task ownership is now persisted in the database via `async_task_owners`, with a process-local fallback only for compatibility with existing in-flight jobs.
- Temporary local-processing downloads are now tied to the owning organization/subscription and require the matching `X-API-Key` in addition to the HMAC download token.
- TypeScript is now a frontend dev dependency with `npm run typecheck`, and React 18 type packages are installed.
- No open code remediation remains from this audit file. Next recommended work is staging smoke testing and the separate UI audit/polish pass.
