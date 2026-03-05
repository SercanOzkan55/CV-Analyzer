import logging
from dotenv import load_dotenv
load_dotenv()
import os
MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
import time
import os
import io
import json
import hmac
import hashlib
from datetime import datetime

from fastapi import FastAPI, Depends, Request, UploadFile, File, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
try:
    from prometheus_fastapi_instrumentator import Instrumentator
except Exception:
    Instrumentator = None

from sqlalchemy import text, select
from alembic.config import Config
from alembic.script import ScriptDirectory

from slowapi import Limiter
from slowapi.util import get_remote_address
try:
    from redis import Redis
except Exception:
    Redis = None
from limits.storage import RedisStorage

from services.embedding_service import get_embedding, find_similar_candidates, save_job_embedding, save_candidate_embedding
from services.scoring_service import calculate_similarity
from services.keyword_service import keyword_match_score
from services.skill_service import skill_coverage_score
from services.experience_service import experience_score
from services.model_service import predict_match
from services.recommendation_service import generate_recommendations
from services.industry_service import detect_industry_and_specialization
from services.domain_service import detect_or_create_domain, get_domain_similarity
from services.ats_service import analyze_cv
from services.tasks import celery_app, analyze_pdf_task

from database import engine, SessionLocal, get_db
from models import Analysis, User, Base, Organization, Candidate, Job
from auth import verify_supabase_jwt

# FastAPI docs hardening for production
if os.getenv("ENV", "dev") == "prod":
    app = FastAPI(docs_url=None, redoc_url=None)
else:
    app = FastAPI()

if Instrumentator:
    try:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except Exception:
        pass

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "https://yourdomain.com")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Serve repository files under /static for debugging (e.g. /static/main.py)
# Note: in production you may want to disable this or protect it behind an env var.
app.mount("/static", StaticFiles(directory=os.path.dirname(__file__)), name="static")

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

logger = logging.getLogger("app.access")

# Structured logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = int((time.time() - start) * 1000)
    # Try to extract user info if available
    user = None
    try:
        user = getattr(request.state, "user", None)
    except Exception:
        user = None
    user_id = None
    organization_id = None
    plan_type = None
    if user:
        user_id = getattr(user, "id", None) or user.get("user_id")
        organization_id = getattr(user, "organization_id", None) or user.get("organization_id")
        plan_type = getattr(user, "plan_type", None) or user.get("plan_type")
    log_payload = {
        "request_id": request.headers.get("X-Request-ID"),
        "user_id": user_id,
        "organization_id": organization_id,
        "plan_type": plan_type,
        "endpoint": request.url.path,
        "duration_ms": duration,
        "status_code": response.status_code,
    }
    logger.info("%s", json.dumps(log_payload, ensure_ascii=False))
    return response

# Health check endpoint
@app.get("/health")
def health_check(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return {"status": "fail"}, 503

# Readiness check endpoint
@app.get("/ready")
def readiness_check():
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()
        return {"migration_head": head, "status": "ready"}
    except Exception as e:
        return {"status": "fail", "error": str(e)}, 503

# NOTE: we used to call ``Base.metadata.create_all`` here to ensure the
# schema matched the models. With Alembic migrations in place that is no
# longer desirable (it can lead to drift and won't add/remove columns).
# In development you can still bootstrap the database by running
# ``python setup_db.py`` or ``alembic upgrade head``; this automatic call
# is intentionally disabled.


@app.on_event("startup")
def start_model_worker():
    try:
        # Allow tests to disable the worker without enabling MOCK_SERVICES
        if os.getenv("MODEL_WORKER_DISABLED"):
            return
        from services import model_worker
        model_worker.start()
    except Exception:
        pass


@app.on_event("shutdown")
def stop_model_worker():
    try:
        from services import model_worker
        model_worker.stop()
    except Exception:
        pass

# Redis connection for rate limiting
# Use a Redis URI string for limits.storage.RedisStorage (it expects a URI)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
if Redis:
    redis_rate = Redis(host='localhost', port=6379, db=1)
else:
    redis_rate = None

# Create limiter, but fall back to a no-op limiter if Redis/limits storage isn't available
try:
    limiter = Limiter(key_func=get_remote_address, storage=RedisStorage(redis_url))
except Exception:
    class NoopLimiter:
        def limit(self, limit_string):
            def decorator(func):
                return func
            return decorator
    limiter = NoopLimiter()

app.state.limiter = limiter

# When mocking (testing), allow unlimited requests; otherwise apply rate limits
def rate_limit(limit_string):
    """Conditional rate limiter: no-op in MOCK_SERVICES mode."""
    if MOCK_SERVICES_ON:
        # Return a no-op decorator that does nothing
        def noop_decorator(func):
            return func
        return noop_decorator
    else:
        # Return the real limiter
        return limiter.limit(limit_string)

MODEL_WEIGHT = float(os.getenv("MODEL_WEIGHT", 0.85))
ATS_WEIGHT = float(os.getenv("ATS_WEIGHT", 0.15))

# Plan-based quota mappings (configurable via env)
USER_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("USER_FREE_DAILY", "5")),
    "pro": int(os.getenv("USER_PRO_DAILY", "100")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_DAILY", "1000")),
}

USER_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("USER_FREE_MONTHLY", "20")),
    "pro": int(os.getenv("USER_PRO_MONTHLY", "500")),
    "enterprise": int(os.getenv("USER_ENTERPRISE_MONTHLY", "5000")),
}

ORG_PLAN_LIMITS_DAILY = {
    "free": int(os.getenv("ORG_FREE_DAILY", "50")),
    "pro": int(os.getenv("ORG_PRO_DAILY", "500")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_DAILY", "5000")),
}

ORG_PLAN_LIMITS_MONTHLY = {
    "free": int(os.getenv("ORG_FREE_MONTHLY", "500")),
    "pro": int(os.getenv("ORG_PRO_MONTHLY", "5000")),
    "enterprise": int(os.getenv("ORG_ENTERPRISE_MONTHLY", "50000")),
}

class AnalyzeRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    job_text: str | None = None

    def model_post_init(self, __context):
        if (not self.job_description) and self.job_text:
            self.job_description = self.job_text


# =====================================================
# USER MANAGEMENT
# =====================================================

def get_or_create_user(db, supabase_id: str, email: str):
    """
    Get existing user or create new one.
    Called on first API request from authenticated user.
    """
    user = db.query(User).filter(User.supabase_id == supabase_id).first()

    if not user:
        user = User(
            supabase_id=supabase_id,
            email=email,
            plan_type="free"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Domain-based auto role assignment: if user's email domain matches an
    # existing Organization, mark them as a recruiter and attach the org.
    try:
        domain = None
        if isinstance(email, str) and "@" in email:
            domain = email.split("@", 1)[1].lower()

        if domain:
            org = db.query(Organization).filter(Organization.domain == domain).first()
            if org and user.organization_id != org.id:
                user.role = "recruiter"
                user.organization_id = org.id
                db.add(user)
                db.commit()
                db.refresh(user)
    except Exception:
        # non-fatal: if org lookup fails, return the user as-is
        pass

    return user


def _ensure_not_expired(user_payload: dict):
    if isinstance(user_payload, dict) and user_payload.get("signature"):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = user_payload.get("payload") if isinstance(user_payload, dict) else None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if exp is None:
        return
    try:
        exp_ts = int(exp)
    except (TypeError, ValueError):
        return
    if exp_ts <= int(datetime.utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")


# =====================================================
# HELPERS
# =====================================================

def interpret_score(score):
    if score > 75:
        return "High Match"
    elif score > 50:
        return "Moderate Match"
    return "Low Match"


def build_features(
    semantic,
    keyword,
    skill,
    exp,
    missing_skills,
    domain_similarity,
    ats_score
):
    missing_count = len(missing_skills)
    total_required_skills = missing_count + max(1, int(skill / 20))
    missing_ratio = missing_count / total_required_skills

    semantic_skill_interaction = float(semantic * skill / 100)
    keyword_skill_interaction = float(keyword * skill / 100)

    # balance_score approximates how balanced semantic vs skill coverage is
    balance_score = float(max(0.0, 100.0 - abs(float(semantic) - float(skill))))

    return [
        float(semantic),
        float(keyword),
        float(skill),
        float(exp),
        int(missing_count),
        float(missing_ratio),
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score,
    ]


def run_pipeline(cv_text: str, job_description: str):
    # Basic input guards
    if not isinstance(cv_text, str):
        cv_text = ""
    if not isinstance(job_description, str):
        job_description = ""

    # Truncate extremely large inputs to avoid resource exhaustion
    MAX_CV_LEN = 200_000
    MAX_JOB_LEN = 100_000
    if len(cv_text) > MAX_CV_LEN:
        cv_text = cv_text[:MAX_CV_LEN]
    if len(job_description) > MAX_JOB_LEN:
        job_description = job_description[:MAX_JOB_LEN]

    cv_embedding = get_embedding(cv_text)
    job_embedding = get_embedding(job_description)

    # If embeddings fail, fall back to conservative defaults and mark
    embedding_failed = False
    if not cv_embedding or not job_embedding:
        semantic_score = 0.0
        embedding_failed = True
    else:
        try:
            semantic_score = calculate_similarity(cv_embedding, job_embedding) * 100
        except Exception:
            semantic_score = 0.0
    keyword_score = keyword_match_score(cv_text, job_description)

    skill_score, missing_skills = skill_coverage_score(
        cv_text,
        job_description
    )

    exp_score = experience_score(cv_text, job_description)

    # DOMAIN CREATE / FETCH
    domain_data = detect_or_create_domain(
        job_description,
        job_embedding
    )

    domain_similarity = get_domain_similarity(
        domain_data["domain_id"],
        job_embedding
    )

    # INDUSTRY + SPECIALIZATION
    industry_data = detect_industry_and_specialization(
        job_description,
        job_embedding
    )

    # ATS DETAILS (detailed breakdown)
    ats_details = analyze_cv(cv_text, job_description)
    ats_score = ats_details.get("overall_score", 0)

    # FEATURES
    features = build_features(
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_skills,
        domain_similarity,
        ats_score
    )

    try:
        prediction, confidence, risk_level, explanation = predict_match(features)
    except Exception as e:
        # If model runner failed, log and return conservative defaults
        print("Model prediction error:", str(e))
        prediction, confidence, risk_level, explanation = 50.0, 50.0, "High Risk", {"error": str(e)}

    recommendations = generate_recommendations(
        missing_skills,
        semantic_score,
        keyword_score
    )

    final_score = (prediction * MODEL_WEIGHT) + (ats_score * ATS_WEIGHT)
    final_score = round(float(final_score), 2)
    interpretation = interpret_score(final_score)

    # If embeddings failed for this request, apply conservative cap to avoid
    # manipulation via embedding failures. Also expose a flag for observability.
    if embedding_failed:
        capped = min(final_score, 40.0)
        if capped != final_score:
            final_score = capped
            interpretation = interpret_score(final_score)


    return {
        "semantic_score": round(semantic_score, 2),
        "keyword_score": keyword_score,
        "skill_score": skill_score,
        "experience_score": exp_score,
        "ats_score": ats_score,
        "ats": ats_details,
        "domain_similarity": round(domain_similarity, 2),
        "missing_skills": missing_skills,
        "final_score": final_score,
        "interpretation": interpretation,
        "confidence": float(confidence),
        "risk_level": risk_level,
        "explanation": explanation,
        "recommendations": recommendations,
        "domain": domain_data,
        "industry": industry_data,
        "specialization": {
            "id": industry_data["specialization_id"],
            "name": industry_data["specialization_name"]
        }
    }


# =====================================================
# TEXT ANALYZE
# =====================================================

@app.post("/api/v1/analyze")
@rate_limit("10/minute")
def analyze(
    request: Request,
    body: AnalyzeRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db)
):
    """
    Analyze CV against job description with JWT authentication.
    User must provide valid Supabase JWT token in Authorization header.
    """
    _ensure_not_expired(user)

    # In MOCK_SERVICES mode skip DB user creation and quota checks
    if MOCK_SERVICES_ON:
        result = run_pipeline(body.cv_text, body.job_description)
        return result

    # Get or create user in database
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # reset daily/monthly counters if a new UTC day/month has started
    now = datetime.utcnow()
    if db_user.last_reset is None or db_user.last_reset.date() < now.date():
        db_user.daily_usage = 0
        db_user.last_reset = now
    if db_user.updated_at is None or db_user.updated_at.month != now.month:
        db_user.monthly_usage = 0
        db_user.updated_at = now

    # enforce limits: individual users use their own quota; recruiters use org quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        # organization daily/monthly quota based on org.plan_type
        if org:
            org_daily_limit = ORG_PLAN_LIMITS_DAILY.get(org.plan_type or "free", ORG_PLAN_LIMITS_DAILY["free"])
            org_monthly_limit = ORG_PLAN_LIMITS_MONTHLY.get(org.plan_type or "free", ORG_PLAN_LIMITS_MONTHLY["free"])
            if (org.daily_usage or 0) >= org_daily_limit:
                raise HTTPException(status_code=403, detail="Organization daily limit reached")
            if (org.monthly_usage or 0) >= org_monthly_limit:
                raise HTTPException(status_code=403, detail="Organization monthly limit reached")
    else:
        # individual user quota using plan mapping
        user_daily_limit = USER_PLAN_LIMITS_DAILY.get(db_user.plan_type or "free", USER_PLAN_LIMITS_DAILY["free"])
        user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(db_user.plan_type or "free", USER_PLAN_LIMITS_MONTHLY["free"])
        if (db_user.daily_usage or 0) >= user_daily_limit:
            raise HTTPException(status_code=403, detail="Daily limit reached")
        if (db_user.monthly_usage or 0) >= user_monthly_limit:
            raise HTTPException(status_code=403, detail="Monthly limit reached")

    # Run analysis pipeline
    result = run_pipeline(body.cv_text, body.job_description)

    # Save analysis record linked to user
    analysis_record = Analysis(
        user_id=db_user.id,
        organization_id=db_user.organization_id,
        similarity_score=float(result["final_score"]),
        interpretation=result["interpretation"],
        confidence=float(result["confidence"]),
        risk_level=result["risk_level"],
        domain_id=int(result["domain"]["domain_id"]),
        industry_id=int(result["industry"]["industry_id"]),
        specialization_id=int(result["specialization"]["id"])
    )

    try:
        # increment counters now that the request is allowed
        if db_user.role == "recruiter" and db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
            if org:
                org.daily_usage = (org.daily_usage or 0) + 1
                org.monthly_usage = (org.monthly_usage or 0) + 1
                db.add(org)
        else:
            db_user.daily_usage = (db_user.daily_usage or 0) + 1
            db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
            db.add(db_user)

        db.add(analysis_record)
        db.commit()
        db.refresh(analysis_record)
    except Exception as e:
        db.rollback()
        print("DB INSERT ERROR:", str(e))
        raise

    # --- Auto-save candidate and its embedding for later semantic retrieval ---
    try:
        try:
            cv_embedding = get_embedding(body.cv_text)
        except Exception:
            cv_embedding = None
        cand = Candidate(
            organization_id=db_user.organization_id,
            cv_text=body.cv_text,
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)
        if cv_embedding:
            # Save embedding using helper (handles DB types)
            save_candidate_embedding(db, cand.id, cv_embedding)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return result


# =====================================================
# PDF ANALYZE
# =====================================================

@app.post("/api/v1/analyze-pdf")
@rate_limit("5/minute")
async def analyze_pdf(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = "",
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db)
):
    """
    Analyze PDF CV against job description with JWT authentication.
    User must provide valid Supabase JWT token in Authorization header.
    """
    from fastapi import HTTPException

    _ensure_not_expired(user)


    # In MOCK_SERVICES mode skip DB user creation and quota checks
    # Use the normalized boolean `MOCK_SERVICES_ON` so values like "0" don't
    # accidentally enable mock behaviour (string "0" is truthy).
    if MOCK_SERVICES_ON:
        contents = await file.read()
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        if len(contents) > 5_000_000:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
        result = run_pipeline(text, job_description)
        return result

    # Get or create user in database *before* running the pipeline
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # reset daily counter if a new day has started
    if db_user.last_reset is None or db_user.last_reset.date() < datetime.utcnow().date():
        db_user.daily_usage = 0
        db_user.last_reset = datetime.utcnow()


    # enforce limits: individual users use personal quota; recruiters use org monthly quota
    if db_user.role == "recruiter":
        org = None
        if db_user.organization_id:
            org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        if org and org.plan_type == "free" and org.monthly_usage >= ORG_PLAN_LIMITS_MONTHLY["free"]:
            raise HTTPException(status_code=429, detail="Organization monthly limit reached")
        # usage increment BEFORE parse
        if org:
            org.daily_usage = (org.daily_usage or 0) + 1
            org.monthly_usage = (org.monthly_usage or 0) + 1
            db.add(org)
            db.commit()
    else:
        if db_user.plan_type == "free" and db_user.daily_usage >= 5:
            raise HTTPException(status_code=429, detail="Daily quota exceeded")
        # usage increment BEFORE parse
        db_user.daily_usage = (db_user.daily_usage or 0) + 1
        db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
        db.add(db_user)
        db.commit()

    # Only after quota check and increment, read and parse file
    contents = await file.read()
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > 5_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    # Queue the analysis job (or run synchronously in LocalTask fallback)
    task = analyze_pdf_task.delay(text, job_description)

    # If the task ran synchronously (LocalTask), the wrapper returns a
    # DummyResult with `.status` and `.result` attributes — return the
    # actual analysis result immediately in that case for a better UX.
    try:
        if getattr(task, "status", None) == "SUCCESS" and hasattr(task, "result"):
            return task.result
    except Exception:
        pass

    return {"task_id": task.id, "status": "queued"}


# =====================================================
# HISTORY
# =====================================================

@app.get("/api/v1/history")
def get_history(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """
    Get analysis history for authenticated user with JWT.
    Returns user's own analyses only.
    """
    # Get or create user in database
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    
    # Return user's analysis records
    records = db.query(Analysis).filter(
        Analysis.user_id == db_user.id
    ).order_by(Analysis.id.desc()).all()
    
    return records


# =====================================================
# SEMANTIC SEARCH (job -> candidate retrieval)
# =====================================================


class SemanticSearchRequest(BaseModel):
    job_text: str | None = None
    job_id: int | None = None
    k: int = 10
    persist_job: bool = False


@app.post("/api/v1/semantic-search")
@rate_limit("20/minute")
def semantic_search(
    body: SemanticSearchRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db)
):
    _ensure_not_expired(user)

    # Require either job_text or job_id
    if not body.job_text and not body.job_id:
        raise HTTPException(status_code=400, detail="Provide job_text or job_id")

    # Resolve job embedding
    job_vec = None
    if body.job_id:
        job = db.query(Job).filter(Job.id == body.job_id).one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_vec = job.job_embedding
        if not job_vec:
            job_vec = get_embedding(job.raw_text or "")
            if job_vec:
                try:
                    save_job_embedding(db, job.id, job_vec)
                except Exception:
                    pass
    else:
        # job_text provided
        job_vec = get_embedding(body.job_text or "")
        if body.persist_job and job_vec:
            try:
                new_job = Job(raw_text=body.job_text, job_embedding=job_vec)
                db.add(new_job)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

    if not job_vec:
        raise HTTPException(status_code=500, detail="Failed to compute job embedding")

    # Find top-k similar candidates (returns list of (id, score))
    matches = find_similar_candidates(db, job_vec, k=body.k)
    candidate_ids = [m[0] for m in matches]

    # Fetch candidate rows preserving order
    candidates = []
    if candidate_ids:
        rows = db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).all()
        rows_map = {r.id: r for r in rows}
        for cid, score in matches:
            r = rows_map.get(cid)
            if r:
                candidates.append({
                    "id": r.id,
                    "cv_text": (r.cv_text[:200] + '...') if r.cv_text and len(r.cv_text) > 200 else r.cv_text,
                    "organization_id": r.organization_id,
                    "score": float(score)
                })

    return {"matches": candidates}

# =====================================================
# STRIPE WEBHOOK ENDPOINT
# =====================================================

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    """
    Stripe webhook endpoint for billing events.
    Verifies Stripe signature and processes event.
    In development (MOCK_SERVICES=true), signature validation is skipped for testing.
    """
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "test_secret")
    IS_TEST_MODE = MOCK_SERVICES_ON
    
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    
    try:
        event = json.loads(payload)
    except Exception as e:
        return {"error": f"Invalid JSON: {str(e)}"}, 400

    # Signature verification (skip in test mode)
    if not IS_TEST_MODE and STRIPE_WEBHOOK_SECRET != "test_secret":
        try:
            expected_sig = hmac.new(
                STRIPE_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
            ).hexdigest()
            if not sig_header or expected_sig not in sig_header:
                return {"error": "Invalid signature"}, 401
        except Exception as e:
            return {"error": f"Signature verification failed: {str(e)}"}, 400

    # Process event type
    event_type = event.get("type", "")
    data = event.get("data", {})
    
    if event_type == "customer.subscription.updated":
        # Extract Stripe customer ID and subscription details
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        status = obj.get("status")  # active, past_due, canceled, trialing
        
        if customer_id:
            # Update user or organization billing_status and stripe_customer_id
            try:
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                if user:
                    user.billing_status = status or "active"
                    db.add(user)
                    db.commit()
                else:
                    org = db.query(Organization).filter(Organization.stripe_customer_id == customer_id).first()
                    if org:
                        org.billing_status = status or "active"
                        db.add(org)
                        db.commit()
            except Exception as e:
                print(f"Error updating billing status: {str(e)}")
                db.rollback()

    elif event_type == "customer.subscription.deleted":
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        if customer_id:
            try:
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                if user:
                    user.billing_status = "canceled"
                    db.add(user)
                    db.commit()
                else:
                    org = db.query(Organization).filter(Organization.stripe_customer_id == customer_id).first()
                    if org:
                        org.billing_status = "canceled"
                        db.add(org)
                        db.commit()
            except Exception as e:
                print(f"Error canceling subscription: {str(e)}")
                db.rollback()

    return {"status": "success", "event_type": event_type}




# =====================================================
# RECRUITER DASHBOARD ENDPOINTS
# =====================================================

def recruiter_required(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Dependency: verify caller is a recruiter by checking DB record."""
    supabase_id = user.get("user_id")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")

    db_user = db.query(User).filter(User.supabase_id == supabase_id).first()
    if not db_user or db_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter role required")
    return db_user


@app.get("/api/v1/recruiter/candidates")
def recruiter_candidates(limit: int = 20, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    """Return recent candidate analyses for the recruiter's organization."""
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    # Find analyses belonging to users in the organization
    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
    records = (
        db.query(Analysis)
        .filter(Analysis.user_id.in_(select(users_subq.c.id)))
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )

    result = []
    for r in records:
        result.append({
            "analysis_id": getattr(r, "id", None),
            "user_id": getattr(r, "user_id", None),
            "similarity_score": getattr(r, "similarity_score", None),
            "interpretation": getattr(r, "interpretation", None),
            "confidence": getattr(r, "confidence", None),
            "risk_level": getattr(r, "risk_level", None),
            "domain_id": getattr(r, "domain_id", None),
            "industry_id": getattr(r, "industry_id", None),
            "specialization_id": getattr(r, "specialization_id", None),
            "created_at": getattr(r, "created_at", None),
        })

    return {"candidates": result}


@app.get("/api/v1/recruiter/top_candidates")
def recruiter_top_candidates(
    limit: int = 10,
    min_score: float = 0.0,
    start_date: str | None = None,
    end_date: str | None = None,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """Return top N candidates for recruiter's org ordered by score.

    Optional filters: `min_score`, `start_date` and `end_date` (ISO format).
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()

    query = db.query(Analysis).filter(Analysis.user_id.in_(select(users_subq.c.id)))

    # Apply score filter
    try:
        if min_score is not None:
            query = query.filter(Analysis.similarity_score >= float(min_score))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid min_score")

    # Date filters (expect ISO-8601 strings)
    from datetime import datetime as _dt

    if start_date:
        try:
            sd = _dt.fromisoformat(start_date)
            query = query.filter(Analysis.created_at >= sd)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format; expected ISO-8601")

    if end_date:
        try:
            ed = _dt.fromisoformat(end_date)
            query = query.filter(Analysis.created_at <= ed)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format; expected ISO-8601")

    records = query.order_by(Analysis.similarity_score.desc()).limit(limit).all()

    result = []
    for r in records:
        result.append({
            "analysis_id": getattr(r, "id", None),
            "user_id": getattr(r, "user_id", None),
            "final_score": getattr(r, "similarity_score", None),
            "interpretation": getattr(r, "interpretation", None),
            "created_at": getattr(r, "created_at", None),
        })

    return {"top_candidates": result}


@app.get("/api/v1/recruiter/candidate/{analysis_id}")
def recruiter_candidate_detail(analysis_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)):
    """Return full analysis detail for a single candidate (scoped to org)."""
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter has no organization")

    # Load analysis and ensure it belongs to a user in the org
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    user = db.query(User).filter(User.id == analysis.user_id).first()
    if not user or user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build response payload
    payload = {
        "analysis_id": getattr(analysis, "id", None),
        "user_id": getattr(analysis, "user_id", None),
        "final_score": getattr(analysis, "similarity_score", None),
        "interpretation": getattr(analysis, "interpretation", None),
        "confidence": getattr(analysis, "confidence", None),
        "risk_level": getattr(analysis, "risk_level", None),
        "domain_id": getattr(analysis, "domain_id", None),
        "industry_id": getattr(analysis, "industry_id", None),
        "specialization_id": getattr(analysis, "specialization_id", None),
        "created_at": getattr(analysis, "created_at", None),
        "raw": {"ats": getattr(analysis, "ats", None)}
    }

    return payload

@app.get("/api/v1/task-status/{task_id}")
def get_task_status(task_id: str):
    # If Celery isn't configured (tests or minimal env), return a safe response
    try:
        from celery.result import AsyncResult
    except Exception:
        return {"task_id": task_id, "status": "unavailable", "note": "Celery not configured"}

    if not celery_app:
        return {"task_id": task_id, "status": "unavailable", "note": "Celery backend not configured"}

    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    return response