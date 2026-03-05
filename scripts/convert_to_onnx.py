"""Convert an sklearn/joblib model to ONNX for safer inference.

Usage:
  python scripts/convert_to_onnx.py resume_model.pkl model.onnx N_FEATURES
"""

import sys
from pathlib import Path

if len(sys.argv) < 4:
    print("usage: convert_to_onnx.py <input.pkl> <output.onnx> <n_features>")
    sys.exit(2)

in_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
n_features = int(sys.argv[3])

import joblib
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

model = joblib.load(in_path)
initial_type = [("input", FloatTensorType([None, n_features]))]
onnx = convert_sklearn(model, initial_types=initial_type)
with open(out_path, "wb") as f:
    f.write(onnx.SerializeToString())

print("wrote", out_path)
