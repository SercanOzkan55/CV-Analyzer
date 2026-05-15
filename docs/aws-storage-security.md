# AWS Storage Security Checklist

CV files contain sensitive personal data. Use this checklist before production.

## S3 Bucket Defaults

- Enable Block Public Access for the whole bucket.
- Enable Bucket owner enforced object ownership.
- Disable ACL usage.
- Enable versioning only if you have a clear recovery need; otherwise rely on backups and short retention.
- Add lifecycle rules:
  - `users/*`: expire after 90 days by default.
  - `tmp/*` or `quarantine/*`: expire after 1 day.
  - incomplete multipart uploads: abort after 1 day.

## Required Bucket Policy

Replace `${S3_BUCKET}` with the real bucket name.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET}",
        "arn:aws:s3:::${S3_BUCKET}/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "DenyPublicObjectAcl",
      "Effect": "Deny",
      "Principal": "*",
      "Action": [
        "s3:PutObjectAcl",
        "s3:PutBucketAcl"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET}",
        "arn:aws:s3:::${S3_BUCKET}/*"
      ]
    }
  ]
}
```

## KMS Mode

For production, prefer KMS over S3-managed AES256:

```env
AWS_USE_IAM_ROLE=1
S3_SSE_ALGORITHM=aws:kms
S3_KMS_KEY_ID=arn:aws:kms:eu-north-1:ACCOUNT_ID:key/KEY_ID
```

The app now supports IAM role credentials, so static `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` are not required in production when `AWS_USE_IAM_ROLE=1`.

## Lifecycle JSON Example

```json
{
  "Rules": [
    {
      "ID": "expire-temp-files",
      "Status": "Enabled",
      "Filter": { "Prefix": "tmp/" },
      "Expiration": { "Days": 1 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 1 }
    },
    {
      "ID": "expire-quarantine-files",
      "Status": "Enabled",
      "Filter": { "Prefix": "quarantine/" },
      "Expiration": { "Days": 1 }
    },
    {
      "ID": "expire-user-cvs",
      "Status": "Enabled",
      "Filter": { "Prefix": "users/" },
      "Expiration": { "Days": 90 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 1 }
    }
  ]
}
```

## App-Level Retention

The app also exposes an admin-only retention runner:

```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://app.example.com/api/v1/admin/storage/retention/run?days=90&dry_run=true"
```

Deletion requires an explicit confirmation parameter:

```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://app.example.com/api/v1/admin/storage/retention/run?days=90&dry_run=false&confirm=DELETE"
```

Users can inspect and delete their own stored data through:

- `GET /api/v1/me/data-summary`
- `DELETE /api/v1/me/data?scope=stored_cvs&confirm=DELETE`
- `DELETE /api/v1/me/data?scope=analyses&confirm=DELETE`
- `DELETE /api/v1/me/data?scope=workspace&confirm=DELETE`
- `DELETE /api/v1/me/data?scope=all&confirm=DELETE`

## Raw Text Minimization

By default the app stores CV version text so users can reopen previous versions.
For stricter privacy deployments, store only hashes and metadata in the database:

```env
CV_VERSION_TEXT_STORAGE_MODE=metadata_only
```

The app still computes match scores before discarding raw text, but the version
detail endpoint will return a metadata JSON string instead of the original CV
or job description text. Keep this disabled if the product must allow full
version editing from stored history.

## Malware Quarantine Pattern

Keep uploads out of the durable user prefix until they pass scanning:

1. Upload incoming files to `tmp/user_{id}/...`.
2. Scan with ClamAV or an S3 Object Lambda/Lambda scanner.
3. Move clean files to `user_{id}/original/` or `user_{id}/optimized/`.
4. Move infected or suspicious files to `quarantine/` with 1-day expiry.
5. Alert on every quarantine event and never generate presigned URLs for
   `tmp/` or `quarantine/` prefixes.

This app already supports synchronous ClamAV checks for upload flows when
`CLAMAV_ENABLED=1`. Use the quarantine prefix if you later move scanning to an
asynchronous S3/Lambda workflow.
