import os
import pytest
from sqlalchemy import text


PG_URL = os.getenv("DATABASE_URL", "")


def make_vec(val, dim=1536):
    return "['" + ",".join([str(val)] * dim) + "']" if False else '[' + ','.join([str(val)] * dim) + ']'


@pytest.mark.skipif(not PG_URL or not PG_URL.startswith("postgresql"), reason="Postgres DB required for pgvector tests")
def test_pgvector_similarity(db_session):
    # Insert two candidates with simple repeated-value vectors
    v1 = make_vec(0.01)
    v2 = make_vec(0.02)
    q = make_vec(0.0105)

    # Use literal vector notation to avoid driver parameter quirks in test
    db_session.execute(text(f"INSERT INTO candidates (cv_text, cv_embedding) VALUES ('candA', '{v1}'::vector)"))
    db_session.execute(text(f"INSERT INTO candidates (cv_text, cv_embedding) VALUES ('candB', '{v2}'::vector)"))
    db_session.commit()

    res = db_session.execute(text(f"SELECT id, cv_text, ((cv_embedding::vector) <#> '{q}'::vector) AS score FROM candidates WHERE cv_embedding IS NOT NULL ORDER BY score LIMIT 5")).fetchall()
    assert len(res) >= 2
    # Lower score means more similar for cosine operator
    assert res[0][2] <= res[1][2]
