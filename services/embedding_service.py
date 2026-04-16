import os
import json
import sys
import hashlib

from dotenv import load_dotenv
from openai import OpenAI

try:
    from loguru import logger
except Exception:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("app.embedding")

try:
    import redis
except Exception:
    redis = None

load_dotenv()

# Redis connection (adjust host/port/db as needed). Use REDIS_URL when
# available to stay consistent with the rest of the app.
if redis:
    _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from redis import Redis as _RedisClient

        redis_client = _RedisClient.from_url(
            _redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_client.ping()
    except Exception:
        redis_client = None
else:
    redis_client = None

# Configure loguru for JSON structured logging when available
if hasattr(logger, "remove") and hasattr(logger, "add"):
    logger.remove()
    logger.add(sys.stdout, format="{message}", serialize=True, level="INFO")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=_OPENAI_KEY) if _OPENAI_KEY else None

# Embedding cache TTL (seconds). Defaults to 7 days.
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "604800"))


def _text_hash(text: str) -> str:
    """Stable SHA-256 hash for cache keys.

    Python's built-in hash() is process-dependent; SHA-256 ensures
    deterministic keys across restarts and workers.
    """

    if not isinstance(text, str):
        text = str(text or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_embedding(text: str, max_length: int = 20000):
    """Return embedding or None on error. Protect against overly large inputs.

    Returns a list of floats or None.
    """
    # Allow mocking for testing without OpenAI API
    if os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes"):
        return [0.01] * 1536  # mock embedding vector

    if not client:
        if hasattr(logger, "bind"):
            logger.bind(event="openai_client_not_configured").warning(
                json.dumps({"event": "openai_client_not_configured"})
            )
        else:
            logger.warning(json.dumps({"event": "openai_client_not_configured"}))
        return None

    # basic input length guard
    if not isinstance(text, str):
        return None
    if len(text) > max_length:
        text = text[:max_length]

    # Redis cache key based on stable SHA-256 hash of the text
    cache_key = f"embedding:{_text_hash(text)}"
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
            # If cache is corrupted, ignore and compute a fresh embedding
            pass

    try:
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        embedding = response.data[0].embedding
        # Cache the embedding
        if redis_client:
            try:
                redis_client.setex(cache_key, EMBEDDING_CACHE_TTL, json.dumps(embedding))
            except Exception:
                # Cache failures must not break the main flow
                pass
        return embedding
    except Exception as e:
        if hasattr(logger, "bind"):
            logger.bind(event="embedding_fail", text_len=len(text)).exception(
                json.dumps(
                    {"event": "embedding_fail", "error": str(e), "text_len": len(text)}
                )
            )
        else:
            try:
                logger.exception(
                    json.dumps(
                        {
                            "event": "embedding_fail",
                            "error": str(e),
                            "text_len": len(text),
                        }
                    )
                )
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
            "SELECT id, (cv_embedding::vector <#> '"
            + vec_literal
            + "'::vector) AS score "
            "FROM candidates WHERE cv_embedding IS NOT NULL ORDER BY score LIMIT :k"
        )
        res = db.execute(sql, {"k": k}).fetchall()
        return [(row[0], row[1]) for row in res]
    except Exception as e:
        logger.error(f"find_similar_candidates error: {e}")
        return []
