import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def _read_secret_file(path: str | None) -> str | None:
    """Read a connection URL from a Docker/OS-level secret file if provided.

    This lets production use DATABASE_URL_FILE while local dev/test can
    continue to rely on a plain .env DATABASE_URL.
    """

    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


DATABASE_URL = os.getenv("DATABASE_URL") or _read_secret_file(
    os.getenv("DATABASE_URL_FILE")
)
ENV = os.getenv("ENV", "development")

if not DATABASE_URL and ENV != "test":
    raise ValueError("DATABASE_URL environment variable not set")

# Clean up SQLAlchemy prefix if present (for psycopg2 compatibility)
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

# Environment-based engine configuration
from sqlalchemy.pool import StaticPool

# Skip database engine creation in mock mode to avoid connection attempts
if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
    # Create a dummy engine for mock mode
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif ENV == "test":
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
elif DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Test connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=False,  # Set to True for SQL debugging
    )

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

Base = declarative_base()


def get_db():
    """Yield a new SQLAlchemy Session and ensure it is closed after use.

    Use this function as a FastAPI dependency so that every request gets
    a fresh session that is cleaned up automatically.
    """
    # In mock mode, return a fake session to avoid database connections
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):

        class MockSession:
            def add(self, obj):
                pass

            def commit(self):
                pass

            def rollback(self):
                pass

            def refresh(self, obj):
                pass

            def query(self, model):
                return MockQuery()

            def execute(self, statement):
                return MockResult()

            def close(self):
                pass

        class MockQuery:
            def filter(self, *args):
                return self

            def first(self):
                return None

            def all(self):
                return []

            def order_by(self, *args):
                return self

        class MockResult:
            def fetchone(self):
                return None

            def fetchall(self):
                return []

        yield MockSession()
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
