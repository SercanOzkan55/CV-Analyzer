# Backup and Restore Runbook

This project stores sensitive CV and recruiter data. Backups must be encrypted,
access-controlled, and regularly tested.

## Database Backups

Run the backup script from the backend container or host that has database
network access:

```bash
./scripts/backup_db.sh
```

Recommended production environment:

```env
BACKUP_DIR=/app/backups
BACKUP_RETENTION_DAYS=7
BACKUP_ENCRYPTION_PASSPHRASE=use-a-secret-manager-value
BACKUP_S3_BUCKET=cv-analyzer-backups
BACKUP_S3_PREFIX=prod/db
BACKUP_S3_KMS_KEY_ID=arn:aws:kms:eu-north-1:ACCOUNT_ID:key/KEY_ID
BACKUP_S3_STORAGE_CLASS=STANDARD_IA
```

Use AWS Secrets Manager, SSM Parameter Store, Docker secrets, or your CI/CD
secret store for `BACKUP_ENCRYPTION_PASSPHRASE`. Do not commit it.

## Cron Example

```bash
0 2 * * * /app/scripts/backup_db.sh >> /app/logs/backup.log 2>&1
```

## Restore Procedure

1. Download the backup and checksum from S3.
2. Verify checksum:

```bash
sha256sum -c cv_analyzer_YYYYMMDD_HHMMSS.sql.gz.gpg.sha256
```

3. Decrypt if encrypted:

```bash
gpg --batch --yes \
  --pinentry-mode loopback \
  --passphrase "$BACKUP_ENCRYPTION_PASSPHRASE" \
  --decrypt cv_analyzer_YYYYMMDD_HHMMSS.sql.gz.gpg \
  > cv_analyzer_YYYYMMDD_HHMMSS.sql.gz
```

4. Restore into a clean database:

```bash
gunzip -c cv_analyzer_YYYYMMDD_HHMMSS.sql.gz | psql "$DATABASE_URL"
```

5. Run migrations after restore:

```bash
python -m alembic upgrade heads
```

6. Smoke test:

```bash
curl -f https://app.example.com/health
```

## AWS Backup Controls

- Use a separate private backup bucket.
- Enable Block Public Access.
- Enable SSE-KMS with a dedicated backup KMS key.
- Restrict writes to the backup job role only.
- Restrict reads to break-glass admin role only.
- Enable lifecycle transition to Glacier/Deep Archive if long-term retention is required.
- Test restore monthly.

## Managed Database Backups

If you run Postgres on RDS:

- Enable automated backups with at least 7 days retention.
- Enable Point-In-Time Recovery for production.
- Enable deletion protection.
- Encrypt the instance and snapshots with KMS.
- Copy critical snapshots to a second region if downtime tolerance requires it.
- Restrict snapshot restore/copy permissions to break-glass admin roles.

If you run Supabase:

- Enable project backups/PITR on the paid production project.
- Export periodic logical backups with this script for independent recovery.
- Test restoring into a separate staging project monthly.
- Document the exact RTO/RPO target in the incident runbook.

## What Not To Back Up

- `.env` files
- runtime logs with possible personal data
- `node_modules`, virtualenvs, build artifacts
- temporary uploaded CV files

The database backup may still include personal data; treat it as highly sensitive.
