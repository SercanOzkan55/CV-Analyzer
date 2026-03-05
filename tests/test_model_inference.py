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
    model_path = meta.get("path")
    expected = meta.get("sha256")
    assert model_path and expected
    assert os.path.exists(model_path)
    with open(model_path, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    assert h == expected


def test_deterministic_prediction():
    # A deterministic feature vector; keep in sync with services.model_runner expectations
    features = [80, 70, 60, 5, 2, 0.1, 75, 65, 70]
    model = joblib.load("resume_model.pkl")

    # Compute an ensemble mean if available, otherwise direct predict
    if hasattr(model, "estimators_"):
        preds = [t.predict([features])[0] for t in model.estimators_]
        pred = float(sum(preds) / len(preds))
    else:
        pred = float(model.predict([features])[0])

    # Expected value captured from a known-good run; tolerances allow tiny float drift
    expected_pred = 98.38457270286895
    assert pytest.approx(expected_pred, rel=1e-6) == pred
