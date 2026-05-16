# CV Analyzer

CV Analyzer is a FastAPI + React application for CV/resume analysis, ATS scoring, CV rewriting, CV building, recruiter ranking, and SaaS-style usage/billing flows.

The README intentionally reflects the current repository state, including known architecture debt. Older README versions described routes, folders, and mobile/TypeScript setup that did not match the codebase.

## Current Status

- Backend: FastAPI application, currently still concentrated in `main.py`.
- Frontend: React 18 + Vite application using mostly JS/JSX, with some TS/TSX files present.
- Styling: a large legacy `frontend/src/style.css` plus `frontend/src/tailwind.css` using Tailwind CSS v4 packages. There is no `tailwind.config.js` in the current frontend.
- Tests: backend pytest suite and frontend Vitest suite are present.
- Mobile: a `mobile/` directory exists, but it is not currently a complete active mobile app in this repository because it has no `mobile/package.json`.
- API namespace: active product endpoints are under `/api/v1/...`, plus `/stripe/webhook`.
- Architecture debt: `routes/`, `schemas/`, `core/`, `middleware/`, `agents/`, and `config/` currently contain only cache/placeholder content. New backend work must fill these modules instead of adding more feature code to `main.py`.

## Architecture Guardrails For Contributors And Agents

The most important rule:

> Do not add new feature code to `main.py`.

`main.py` should be treated as the FastAPI composition root: app creation, middleware setup, router registration, global handlers, metrics, and startup/shutdown wiring. New API endpoints, schemas, business logic, upload parsing, AI provider calls, recruiter workflows, dashboard aggregation, billing behavior, and persistence helpers must live in domain modules.

Required backend pattern for new work:

```text
routes/<domain>.py      # APIRouter endpoints only
schemas/<domain>.py     # Pydantic request/response contracts
services/<domain>.py    # business behavior and provider integrations
tests/test_<domain>.py  # contract, regression, security tests
```

Read these before backend or agent-driven work:

- [Repository Agent Instructions](AGENTS.md)
- [Backend Architecture And Modularization Guide](docs/backend-architecture.md)
- [Agent Workflow For Safe Product Changes](docs/agent-workflow.md)

Parser/upload work must stay general across PDF, DOCX, TXT, multiple languages, multi-page CVs, and multi-column layouts. Do not fix parser bugs with one-language or one-sample special cases.

## Product Capabilities

### Individual CV Analysis

- Upload CV files for analysis.
- Supported upload formats: PDF, DOCX, TXT.
- Compare CV content against an optional job description.
- Return match score, ATS score, missing skills, keyword gaps, recommendations, risk level, language-aware interpretation, and history records.

### CV Auto-Fix And Rewrite

- Auto-fix CV text into a cleaner ATS-friendly structure.
- Export optimized CV output as PDF or DOCX.
- Rewrite CVs, bullets, cover letters, and profile-style content.
- Uses a mock provider in local/test mode.
- Uses OpenAI when configured with `OPENAI_API_KEY` and rewrite provider settings.

### CV Builder

- Generate and preview CV documents.
- List available templates by plan.
- Expose a template marketplace-style API for the frontend.
- Expose basic ATS-safe font options.

### Recruiter Workflows

- Organization-scoped candidate listing.
- Top candidate ranking.
- Candidate detail lookup.
- Candidate search.
- Batch ranking for multiple CV uploads.
- Recruiter jobs, pipeline/action tracking, templates, reports, and batch upload support.

### Dashboard And User Data

- Usage summary.
- Usage history and streaks.
- Analysis history.
- Benchmarks.
- Favorites.
- JD templates.
- Notes.
- Sharing links.
- Data summary/export/delete endpoints.
- Reminders.

### Billing And SaaS

- Stripe checkout session creation.
- Stripe customer portal session creation.
- Contact sales flow.
- Premium trial activation.
- Admin plan updates.
- Stripe webhook endpoint with signature verification.

## Technology Stack

### Backend

| Area | Current implementation |
| --- | --- |
| Web framework | FastAPI |
| Language | Python |
| ORM/database access | SQLAlchemy |
| Migrations | Alembic |
| Database target | PostgreSQL, with pgvector support |
| Auth | Supabase JWT verification |
| Rate limiting | SlowAPI/limits, Redis when available |
| Background jobs | Celery when Redis is reachable; local synchronous fallback otherwise |
| CV parsing | pdfplumber/PyPDF2 for PDF, python-docx for DOCX, UTF-8 text for TXT |
| ML/scoring | scikit-learn/joblib model path plus deterministic scoring services |
| AI providers | OpenAI client when configured; mock fallback |
| Billing | Stripe-oriented billing service and webhook flow |
| Testing | pytest |

### Frontend

| Area | Current implementation |
| --- | --- |
| Framework | React 18 |
| Build tool | Vite |
| Language | Mostly JS/JSX; some TS/TSX support files exist |
| Styling | Legacy CSS in `frontend/src/style.css` plus Tailwind v4 CSS import |
| UI libraries | lucide-react, framer-motion |
| Auth client | Supabase JS |
| Testing | Vitest + Testing Library + jsdom |

### Not Currently Active As Documented

These were previously overstated in the README:

- `spaCy`, `NLTK`, and `transformers` are not required by `requirements.txt` and are not part of the current active backend dependency set.
- The primary frontend entry is `frontend/src/App.jsx`, not `App.tsx`.
- There is no current `frontend/tailwind.config.js`; Tailwind v4 can run without the old config file.
- `mobile/` exists, but it is not a complete active Expo app in the current repo state.
- `routes/` and `schemas/` exist but are not yet populated with real modules. They are the target for the next refactor.

## System Flow

```mermaid
flowchart LR
    User["User / Recruiter"] --> Frontend["React + Vite frontend"]
    Frontend --> API["FastAPI backend /api/v1"]
    API --> Auth["Supabase JWT verification"]
    API --> Upload["Upload parser: PDF / DOCX / TXT"]
    API --> Scoring["ATS, keyword, skill, experience scoring"]
    API --> AI["OpenAI or mock rewrite provider"]
    API --> DB["PostgreSQL / pgvector"]
    API --> Redis["Redis when available"]
    API --> Stripe["Stripe billing and webhook"]
    API --> Frontend
```

## CV Analysis Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as FastAPI
    participant P as Upload Parser
    participant S as Scoring Pipeline
    participant D as Database

    U->>F: Upload CV and optional job description
    F->>B: POST /api/v1/analyze-pdf
    B->>B: Verify JWT, rate limits, quota
    B->>P: Extract text from PDF/DOCX/TXT
    P-->>B: Plain CV text
    B->>S: Run matching and ATS pipeline
    S-->>B: Scores, gaps, recommendations
    B->>D: Save analysis/history where applicable
    B-->>F: JSON result
    F-->>U: Dashboard/result view
```

## Local Setup

### Prerequisites

- Python 3.11 or 3.12.
- Node.js. This workspace also contains a bundled Node runtime under `tools/node-v24.14.0-win-x64`.
- PostgreSQL for full database-backed development.
- Redis for Celery/rate-limit paths that require it. The app has fallbacks for some local/test flows.

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure environment variables in `.env` or your shell. At minimum, local development normally needs:

```bash
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/cv_analyzer
SUPABASE_JWT_SECRET=...
OPENAI_API_KEY=...        # optional unless real AI provider output is required
STRIPE_SECRET_KEY=...     # optional unless billing is tested
STRIPE_WEBHOOK_SECRET=... # optional unless webhook verification is tested
```

Run the backend:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Health checks:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/ready
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend defaults to the configured `VITE_API_BASE_URL`. In local static/dev use, the app is expected to call the backend at `http://127.0.0.1:8001`.

Production build:

```bash
cd frontend
npm run build
```

Static SPA fallback server used by this workspace:

```bash
python scripts/spa_static_server.py --directory frontend/dist --host 127.0.0.1 --port 5173
```

## Testing

Backend:

```bash
python -m py_compile main.py services/rewrite_service.py
python -m pytest
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

Type checking:

```bash
npx tsc --noEmit
```

Note: type checking requires TypeScript tooling to be installed in the relevant workspace. If network access is blocked and TypeScript is missing, this command may not be available.

## Main API Endpoints

This is not a full OpenAPI reference. Run the backend and open `http://127.0.0.1:8001/docs` for the generated API docs.

### Core Analysis

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/analyze` | Analyze pasted CV text against a job description |
| `POST` | `/api/v1/analyze-async` | Queue or locally run text analysis |
| `POST` | `/api/v1/analyze-pdf` | Analyze uploaded PDF/DOCX/TXT CV |
| `GET` | `/api/v1/analysis/{job_id}` | Fetch async analysis/job result |
| `GET` | `/api/v1/history` | Fetch analysis history |
| `GET` | `/api/v1/history/export` | Export history as CSV |

### Dashboard/User Data

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/usage` | Current usage/quota summary |
| `GET` | `/api/v1/usage-history` | Daily usage history |
| `GET` | `/api/v1/usage-streak` | Current and longest usage streak |
| `GET` | `/api/v1/insights` | Dashboard insight summary |
| `GET` | `/api/v1/me` | Current user profile |
| `GET` | `/api/v1/me/data-summary` | User data summary |
| `GET` | `/api/v1/me/data-export` | User data export |
| `DELETE` | `/api/v1/me/data` | User data deletion flow |

### Favorites, Notes, Sharing, Templates, Reminders

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/favorites` | List favorites |
| `GET` | `/api/v1/favorites/ids` | List favorite analysis IDs |
| `POST` | `/api/v1/favorites/toggle` | Toggle a favorite |
| `GET` | `/api/v1/jd-templates` | List job description templates |
| `POST` | `/api/v1/jd-templates` | Create job description template |
| `DELETE` | `/api/v1/jd-templates/{template_id}` | Delete job description template |
| `POST` | `/api/v1/notes` | Save analysis note |
| `GET` | `/api/v1/notes/{analysis_id}` | Fetch analysis note |
| `DELETE` | `/api/v1/notes/{analysis_id}` | Delete analysis note |
| `POST` | `/api/v1/share` | Create share link |
| `GET` | `/api/v1/shared/{share_token}` | Fetch shared analysis |
| `DELETE` | `/api/v1/share/{share_token}` | Remove share link |
| `GET` | `/api/v1/reminders` | List reminders |
| `POST` | `/api/v1/reminders` | Create reminder |
| `PUT` | `/api/v1/reminders/{reminder_id}` | Update reminder |
| `DELETE` | `/api/v1/reminders/{reminder_id}` | Delete reminder |

### Rewrite, Auto-Fix, Interview, Matching

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/cv/auto-fix` | Extract and optimize uploaded CV |
| `POST` | `/api/v1/cv/auto-fix/export` | Export optimized CV as PDF/DOCX |
| `POST` | `/api/v1/cv/auto-fix/parse` | Parse optimized text into builder payload |
| `POST` | `/api/v1/rewrite/cv` | Rewrite CV text |
| `POST` | `/api/v1/rewrite/bullets` | Rewrite bullet points |
| `POST` | `/api/v1/rewrite/cover-letter` | Generate/rewrite cover letter |
| `POST` | `/api/v1/cv/rewrite` | Compatibility alias for CV rewrite |
| `POST` | `/api/v1/cv/optimize-keywords` | Optimize CV keywords |
| `POST` | `/api/v1/cv/diff` | Compare original and optimized text |
| `POST` | `/api/v1/score/breakdown` | Return score breakdown |
| `POST` | `/api/v1/job/match-score` | Return match score for CV/JD text |
| `POST` | `/api/v1/interview/questions` | Generate interview questions |
| `POST` | `/api/v1/interview/evaluate` | Evaluate interview answer |
| `POST` | `/api/v1/linkedin/optimize` | Generate LinkedIn-style optimization output |

### Recruiter

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/recruiter/candidates` | List organization candidates |
| `GET` | `/api/v1/recruiter/top_candidates` | List top ranked candidates |
| `GET` | `/api/v1/recruiter/candidate/{analysis_id}` | Candidate detail |
| `GET` | `/api/v1/recruiter/search` | Search organization candidates |
| `POST` | `/api/v1/recruiter/batch-rank` | Batch rank uploaded CVs |
| `GET` | `/api/v1/recruiter/jobs` | List recruiter jobs |
| `POST` | `/api/v1/recruiter/jobs` | Create recruiter job |
| `GET` | `/api/v1/recruiter/dashboard/actions/{job_id}` | List job actions |
| `GET` | `/api/v1/recruiter/pipeline/{job_id}` | Pipeline view |
| `PUT` | `/api/v1/recruiter/dashboard/actions/{action_id}/stage` | Update action stage |
| `POST` | `/api/v1/recruiter/dashboard/action` | Create dashboard action |
| `POST` | `/api/v1/recruiter/dashboard/preview` | Preview candidate ranking |
| `POST` | `/api/v1/recruiter/dashboard/rank` | Rank one candidate |
| `POST` | `/api/v1/recruiter/dashboard/batch-upload` | Batch upload for recruiter dashboard |
| `GET` | `/api/v1/recruiter/report/{job_id}` | Export recruiter report |
| `GET` | `/api/v1/recruiter/templates` | List recruiter message templates |
| `POST` | `/api/v1/recruiter/templates` | Create recruiter template |
| `DELETE` | `/api/v1/recruiter/templates/{template_id}` | Delete recruiter template |
| `POST` | `/api/v1/recruiter/templates/preview` | Preview recruiter template |
| `POST` | `/api/v1/recruiter/send-email` | Queue/send recruiter email intent |

### CV Builder

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/fonts` | List available font options |
| `GET` | `/api/v1/cv-builder/template-marketplace` | List template catalog |
| `GET` | `/api/v1/cv-builder/templates` | List templates available to plan |
| `POST` | `/api/v1/cv-builder/generate` | Generate CV document |
| `POST` | `/api/v1/cv-builder/preview` | Generate CV preview |
| `POST` | `/api/v1/cv-builder/suggest-summary` | Suggest professional summaries |

### Billing And Webhooks

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/billing/checkout-session` | Create Stripe checkout session |
| `POST` | `/api/v1/billing/portal-session` | Create Stripe portal session |
| `POST` | `/api/v1/billing/contact-sales` | Contact sales request |
| `POST` | `/api/v1/billing/activate-trial` | Activate premium trial |
| `GET` | `/api/v1/billing/admin/me` | Admin identity summary |
| `GET` | `/api/v1/billing/admin/users` | Admin user list |
| `GET` | `/api/v1/billing/admin/feedback` | Admin feedback list |
| `POST` | `/api/v1/billing/admin/set-user-plan` | Admin plan update |
| `POST` | `/stripe/webhook` | Stripe webhook receiver |

## API Examples

### Analyze Uploaded CV

```bash
curl -X POST http://127.0.0.1:8001/api/v1/analyze-pdf \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -F "file=@resume.pdf" \
  -F "job_description=Looking for a backend engineer with Python and SQL" \
  -F "lang=en"
```

Typical response fields include:

```json
{
  "final_score": 82.5,
  "ats_score": 78.0,
  "skill_score": 86.0,
  "missing_skills": ["docker"],
  "keyword_gap": {},
  "recommendations": []
}
```

### Analyze Text

```bash
curl -X POST http://127.0.0.1:8001/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Python developer with SQL experience",
    "job_description": "Backend role requiring Python and SQL",
    "lang": "en"
  }'
```

### Recruiter Batch Ranking

```bash
curl -X POST http://127.0.0.1:8001/api/v1/recruiter/batch-rank \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -F "job_description=Senior backend engineer, Python, APIs, PostgreSQL" \
  -F "files=@candidate_1.pdf" \
  -F "files=@candidate_2.docx"
```

### CV Auto-Fix

```bash
curl -X POST http://127.0.0.1:8001/api/v1/cv/auto-fix \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -F "file=@resume.docx" \
  -F "job_description=Product manager role with SaaS experience" \
  -F "lang=en" \
  -F "use_ai=true"
```

## Project Structure

Current high-level repository structure:

```text
cv-analyzer/
  main.py                         # Current FastAPI app/composition root; still contains legacy route code
  auth.py                         # Supabase JWT verification helpers
  database.py                     # SQLAlchemy engine/session setup
  models.py                       # SQLAlchemy models
  requirements.txt                # Minimal active backend dependencies
  requirements_full.txt           # Larger captured environment, not the default install target
  alembic.ini
  migrations/                     # Alembic migration versions
  services/                       # Active business/scoring/rewrite/billing services
  tests/                          # Backend pytest suite
  frontend/
    package.json
    vite.config.js
    tsconfig.json
    public/
    src/
      App.jsx
      main.jsx
      api.js
      style.css
      tailwind.css
      blog/
      components/
      context/
      hooks/
      i18n/
      pages/
      utils/
      __tests__/
  docs/
    README.md
    backend-architecture.md
    agent-workflow.md
    deploy.md
    usage.md
  .codex/
    skills/
  routes/                         # Target for future APIRouter modules; currently not populated
  schemas/                        # Target for future Pydantic schemas; currently not populated
  core/                           # Target for future config/security/dependency modules
  middleware/                     # Target for future middleware modules
  scripts/
  sample_cvs/
```

## Active Service Modules

Important current backend services include:

- `services/ats_service.py`
- `services/billing_service.py`
- `services/cv_autofix_service.py`
- `services/cv_builder_service.py`
- `services/domain_service.py`
- `services/embedding_service.py`
- `services/experience_service.py`
- `services/industry_service.py`
- `services/keyword_service.py`
- `services/language_service.py`
- `services/model_service.py`
- `services/recommendation_service.py`
- `services/rewrite_service.py`
- `services/scoring_service.py`
- `services/skill_service.py`
- `services/tasks.py`

## Security Notes

- JWT auth is handled through Supabase token verification.
- Recruiter endpoints must remain organization-scoped.
- Upload endpoints must validate size and supported file types before parsing.
- Production CORS should not allow arbitrary localhost origins.
- Stripe webhooks must use Stripe-style timestamped signature verification.
- Secrets must remain in environment variables or secure secret stores, never in committed files.

## CI

The GitHub Actions workflow is in `.github/workflows/ci.yml`.

Current intended checks:

- Backend tests on Python 3.11 and 3.12.
- PostgreSQL service with pgvector image.
- Alembic migrations.
- Full pytest suite.
- Frontend `npm test`.
- Frontend `npm run build`.
- Git safe-directory configuration for scanners that inspect the repository.

## Deployment

See [docs/deploy.md](docs/deploy.md) for deployment notes.

At a high level:

- Configure production environment variables.
- Use PostgreSQL with migrations applied.
- Configure Supabase JWT settings.
- Configure OpenAI only when real rewrite/embedding behavior is required.
- Configure Stripe keys and webhook secret for billing flows.
- Serve the frontend build through an SPA-capable static server or platform.
- Route API traffic to the FastAPI backend.

## Known Technical Debt

These are intentional, documented next steps:

1. Extract upload/parsing helpers from `main.py` into `services/upload_service.py` and `services/parsing_service.py`.
2. Extract rewrite endpoints into `routes/rewrite.py` and `schemas/rewrite.py`.
3. Extract dashboard/user/favorites/notes/reminders endpoints into proper route/schema/service modules.
4. Extract recruiter endpoints into `routes/recruiter.py`, `schemas/recruiter.py`, and `services/recruiter_service.py`.
5. Move local feature-store style behavior into database-backed models and Alembic migrations.
6. Replace remaining `datetime.utcnow()` usage with timezone-aware UTC helpers.
7. Add a CI guard that fails when new `@app.get`, `@app.post`, `@app.put`, or `@app.delete` decorators are added directly to `main.py`.
8. Expand browser QA coverage for authenticated routes.

## Contributing Rules

- Do not add feature code to `main.py`.
- Keep route contracts stable unless intentionally versioned.
- Add regression tests for parser bugs.
- Keep frontend API calls centralized in `frontend/src/api.js`.
- Do not remove restored product features such as Blog, Cover Letter, Career Studio, Compare, CV Builder, Recruiter, Dashboard, Settings, and Profile.
- Run backend and frontend checks before handing off a change.

## Useful Links

- FastAPI docs: https://fastapi.tiangolo.com/
- React docs: https://react.dev/
- Vite docs: https://vite.dev/
- Supabase docs: https://supabase.com/docs
- Stripe docs: https://docs.stripe.com/
- OpenAI docs: https://platform.openai.com/docs/
