from openai import OpenAI
import os
from dotenv import load_dotenv
try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("app.embedding")
import sys
import json
try:
    import redis
except Exception:
    redis = None

# Redis connection (adjust host/port/db as needed)
if redis:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
else:
    redis_client = None

load_dotenv()

# Configure loguru for JSON structured logging when available
if hasattr(logger, "remove") and hasattr(logger, "add"):
    logger.remove()
    logger.add(sys.stdout, format="{message}", serialize=True, level="INFO")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=_OPENAI_KEY) if _OPENAI_KEY else None


def get_embedding(text: str, max_length: int = 20000):
    """Return embedding or None on error. Protect against overly large inputs.

    Returns a list of floats or None.
    """
    # Allow mocking for testing without OpenAI API
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return [0.01] * 1536  # mock embedding vector

    if not client:
        if hasattr(logger, "bind"):
            logger.bind(event="openai_client_not_configured").warning(json.dumps({"event": "openai_client_not_configured"}))
        else:
            logger.warning(json.dumps({"event": "openai_client_not_configured"}))
        return None

    # basic input length guard
    if not isinstance(text, str):
        return None
    if len(text) > max_length:
        text = text[:max_length]

    # Redis cache key
    cache_key = f"embedding:{hash(text)}"
    cached = None
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
        except Exception:
            cached = None
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        embedding = response.data[0].embedding
        # Cache the embedding
        if redis_client:
            try:
                redis_client.set(cache_key, json.dumps(embedding), ex=60*60*24)  # 1 day expiry
            except Exception:
                pass
        return embedding
    except Exception as e:
        if hasattr(logger, "bind"):
            logger.bind(event="embedding_fail", text_len=len(text)).exception(json.dumps({"event": "embedding_fail", "error": str(e), "text_len": len(text)}))
        else:
            try:
                logger.exception(json.dumps({"event": "embedding_fail", "error": str(e), "text_len": len(text)}))
            except Exception:
                logger.error(f"embedding_fail: {str(e)}")
        return None


def save_candidate_embedding(db, candidate_id: int, embedding: list):
    """Save a candidate embedding (expects a SQLAlchemy `Session`).

    Returns True on success, False otherwise.
    """
    try:
        # Import inside function to avoid circular imports
        from models import Candidate
        cand = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
        if not cand:
            return False
        cand.cv_embedding = embedding
        db.add(cand)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"save_candidate_embedding error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def save_job_embedding(db, job_id: int, embedding: list):
    """Save a job embedding (expects a SQLAlchemy `Session`)."""
    try:
        from models import Job
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            return False
        job.job_embedding = embedding
        db.add(job)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"save_job_embedding error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def find_similar_candidates(db, job_embedding: list, k: int = 10):
    """Return top-k similar candidates for given job embedding.

    This uses Postgres `pgvector` cosine operator. The function executes
    a raw SQL query; depending on your DB driver you may need to adapt
    parameter passing (some drivers expect a Vector wrapper).
    Returns list of tuples (id, score).
    """
    try:
        from sqlalchemy import text
        # Build a literal vector representation. We explicitly cast both the
        # stored column and the literal to `vector` to avoid driver/typing
        # coercion issues where parameters are treated as text.
        vec_literal = "[" + ",".join([str(float(x)) for x in job_embedding]) + "]"
        sql = text(
            "SELECT id, (cv_embedding::vector <#> '" + vec_literal + "'::vector) AS score "
            "FROM candidates WHERE cv_embedding IS NOT NULL ORDER BY score LIMIT :k"
        )
        res = db.execute(sql, {"k": k}).fetchall()
        return [(row[0], row[1]) for row in res]
    except Exception as e:
        logger.error(f"find_similar_candidates error: {e}")
        return []