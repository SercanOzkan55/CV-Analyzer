import joblib

model = joblib.load("resume_model.pkl")

def predict_match(features):
    prediction = model.predict([features])[0]
    probability = model.predict_proba([features])[0][1]
    return prediction, probability