import ast
import os

import psycopg2
from dotenv import load_dotenv

from .domain_service import detect_or_create_domain
from .embedding_service import get_embedding
from .naming_service import generate_primary_name, generate_specialization_name

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# helper to adapt for psycopg2


def _clean_psycopg2_url(url):
    if url and url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


CLEAN_DB_URL = _clean_psycopg2_url(DATABASE_URL)

INDUSTRY_THRESHOLD = 0.70
SPECIALIZATION_THRESHOLD = 0.80


# ==========================================================
# MAIN ENTRY (3 LEVEL)
# ==========================================================
def detect_industry_and_specialization(job_text, embedding=None):
    # Allow mocking for testing without database
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return {
            "industry_id": 1,
            "industry_name": "Technology",
            "specialization_id": 1,
            "specialization_name": "Software Development",
        }

    if embedding is None:
        embedding = get_embedding(job_text)

    conn = psycopg2.connect(CLEAN_DB_URL)
    cur = conn.cursor()

    # ===================== 1️⃣ DOMAIN =====================
    domain_data = detect_or_create_domain(job_text, embedding)
    domain_id = domain_data.get("domain_id")
    domain_name = domain_data.get("domain_name")

    # ===================== 2️⃣ INDUSTRY =====================
    cur.execute(
        """
        SELECT id, name, 1 - (centroid <=> %s::vector) AS similarity
        FROM industries
        WHERE domain_id = %s
        ORDER BY centroid <=> %s::vector
        LIMIT 1;
    """,
        (embedding, domain_id, embedding),
    )

    industry = cur.fetchone()

    if industry and industry[2] is not None and industry[2] >= INDUSTRY_THRESHOLD:
        industry_id = industry[0]
        industry_name = industry[1]
        update_industry_centroid(cur, industry_id, embedding)
    else:
        industry_name = generate_primary_name(job_text)

        cur.execute(
            """
            INSERT INTO industries (domain_id, name, centroid)
            VALUES (%s, %s, %s)
            RETURNING id;
        """,
            (domain_id, industry_name, embedding),
        )

        industry_id = cur.fetchone()[0]

    # ===================== 3️⃣ SPECIALIZATION =====================
    cur.execute(
        """
        SELECT id, name, 1 - (centroid <=> %s::vector) AS similarity
        FROM specializations
        WHERE industry_id = %s
        ORDER BY centroid <=> %s::vector
        LIMIT 1;
    """,
        (embedding, industry_id, embedding),
    )

    spec = cur.fetchone()

    if spec and spec[2] is not None and spec[2] >= SPECIALIZATION_THRESHOLD:
        specialization_id = spec[0]
        specialization_name = spec[1]
        update_specialization_centroid(cur, specialization_id, embedding)
    else:
        specialization_name = generate_specialization_name(job_text)

        cur.execute(
            """
            INSERT INTO specializations (industry_id, name, centroid)
            VALUES (%s, %s, %s)
            RETURNING id;
        """,
            (industry_id, specialization_name, embedding),
        )

        specialization_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    return {
        "domain_id": domain_id,
        "domain_name": domain_name,
        "industry_id": industry_id,
        "industry_name": industry_name,
        "specialization_id": specialization_id,
        "specialization_name": specialization_name,
    }


# ==========================================================
# CENTROID UPDATE FUNCTIONS
# ==========================================================
def update_industry_centroid(cur, industry_id, embedding):

    cur.execute(
        "SELECT centroid, sample_count FROM industries WHERE id = %s;", (industry_id,)
    )

    row = cur.fetchone()
    if not row:
        return

    centroid, count = row
    # Fix string centroid issue (some DB rows may store centroid as text)
    if isinstance(centroid, str):
        centroid = ast.literal_eval(centroid)
    centroid = list(centroid)

    updated = [
        (float(c) * count + float(e)) / (count + 1) for c, e in zip(centroid, embedding)
    ]

    cur.execute(
        """
        UPDATE industries
        SET centroid = %s,
            sample_count = sample_count + 1
        WHERE id = %s;
    """,
        (updated, industry_id),
    )


def update_specialization_centroid(cur, specialization_id, embedding):

    cur.execute(
        "SELECT centroid, sample_count FROM specializations WHERE id = %s;",
        (specialization_id,),
    )

    row = cur.fetchone()
    if not row:
        return

    centroid, count = row
    if isinstance(centroid, str):
        centroid = ast.literal_eval(centroid)
    centroid = list(centroid)

    updated = [
        (float(c) * count + float(e)) / (count + 1) for c, e in zip(centroid, embedding)
    ]

    cur.execute(
        """
        UPDATE specializations
        SET centroid = %s,
            sample_count = sample_count + 1
        WHERE id = %s;
    """,
        (updated, specialization_id),
    )
