# 500 TL budget: recovery status and deployment requirements

## Verified on 2026-10-13

- Google Cloud project: `cv-analyzer-production`; billing is disabled.
- The linked billing account uses TRY and is closed (`open=false`).
- Compute inventory requests fail while billing is disabled. The actual VM size,
  disks, IP addresses and outstanding charges have not been verified.
- The old runbook describes an `e2-standard-2` VM in Frankfurt. This is a
  deployment example, not proof of the current inventory or a 500 TL quote.
- Google remains closed. Apex DNS now points to the free Render static site;
  Cloudflare proxy remains enabled. Apex and www Render domains are verified.
  HTTPS root returns 200 and www returns 301 to the root.
- Supabase restoration completed; read-only SELECT 1 succeeds. Organization is
  Free with spend cap enabled.
- Existing AWS credentials return InvalidAccessKeyId; old AWS objects were not changed.

## Application changes prepared locally

`.env.production` and `.env.production.example` now specify:

```dotenv
PAID_AI_ENABLED=0
COST_GUARD_REQUIRE_REDIS=1
COST_UPLOAD_PER_DAY=100
COST_ANALYZE_PER_DAY=100
COST_OPTIMIZE_PER_DAY=0
```

The AI switch blocks client factories, embedding calls (including existing
clients), AI entitlements and rewrite generation. AI-only requests return an
unavailable response rather than falling back to generated demonstration text.
Blog moderation keeps local checks; mandatory AI moderation fails closed.
Basic parsing and ATS scoring are not disabled by the AI switch, but their
end-to-end operation still requires validation on the chosen host.

The shared analysis cap covers text, asynchronous and uploaded CV analyses;
uploads also have their own cap. Redis failure rejects guarded operations.
Daily resets use Europe/Istanbul. Production Redis uses `noeviction` so caches
cannot evict quota counters. On the existing Docker profile keep its persistent volume: deleting or restoring
old Redis data can reset counts. The free Render profile is volatile (see below). These are operation counts, not currency limits.

These local changes take effect remotely only after deployment and restart of
both the API and any workers. The AI switch does not cancel historical bills,
AWS storage charges, Supabase subscriptions, email plans or domain renewals.

## Free-host evaluation

- Cloudflare Pages Free is a candidate for the React frontend. It does not run
  the existing Python API. Moving only the frontend does not restore analysis.
- Render Free is a candidate for a limited backend preview, subject to measured
  memory/CPU, cold-start and dependency checks. It has ephemeral disk, limited
  free hours and bandwidth, and SMTP-port restrictions. Do not store CVs or
  backups on its ephemeral filesystem. Its documentation advises against using
  free instances for production; a working preview is not a reliability promise.
- Do not create Render Free Postgres as permanent storage: it expires after
  30 days. Check the existing Supabase project's plan, quotas and availability
  before keeping it. Do not replace or erase the existing database.
- Render access is available through the official CLI. Workspace is Hobby, no
  card on file. Free API: `srv-db6mvbks728c73cksmfg`; static frontend:
  `srv-db6mu6favr4c73cs8obg`. API branch: `codex/budget-recovery`.
- Quotas use free Frankfurt Key Value `red-db6mqlpsrm7s73c4tcmg`, noeviction.
  Free Key Value is volatile: restarts can reset daily counters. AI keys are
  omitted and paid AI disabled independently of those counters.
- One Gunicorn worker, explicit CELERY_ENABLED=0 uses existing synchronous
  LocalTask execution. No paid worker or paid database was provisioned.
- Main frontend: https://cvanalyzer.dev (fallback https://cv-analyzer-site.onrender.com).
  API: https://cv-analyzer-api-lb46.onrender.com. Health and readiness return 200.
- Supabase private bucket `cv-analyzer-storage`: max 5 MB, PDF/DOCX only.
  The user explicitly approved the S3 credential's full-bucket/RLS-bypass scope.
  Credentials are stored only as Render server environment variables. Old AWS
  objects were neither accessed nor deleted; historical files remain inaccessible
  until valid AWS access is recovered.
- Live authenticated synthetic PDF analysis completed, history and original-file
  reference persisted, private presigned download returned a valid PDF (200).
  Database, Redis, S3, model worker all report healthy. RSS before/after this
  single small analysis: 296.6/387.9 MB (web process, not full container peak).
  This is not proof that every large PDF or OCR workload fits 512 MB.
- Final resource profile: global/path/parse concurrency 1, memory admission
  threshold 400 MB, PDF page maximum 10, one Gunicorn worker recycling after
  150 requests plus jitter. These limit admission; they are not OS memory caps.
- 50 focused quota/AI/rewrite/ownership tests passed in the isolated checkout.
  Explicit CELERY_ENABLED=0 LocalTask execution and Python syntax checks passed.
- Render no-card/free plans, Supabase Free spend cap, Cloudflare Free verified.
  Domain registration renewals and past invoices have not been verified or cancelled.

Before publishing, verify the replacement account cannot charge for overages
or automatic upgrades, verify all external plans, and reserve domain/tax costs
within the total 500 TL. Do not add a payment method or select a paid plan
merely to get the deployment running. Do not promise a zero-cost migration
until a complete backend and frontend smoke test succeeds.

## Deployment acceptance checks

1. Confirm no paid AI calls with keys present; retain `MOCK_SERVICES=0`.
2. Confirm the shared Redis cap, restart durability and refusal on Redis failure.
3. Confirm startup, health, authentication, real CV analysis/history, downloads,
   background tasks, file storage and any required email delivery.
4. Measure peak memory under analysis; do not assume a 512 MB instance fits.
5. Verify provider free-plan overage behavior and billing settings. Check all
   billable accounts, including S3 and Supabase, independently.
6. Back up data; change DNS only after the replacement passes these checks.

Google budget alerts and delayed enforcement cannot guarantee a strict VM
spending ceiling. Keep Google billing closed until a compatible plan satisfies
the user's budget requirement.

Sources:
- https://render.com/docs/free
- https://developers.cloudflare.com/pages/functions/pricing/
- https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps
