import os
import sys
import json
import hashlib
import joblib
import numpy as np

MODEL_PATH = os.getenv("MODEL_PATH", "resume_model.pkl")
EXPECTED_HASH = os.getenv("MODEL_SHA256", "")


def verify_model(path: str):
    if EXPECTED_HASH:
        with open(path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        if h != EXPECTED_HASH:
            raise RuntimeError("Model integrity check failed in runner")


def calibrate_confidence(std):
    confidence = np.exp(-std / 10)
    return round(confidence * 100, 2)


def get_risk_level(score, confidence):
    if confidence < 60:
        return "High Risk"
    elif score < 50:
        return "Medium Risk"
    else:
        return "Low Risk"


def explain_prediction(model, features):
    feature_names = [
        "semantic",
        "keyword",
        "skill",
        "experience",
        "missing_count",
        "missing_ratio",
        "semantic_skill_interaction",
        "keyword_skill_interaction",
        "balance_score"
    ]
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        importances = [1.0 / len(feature_names)] * len(feature_names)

    contributions = []
    for name, value, imp in zip(feature_names, features, importances):
        contributions.append((name, value, imp, value * imp))

    contributions.sort(key=lambda x: x[3], reverse=True)
    FEATURE_LABELS = {n: n.replace("_", " ").title() for n in feature_names}

    strong = [FEATURE_LABELS[s[0]] for s in contributions[:3] if s[1] > 50]
    weak = [FEATURE_LABELS[s[0]] for s in contributions[:3] if s[1] <= 50]

    return {
        "strong_areas": strong,
        "weak_areas": weak,
        "key_driver": FEATURE_LABELS[contributions[0][0]]
    }


def main():
    data = json.load(sys.stdin)
    features = data.get("features")
    if features is None:
        print(json.dumps({"error": "missing features"}))
        sys.exit(2)

    # Basic safety: ensure model path is local and not an absolute outside path
    model_path = os.path.abspath(MODEL_PATH)
    cwd = os.path.abspath(os.getcwd())
    if not model_path.startswith(cwd):
        print(json.dumps({"error": "invalid model path"}))
        sys.exit(2)

    if not os.path.exists(model_path):
        print(json.dumps({"error": "model file not found"}))
        sys.exit(2)

    try:
        verify_model(model_path)
        model = joblib.load(model_path)

        trees = getattr(model, "estimators_", None)
        if not trees:
            # fallback: try predict directly
            pred = float(model.predict([features])[0])
            std = 0.0
        else:
            preds = [tree.predict([features])[0] for tree in trees]
            pred = float(np.mean(preds))
            std = float(np.std(preds))

        confidence = calibrate_confidence(std)
        risk = get_risk_level(pred, confidence)
        explanation = explain_prediction(model, features)

        out = {
            "prediction": pred,
            "confidence": confidence,
            "risk_level": risk,
            "explanation": explanation
        }
        sys.stdout.write(json.dumps(out))
    except Exception as e:
        sys.stdout.write(json.dumps({"error": str(e)}))
        sys.exit(2)


if __name__ == "__main__":
    main()
