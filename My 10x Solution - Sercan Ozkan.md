# My 10x Solution — Sercan Özkan

**Project:** CV Analyzer
**Repository:** https://github.com/SercanOzkan55/CV-Analyzer
**Stack:** Python · FastAPI · PostgreSQL · Redis · Celery · React · LLM

---

## The Problem

Every year, millions of qualified candidates get filtered out by Applicant Tracking Systems (ATS) before a single human reads their resume. ATS tools reject CVs for reasons that have nothing to do with the candidate's actual skill — wrong section headings, missing keywords, non-standard date formats, or unreadable PDF layouts.

Candidates have no way to know why they were rejected or how to fix it. Generic resume advice is vague. Existing ATS simulators are either expensive SaaS tools or shallow free checkers that only look at keyword density.

I built CV Analyzer because I saw this problem firsthand. It parses, scores, rewrites, and benchmarks resumes against real ATS criteria — and it does it with a deterministic parsing core that does not blindly outsource every decision to an LLM.

---

## What I Built

CV Analyzer is a hybrid SaaS + local-privacy platform composed of four cooperating runtimes:

| Runtime | Technology | Role |
|---|---|---|
| Backend API | FastAPI (ASGI) | REST gateway, parsing pipeline, scoring, auth, billing, quotas |
| Web Portal | React 18 + Vite | Dashboards, CV builder, recruiter workspace, billing UI |
| Mobile Client | Expo React Native | Upload and history |
| Local Worker | PySide6 / QML | Offline batch processing on the user's own machine |

The architecture is intentionally hybrid: sensitive batch processing stays on the user's machine until explicitly synced. The cloud handles accounts, recruiter collaboration, and shared workflows.

---

## How I Implemented the 7 Program Concepts

### 1. API Endpoints
FastAPI REST gateway with 40+ endpoints covering the full product surface:
- `POST /api/v1/resumes/analyze` — parse and score a resume
- `POST /api/v1/resumes/rewrite` — AI-powered rewrite with ATS optimization
- `GET /api/v1/resumes/{id}/report` — fetch structured analysis report
- `POST /api/v1/batch/upload` — enqueue multiple CVs for background processing
- `GET /api/v1/recruiters/pipeline` — recruiter workspace endpoints
- `GET /api/v1/auth/me`, `POST /api/v1/auth/token` — authentication

### 2. Database
PostgreSQL with SQLAlchemy 2.0 ORM and Alembic migrations:
- `users`, `resumes`, `analysis_results`, `recruiter_pipelines`, `billing_plans` tables
- Full migration history — schema changes are tracked and reversible
- Separate test database isolation per worker via pytest fixtures

### 3. Authentication
JWT-based authentication in `auth.py`:
- Access + refresh token flow
- Per-user quota enforcement at the API layer
- Recruiter workspace with shared-access permission model
- Worker key for Local Worker sync (separate credential from user JWT)

### 4. Background / Cron Jobs
Celery 5.6 with Redis as broker:
- Batch CV processing enqueued asynchronously — upload 50 CVs, get results when ready
- Background rewrite jobs — AI calls never block the request thread
- Celery Beat for scheduled quota resets and cleanup tasks
- `backend-dev.job.log` tracks job history and retry events

### 5. Caching
Redis used as both Celery broker and application cache:
- Parsed resume sections cached by content hash — identical PDFs are not re-parsed
- ATS keyword index cached at startup and invalidated on config change
- Per-user analysis history cached to avoid repeated DB hits on dashboard load

### 6. LLM Integration
AI is used only where it earns its cost — deterministic parsing runs first:
- Section extraction, date normalization, and keyword scoring are deterministic
- LLM (OpenAI) is called only for natural-language rewrite and feedback generation
- Prompt templates in `services/ai_service.py` keep context tight and cost predictable
- Per-user daily quota enforced server-side to prevent runaway spend

### 7. Reporting
`renderers/` module generates structured output in multiple formats:
- PDF report: ATS score breakdown, section-by-section feedback, keyword gap analysis
- JSON report: machine-readable for batch workflows (`tmp_cv_batch_report.json`)
- Batch summary report: aggregate statistics across a recruiter's candidate pool

---

## What Makes It 10x

Most ATS checkers are a single score between 0-100 with a keyword list. CV Analyzer does:

- **Deterministic parsing first** — section detection, date normalization, and keyword matching run without any API call, making results reproducible and fast
- **Layered rewrite** — the AI rewrites only the sections that scored poorly, not the whole document, preserving the candidate's voice
- **Privacy mode** — the Local Worker processes sensitive batches entirely offline; nothing leaves the machine until the user explicitly syncs
- **Recruiter workspace** — hiring managers can compare candidates side by side, leave notes, and move candidates through a pipeline

---

## Limitations

- Local Worker requires PySide6 which adds a desktop dependency — not a pure web experience
- LLM rewrite quality depends on the model tier; GPT-3.5 rewrites are noticeably weaker than GPT-4
- ATS keyword index is manually curated for common ATS platforms (Workday, Greenhouse, Lever) and may miss niche vertical tools
- Batch processing at scale (500+ CVs) would require a distributed Celery cluster; the current single-worker setup handles ~50 concurrent jobs comfortably

---

## Running Locally

```bash
git clone https://github.com/SercanOzkan55/CV-Analyzer
cd CV-Analyzer
cp .env.example .env        # fill in OPENAI_API_KEY and DATABASE_URL
pip install -r requirements.txt
alembic upgrade head        # run migrations
celery -A core.celery worker --loglevel=info &
uvicorn main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
