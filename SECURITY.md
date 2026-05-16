# Security Policy

## Supported Branch

Security fixes target the `main` branch.

## Reporting a Vulnerability

Do not open a public issue for secrets, account access bugs, storage leaks, or
other sensitive findings.

Send a private report to:

- Email: `sikayet.cvanalizor@gmail.com`

Please include:

- affected endpoint, page, or workflow;
- clear reproduction steps;
- impact summary;
- whether any personal data or credentials were exposed.

## Response Targets

- Critical: acknowledge within 24 hours and prepare a fix as soon as possible.
- High: acknowledge within 2 business days.
- Medium/Low: triage in the normal maintenance cycle.

## Secret Handling

If a secret is committed:

1. Rotate the secret immediately in the provider dashboard.
2. Remove it from the repository.
3. Check GitHub Actions and deployment logs for exposure.
4. Use the security workflow secret scan before merging the fix.

## Data Handling

CVs, parsed CV text, candidate data, reminder emails, and recruiter notes are
personal data. Production deployments should enable:

- short-lived S3 presigned URLs;
- S3 Block Public Access;
- KMS encryption for stored CVs;
- app-level retention cleanup;
- user data deletion endpoints;
- log redaction for S3 keys and personal data.
