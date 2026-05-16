"""ML Scoring Model — trains a lightweight Ridge Regression calibration layer.

This model learns optimal score weights from the benchmark dataset.
It takes existing rule-based scores (keyword, skill, exp, ats, semantic)
as features and predicts the ideal final_score.

Usage:
    python scripts/train_ml_model.py
    → saves model to models/score_calibrator.pkl

The model is optional and feature-flagged via ML_CALIBRATOR_ENABLED env var.
"""
import json
import pathlib
import pickle
import sys

import numpy as np

# Add project root to path
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATASET_PATH = ROOT / "tests" / "benchmark" / "benchmark_dataset.json"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "score_calibrator.pkl"


def load_benchmark_data():
    """Load benchmark entries and extract features + targets."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]
    features_list = []
    targets = []
    entry_ids = []

    for entry in entries:
        cv_text = entry.get("cv_text", "")
        jd = entry.get("job_description", "")
        expected = entry.get("expected", {})

        # Skip entries without JD (no final_score target)
        if not jd or not jd.strip():
            continue

        # Target: midpoint of expected range (our "ideal" score)
        fs_range = expected.get("final_score", {})
        if not fs_range:
            continue
        target = (fs_range["min"] + fs_range["max"]) / 2.0

        # Extract features by running the scoring pipeline
        try:
            from services.keyword_service import keyword_match_score
            from services.skill_service import skill_coverage_score
            from services.ats_service import analyze_cv

            keyword_score = keyword_match_score(cv_text, jd)
            skill_score, missing_skills = skill_coverage_score(cv_text, jd)

            # ATS details
            ats_details = analyze_cv(cv_text, jd)
            ats_score = ats_details.get("overall_score", 0)
            content_score = ats_details.get("content_score", 0)
            layout_score = ats_details.get("layout_score", 0)

            # Additional features
            missing_count = len(missing_skills)
            cv_len = len(cv_text)
            jd_len = len(jd)

            features = [
                keyword_score,
                skill_score,
                ats_score,
                content_score,
                layout_score,
                missing_count,
                cv_len / 1000.0,  # normalize
                jd_len / 1000.0,  # normalize
            ]

            features_list.append(features)
            targets.append(target)
            entry_ids.append(entry["id"])

        except Exception as e:
            print(f"  [SKIP] {entry['id']}: {e}")
            continue

    return np.array(features_list), np.array(targets), entry_ids


def train_model():
    """Train Ridge Regression calibration model."""
    print("=" * 60)
    print("  ML Score Calibrator — Training")
    print("=" * 60)

    print("\n[1/3] Loading benchmark data...")
    X, y, ids = load_benchmark_data()
    print(f"  Loaded {len(X)} entries with {X.shape[1]} features")

    if len(X) < 10:
        print("  ERROR: Not enough data to train. Need at least 10 entries.")
        return

    # Feature names for interpretability
    feature_names = [
        "keyword_score", "skill_score", "ats_score",
        "content_score", "layout_score", "missing_count",
        "cv_length_k", "jd_length_k",
    ]

    print("\n[2/3] Training Ridge Regression...")

    # Manual Ridge Regression (no sklearn dependency needed)
    # Ridge: w = (X^T X + alpha * I)^{-1} X^T y
    alpha = 1.0  # regularization strength

    # Add bias column
    ones = np.ones((X.shape[0], 1))
    X_bias = np.hstack([ones, X])

    # Solve Ridge
    I = np.eye(X_bias.shape[1])
    I[0, 0] = 0  # don't regularize intercept
    XtX = X_bias.T @ X_bias
    Xty = X_bias.T @ y
    weights = np.linalg.solve(XtX + alpha * I, Xty)

    intercept = weights[0]
    coefficients = weights[1:]

    # Predictions
    y_pred = X_bias @ weights
    y_pred = np.clip(y_pred, 0, 100)

    # Metrics
    residuals = y - y_pred
    mae = np.mean(np.abs(residuals))
    rmse = np.sqrt(np.mean(residuals ** 2))
    r2 = 1 - np.sum(residuals ** 2) / np.sum((y - np.mean(y)) ** 2)

    print(f"  MAE:  {mae:.2f}")
    print(f"  RMSE: {rmse:.2f}")
    print(f"  R²:   {r2:.4f}")

    print("\n  Feature weights:")
    for name, coef in zip(feature_names, coefficients):
        print(f"    {name:20s}: {coef:+.4f}")
    print(f"    {'intercept':20s}: {intercept:+.4f}")

    # Cross-validation (Leave-One-Out for small dataset)
    print("\n  Leave-One-Out Cross-Validation...")
    loo_errors = []
    for i in range(len(X)):
        X_train = np.delete(X_bias, i, axis=0)
        y_train = np.delete(y, i)
        w_cv = np.linalg.solve(X_train.T @ X_train + alpha * np.eye(X_bias.shape[1]), X_train.T @ y_train)
        w_cv_I = np.eye(X_bias.shape[1])
        w_cv_I[0, 0] = 0
        w_cv = np.linalg.solve(X_train.T @ X_train + alpha * w_cv_I, X_train.T @ y_train)
        pred = np.clip(X_bias[i] @ w_cv, 0, 100)
        loo_errors.append(abs(y[i] - pred))
    loo_mae = np.mean(loo_errors)
    print(f"  LOO-CV MAE: {loo_mae:.2f}")

    # Save model
    print("\n[3/3] Saving model...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model = {
        "type": "ridge_regression",
        "intercept": float(intercept),
        "coefficients": coefficients.tolist(),
        "feature_names": feature_names,
        "alpha": alpha,
        "metrics": {
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 4),
            "loo_cv_mae": round(loo_mae, 3),
            "n_samples": len(X),
        },
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    # Also save human-readable JSON
    json_path = MODEL_DIR / "score_calibrator_meta.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)

    print(f"  Saved to {MODEL_PATH}")
    print(f"  Metadata: {json_path}")
    print(f"\n{'=' * 60}")
    print(f"  DONE — R²={r2:.4f}, MAE={mae:.2f}, LOO-CV MAE={loo_mae:.2f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    train_model()
