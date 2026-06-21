"""ML Score Calibrator — runtime prediction from trained Ridge model.

Loads the trained model from models/score_calibrator.pkl and provides
a predict function that blends ML prediction with rule-based score.

Feature-flagged: ML_CALIBRATOR_ENABLED=1 to activate (default: 0).
"""

import json
import logging
import os
import pathlib
import pickle

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models"
_MODEL_PATH = _MODEL_DIR / "score_calibrator.pkl"

# Cache loaded model
_model_cache = None


def _load_model():
    """Load the trained model from disk (cached)."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not _MODEL_PATH.exists():
        logger.warning("ML calibrator model not found at %s", _MODEL_PATH)
        return None

    try:
        with open(_MODEL_PATH, "rb") as f:
            # The calibrator artifact is a local build-time model bundled with the app.
            _model_cache = pickle.load(f)  # nosec B301
        logger.info(
            "ML calibrator loaded: R²=%.4f, MAE=%.3f, n=%d",
            _model_cache["metrics"]["r2"],
            _model_cache["metrics"]["mae"],
            _model_cache["metrics"]["n_samples"],
        )
        return _model_cache
    except Exception as e:
        logger.error("Failed to load ML calibrator: %s", e)
        return None


def predict_calibrated_score(
    keyword_score: float,
    skill_score: float,
    ats_score: float,
    content_score: float,
    layout_score: float,
    missing_count: int,
    cv_length: int,
    jd_length: int,
) -> dict | None:
    """Predict calibrated score using the trained Ridge model.

    Returns:
        dict with 'ml_calibrated_score', 'confidence', 'model_metrics'
        or None if model is unavailable or disabled.
    """
    enabled = os.getenv("ML_CALIBRATOR_ENABLED", "0") in ("1", "true", "yes")
    if not enabled:
        return None

    model = _load_model()
    if model is None:
        return None

    try:
        features = np.array(
            [
                float(keyword_score),
                float(skill_score),
                float(ats_score),
                float(content_score),
                float(layout_score),
                int(missing_count),
                float(cv_length) / 1000.0,
                float(jd_length) / 1000.0,
            ]
        )

        # Ridge prediction: intercept + coefficients · features
        intercept = model["intercept"]
        coefficients = np.array(model["coefficients"])
        raw_pred = intercept + coefficients @ features
        prediction = float(np.clip(raw_pred, 0, 100))

        return {
            "ml_calibrated_score": round(prediction, 2),
            "model_r2": model["metrics"]["r2"],
            "model_mae": model["metrics"]["mae"],
            "model_loo_mae": model["metrics"]["loo_cv_mae"],
            "n_training_samples": model["metrics"]["n_samples"],
        }
    except Exception as e:
        logger.error("ML calibrator prediction failed: %s", e)
        return None


def blend_with_rule_score(
    rule_score: float,
    ml_result: dict | None,
    ml_blend_weight: float = 0.2,
) -> tuple[float, dict | None]:
    """Blend ML prediction with rule-based score.

    Returns (blended_score, ml_metadata).
    If ML is unavailable, returns (rule_score, None).

    The blend is conservative: ML gets only 20% weight by default,
    and is completely ignored if its prediction diverges too much
    from the rule-based score (> 15 points).
    """
    if ml_result is None:
        return rule_score, None

    ml_score = ml_result["ml_calibrated_score"]
    divergence = abs(rule_score - ml_score)

    # Safety: if ML diverges too much, don't blend
    max_divergence = float(os.getenv("ML_CALIBRATOR_MAX_DIVERGENCE", 15.0))
    if divergence > max_divergence:
        ml_result["blended"] = False
        ml_result["divergence"] = round(divergence, 2)
        ml_result["reason"] = "divergence_too_high"
        return rule_score, ml_result

    blended = rule_score * (1 - ml_blend_weight) + ml_score * ml_blend_weight
    blended = round(max(0.0, min(100.0, blended)), 2)

    ml_result["blended"] = True
    ml_result["divergence"] = round(divergence, 2)
    ml_result["blend_weight"] = ml_blend_weight
    ml_result["rule_score"] = round(rule_score, 2)
    ml_result["blended_score"] = blended

    return blended, ml_result
