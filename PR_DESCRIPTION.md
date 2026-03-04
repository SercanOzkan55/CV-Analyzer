Title: Add IVFFlat tuning notes and CI ops guidance for pgvector

Summary:
- Documented `ivfflat` tuning recommendations (lists, reindexing, warmup workflow).
- Added CI/DevOps guidance for enabling `pgvector` in CI (Docker service image and install steps).
- Provided example SQL and GitHub Actions/Docker snippets, and testing tips for CI.

Files changed:
- TEST_DOCUMENTATION.md (appended IVFFlat tuning & CI ops section)

Commit message:
Add documentation: IVFFlat tuning and CI ops notes

This change documents how to tune `ivfflat` indexes (lists/nlist), index rebuild and
reindex instructions, warmup & tuning workflow, and CI setup options (use `ankane/pgvector` image
or install `pgvector` in CI). Also includes example SQL and tips for keeping CI fast and
deterministic.

Notes for reviewer:
- These are documentation-only changes and do not modify runtime code.
- Follow the CI snippet to ensure your CI runner has `pgvector` available before running integration tests.
