import os

import pytest
from sqlalchemy import create_engine, text

POSTGRES_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb"
)


def test_postgres_connection():
    if os.getenv("RUN_EXTERNAL_DB_TESTS", "").lower() not in ("1", "true", "yes"):
        pytest.skip("external database smoke test is opt-in")

    engine = create_engine(POSTGRES_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
