# Local Worker MVP

This document describes the Local Worker MVP for employer-side CV processing.

## Architecture

The Local Worker flow lets an employer generate a scoped API key, run a Python CLI worker on their own machine, claim job-specific CVs, process them locally, and send results back to the platform.

Core properties:

- Worker API keys are shown only once and only stored as SHA-256 hashes.
- Worker sessions use short-lived access tokens.
- Claims are job-specific and lease based.
- Quota is reserved on claim, finalized on successful result submit, and refunded when a claim expires or duplicate processing is detected.
- Download links are short-lived signed URLs tied to a single claim and CV. If a candidate action has stored file metadata, the worker receives the storage provider's signed URL; otherwise it receives a backend-signed TXT fallback for `cv_text`.
- Local workers never receive platform OpenAI keys.

## Production Environment Variables

Recommended production settings:

- `WORKER_DOWNLOAD_SIGNING_SECRET`: high-entropy secret used for backend-signed TXT fallback URLs. Set this explicitly in production.
- `WORKER_DOWNLOAD_URL_TTL_SECONDS`: signed download URL TTL. Defaults to 600 and must be between 60 and 3600 seconds.
- `SECRET_KEY`: application secret fallback. Do not rely on the development fallback value.
- `CV_ANALYZER_API_URL`: local worker API base URL, for example `https://app.example.com/api/worker`.
- `CV_WORKER_API_KEY`: optional local worker API key environment variable on the employer machine.
- `CV_WORKER_PROGRESS_LOG`: optional local worker JSONL progress log path.
- `CV_WORKER_MAX_FILE_BYTES`: optional max downloaded CV size for the CLI worker. Defaults to 25 MB.
- Storage provider variables used by `services.storage_service`, such as S3/R2 endpoint, bucket, region, access key, and secret key.

Production must not run with the implicit development download signing secret.

## Backend Endpoints

Routes are implemented in `routes/worker.py` and mounted under `/api`.

- `POST /api/worker-keys`
- `GET /api/worker-keys`
- `POST /api/worker-keys/{id}/revoke`
- `POST /api/worker/auth`
- `GET /api/worker/jobs`
- `GET /api/worker/jobs/{jobId}/config`
- `POST /api/worker/jobs/{jobId}/claim`
- `GET /api/worker/download/{claim_id}?token=...`
- `POST /api/worker/jobs/{jobId}/results`
- `POST /api/worker/heartbeat`
- `GET /api/worker/dashboard-progress/{job_id}`

## Data Model

The migration is `migrations/versions/e63b476f4381_add_local_worker_models.py`.

Tables:

- `worker_keys`
- `worker_sessions`
- `worker_claims`
- `worker_analysis_results`
- `quota_events`

`candidate_actions` stores optional `cv_file_key`, `cv_file_name`, and `cv_file_type` metadata for recruiter uploads.

`worker_claims` and `worker_analysis_results` reference `candidate_actions` so claims come from the job-specific candidate pool instead of the global candidate table.

## Claim And Quota Rules

1. Claim selects only `candidate_actions` for the requested `job_id` and organization.
2. Active unexpired claims and completed results are excluded.
3. `quota_reserved` is atomically increased.
4. Each claim receives a 10-minute signed download URL. Stored files use `services.storage_service.get_download_url(...)`; text-only records use `/api/worker/download/{claim_id}?token=...`.
5. Successful result submit moves one unit from `quota_reserved` to `quota_used`.
6. Duplicate result submit returns idempotent success and does not double charge.
7. Expired claims are marked expired and refunded before new claims are created.
8. If the CLI worker cannot download or extract a CV, it submits a low-confidence `recommended_reject` result with an extraction risk flag. This moves reserved quota to used quota and prevents stuck leases. Change this policy later if failed extraction should be refunded instead.

## Storage Signed URLs

Stored CV files are only returned when the claimed `candidate_action` has file metadata:

- `cv_file_key`
- `cv_file_name`
- `cv_file_type`

`routes/worker.py` calls `services.storage_service.get_download_url(key, owner_id, expires=600)`. The storage layer must keep enforcing ownership and key validation so a worker cannot request arbitrary object keys. If storage is unavailable, returns a local path, or cannot generate an HTTP(S) signed URL, the claim safely falls back to backend-signed TXT only when `cv_text` exists.

The signed URL TTL is 600 seconds.

## TXT Fallback Behavior

TXT fallback exists for older or text-only candidate records that do not have stored CV file metadata. The fallback URL:

- is HMAC signed,
- includes claim id, CV id, and expiry,
- expires after at most 10 minutes,
- checks the claim is active,
- checks the worker session is still active,
- checks the worker key is still active,
- checks company/job/candidate scope,
- responds with `Cache-Control: no-store`.

Revoked keys, revoked sessions, expired sessions, expired claims, completed claims, and mismatched claim/CV ids cannot download the fallback text.

## Python Worker

Employers can download a ready-to-run ZIP from the Settings > Local Worker panel. The
download is served by `GET /api/worker/download-package` and contains:

- `worker.py`
- `requirements.txt`
- `README.md`
- `.env.example`
- `run-worker.ps1`

The ZIP never includes an API key. The employer must paste the one-time key shown
after creating a worker key in the web app.

Install:

```bash
cd local_worker
python -m pip install -r requirements.txt
```

Use:

```bash
python worker.py login --api-key sk_worker_live_xxx
python worker.py jobs --api-key sk_worker_live_xxx
python worker.py run --api-key sk_worker_live_xxx --job-id 123 --batch-size 20
python worker.py status --api-key sk_worker_live_xxx
```

For local development, the worker defaults to `http://127.0.0.1:8001/api/worker`,
matching the FastAPI dev server documented in the project README. For staging or
production, set `CV_ANALYZER_API_URL` explicitly.

The worker supports:

- storage signed URL download
- backend-signed TXT fallback download
- TXT extraction
- PDF extraction through `pypdf` or `PyPDF2`
- DOCX extraction through `python-docx`
- rule-based scoring
- retry/backoff
- network timeouts
- access-token re-auth on 401 responses
- max file size guard through `CV_WORKER_MAX_FILE_BYTES`
- low-confidence failed extraction result submit
- local JSONL progress log

`local_folder` mode is intentionally extraction-only in this MVP. It can read local PDF/DOCX/TXT files and report extracted character counts, but it does not sync results to the backend because local files do not yet have server-side candidate ids, claims, signed download scope, or quota ownership. The next phase should add local upload/virtual-claim design before enabling backend sync.

## Security Checklist

- API keys are never stored in plaintext.
- Plaintext keys are returned only on creation.
- Revoking a key revokes active sessions.
- Worker tokens expire.
- Signed download URLs expire after 10 minutes.
- Fallback TXT download refuses revoked keys and revoked/expired sessions.
- Workers can only claim CVs for their organization and allowed job.
- Results require an active claim from the same session.
- Result score is validated in the schema.
- Quota events record reserve, completed, refunded, and expired transitions.
- Worker CLI does not log API keys or bearer tokens.
- Worker CLI submits safe failed results for empty or unreadable CV files rather than leaving claims reserved until manual intervention.

## Production Checklist

- Set `WORKER_DOWNLOAD_SIGNING_SECRET`.
- Configure object storage and verify generated URLs expire after 10 minutes.
- Verify storage object keys cannot traverse outside the worker's company/user namespace.
- Enable a distributed rate-limit backend for multi-instance deployment.
- Monitor `quota_events` for negative or unexpected quota patterns.
- Review retention rules for `worker_analysis_results` because local processing can still include CV-derived personal data in summaries/explanations.
- Add operational alerts for repeated `extraction_failed`, `download_failed`, or quota exhaustion.
- Decide whether failed local extraction should consume quota or be refunded for your billing policy.

## Tests

Worker MVP tests live in `tests/test_worker_mvp.py`.

Covered scenarios:

- key creation returns plaintext once
- auth success/failure
- revoked and expired keys cannot authenticate
- another company job cannot be used
- job-specific claim pool
- signed download URL content
- revoked key cannot download fallback content
- claim reserves quota
- result submit moves reserved quota to used quota
- duplicate result submit does not double charge
- another session cannot submit a claim
- expired claim submit is rejected and refunded
- revoked key/session cannot submit results
- two sessions claim distinct candidates
- expired claim refund
- quota limit over-claim protection
- score range validation

Run:

```bash
python -m pytest tests/test_worker_mvp.py -q
```

## Remaining MVP Risks

- Recruiter batch upload now attempts to store original files and propagate file metadata into `candidate_actions`. If storage is not configured, the worker safely falls back to backend-signed TXT download from `cv_text`.
- `local_folder` mode is extraction-only for now; result sync should be added after local uploads or virtual claims are designed.
- Rate limiting uses the app limiter. A distributed rate-limit backend is recommended before multi-instance production.
- The rule-based scoring engine is intentionally simple and should be calibrated with real employer feedback.
- The fallback TXT endpoint necessarily returns CV text for a valid active claim. Keep token TTL short and audit access.
- Failed extraction currently consumes quota through a low-confidence failed result. This is operationally safe for leases but may need product/billing review.
