import os
from typing import Dict


_DEFAULT_WEIGHTS: Dict[str, float] = {
    "skills": 0.35,
    "keywords": 0.25,
    "format": 0.15,
    "experience": 0.25,
}

_DEFAULT_LENGTH_PROFILE: Dict[str, float] = {
    "ideal_min_words": 250,
    "ideal_max_words": 1100,
    "extended_max_words": 1800,
    "very_long_max_words": 2600,
}

_cached_weights: Dict[str, float] | None = None
_cached_length_profile: Dict[str, float] | None = None


def _parse_numeric_section(path: str, section_name: str) -> Dict[str, float] | None:
    """Very small YAML reader for numeric top-level mappings.

    Supports the following minimal structure:

    weights:
      skills: 0.35
      keywords: 0.25
      format: 0.15
      experience: 0.25

    length_profile:
      ideal_min_words: 250
      ideal_max_words: 1100

    Any parsing error results in None so that callers can fall back to
    in-code defaults. This avoids introducing an external YAML parser
    dependency just for a simple config.
    """

    if not os.path.exists(path):
        return None

    values: Dict[str, float] = {}
    in_section = False

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith(section_name) and stripped.rstrip().endswith(":"):
                    in_section = True
                    continue
                if not in_section:
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
                values[key] = value
    except Exception:
        return None

    return values or None


def _parse_ats_config(path: str) -> Dict[str, float] | None:
    return _parse_numeric_section(path, "weights")


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


def get_ats_length_profile() -> Dict[str, float]:
    """Return configurable CV length thresholds measured in words."""

    global _cached_length_profile
    if _cached_length_profile is None:
        path = os.getenv("ATS_CONFIG_PATH", "ats_config.yaml")
        loaded = _parse_numeric_section(path, "length_profile")
        base = dict(_DEFAULT_LENGTH_PROFILE)
        if loaded:
            for key, value in loaded.items():
                if key in base and value > 0:
                    base[key] = float(value)

        ordered_keys = [
            "ideal_min_words",
            "ideal_max_words",
            "extended_max_words",
            "very_long_max_words",
        ]
        previous = 0.0
        stable = True
        for key in ordered_keys:
            if base[key] <= previous:
                stable = False
                break
            previous = base[key]
        _cached_length_profile = base if stable else dict(_DEFAULT_LENGTH_PROFILE)

    return dict(_cached_length_profile)
