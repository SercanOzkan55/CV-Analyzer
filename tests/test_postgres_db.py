import os

import pytest
from sqlalchemy import create_engine, text

POSTGRES_URL = os.getenv("POSTGRES_TEST_URL") or os.getenv("DATABASE_URL")


def test_postgres_connection():
    if os.getenv("RUN_POSTGRES_INTEGRATION", "").lower() not in ("1", "true", "yes"):
        pytest.skip("Set RUN_POSTGRES_INTEGRATION=1 and POSTGRES_TEST_URL to run this integration test")
    if not POSTGRES_URL:
        pytest.skip("POSTGRES_TEST_URL or DATABASE_URL is required for Postgres integration test")

    engine = create_engine(POSTGRES_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
