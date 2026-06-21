"""
CV-ATS Model Training Pipeline
===============================
Trains two models:
  1. score_model  — XGBoost regressor  → predicts ATS score (0-100)
  2. hire_model   — XGBoost classifier → predicts hire probability (0/1)

Feature vector (29 features) matches build_features() in main.py.
"""

import argparse
import hashlib
import json
import os
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
    r2_score,
)
from sklearn.model_selection import train_test_split, cross_val_score

try:
    from xgboost import XGBRegressor, XGBClassifier

    USE_XGBOOST = True
except ImportError:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    USE_XGBOOST = False
    print("⚠ xgboost not installed, falling back to RandomForest")

# ── Feature names (must match build_features() in main.py) ──────────────

FEATURE_NAMES = [
    # Core matching scores (0-100)
    "semantic",
    "keyword",
    "skill",
    "experience",
    # Skill gap
    "missing_count",
    "missing_ratio",
    # Interactions
    "semantic_skill_interaction",
    "keyword_skill_interaction",
    "balance_score",
    # ATS layout features (0-100)
    "bullet_score",
    "section_count",
    "section_presence_score",
    "formatting_score",
    "length_score",
    "contact_score",
    # ATS content features (0-100)
    "action_verb_score",
    "achievement_score",
    # Layout presence flags (0 or 1)
    "has_summary",
    "has_skills",
    "has_experience",
    "has_education",
    "has_projects",
    # Job match features
    "domain_similarity",
    "title_match",
    "seniority_match",
    # New quality features (0-100)
    "soft_skill_score",
    "readability_score",
    "keyword_density",
    "education_quality",
]

N_FEATURES = len(FEATURE_NAMES)

# ── Synthetic data generation ────────────────────────────────────────────


def _clamp(v, lo=0.0, hi=100.0):
    return float(np.clip(v, lo, hi))


def generate_cv_sample(profile: str, rng: np.random.Generator):
    """Generate a single synthetic CV feature vector + target score.

    profile: 'good', 'medium', 'bad', 'student', or 'senior'
    — controls the score distribution.
    """
    if profile == "good":
        base = rng.uniform(65, 95)
        layout_base = rng.uniform(70, 100)
    elif profile == "medium":
        base = rng.uniform(35, 70)
        layout_base = rng.uniform(40, 80)
    elif profile == "student":
        base = rng.uniform(25, 60)
        layout_base = rng.uniform(50, 85)
    elif profile == "senior":
        base = rng.uniform(70, 98)
        layout_base = rng.uniform(75, 100)
    else:  # bad
        base = rng.uniform(5, 40)
        layout_base = rng.uniform(10, 50)

    noise = lambda scale=8: rng.normal(0, scale)  # noqa: E731

    # Core scores
    semantic = _clamp(base + noise())
    keyword = _clamp(base * 0.9 + noise())
    skill = _clamp(base * 1.05 + noise())
    if profile == "student":
        exp = _clamp(base * 0.5 + noise(15))
    elif profile == "senior":
        exp = _clamp(base * 1.1 + noise(8))
    else:
        exp = _clamp(base * 0.85 + noise(12))

    # Skill gap
    total_required = rng.integers(5, 16)
    if profile in ("good", "senior"):
        missing_count = rng.integers(0, max(1, int(total_required * 0.3)))
    elif profile in ("medium", "student"):
        missing_count = rng.integers(1, max(2, int(total_required * 0.6)))
    else:
        missing_count = rng.integers(int(total_required * 0.4), total_required + 1)
    missing_ratio = missing_count / total_required

    # Interactions
    semantic_skill = semantic * skill / 100
    keyword_skill = keyword * skill / 100
    balance = max(0.0, 100.0 - abs(semantic - skill))

    # ATS layout
    bullet_score = _clamp(layout_base + noise())
    section_count = int(np.clip(rng.normal(5 if profile != "bad" else 3, 1.5), 1, 8))
    section_presence = _clamp(layout_base * 0.95 + noise(5))
    formatting = _clamp(layout_base + noise(6))
    length_score = _clamp(layout_base * 0.9 + noise(10))
    contact_score = _clamp(layout_base * 1.05 + noise(5))

    # ATS content
    action_verb = _clamp(base * 0.85 + noise(10))
    achievement = _clamp(base * 0.7 + noise(12))

    # Layout presence (correlated with profile quality)
    p_section = {
        "good": 0.92,
        "medium": 0.7,
        "bad": 0.4,
        "student": 0.65,
        "senior": 0.95,
    }[profile]
    has_summary = int(rng.random() < p_section)
    has_skills = int(rng.random() < p_section * 1.05)
    has_experience = int(rng.random() < min(1.0, p_section * 1.1))
    has_education = int(rng.random() < p_section)
    has_projects = int(rng.random() < p_section * 0.7)

    # Job match
    domain_sim = _clamp(base * 0.8 + noise(15))
    title_match = _clamp(base * 0.75 + noise(15))
    seniority_match = _clamp(base * 0.7 + noise(20))

    # ── New quality features ─────────────────────────────────────────
    # soft_skill_score: how many soft-skill keywords present
    if profile == "senior":
        soft_skill_score = _clamp(rng.uniform(50, 95) + noise(8))
    elif profile in ("good", "medium"):
        soft_skill_score = _clamp(base * 0.8 + noise(12))
    elif profile == "student":
        soft_skill_score = _clamp(rng.uniform(20, 60) + noise(10))
    else:
        soft_skill_score = _clamp(rng.uniform(0, 35) + noise(10))

    # readability_score: vocabulary richness / sentence structure
    readability_score = _clamp(layout_base * 0.85 + noise(10))

    # keyword_density: keyword spread across sections (not concentrated)
    keyword_density = _clamp(keyword * 0.6 + noise(15))

    # education_quality: degree level weighting
    edu_map = {
        "senior": rng.choice([60, 80, 100], p=[0.25, 0.45, 0.30]),
        "good": rng.choice([40, 60, 80, 100], p=[0.1, 0.3, 0.4, 0.2]),
        "medium": rng.choice([20, 40, 60, 80], p=[0.15, 0.35, 0.35, 0.15]),
        "student": rng.choice([40, 60], p=[0.4, 0.6]),
        "bad": rng.choice([0, 20, 40], p=[0.3, 0.5, 0.2]),
    }
    education_quality = float(edu_map[profile])

    features = [
        semantic,
        keyword,
        skill,
        exp,
        int(missing_count),
        missing_ratio,
        semantic_skill,
        keyword_skill,
        balance,
        bullet_score,
        section_count,
        section_presence,
        formatting,
        length_score,
        contact_score,
        action_verb,
        achievement,
        has_summary,
        has_skills,
        has_experience,
        has_education,
        has_projects,
        domain_sim,
        title_match,
        seniority_match,
        soft_skill_score,
        readability_score,
        keyword_density,
        education_quality,
    ]

    # ── Target score (realistic non-linear) ──────────────────────────────
    target = (
        semantic * 0.18
        + keyword * 0.10
        + skill * 0.16
        + exp * 0.07
        - missing_ratio * 22
        + bullet_score * 0.04
        + section_presence * 0.03
        + formatting * 0.03
        + action_verb * 0.05
        + achievement * 0.04
        + has_summary * 3
        + has_skills * 2
        + has_experience * 4
        + has_education * 2
        + domain_sim * 0.05
        + title_match * 0.04
        + seniority_match * 0.03
        + soft_skill_score * 0.04
        + readability_score * 0.03
        + keyword_density * 0.02
        + education_quality * 0.03
        + (semantic * skill / 300)  # non-linear interaction
        + rng.normal(0, 2.5)  # realistic noise
    )
    target = _clamp(target)

    return features, target


def generate_dataset(
    n_good=1000,
    n_medium=1000,
    n_bad=1000,
    n_student=500,
    n_senior=500,
    seed=42,
):
    rng = np.random.default_rng(seed)
    X, y = [], []

    for profile, count in [
        ("good", n_good),
        ("medium", n_medium),
        ("bad", n_bad),
        ("student", n_student),
        ("senior", n_senior),
    ]:
        for _ in range(count):
            feats, target = generate_cv_sample(profile, rng)
            X.append(feats)
            y.append(target)

    return np.array(X), np.array(y)


def load_dataset_from_csv(path, hire_threshold=65):
    """Load training data from a CSV file.

    Required columns:
      - all feature names listed in FEATURE_NAMES

    Optional target columns:
      - score: regression target for ATS score prediction
      - hire: binary label (0/1) for hire classifier

    If `hire` is absent but `score` is provided, the hire labels are
    derived by thresholding `score >= hire_threshold`.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV dataset not found: {path}")

    df = pd.read_csv(path)
    missing = [f for f in FEATURE_NAMES if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required feature columns in CSV: {', '.join(missing)}")

    X = df[FEATURE_NAMES].astype(float).to_numpy(dtype=np.float32)
    y = None
    if "score" in df.columns:
        y = df["score"].astype(float).to_numpy(dtype=np.float32)

    hire_labels = None
    if "hire" in df.columns:
        hire_values = pd.to_numeric(df["hire"], errors="coerce")
        if y is not None:
            derived = (y >= hire_threshold).astype(int)
            hire_labels = np.where(hire_values.isna(), derived, hire_values.fillna(0).astype(int))
        else:
            if hire_values.isna().any():
                raise ValueError(
                    "CSV hire column contains missing or invalid values and no score column is available "
                    "to derive labels from."
                )
            hire_labels = hire_values.astype(int).to_numpy()
    elif y is not None:
        hire_labels = (y >= hire_threshold).astype(int)

    return X, y, hire_labels


def validate_dataset(
    X,
    y,
    hire_labels,
    source,
    min_samples=30,
    min_class_count=5,
):
    if len(X) != len(hire_labels):
        raise ValueError("Feature matrix and hire labels must have the same number of rows.")

    sample_count = len(X)
    if source != "synthetic":
        if sample_count < min_samples:
            raise ValueError(
                f"CSV dataset is too small for reliable training ({sample_count} samples). "
                f"Provide at least {min_samples} samples with both hire=0 and hire=1 examples."
            )
        unique, counts = np.unique(hire_labels, return_counts=True)
        if len(unique) < 2:
            raise ValueError("CSV dataset must contain both hire=0 and hire=1 examples for classifier training.")
        if counts.min() < min_class_count:
            warnings.warn(
                f"Class imbalance detected in CSV dataset: {dict(zip(unique.tolist(), counts.tolist()))}. "
                f"Recommend at least {min_class_count} samples per class.",
                UserWarning,
            )
    else:
        if sample_count < min_samples:
            warnings.warn(
                f"Synthetic dataset is small ({sample_count} samples). Use more samples for stable model evaluation.",
                UserWarning,
            )

    if y is not None and sample_count < 10:
        warnings.warn(
            "Sample size is very small for regression metrics; results may not be reliable.",
            UserWarning,
        )


def build_dataset(data_csv=None, hire_threshold=65):
    if data_csv:
        X, y, hire_labels = load_dataset_from_csv(data_csv, hire_threshold)
    else:
        X, y = generate_dataset()
        hire_labels = (y >= hire_threshold).astype(int)
    return X, y, hire_labels


# ── Training ─────────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(description="Train or validate the CV ATS score and hire models.")
    parser.add_argument(
        "--data-csv",
        help="Optional CSV dataset path. Must contain the feature columns and either score or hire labels.",
    )
    parser.add_argument(
        "--hire-threshold",
        type=float,
        default=65.0,
        help="Score threshold used to derive hire labels when no hire column is present.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of data reserved for the test set.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=30,
        help="Minimum number of training samples required when using a CSV dataset.",
    )
    parser.add_argument(
        "--min-class-samples",
        type=int,
        default=5,
        help="Minimum number of samples required for each hire label class.",
    )
    parser.add_argument(
        "--model-prefix",
        default="",
        help="Optional prefix for saved model files.",
    )
    parser.add_argument(
        "--version",
        default="v3.0.0",
        help="Model metadata version.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Features: {N_FEATURES}")
    print(f"Engine:   {'XGBoost' if USE_XGBOOST else 'RandomForest (fallback)'}\n")

    X, y, hire_labels = build_dataset(args.data_csv, args.hire_threshold)
    if hire_labels is None:
        raise ValueError("Dataset must include a 'hire' column or score to derive hire labels.")

    dataset_source = args.data_csv or "synthetic"
    print(f"Dataset:  {dataset_source}")
    print(f"Samples:  {len(X)}")
    print(f"Test set: {args.test_size * 100:.0f}%\n")

    validate_dataset(
        X,
        y,
        hire_labels,
        source=dataset_source,
        min_samples=args.min_samples,
        min_class_count=args.min_class_samples,
    )

    stratify = None
    if len(np.unique(hire_labels)) > 1:
        counts = np.bincount(hire_labels)
        if counts.min() >= 2:
            stratify = hire_labels

    if y is not None:
        X_train, X_test, y_train, y_test, hire_train, hire_test = train_test_split(
            X,
            y,
            hire_labels,
            test_size=args.test_size,
            random_state=42,
            stratify=stratify,
        )
    else:
        X_train, X_test, hire_train, hire_test = train_test_split(
            X,
            hire_labels,
            test_size=args.test_size,
            random_state=42,
            stratify=stratify,
        )
        y_train = y_test = None

    score_model = None
    if y is not None:
        if USE_XGBOOST:
            score_model = XGBRegressor(
                n_estimators=600,
                max_depth=6,
                learning_rate=0.04,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                early_stopping_rounds=30,
            )
        else:
            score_model = RandomForestRegressor(
                n_estimators=300,
                max_depth=12,
                random_state=42,
            )

        if USE_XGBOOST:
            score_model.fit(
                X_train,
                y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )
        else:
            score_model.fit(X_train, y_train)

        y_pred = score_model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        print("=== Score Model (Regressor) ===")
        print(f"  MAE:  {mae:.2f}")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  R2:   {r2:.3f}")

        cv_scores = cross_val_score(
            XGBRegressor(
                n_estimators=400,
                max_depth=6,
                learning_rate=0.04,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
            )
            if USE_XGBOOST
            else score_model,
            X,
            y,
            cv=5,
            scoring="neg_mean_absolute_error",
        )
        print(f"  CV MAE: {-cv_scores.mean():.2f} +/- {cv_scores.std():.2f}\n")

    if USE_XGBOOST:
        hire_model = XGBClassifier(
            n_estimators=400,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss",
            early_stopping_rounds=30,
        )
    else:
        hire_model = RandomForestClassifier(
            n_estimators=300,
            max_depth=10,
            random_state=42,
        )

    if USE_XGBOOST:
        hire_model.fit(
            X_train,
            hire_train,
            eval_set=[(X_test, hire_test)],
            verbose=False,
        )
    else:
        hire_model.fit(X_train, hire_train)

    hire_pred = hire_model.predict(X_test)
    precision = precision_score(hire_test, hire_pred, zero_division=0)
    recall = recall_score(hire_test, hire_pred, zero_division=0)
    f1 = f1_score(hire_test, hire_pred, zero_division=0)
    roc_auc = None
    if hasattr(hire_model, "predict_proba"):
        proba = hire_model.predict_proba(X_test)
        if proba.shape[1] > 1 and len(np.unique(hire_test)) > 1:
            roc_auc = roc_auc_score(hire_test, proba[:, 1])

    print("=== Hire Model (Classifier) ===")
    print(f"  Accuracy:  {accuracy_score(hire_test, hire_pred):.3f}")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1-score:  {f1:.3f}")
    if roc_auc is not None:
        print(f"  ROC AUC:   {roc_auc:.3f}")
    elif len(np.unique(hire_test)) == 1:
        print("  ROC AUC:   n/a (only one class present in test labels)")

    if len(np.unique(hire_test)) == 1:
        print(
            classification_report(
                hire_test,
                hire_pred,
                labels=[0, 1],
                target_names=["Reject", "Hire"],
                zero_division=0,
            )
        )
    else:
        print(classification_report(hire_test, hire_pred, target_names=["Reject", "Hire"]))

    if score_model is not None:
        importances = (
            score_model.feature_importances_ if hasattr(score_model, "feature_importances_") else np.zeros(N_FEATURES)
        )
        imp_df = pd.DataFrame({"feature": FEATURE_NAMES, "importance": importances}).sort_values(
            by="importance", ascending=False
        )

        print("=== Feature Importance (Score Model) ===")
        print(imp_df.to_string(index=False))

    prefix = args.model_prefix.strip()
    score_path = f"{prefix + '_' if prefix else ''}resume_model.pkl"
    hire_path = f"{prefix + '_' if prefix else ''}hire_model.pkl"

    if score_model is not None:
        joblib.dump(score_model, score_path)
    joblib.dump(hire_model, hire_path)

    score_hash = None
    if score_model is not None:
        with open(score_path, "rb") as f:
            score_hash = hashlib.sha256(f.read()).hexdigest()
    with open(hire_path, "rb") as f:
        hire_hash = hashlib.sha256(f.read()).hexdigest()

    metadata = {
        "version": args.version,
        "features": FEATURE_NAMES,
        "n_features": N_FEATURES,
        "dataset": {
            "source": dataset_source,
            "samples": len(X),
            "test_size": args.test_size,
            "hire_threshold": args.hire_threshold,
        },
        "training": {
            "early_stopping": USE_XGBOOST,
            "cross_validation": "5-fold",
            "score_available": y is not None,
        },
        "score_model": None,
        "hire_model": {
            "path": hire_path,
            "sha256": hire_hash,
            "type": "XGBClassifier" if USE_XGBOOST else "RandomForestClassifier",
        },
    }
    if score_model is not None:
        metadata["score_model"] = {
            "path": score_path,
            "sha256": score_hash,
            "type": "XGBRegressor" if USE_XGBOOST else "RandomForestRegressor",
        }

    with open("model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    if score_model is not None:
        print(f"\n[OK] {score_path}  ({score_hash[:12]}...)")
    print(f"[OK] {hire_path}  ({hire_hash[:12]}...)")
    print(f"[OK] model_metadata.json updated ({args.version})")
    print(f"[OK] Training samples: {len(X)}")


if __name__ == "__main__":
    main()
