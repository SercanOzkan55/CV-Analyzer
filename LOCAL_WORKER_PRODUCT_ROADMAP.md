# Local Worker Product Roadmap

This document tracks the productization path for the downloadable CV Analyzer Local Worker. Each phase should be shipped as a small commit, validated locally, pushed to `main`, and checked in GitHub Actions before continuing.

## Phase 1 - One-click local worker foundation

Status: shipped in `Productize local worker first pass`.

- Windows one-click setup scripts.
- Visual local worker app.
- Local job description workflow.
- Local CV folder analysis.
- Local CSV/JSON export.
- Local SQLite workspace for saved jobs and run history.
- Duplicate detection and ranked exports.

## Phase 2 - Real desktop packaging

Goal: remove terminal and Python setup friction.

- Build a Windows `.exe` launcher.
- Package Python runtime/dependencies or provide a reliable bootstrapper.
- Add desktop/start menu shortcuts.
- Add uninstall guidance.
- Add version metadata.

## Phase 3 - Professional desktop UI

Goal: make the local worker feel like a real product, not a utility script.

- Replace the minimal Tkinter layout with a polished desktop shell or significantly improve the existing UI.
- Add dark/light theme.
- Add drag-and-drop CV folder/file selection.
- Add responsive panes for job setup, run progress, and result review.
- Add empty/error/loading states.

## Phase 4 - Local job workspace

Goal: support repeatable offline recruiting workflows.

- Saved local jobs with title, description, skills, thresholds, and hard reject criteria.
- Run history per job.
- Re-open previous results.
- Clone/edit job profiles.
- Compare runs.

## Phase 5 - Stronger local scoring engine

Goal: improve local analysis quality before adding AI cost.

- Section-aware CV parsing.
- Skill synonym matching.
- Fuzzy skill matching.
- Seniority and experience extraction.
- Education/certification extraction.
- Weighted score breakdown.
- Explainable recommendation output.

## Phase 6 - Optional AI review

Goal: improve uncertain/borderline results without forcing cost on every CV.

- AI off by default.
- Customer OpenAI key stored only locally.
- Platform AI proxy mode only when explicitly enabled.
- AI only for uncertain cases.
- Token/cost estimate before run.
- PII redaction option.

## Phase 7 - Robust file handling

Goal: survive real employer CV folders.

- PDF/DOCX/TXT extraction hardening.
- OCR path for scanned PDFs.
- Failed-file queue.
- Retry failed files.
- Max file size guard in UI.
- Duplicate file report.

## Phase 8 - Secure local credential handling

Goal: remove environment variable/API key friction.

- API key input in UI.
- Store API key in OS credential store where available.
- Redact secrets from logs and exports.
- Detect revoked keys.
- Refresh short-lived tokens.

## Phase 9 - Offline-first sync

Goal: let employers work locally and sync later.

- Local-only mode remains default.
- Optional site sync queue.
- Retry/backoff for failed sync.
- Conflict handling.
- Network-offline indicator.

## Phase 10 - Employer dashboard management

Goal: give the website a complete management surface.

- Worker device list.
- Last seen/version/status.
- Quota usage and local run summaries.
- Revoke/rotate keys.
- Audit log.
- Force update warnings.

## Phase 11 - Release and quality gate

Goal: make releases predictable.

- Installer smoke tests.
- GUI smoke tests.
- Worker E2E smoke tests.
- Large folder performance test.
- Signed release artifacts.
- Auto-update plan.
- CI jobs that do not require unavailable GitHub Advanced Security features.
