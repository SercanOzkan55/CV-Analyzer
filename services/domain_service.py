import json
import os

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

from services.embedding_service import get_embedding

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# when using psycopg2 directly, strip the SQLAlchemy prefix if present
def _clean_psycopg2_url(url):
    if url and url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


CLEAN_DB_URL = _clean_psycopg2_url(DATABASE_URL)

# Initialize OpenAI client conditionally
MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if MOCK_SERVICES_ON or not _OPENAI_KEY:
    client = None  # Will be checked in functions
else:
    client = OpenAI(api_key=_OPENAI_KEY)

DOMAIN_THRESHOLD = 0.70

ALLOWED_DOMAINS = [
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
]


# ==========================================================
# MAIN ENTRY
# ==========================================================
def detect_or_create_domain(job_text, embedding=None):
    # Allow mocking for testing without database
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return {"domain_id": 1, "domain_name": "Other"}

    if embedding is None:
        embedding = get_embedding(job_text)

    conn = psycopg2.connect(CLEAN_DB_URL)
    cur = conn.cursor()

    # 1️⃣ Try similarity match first
    cur.execute(
        """
        SELECT id, name, sample_count,
               1 - (centroid <=> %s::vector) AS similarity
        FROM domains
        ORDER BY centroid <=> %s::vector
        LIMIT 1;
    """,
        (embedding, embedding),
    )

    result = cur.fetchone()

    if result and result[3] is not None and result[3] >= DOMAIN_THRESHOLD:
        domain_id = result[0]
        domain_name = result[1]
        update_domain_centroid(cur, domain_id, embedding)

    else:
        # 2️⃣ Classify with LLM
        domain_name = classify_domain_llm(job_text)

        if domain_name not in ALLOWED_DOMAINS:
            domain_name = "Other"

        # 3️⃣ Check if domain already exists (avoid duplicate)
        cur.execute("SELECT id FROM domains WHERE name = %s;", (domain_name,))
        existing = cur.fetchone()

        if existing:
            domain_id = existing[0]
            update_domain_centroid(cur, domain_id, embedding)
        else:
            cur.execute(
                """
                INSERT INTO domains (name, centroid, sample_count)
                VALUES (%s, %s, 1)
                RETURNING id;
            """,
                (domain_name, embedding),
            )

            domain_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    return {
        "domain_id": domain_id,
        "domain_name": domain_name,
        "similarity": float(result[2]) if result else 0.0,
    }


# ==========================================================
# CENTROID UPDATE
# ==========================================================
def update_domain_centroid(cur, domain_id, embedding):

    cur.execute(
        "SELECT centroid, sample_count FROM domains WHERE id = %s;", (domain_id,)
    )

    row = cur.fetchone()
    if not row:
        return

    centroid, count = row

    # Fix string centroid issue
    if isinstance(centroid, str):
        centroid = json.loads(centroid)

    centroid = list(centroid)

    updated = [
        (float(c) * count + float(e)) / (count + 1) for c, e in zip(centroid, embedding)
    ]

    cur.execute(
        """
        UPDATE domains
        SET centroid = %s,
            sample_count = sample_count + 1
        WHERE id = %s;
    """,
        (updated, domain_id),
    )


# ==========================================================
# LLM DOMAIN CLASSIFICATION
# ==========================================================
def classify_domain_llm(job_text):
    # Allow mocking for testing without OpenAI API
    if MOCK_SERVICES_ON or not client:
        return "Engineering & Technology"  # Default mock domain

    prompt = f"""
You are a strict job domain classifier.

Return EXACTLY one of the following domains:

Engineering & Technology
Retail & Sales
Healthcare
Finance
Education
Logistics
Hospitality
Manufacturing
Construction
Creative & Media
Government
General Labor
Other

No explanation.
Only return one label.

Job Description:
{job_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    return response.choices[0].message.content.strip()


def get_domain_similarity(domain_id, embedding):
    # Allow mocking for testing without database
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return 0.85  # mock similarity score

    conn = psycopg2.connect(CLEAN_DB_URL)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 1 - (centroid <=> %s::vector)
        FROM domains
        WHERE id = %s;
    """,
        (embedding, domain_id),
    )

    result = cur.fetchone()
    conn.close()

    if result and result[0] is not None:
        return float(result[0]) * 100

    return 0.0
