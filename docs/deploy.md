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

`.env.example`
- Contains keys and sample values; copy to `.env` locally. For production, use secrets instead of `.env` files.
