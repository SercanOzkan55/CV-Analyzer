import os
import json
import sys
import hashlib
import threading
import time

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

load_dotenv(encoding="utf-8-sig")

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
_OPENAI_BASE = os.getenv("OPENAI_API_BASE")
client = OpenAI(api_key=_OPENAI_KEY, base_url=_OPENAI_BASE) if _OPENAI_KEY else None

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Embedding cache TTL (seconds). Defaults to 7 days.
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "604800"))

# ── Embedding rate limiting (process-local token bucket) ──────────────────
_EMBED_MAX_CALLS_PER_MIN = int(os.getenv("EMBED_MAX_CALLS_PER_MIN", "60"))
_EMBED_MAX_TOKENS_PER_REQ = int(os.getenv("EMBED_MAX_TOKENS_PER_REQ", "8000"))
_embed_call_times: list[float] = []
_embed_lock = threading.Lock()


def _embed_rate_ok() -> bool:
    """Return True if we haven't exceeded the per-minute call budget."""
    now = time.time()
    cutoff = now - 60
    with _embed_lock:
        # Prune old entries
        while _embed_call_times and _embed_call_times[0] < cutoff:
            _embed_call_times.pop(0)
        if len(_embed_call_times) >= _EMBED_MAX_CALLS_PER_MIN:
            return False
        _embed_call_times.append(now)
        return True


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

    # SAFE_MODE: skip embeddings entirely to reduce load
    if os.getenv("SAFE_MODE", "").lower() in ("1", "true", "yes"):
        logger.warning(json.dumps({"event": "embedding_skipped_safe_mode"}))
        return None

    # Circuit breaker: skip if OpenAI service is in open state
    try:
        from shared import _cb_is_open, _cb_record_failure, _cb_record_success
        if _cb_is_open("openai_embedding"):
            logger.warning(json.dumps({"event": "embedding_circuit_open"}))
            return None
        _cb_available = True
    except Exception:
        _cb_available = False

    # Security: rate limit embedding calls
    if not _embed_rate_ok():
        logger.warning(json.dumps({"event": "embedding_rate_limited"}))
        return None

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
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        embedding = response.data[0].embedding
        # Record success for circuit breaker
        if _cb_available:
            try:
                _cb_record_success("openai_embedding")
            except Exception:
                pass
        # Cache the embedding
        if redis_client:
            try:
                redis_client.setex(cache_key, EMBEDDING_CACHE_TTL, json.dumps(embedding))
            except Exception:
                # Cache failures must not break the main flow
                pass
        return embedding
    except Exception as e:
        # Record failure for circuit breaker
        if _cb_available:
            try:
                _cb_record_failure("openai_embedding")
            except Exception:
                pass
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


def find_similar_candidates(
    db,
    job_embedding: list,
    k: int = 10,
    organization_id: int | None = None,
):
    """Return top-k similar candidates for given job embedding.

    This uses Postgres `pgvector` cosine operator. The function executes
    a raw SQL query; depending on your DB driver you may need to adapt
    parameter passing (some drivers expect a Vector wrapper).
    Returns list of tuples (id, score).
    """
    try:
        from sqlalchemy import text

        # Validate all elements are numeric to prevent injection
        floats = [float(x) for x in job_embedding]
        vec_literal = "[" + ",".join(str(f) for f in floats) + "]"
        if organization_id is None:
            logger.warning("find_similar_candidates skipped: missing organization scope")
            return []
        sql = text(
            "SELECT id, (cv_embedding::vector <#> :vec::vector) AS score "
            "FROM candidates "
            "WHERE cv_embedding IS NOT NULL AND organization_id = :organization_id "
            "ORDER BY score LIMIT :k"
        )
        res = db.execute(
            sql,
            {"vec": vec_literal, "k": k, "organization_id": int(organization_id)},
        ).fetchall()
        return [(row[0], row[1]) for row in res]
    except Exception as e:
        logger.error(f"find_similar_candidates error: {e}")
        return []


def find_best_jobs_for_cv(db, cv_embedding: list, k: int = 10):
    """Return top-k most relevant jobs for a given CV embedding.

    Uses pgvector negative inner product operator (<#>).
    Returns list of tuples (job_id, score).
    """
    try:
        from sqlalchemy import text

        floats = [float(x) for x in cv_embedding]
        vec_literal = "[" + ",".join(str(f) for f in floats) + "]"
        sql = text(
            "SELECT id, (job_embedding::vector <#> :vec::vector) AS score "
            "FROM jobs WHERE job_embedding IS NOT NULL ORDER BY score LIMIT :k"
        )
        res = db.execute(sql, {"vec": vec_literal, "k": k}).fetchall()
        return [(row[0], row[1]) for row in res]
    except Exception as e:
        logger.error(f"find_best_jobs_for_cv error: {e}")
        return []


def index_cv(db, candidate_id: int, cv_text: str) -> bool:
    """Compute embedding for CV text and store it on the candidate record.

    Convenience wrapper: get_embedding → save_candidate_embedding.
    Returns True on success, False otherwise.
    """
    embedding = get_embedding(cv_text)
    if embedding is None:
        return False
    return save_candidate_embedding(db, candidate_id, embedding)


def index_job(db, job_id: int, job_text: str) -> bool:
    """Compute embedding for job description and store it on the job record.

    Convenience wrapper: get_embedding → save_job_embedding.
    Returns True on success, False otherwise.
    """
    embedding = get_embedding(job_text)
    if embedding is None:
        return False
    return save_job_embedding(db, job_id, embedding)
