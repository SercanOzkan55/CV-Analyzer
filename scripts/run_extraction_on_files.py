import sys
import io
import json
import hashlib
from pathlib import Path

FILES = [
    r"c:\Users\ASUS\Desktop\AhmetKuşcu.cv.pdf",
    r"c:\Users\ASUS\Downloads\Sercan_Ozkan_CV_optimized.pdf",
    r"c:\Users\ASUS\Downloads\AhmetKuşcu.cv_optimized.pdf",
    r"c:\Users\ASUS\Desktop\Sercan_Ozkan_CV.pdf",
]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

out = []
seen_hashes = {}

try:
    from services.pdf_text_extractor import extract_pdf_text
    from agents.extract_agent import extract_structured
    from services.extraction_validator import validate_extraction
except Exception as e:
    print(json.dumps({"error": "import_failed", "detail": str(e)}))
    raise

for p in FILES:
    try:
        path = Path(p)
        if not path.exists():
            out.append({"path": str(p), "error": "not_found"})
            continue
        contents = path.read_bytes()
        raw, truncated = extract_pdf_text(contents, max_pages=20, max_chars=300000, ocr_extract_text=None)
        extracted = extract_structured(raw)
        report = validate_extraction(raw, extracted, strict=True)
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        dup = seen_hashes.get(fingerprint)
        if dup:
            dup_note = f"duplicate_of:{dup}"
        else:
            seen_hashes[fingerprint] = path.name
            dup_note = None
        entry = {
            "path": str(path),
            "name": path.name,
            "raw_truncated": bool(truncated),
            "fingerprint": fingerprint,
            "duplicate_note": dup_note,
            "extraction_report": report,
            "extracted_preview": {
                k: (extracted.get(k) if k in ("skills", "languages", "summary") else None)
                for k in ("skills", "languages", "summary")
            },
        }
        out.append(entry)
    except Exception as e:
        out.append({"path": str(p), "error": "exception", "detail": str(e)})

out_path = ROOT / "extraction_reports.json"
out_path.write_bytes(json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8"))
print("WROTE", str(out_path))
print(json.dumps(out, ensure_ascii=False))
