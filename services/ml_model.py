"""Singleton ML model loader for ATS scoring.

Loads both score (regressor) and hire (classifier) models once on first
use.  Subsequent calls reuse the cached model objects.
"""

import logging
import os

import joblib
import numpy as np

logger = logging.getLogger("app.ml_model")

SCORE_MODEL_PATH = os.getenv("ATS_MODEL_PATH", "resume_model.pkl")
HIRE_MODEL_PATH = os.getenv("HIRE_MODEL_PATH", "hire_model.pkl")

_score_model = None
_hire_model = None


def health_check() -> dict:
    """Return model health status without loading models into memory.

    Checks file existence and basic readability for both models.
    Returns dict with "score_model" and "hire_model" status.
    """
    result = {}
    for name, path_str in [("score_model", SCORE_MODEL_PATH), ("hire_model", HIRE_MODEL_PATH)]:
        path = os.path.abspath(path_str)
        if not os.path.exists(path):
            result[name] = {"status": "missing", "path": path}
        else:
            try:
                size = os.path.getsize(path)
                if size < 100:
                    result[name] = {"status": "corrupt", "path": path, "size": size}
                else:
                    result[name] = {"status": "ok", "path": path, "size": size}
            except OSError as e:
                result[name] = {"status": "error", "path": path, "error": str(e)}
    return result


def get_score_model():
    """Return the cached XGBoost/RF score regressor."""
    global _score_model
    if _score_model is None:
        path = os.path.abspath(SCORE_MODEL_PATH)
        if not os.path.exists(path):
            logger.warning("Score model not found at %s — predictions will fail", path)
            raise FileNotFoundError(f"Score model not found: {path}")
        _score_model = joblib.load(path)
        logger.info("Score model loaded from %s", path)
    return _score_model


def get_hire_model():
    """Return the cached XGBoost/RF hire classifier."""
    global _hire_model
    if _hire_model is None:
        path = os.path.abspath(HIRE_MODEL_PATH)
        if not os.path.exists(path):
            logger.warning("Hire model not found at %s — using default probability", path)
            return None
        _hire_model = joblib.load(path)
        logger.info("Hire model loaded from %s", path)
    return _hire_model


def predict_score(features: list[float]) -> float:
    """Predict ATS score (0-100) from a 29-element feature vector.

    The model was trained on synthetic data so its raw output can be
    overly pessimistic on real CVs.  We blend the raw prediction toward
    the rule-based feature average so that the ML component acts as a
    corrective signal rather than the dominant score driver.
    """
    model = get_score_model()
    arr = np.array([features], dtype=np.float32)
    raw = float(model.predict(arr)[0])
    raw = max(0.0, min(100.0, raw))

    # Feature-average anchor: first 4 features are typically
    # semantic, keyword, skill, experience scores (each 0-100).
    core = [f for f in features[:4] if 0 <= f <= 100]
    anchor = sum(core) / len(core) if core else 50.0

    # Blend: 60% raw ML + 40% feature anchor to dampen synthetic bias
    blended = raw * 0.6 + anchor * 0.4
    return max(0.0, min(100.0, round(blended, 2)))


def predict_hire_proba(features: list[float]) -> tuple[bool, float]:
    """Predict hire decision and probability from a 29-element feature vector.

    Returns (hire_decision, hire_probability).
    """
    model = get_hire_model()
    if model is None:
        return False, 0.5

    arr = np.array([features], dtype=np.float32)
    decision = bool(model.predict(arr)[0])
    probability = 0.5
    if hasattr(model, "predict_proba"):
        probas = model.predict_proba(arr)[0]
        probability = float(probas[1]) if len(probas) > 1 else float(probas[0])
    return decision, round(probability, 3)
