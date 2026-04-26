from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# ── Schema / model version for cache invalidation ────────────────────────
# Bump this whenever schema structure changes to avoid stale cache hits.
# PARSER_VERSION is also folded into the key so canary traffic (v2) never
# serves a v1-produced cached render and vice versa.
SCHEMA_VERSION = os.getenv("SCHEMA_VERSION", "1").strip()
_PARSER_VERSION = os.getenv("PARSER_VERSION", "v1").strip().lower()

# In-memory cache — process-local by design.  In a multi-worker cluster
# each worker maintains its own cache; this avoids cross-process staleness.
# For shared caching, swap this dict for a Redis-backed store.
_RENDER_CACHE: dict[str, dict[str, Any]] = {}


def make_cache_key(payload: dict) -> str:
    versioned = {"_schema_v": SCHEMA_VERSION, "_parser_v": _PARSER_VERSION, **payload}
    return hashlib.sha256(
        json.dumps(versioned, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def get_cached(key: str):
    return _RENDER_CACHE.get(key)


def set_cached(key: str, value: dict):
    _RENDER_CACHE[key] = value
