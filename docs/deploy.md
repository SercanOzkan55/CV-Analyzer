# Deployment and Secrets

This document covers production deployment tips, Docker secrets, and Sentry setup.

Docker secrets
- Prefer Docker secrets or cloud provider secret stores for credentials rather than committing `.env` to the repo.
- Example Docker Compose secret usage (in `docker-compose.yml`):

```yaml
services:
  web:
    image: yourorg/cv-analyzer:latest
    secrets:
      - db_password
secrets:
  db_password:
    file: ./secrets/db_password.txt
```

GitHub Actions / Docker Hub
- Use repository `secrets` for `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (already referenced in `.github/workflows/docker-build-push.yml`).

Sentry
- Add the `SENTRY_DSN` value in your environment/secrets. Do not commit it to source control.
- `main.py` initializes Sentry automatically when `SENTRY_DSN` is set; use `SENTRY_ENV` to indicate staging/production and `SENTRY_TRACES_SAMPLE_RATE` to control transaction sampling.

Daily quota reset timezone
- Daily quota key/TTL reset now follows `QUOTA_RESET_TIMEZONE` (fallback order: `QUOTA_RESET_TIMEZONE` -> `APP_TIMEZONE` -> `Europe/Istanbul`).
- For production, set `QUOTA_RESET_TIMEZONE` explicitly in secrets/environment so midnight reset matches your business timezone.
- Example values: `Europe/Istanbul`, `UTC`, `Europe/Berlin`, `America/New_York`.

Where to set it
- Docker Compose (web/api service):

```yaml
services:
  web:
    image: yourorg/cv-analyzer:latest
    environment:
      QUOTA_RESET_TIMEZONE: Europe/Istanbul
```

- Docker run:

```bash
docker run -e QUOTA_RESET_TIMEZONE=Europe/Istanbul yourorg/cv-analyzer:latest
```

- systemd service (`/etc/systemd/system/cv-analyzer.service`):

```ini
[Service]
Environment=QUOTA_RESET_TIMEZONE=Europe/Istanbul
```

- After systemd change:

```bash
sudo systemctl daemon-reload
sudo systemctl restart cv-analyzer
```

Verification checklist (production/staging)
- Confirm env is set on the running service: `QUOTA_RESET_TIMEZONE=Europe/Istanbul`.
- Call an analyze endpoint and inspect response headers:
  - `X-Daily-Limit`
  - `X-Daily-Used`
  - `X-Daily-Remaining`
- Re-test after local midnight in configured timezone; first request after midnight should start a new daily key and show refreshed remaining quota.
- If Redis is temporarily unavailable, fallback memory quota uses the same timezone boundary.

`.env.example`
- Contains keys and sample values; copy to `.env` locally. For production, use secrets instead of `.env` files.
