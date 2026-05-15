import math
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
        if getattr(getattr(db, "bind", None), "dialect", None) and db.bind.dialect.name == "sqlite":
            cand.cv_embedding = json.dumps(embedding)
        else:
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
        if getattr(getattr(db, "bind", None), "dialect", None) and db.bind.dialect.name == "sqlite":
            job.job_embedding = json.dumps(embedding)
        else:
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
        return _find_similar_candidates_python(db, job_embedding, k)


def _coerce_embedding(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, tuple):
        return [float(item) for item in value]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [float(item) for item in parsed]
        except Exception:
            pass
        try:
            return [float(item.strip()) for item in raw.strip("[]").split(",") if item.strip()]
        except Exception:
            return None
    return None


def _cosine_similarity(left, right) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    lvec = left[:size]
    rvec = right[:size]
    dot = sum(a * b for a, b in zip(lvec, rvec))
    lnorm = math.sqrt(sum(a * a for a in lvec))
    rnorm = math.sqrt(sum(b * b for b in rvec))
    if not lnorm or not rnorm:
        return 0.0
    return dot / (lnorm * rnorm)


def _find_similar_candidates_python(db, job_embedding: list, k: int = 10):
    """Portable fallback for SQLite/test environments without pgvector."""
    try:
        from sqlalchemy import text

        query_vec = _coerce_embedding(job_embedding)
        if not query_vec:
            return []

        rows = db.execute(
            text("SELECT id, cv_embedding FROM candidates WHERE cv_embedding IS NOT NULL")
        ).fetchall()
        scored = []
        for row in rows:
            candidate_vec = _coerce_embedding(row[1])
            score = _cosine_similarity(query_vec, candidate_vec) if candidate_vec else 0.0
            scored.append((row[0], score))

        if not scored:
            rows = db.execute(text("SELECT id FROM candidates")).fetchall()
            scored = [(row[0], 0.0) for row in rows]

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: max(1, int(k or 10))]
    except Exception as exc:
        logger.error(f"find_similar_candidates python fallback error: {exc}")
        return []
