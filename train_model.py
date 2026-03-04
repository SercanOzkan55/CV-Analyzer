import numpy as np
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

X = []
y = []

for _ in range(1000):

    semantic = np.random.uniform(0, 100)
    keyword = np.random.uniform(0, 100)
    skill = np.random.uniform(0, 100)
    exp = np.random.uniform(0, 100)

    total_required_skills = np.random.randint(5, 15)
    missing_count = np.random.randint(0, total_required_skills + 1)
    missing_ratio = missing_count / total_required_skills

    # 🔥 Gerçekçi Non-Linear Target
    noise = np.random.normal(0, 5)

    weighted_score = (
        semantic * 0.35 +
        keyword * 0.2 +
        skill * 0.25 +
        exp * 0.1 -
        missing_ratio * 30 +
        (semantic * skill / 200) +
        noise
    )

    X.append([
        semantic,
        keyword,
        skill,
        exp,
        missing_count,
        missing_ratio,
        semantic * skill / 100,
        keyword * skill / 100,
        abs(semantic - skill)
    ])

    y.append(weighted_score)

X = np.array(X)
y = np.array(y)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = RandomForestRegressor(n_estimators=200)
model.fit(X_train, y_train)

# 🔹 Evaluation
y_pred = model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\nModel Evaluation")
print("MAE:", round(mae, 2))
print("RMSE:", round(rmse, 2))
print("R2 Score:", round(r2, 3))

# 🔹 Feature Importance
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

importances = model.feature_importances_

importance_df = pd.DataFrame({
    "feature": feature_names,
    "importance": importances
}).sort_values(by="importance", ascending=False)

print("\nFeature Importance:")
print(importance_df)

joblib.dump(model, "resume_model.pkl")

print("\nModel trained successfully.")