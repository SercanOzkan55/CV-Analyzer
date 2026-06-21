import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv(encoding="utf-8-sig")


def _read_secret_file(path: str | None) -> str | None:
    """Read a connection URL from a Docker/OS-level secret file if provided."""

    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in ("1", "true", "yes")


ENV = os.getenv("ENV", "development")
_mock_mode = _truthy(os.getenv("MOCK_SERVICES")) and ENV.lower() not in (
    "production",
    "prod",
)
_mock_use_real_db = _truthy(os.getenv("MOCK_USE_REAL_DB"))
_raw_database_url = os.getenv("DATABASE_URL") or _read_secret_file(os.getenv("DATABASE_URL_FILE"))

if _mock_mode and not _mock_use_real_db:
    DATABASE_URL = os.getenv("MOCK_DATABASE_URL", "sqlite:///./mock_dev.db")
else:
    DATABASE_URL = _raw_database_url

if not DATABASE_URL and ENV != "test":
    raise ValueError("DATABASE_URL environment variable not set")

# Clean up SQLAlchemy prefix if present (for psycopg2 compatibility).
if DATABASE_URL and DATABASE_URL.startswith("postgresql+psycopg2://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1)

# Warn if the URL appears to point at a Supabase-managed database.
if DATABASE_URL and "supabase.com" in DATABASE_URL:
    import warnings

    warnings.warn(
        "DATABASE_URL is pointed at a Supabase host; confirm that this is the "
        "intended database. For local development consider running a "
        "standalone PostgreSQL instance and updating .env accordingly.",
        UserWarning,
    )

if ENV == "test" and not DATABASE_URL:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
elif DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    sqlite_kwargs = {"connect_args": {"check_same_thread": False}}
    if DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
        sqlite_kwargs["poolclass"] = StaticPool
    engine = create_engine(DATABASE_URL, **sqlite_kwargs)
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Yield a SQLAlchemy Session and ensure it is closed after use."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
