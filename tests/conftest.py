"""
Professional test conftest.py
- Per-function isolated in-memory SQLite DB
- JWT mock (verify_supabase_jwt override)
- PyPDF2 mock (DummyPdfReader)
- Service stubs (model, embedding, domain, industry)
"""

import os
from pathlib import Path
import shutil
import sys
import types
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import alembic.command
import alembic.config

# Ensure tests always have an API key for header-based tests
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENV", "test")
# Ensure MOCK_SERVICES is disabled so quota/rate-limit logic runs in tests
os.environ.setdefault("MOCK_SERVICES", "0")
# Keep rewrite endpoints deterministic in local/CI tests even when a developer
# .env selects a real AI provider.
os.environ.setdefault("REWRITE_PROVIDER", "mock")
# Disable background model worker during tests to avoid concurrency issues
os.environ.setdefault("MODEL_WORKER_DISABLED", "1")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError


# ─── Stub heavy/external services BEFORE importing app ───
_service_stubs = [
    (
        "services.model_service",
        {
            "is_mock": lambda: os.getenv("MOCK_SERVICES", "1") == "1",
            "predict_hire": lambda features: (False, 0.5),
            "predict_match": lambda features: (
                50.0,
                50.0,
                "High Risk",
                {"mock": "test mode", "features_count": len(features)},
            ),
        },
    ),
    (
        "services.embedding_service",
        {
            "get_embedding": lambda text: [0.01] * 1536,
            # Basic stub that returns candidate ids already present in DB (simple fallback for tests)
            "find_similar_candidates": (
                lambda db, vec, k=10, organization_id=None: [
                    (row[0], 0.1)
                    for row in db.execute(
                        text("SELECT id FROM candidates LIMIT :k"), {"k": k}
                    ).fetchall()
                ]
            ),
            "save_job_embedding": lambda db, jid, vec: True,
            "save_candidate_embedding": lambda db, cid, vec: True,
            "EMBEDDING_CACHE_TTL": 604800,
            "_EMBED_MAX_CALLS_PER_MIN": 60,
        },
    ),
    (
        "services.domain_service",
        {
            "detect_or_create_domain": lambda j, e=None: {
                "domain_id": 1,
                "domain_name": "Other",
            },
            "get_domain_similarity": lambda i, e: 0.0,
            "ALLOWED_DOMAINS": [
                "Engineering & Technology",
                "Retail & Sales",
                "Healthcare",
                "Finance",
                "Education",
                "Logistics",
                "Hospitality",
                "Manufacturing",
                "Construction",
                "Creative & Media",
                "Government",
                "General Labor",
                "Other",
            ],
        },
    ),
    (
        "services.industry_service",
        {
            "detect_industry_and_specialization": lambda j, e=None: {
                "industry_id": 1,
                "industry_name": "Technology",
                "specialization_id": 1,
                "specialization_name": "Software Development",
            },
        },
    ),
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
        content = b""
        try:
            if hasattr(stream, "read"):
                pos = stream.tell()
                content = stream.read()
                stream.seek(pos)
            else:
                content = bytes(stream)
        except Exception:
            pass
        if b"not a real parseable pdf" in content or b"broken" in content:
            raise Exception("EOF marker not found")
        self.pages = [_DummyPage()]


_dummy_pypdf2.PdfReader = _DummyPdfReader
sys.modules["PyPDF2"] = _dummy_pypdf2

# ─── Now safe to import app / DB ───
import pytest

from auth import verify_supabase_jwt
from database import Base, get_db
from main import app
import main as main_module

main_module.RATE_LIMIT_ENABLED = False
# Disable IP-level global rate limit for tests (avoids 429 cascade across tests)
main_module._IP_GLOBAL_LIMIT_PER_MIN = 0
# Disable abuse protection for tests (fingerprint accumulation causes false 429s)
main_module.ABUSE_PROTECTION_ENABLED = False
# Disable CPU guard for tests (test runner itself pushes CPU to 100%)
main_module._CPU_USAGE_LIMIT = 100.0


# ─── Mock JWT ───
def _mock_verify_jwt(authorization: str = None):
    return {
        "user_id": "test-user-123",
        "email": "testuser@example.com",
        "payload": {"sub": "test-user-123"},
    }


# ─── DB URL used by all fixtures ───
_TEST_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb"
)
_FALLBACK_SQLITE_URL = f"sqlite:///./.pytest_test_{os.getpid()}.db"
_ACTIVE_TEST_DB_URL = _TEST_DB_URL


def _is_sqlite_url(db_url: str) -> bool:
    return str(db_url).startswith("sqlite")


# ─── Session-scoped: create DB tables ONCE for the entire test session ───
@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db_ready():
    """Create enum types and tables once; they persist for the whole session."""
    global _ACTIVE_TEST_DB_URL

    _engine = None
    try:
        _engine = create_engine(_TEST_DB_URL)
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _ACTIVE_TEST_DB_URL = _TEST_DB_URL
    except Exception:
        # If Postgres is not reachable in local/dev CI, run tests with SQLite.
        _ACTIVE_TEST_DB_URL = _FALLBACK_SQLITE_URL
        _engine = create_engine(
            _ACTIVE_TEST_DB_URL,
            connect_args={"check_same_thread": False},
        )

    # Postgres ENUM types
    if not _is_sqlite_url(_ACTIVE_TEST_DB_URL):
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
            safe_url = _ACTIVE_TEST_DB_URL.replace("%", "%%")
            alembic_cfg.set_main_option("sqlalchemy.url", safe_url)
            with _engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL)"
                    )
                )
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
                        )
                    )
                except Exception:
                    pass
            alembic.command.upgrade(alembic_cfg, "heads")
        except Exception:
            pass

    # SQLite fallback uses a file so app/TestClient connections share state.
    # Start each test session from an empty schema in case a prior run crashed.
    if _is_sqlite_url(_ACTIVE_TEST_DB_URL):
        try:
            Base.metadata.drop_all(bind=_engine)
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
def tmp_path():
    """Workspace-local tmp_path replacement for sandboxed Windows test runs."""
    base = Path.cwd() / "test_tmp"
    path = base / f"tmp_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            base.rmdir()
        except OSError:
            pass


@pytest.fixture(scope="function")
def db_session():
    """Fresh Postgres DB session for every test (tables already exist from session fixture)."""
    if _is_sqlite_url(_ACTIVE_TEST_DB_URL):
        engine = create_engine(
            _ACTIVE_TEST_DB_URL,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(_ACTIVE_TEST_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from sqlalchemy import text

    # Clean data for a fresh slate
    if _is_sqlite_url(_ACTIVE_TEST_DB_URL):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "TRUNCATE TABLE analysis, app_users, organizations RESTART IDENTITY CASCADE"
                    )
                )
        except Exception:
            pass
    db = Session()
    try:
        yield db
    finally:
        db.close()
        # Clean data but keep tables for other tests
        if not _is_sqlite_url(_ACTIVE_TEST_DB_URL):
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "TRUNCATE TABLE analysis, app_users, organizations RESTART IDENTITY CASCADE"
                        )
                    )
            except Exception:
                pass


@pytest.fixture(scope="function")
def db(db_session):
    """Backward-compatible alias for integration tests that request `db`."""
    return db_session


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
        if _is_sqlite_url(_ACTIVE_TEST_DB_URL):
            Base.metadata.create_all(bind=db_session.get_bind())
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


@pytest.fixture(scope="function")
def recruiter_user(db_session):
    """Create a recruiter user that matches the default mocked JWT subject."""
    from models import Organization, User

    org = Organization(
        name="Test Organization",
        domain=f"test-{uuid.uuid4().hex[:8]}.example.com",
        plan_type="pro",
        billing_status="active",
    )
    db_session.add(org)
    db_session.commit()

    user = User(
        supabase_id="test-user-123",
        email="testuser@example.com",
        organization_id=org.id,
        role="recruiter",
        plan_type="pro",
        billing_status="active",
    )
    db_session.add(user)
    db_session.commit()

    return {
        "user_id": user.id,
        "supabase_id": user.supabase_id,
        "email": user.email,
        "organization_id": user.organization_id,
        "org": org,
        "token": "mock-jwt-token",
    }


@pytest.fixture(scope="function")
def test_job(db_session, recruiter_user):
    """Create a recruiter job owned by the shared recruiter fixture."""
    from models import RecruiterJob

    job = RecruiterJob(
        title="Senior Python Developer",
        description="Looking for experienced Python developer with FastAPI experience",
        organization_id=recruiter_user["organization_id"],
        created_by=recruiter_user["user_id"],
    )
    db_session.add(job)
    db_session.commit()

    return job
