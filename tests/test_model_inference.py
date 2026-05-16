import hashlib
import json
import os

import joblib
import pytest


def load_metadata(path="model_metadata.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_model_file_hash_matches_metadata():
    meta = load_metadata()
    # v2 metadata nests under "score_model"; fall back to flat for v1
    if "score_model" in meta:
        model_path = meta["score_model"].get("path")
        expected = meta["score_model"].get("sha256")
    else:
        model_path = meta.get("path")
        expected = meta.get("sha256")
    assert model_path and expected
    assert os.path.exists(model_path)
    with open(model_path, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    assert h == expected


def test_deterministic_prediction():
    meta = load_metadata()
    n_features = meta.get("n_features", 9)

    # Build a deterministic feature vector matching the expected count
    base_features = [80, 70, 60, 50, 2, 0.1, 48.0, 42.0, 80.0]
    # Pad with realistic defaults for extra features added in v2/v3
    extra = [
        70.0, 5, 80.0, 85.0, 75.0, 90.0,  # layout features
        60.0, 40.0,                          # content features
        1, 1, 1, 1, 0,                       # section flags
        65.0, 70.0, 60.0,                    # job match
        50.0, 65.0, 40.0, 60.0,             # quality: soft_skill, readability, keyword_density, education_quality
    ]
    features = base_features + extra[:max(0, n_features - len(base_features))]
    features = features[:n_features]

    model = joblib.load("resume_model.pkl")

    if hasattr(model, "estimators_"):
        preds = [t.predict([features])[0] for t in model.estimators_]
        pred = float(sum(preds) / len(preds))
    else:
        pred = float(model.predict([features])[0])

    if 0.0 <= pred <= 1.0:
        pred *= 100.0

    # Score should be reasonable (good CV features → high score)
    assert 40.0 <= pred <= 100.0, f"Prediction {pred} out of reasonable range"
