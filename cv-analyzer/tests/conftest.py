"""
Professional test conftest.py
- Per-function isolated in-memory SQLite DB
- JWT mock (verify_supabase_jwt override)
- PyPDF2 mock (DummyPdfReader)
- Service stubs (model, embedding, domain, industry)
"""
import os
import sys
import types
import alembic.config
import alembic.command
# Ensure tests always have an API key for header-based tests
os.environ.setdefault("API_KEY", "test-key")
# Ensure MOCK_SERVICES is disabled so quota/rate-limit logic runs in tests
os.environ.setdefault("MOCK_SERVICES", "0")
# Disable background model worker during tests to avoid concurrency issues
os.environ.setdefault("MODEL_WORKER_DISABLED", "1")
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from models import User, Analysis, Organization  # ensure models are registered with Base


# ─── Stub heavy/external services BEFORE importing app ───
_service_stubs = [
    ("services.model_service", {
        "predict_match": lambda features: (80.0, 90.0, "Low Risk", {"note": "stub"}),
    }),
    ("services.embedding_service", {
        "get_embedding": lambda text: [0.01] * 1536,
        # Basic stub that returns candidate ids already present in DB (simple fallback for tests)
        "find_similar_candidates": (lambda db, vec, k=10: [(row[0], 0.1) for row in db.execute(text("SELECT id FROM candidates LIMIT :k"), {"k": k}).fetchall()]),
        "save_job_embedding": lambda db, jid, vec: True,
        "save_candidate_embedding": lambda db, cid, vec: True,
    }),
    ("services.domain_service", {
        "detect_or_create_domain": lambda j, e=None: {"domain_id": 1, "domain_name": "Other"},
        "get_domain_similarity": lambda i, e: 0.0,
    }),
    ("services.industry_service", {
        "detect_industry_and_specialization": lambda j, e=None: {
            "industry_id": 1, "industry_name": "Other",
            "specialization_id": 1, "specialization_name": "General",
        },
    }),
]

for mod_name, attrs in _service_stubs:
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[mod_name] = m
        parts = mod_name.split(".")
        if len(parts) > 1:
            parent, child = parts[0], parts[1]
            try:
                if parent in sys.modules:
                    setattr(sys.modules[parent], child, m)
            except Exception:
                pass

try:
    import importlib as _il
    _pkg = _il.import_module("services")
    for _mn, _ in _service_stubs:
        _p = _mn.split(".")
        if len(_p) > 1 and _mn in sys.modules:
            setattr(_pkg, _p[1], sys.modules[_mn])
except Exception:
    pass

# ─── PyPDF2 mock ───
_dummy_pypdf2 = types.ModuleType("PyPDF2")

class _DummyPage:
    def extract_text(self):
        return "Managed projects and increased revenue by 20%"

class _DummyPdfReader:
    def __init__(self, stream):
        self.pages = [_DummyPage()]

_dummy_pypdf2.PdfReader = _DummyPdfReader
sys.modules["PyPDF2"] = _dummy_pypdf2

# ─── Now safe to import app / DB ───
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base, get_db
from main import app
from auth import verify_supabase_jwt
from models import User, Analysis, Organization  # ensure models are registered with Base


# ─── Mock JWT ───
def _mock_verify_jwt(authorization: str = None):
    return {
        "user_id": "test-user-123",
        "email": "testuser@example.com",
        "payload": {"sub": "test-user-123"},
    }


# ─── DB URL used by all fixtures ───
_TEST_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")


# ─── Session-scoped: create DB tables ONCE for the entire test session ───
@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db_ready():
    """Create enum types and tables once; they persist for the whole session."""
    _engine = create_engine(_TEST_DB_URL)
    from sqlalchemy import text
    # Postgres ENUM types
    try:
        with _engine.begin() as conn:
            for sql in [
                "DO $$ BEGIN CREATE TYPE org_plan_type_enum AS ENUM ('free','pro','enterprise'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE org_billing_status_enum AS ENUM ('active','past_due','canceled','trialing'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE plan_type_enum AS ENUM ('free','pro','enterprise'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE billing_status_enum AS ENUM ('active','past_due','canceled','trialing'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
            ]:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
    except Exception:
        pass
    # Try Alembic first
    try:
        alembic_cfg = alembic.config.Config("alembic.ini")
        safe_url = _TEST_DB_URL.replace('%', '%%')
        alembic_cfg.set_main_option("sqlalchemy.url", safe_url)
        with _engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL)"))
            try:
                conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))
            except Exception:
                pass
        alembic.command.upgrade(alembic_cfg, "heads")
    except Exception:
        pass
    # Always create missing model tables from SQLAlchemy metadata
    Base.metadata.create_all(bind=_engine)
    yield
    # Final session cleanup
    try:
        Base.metadata.drop_all(bind=_engine)
    except Exception:
        pass


# ─── Per-function fixtures ───

@pytest.fixture(scope="function")
def db_session():
    """Fresh Postgres DB session for every test (tables already exist from session fixture)."""
    engine = create_engine(_TEST_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from sqlalchemy import text
    # Clean data for a fresh slate
    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analysis, app_users, organizations RESTART IDENTITY CASCADE"))
    except Exception:
        pass
    db = Session()
    try:
        yield db
    finally:
        db.close()
        # Clean data but keep tables for other tests
        try:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE analysis, app_users, organizations RESTART IDENTITY CASCADE"))
        except Exception:
            pass


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with DB + JWT overrides."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[verify_supabase_jwt] = _mock_verify_jwt

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def sample_texts():
    cv = (
        "John Doe\n"
        "Experience: Managed a team that increased revenue by 20%\n"
        "Skills: Python, SQL\n"
        "Contact: john@example.com"
    )
    job = (
        "Looking for a software engineer with experience in Python and SQL. "
        "Increase revenue and manage team."
    )
    return cv, job
