import pandas as pd
import pytest

from train_model import FEATURE_NAMES, load_dataset_from_csv, validate_dataset


def _sample_row(score=70, hire=1):
    row = {name: 50.0 for name in FEATURE_NAMES}
    row["score"] = score
    if hire is not None:
        row["hire"] = hire
    return row


def test_load_dataset_from_csv_with_score_and_hire(tmp_path):
    rows = [
        _sample_row(score=85, hire=1),
        _sample_row(score=45, hire=0),
        _sample_row(score=72, hire=1),
    ]
    path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(path, index=False)

    X, y, hire_labels = load_dataset_from_csv(str(path), hire_threshold=70)

    assert X.shape == (3, len(FEATURE_NAMES))
    assert y.shape == (3,)
    assert hire_labels.tolist() == [1, 0, 1]


def test_load_dataset_from_csv_missing_features_raises(tmp_path):
    df = pd.DataFrame({"score": [80, 45, 72], "hire": [1, 0, 1]})
    path = tmp_path / "broken.csv"
    df.to_csv(path, index=False)

    with pytest.raises(ValueError, match="Missing required feature columns"):
        load_dataset_from_csv(str(path), hire_threshold=70)


def test_validate_dataset_raises_for_small_csv():
    rows = [
        _sample_row(score=85, hire=1),
        _sample_row(score=45, hire=0),
        _sample_row(score=72, hire=1),
    ]
    df = pd.DataFrame(rows)
    X = df[FEATURE_NAMES].astype(float).to_numpy(dtype="float32")
    y = df["score"].astype(float).to_numpy(dtype="float32")
    hire_labels = df["hire"].astype(int).to_numpy()

    with pytest.raises(ValueError, match="too small for reliable training"):
        validate_dataset(X, y, hire_labels, source="csv", min_samples=10, min_class_count=2)
