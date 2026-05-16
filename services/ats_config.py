import os
from typing import Dict


_DEFAULT_WEIGHTS: Dict[str, float] = {
    "skills": 0.35,
    "keywords": 0.25,
    "format": 0.15,
    "experience": 0.25,
}


_cached_weights: Dict[str, float] | None = None


def _parse_ats_config(path: str) -> Dict[str, float] | None:
    """Very small YAML reader for a weights: mapping.

    Supports the following minimal structure:

    weights:
      skills: 0.35
      keywords: 0.25
      format: 0.15
      experience: 0.25

    Any parsing error results in None so that callers can fall back to
    in-code defaults. This avoids introducing an external YAML parser
    dependency just for a simple config.
    """

    if not os.path.exists(path):
        return None

    weights: Dict[str, float] = {}
    in_weights = False

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("weights") and stripped.rstrip().endswith(":"):
                    in_weights = True
                    continue
                if not in_weights:
                    continue
                # Stop if we encounter a new top-level key
                if not line.startswith((" ", "\t")):
                    break
                # Parse "key: value" pairs
                parts = stripped.split(":", 1)
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                value_str = parts[1].split("#", 1)[0].strip()
                if not value_str:
                    continue
                try:
                    value = float(value_str)
                except ValueError:
                    continue
                weights[key] = value
    except Exception:
        return None

    return weights or None


def get_ats_weights() -> Dict[str, float]:
    """Return configured ATS dimension weights with safe defaults.

    Values are normalized so that their sum is > 0 and they remain
    numerically stable even if the config file is partially specified.
    """

    global _cached_weights
    if _cached_weights is None:
        path = os.getenv("ATS_CONFIG_PATH", "ats_config.yaml")
        loaded = _parse_ats_config(path)
        base = dict(_DEFAULT_WEIGHTS)
        if loaded:
            base.update({k: float(v) for k, v in loaded.items() if k in base})
        # Normalize to avoid extreme scaling if someone changes values
        total = sum(v for v in base.values() if v > 0)
        if total <= 0:
            _cached_weights = dict(_DEFAULT_WEIGHTS)
        else:
            _cached_weights = {k: float(v) / float(total) for k, v in base.items()}
    return dict(_cached_weights)
