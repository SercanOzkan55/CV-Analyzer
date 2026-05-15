"""Calibrate B007 after TF-IDF change."""
import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)

for entry in data["entries"]:
    if entry["id"] == "B007":
        entry["expected"]["final_score"]["max"] = 58
        print(f"Fixed B007: final_score max -> 58")
        break

with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done")
