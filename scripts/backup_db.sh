#!/usr/bin/env bash
# Daily PostgreSQL backup script.
#
# Usage:
#   ./scripts/backup_db.sh
#
# Cron:
#   0 2 * * * /app/scripts/backup_db.sh >> /app/logs/backup.log 2>&1
#
# Requires:
#   pg_dump, gzip, sha256sum or shasum
#
# Optional:
#   gpg for BACKUP_ENCRYPTION_PASSPHRASE
#   aws CLI for BACKUP_S3_BUCKET
#
# Exits non-zero on failure so cron/systemd alerts can fire.
set -euo pipefail
umask 077

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BASE_NAME="cv_analyzer_${TIMESTAMP}.sql.gz"
BACKUP_FILE="${BACKUP_DIR}/${BASE_NAME}"
FINAL_FILE="${BACKUP_FILE}"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
TMP_FILE="${BACKUP_FILE}.tmp"

BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-db-backups}"
BACKUP_S3_KMS_KEY_ID="${BACKUP_S3_KMS_KEY_ID:-}"
BACKUP_S3_STORAGE_CLASS="${BACKUP_S3_STORAGE_CLASS:-STANDARD_IA}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup: $*"; }

cleanup() {
    rm -f "${TMP_FILE}" "${BACKUP_FILE}.gpg.tmp"
}
trap cleanup EXIT

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log "FATAL: $1 not found"
        exit 1
    fi
}

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        log "FATAL: sha256sum or shasum not found"
        exit 1
    fi
}

require_command pg_dump
require_command gzip

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}" || true

log "Starting database backup"

if [ -n "${DATABASE_URL:-}" ]; then
    pg_dump --no-owner --no-acl "${DATABASE_URL}" | gzip -9 > "${TMP_FILE}"
else
    PGHOST="${POSTGRES_HOST:-db}"
    PGPORT="${POSTGRES_PORT:-5432}"
    PGUSER="${POSTGRES_USER:-testuser}"
    PGDATABASE="${POSTGRES_DB:-testdb}"
    export PGPASSWORD="${POSTGRES_PASSWORD:-}"
    pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" --no-owner --no-acl "${PGDATABASE}" | gzip -9 > "${TMP_FILE}"
fi

if [ ! -s "${TMP_FILE}" ]; then
    log "FATAL: backup file is empty"
    exit 1
fi

gzip -t "${TMP_FILE}"
mv "${TMP_FILE}" "${BACKUP_FILE}"
chmod 600 "${BACKUP_FILE}" || true

if [ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]; then
    require_command gpg
    log "Encrypting backup with GPG symmetric encryption"
    gpg --batch --yes \
        --pinentry-mode loopback \
        --passphrase "${BACKUP_ENCRYPTION_PASSPHRASE}" \
        --symmetric \
        --cipher-algo AES256 \
        --output "${BACKUP_FILE}.gpg.tmp" \
        "${BACKUP_FILE}"
    mv "${BACKUP_FILE}.gpg.tmp" "${BACKUP_FILE}.gpg"
    chmod 600 "${BACKUP_FILE}.gpg" || true
    rm -f "${BACKUP_FILE}"
    FINAL_FILE="${BACKUP_FILE}.gpg"
    CHECKSUM_FILE="${FINAL_FILE}.sha256"
fi

CHECKSUM="$(sha256_file "${FINAL_FILE}")"
printf "%s  %s\n" "${CHECKSUM}" "$(basename "${FINAL_FILE}")" > "${CHECKSUM_FILE}"
chmod 600 "${CHECKSUM_FILE}" || true

SIZE="$(stat -c%s "${FINAL_FILE}" 2>/dev/null || stat -f%z "${FINAL_FILE}" 2>/dev/null || echo 0)"
log "Backup complete: $(basename "${FINAL_FILE}") (${SIZE} bytes, sha256=${CHECKSUM})"

if [ -n "${BACKUP_S3_BUCKET}" ]; then
    require_command aws
    S3_URI="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX%/}/$(basename "${FINAL_FILE}")"
    S3_SUM_URI="${S3_URI}.sha256"
    AWS_ARGS=(--storage-class "${BACKUP_S3_STORAGE_CLASS}")
    if [ -n "${BACKUP_S3_KMS_KEY_ID}" ]; then
        AWS_ARGS+=(--sse aws:kms --sse-kms-key-id "${BACKUP_S3_KMS_KEY_ID}")
    else
        AWS_ARGS+=(--sse AES256)
    fi
    log "Uploading backup to S3: s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX%/}/$(basename "${FINAL_FILE}")"
    aws s3 cp "${FINAL_FILE}" "${S3_URI}" "${AWS_ARGS[@]}"
    aws s3 cp "${CHECKSUM_FILE}" "${S3_SUM_URI}" "${AWS_ARGS[@]}"
fi

DELETED="$(
    find "${BACKUP_DIR}" \
        \( -name "cv_analyzer_*.sql.gz" -o -name "cv_analyzer_*.sql.gz.gpg" -o -name "cv_analyzer_*.sha256" \) \
        -mtime "+${RETENTION_DAYS}" \
        -print -delete | wc -l
)"
if [ "${DELETED}" -gt 0 ]; then
    log "Pruned ${DELETED} local backup artifact(s) older than ${RETENTION_DAYS} days"
fi

COUNT="$(
    find "${BACKUP_DIR}" \
        \( -name "cv_analyzer_*.sql.gz" -o -name "cv_analyzer_*.sql.gz.gpg" \) \
        | wc -l
)"
log "Done. Local backup files in ${BACKUP_DIR}: ${COUNT}"
