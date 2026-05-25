# CV Analyzer: Enterprise-Grade AI Resume Intelligence & ATS Optimization Platform

CV Analyzer is a production-grade, high-throughput AI resume intelligence and ATS optimization platform. Spanning nearly **160,000 lines of code**, the codebase architecture is split into a modular **FastAPI** backend, a high-performance **React 18 + Vite** web client, a **React Native + Expo** mobile scaffold, and specialized AI/ML pipeline modules.

The platform transforms raw, unstructured resume files (PDF, DOCX, TXT) into structured JSON entities, evaluates them against complex applicant tracking system (ATS) algorithms and job descriptions, delivers actionable improvement roadmaps, and facilitates recruiter workflows like batch ranking and pipeline exporting.

---

## Table of Contents

- [Core Product Capabilities](#core-product-capabilities)
- [System & Data Architecture](#system--data-architecture)
- [Deep Dive: Processing & Scoring Pipelines](#deep-dive-processing--scoring-pipelines)
  - [1. Section Parsing & Resolution Pipeline](#1-section-parsing--resolution-pipeline)
  - [2. ATS Evaluation & ML Calibration Engine](#2-ats-evaluation--ml-calibration-engine)
  - [3. Auto-Fix & Section Floor Optimization Engine](#3-auto-fix--section-floor-optimization-engine)
- [Technology Stack](#technology-stack)
- [Project Directory Mapping](#project-directory-mapping)
- [Environment Configuration](#environment-configuration)
- [Installation & Quick Start](#installation--quick-start)
  - [FastAPI Backend Setup](#fastapi-backend-setup)
  - [React/Vite Frontend Setup](#reactvite-frontend-setup)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Multi-Agent UI Workflow](#multi-agent-ui-workflow)

---

## Core Product Capabilities

*   **Multi-Format Document Parsing:** Linearizes complex, multi-page, multi-column layouts into unified text blocks, utilizing regex heuristics and layout analyzers.
*   **Comprehensive Resume Scoring:** Scores resumes out of 100 based on ATS formatting guidelines, keyword density, semantic relevance, skills, experience, layout, and content quality.
*   **Smart ATS Auto-Fix:** Restructures resume text, injects powerful ATS action verbs, aligns formatting, and guarantees that core content (e.g., projects, skills, education) is never lost or shrunken during optimization.
*   **Recruiter Workspaces:** Allows batch uploads (up to 5,000 resumes), runs concurrent scoring pipelines, calculates domain similarities, and generates Excel/CSV candidate reports.
*   **Interactive CV Builder:** Re-compiles structured resume payloads back into clean templates, previewable in HTML and exportable to styled DOCX and PDF documents.
*   **Enterprise SaaS Infrastructure:** Features user authentication, Stripe subscription webhooks, Redis-backed request caching and rate-limiting, and detailed operational health checks.

---

## System & Data Architecture

The application is structured to isolate compute-heavy AI and ML tasks from the web application loop. Under production settings, Redis coordinates task queues and caches semantic analysis objects, minimizing OpenAI/LLM API calls and database reads.

```mermaid
flowchart TB
  user["User / Recruiter"] --> web["React 18 + Vite Web App"]
  user --> mobile["React Native / Expo App"]

  web --> api["FastAPI Gateway Node"]
  mobile --> api

  subgraph Gateway ["API Guard Rails & Controls"]
    api --> auth["Supabase JWT Validator"]
    api --> quota["Tenant Quotas & Stripe Billing Guard"]
    api --> redis_cache["Redis Caching & Token Buckets"]
  end

  subgraph Pipelines ["Processing Engines"]
    quota --> parser["Multi-stage CV Parser Pipeline"]
    quota --> scoring["ATS & ML Scoring Engine"]
    quota --> builder["CV Builder Template Engine"]
  end

  subgraph Datastores ["Storage & State Layer"]
    parser --> db["PostgreSQL Database (SQLAlchemy)"]
    parser --> s3["S3-Compatible Object Store"]
    redis_cache --> redis["Redis Memory Grid"]
  end

  scoring --> ml_model["Local Scikit-Learn Match Predictor"]
  scoring --> openai["LLM & Embeddings Middleware"]
```

---

## Deep Dive: Processing & Scoring Pipelines

### 1. Section Parsing & Resolution Pipeline

Unstructured text extracted from files goes through a robust layout-aware parser before semantic extraction begins.

```mermaid
flowchart LR
  file["Raw CV Document"] --> ext["Text Extraction (fitz / docx)"]
  ext --> layout["Layout Analyzer (linearizes multi-columns)"]
  layout --> classify["Section Classifier (labels sections)"]
  classify --> resolver["Section Resolver (fixes key overlaps)"]
  resolver --> normalize["Normalizer (strips formatting noise)"]
  normalize --> validate["CVSchema Compliance Verification"]
```

1.  **Layout Analyzer:** Detects column structures and re-orders text blocks logically to ensure single-column reading order.
2.  **Section Classifier:** Identifies candidate boundaries using multi-language heading patterns (Turkish and English).
3.  **Section Resolver:** Eliminates ambiguities (e.g., preventing certificates from being swallowed by experience blocks).
4.  **Normalizer:** Cleans stray bullets, whitespace markers, and normalizes contact, education, skills, and languages.
5.  **CVSchema Validation:** Validates the structure using Pydantic models (`CVSchema`, `ProjectEntry`, `CertificationEntry`).

### 2. ATS Evaluation & ML Calibration Engine

Match scores are calculated via a hybrid logic that blends deterministic rules with machine learning:

$$\text{Final Match Score} = \text{Rule-based Score (70\%)} + \text{ML-Calibrated Score (30\%)} $$

```mermaid
flowchart TD
  cv["CV Text & Schema"] --> keywords["Keyword Coverage (35%)"]
  cv --> skills["Skill Mapping (25%)"]
  cv --> semantic["Semantic Similarity via Embeddings (25%)"]
  cv --> seniority["Seniority Alignment (15%)"]

  keywords --> rule_calc["Weighted Match Calculator"]
  skills --> rule_calc
  semantic --> rule_calc
  seniority --> rule_calc

  rule_calc --> ml_blend["ML Calibrator (Scikit-Learn)"]
  ml_blend --> final_score["Final ATS & Job Match Score"]
```

*   **Keyword Match:** Evaluates keyword coverage against the target job description (weighted at 35%).
*   **Skill Coverage:** Compares CV skills to the requirements of the job (weighted at 25%).
*   **Semantic Matching:** Computes cosine similarity between OpenAI/Mock embeddings of the CV and job description (weighted at 25%).
*   **Seniority Matching:** Resolves matching levels (intern, junior, mid, senior, lead) using token-based mapping (weighted at 15%).
*   **ML Calibration:** A pre-trained model (`resume_model.pkl`) fine-tunes the rule-based output based on historical evaluations.
*   **Outage Safeguard:** If the job description is absent, the overall score defaults to the structural ATS quality score. If embeddings fail, a conservative cap of 40 is applied to prevent score inflation.

### 3. Auto-Fix & Section Floor Optimization Engine

When users trigger the "Auto-Fix" flow, the application optimizes their CV text for ATS parser compatibility.

```mermaid
sequenceDiagram
  participant U as User / Client
  participant AF as Auto-Fix Service
  participant Norm as Normalization Pipeline
  participant Floor as Floor Guardrail
  participant ATS as ATS Scorer

  U->>AF: Send CV text (safe mode)
  AF->>AF: Extract, clean, and reconstruct sections
  AF->>Norm: Wording polish & ATS verb injection
  AF->>Floor: Compare line counts per section
  alt Optimized section is shorter than original
    Floor->>Floor: Restore original section lines (Preservation)
  end
  Floor-->>AF: Safe structured text
  AF->>ATS: Score optimized text
  alt Score regressed from original CV
    AF->>AF: Fallback to original CV with identity header
  end
  AF-->>U: Optimized CV Text + Improvement details
```

*   **Action Verb Injection:** Replaces passive verbs with strong, ATS-recognized action verbs.
*   **Protected Section Floor Guard:** Compares line counts of critical sections (Skills, Projects, Certifications, Education, Languages) before and after optimization. If an optimization shrinks a section, it automatically restores the original text to prevent evidence loss.
*   **Regression Guard:** Evaluates the score of the rewritten text. If the score is lower than the original CV, it rolls back to a minimal heading-only rewrite or preserves the source CV text.

---

## Technology Stack

*   **Backend Framework:** FastAPI (Python 3.12)
*   **Database Tooling:** SQLAlchemy ORM, Alembic Migrations
*   **Frontend Library:** React 18, Vite, Framer Motion, TailwindCSS (for public pages), Vanilla CSS Variables (design tokens)
*   **Mobile App:** React Native, Expo, TypeScript
*   **Machine Learning & Data:** Scikit-Learn, Pytest, Pandas, Numpy, Pydantic v2
*   **Infrastructure Support:** Redis (rate-limiting/cache), Docker/Docker-compose, AWS S3-compatible SDKs

---

## Project Directory Mapping

```text
cv-analyzer/
├── agents/                       # Extract and Normalize pipeline agents
│   ├── extract_agent.py          # Extracts raw text into structured JSON schema
│   └── normalize_agent.py        # Cleans noise, dedupes, caps sizes, formats sections
├── core/                         # Operational core of the FastAPI application
│   ├── config.py                 # Handles settings, secrets, and environment loading
│   ├── database.py               # SQL database connection pooling and sessions
│   ├── metrics.py                # Prometheus-compatible application metrics
│   ├── quota.py                  # Rate-limiting, billing boundaries, Redis hooks
│   └── security.py               # Request validation, CSRF, and CORS headers
├── routes/                       # FastAPI router modules (HTTP endpoints)
│   ├── ai_tools.py               # Auto-fix, AI rewrite, roadmaps, and custom tips
│   ├── analysis.py               # Upload endpoints, parsing, and history
│   ├── billing.py                # Subscription controls, Stripe callbacks, plans
│   ├── dashboard.py              # Recruiter lists, shared links, metrics, logs
│   ├── user_data.py              # User profiles, preferences, and data exports
│   └── worker.py                 # Offline local worker sync and candidate management
├── services/                     # Business logic and computations
│   ├── ats_scoring.py            # Keyword density, structure, layout rules
│   ├── ats_service.py            # Combines scoring rules and ML predictors
│   ├── cv_autofix_service.py     # Heading normalization, section floors, verb injection
│   ├── embedding_service.py      # OpenAI embedding calls and fallback mock logic
│   ├── language_service.py       # Sentence-level language detection
│   ├── pdf_text_extractor.py     # Handles fitz, pdfplumber, and raw parsing
│   ├── pipeline_runtime.py       # Main pipeline execution entry point
│   ├── rewrite_service.py        # OpenAI/Claude LLM resume rewriting wrappers
│   ├── schema_builder.py         # Converts raw extraction dict into validated schema
│   └── storage_service.py        # File upload logic (Local disk vs AWS S3 buckets)
├── frontend/                     # React Single Page Application (SPA)
│   ├── src/pages/                # Major views (Landing, Dashboard, Analyze, Recruiter)
│   ├── src/components/           # Reusable components (Navbar, Modal, Skeletons)
│   └── src/style.css             # Main styling, HSL colors, design tokens
├── mobile/                       # Expo-based React Native mobile workspace
├── security/                     # Encryption, sanitization, XSS, and replay guards
└── tests/                        # Comprehensive unit and regression test suite
```

---

## Environment Configuration

Copy the example configuration to begin local setup:

```bash
cp .env.example .env
```

Key configuration parameters inside `.env`:

```env
ENV=development
PORT=8001
MOCK_SERVICES=true
MOCK_DATABASE_URL=sqlite:///./mock_dev.db

# Production integrations (Uncomment and populate for cloud deployment)
# DATABASE_URL=postgresql://user:pass@host:5432/dbname
# REDIS_URL=redis://localhost:6379/0
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_JWT_SECRET=your-jwt-secret
# OPENAI_API_KEY=your-openai-api-key
# STRIPE_SECRET_KEY=your-stripe-secret-key
# S3_BUCKET_NAME=your-s3-bucket
```

---

## Installation & Quick Start

### FastAPI Backend Setup

1.  Create and activate a Python virtual environment:
    ```bash
    python -m venv .venv
    # Windows:
    .\.venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate
    ```
2.  Install required packages:
    ```bash
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    ```
3.  Launch the Uvicorn development server:
    ```bash
    python -m uvicorn main:app --host 127.0.0.1 --port 8001
    ```
4.  Access the OpenAPI documentation:
    [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

### React/Vite Frontend Setup

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install package dependencies:
    ```bash
    npm install
    ```
3.  Start the Vite development server:
    ```bash
    npm run dev
    ```
4.  Open the web application:
    [http://127.0.0.1:5173/](http://127.0.0.1:5173/) (Vite automatically proxies API calls to port `8001`).

---

## Testing & Quality Assurance

The codebase maintains strict stability rules. Both backend test suites and frontend builds must pass successfully before checking in code.

### Run Backend Tests

We utilize `pytest` to run our test suite, containing **over 790 unit and integration tests** verifying parser accuracy, scoring weight boundaries, tenant isolation, and security controls:

```bash
python -m pytest
```

### Validate Frontend Quality

Execute typechecks, unit tests, and production bundling from the `frontend/` directory:

```bash
npx tsc --noEmit
npm test
npm run build
```

---

## Multi-Agent UI Workflow

This repository utilizes a **Multi-Agent UI Design Workflow** to align codebase changes with design objectives. When modifying primary views (`LandingPage.jsx`, `DashboardPage.jsx`, `AnalyzePage.jsx`, `RecruiterPage.jsx`), modifications are routed through consecutive agent stages:

```mermaid
flowchart LR
  design["Product Designer Agent (SKILL.md)"] --> token["Design System Agent (SKILL.md)"]
  token --> motion["Motion Design Agent (Framer Motion)"]
  motion --> implement["Frontend Implementation Agent"]
  implement --> qa["QA Review Agent (Viewports & Access)"]
```

Refer to [AGENTS.md](file:///c:/Users/ASUS/Desktop/cv-analyzer/AGENTS.md) for full instructions, local Figma workspace configurations, and checklist rules.
