import argparse
import csv
import difflib
import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import requests

from owner_workflow import build_candidate_notification, enrich_row_with_owner_workflow
from credentials import load_worker_api_key, save_worker_api_key
from workspace import WorkspaceStore


API_BASE_URL = os.environ.get("CV_ANALYZER_API_URL", "http://127.0.0.1:8001/api/worker")
VERIFY_SSL = os.environ.get("VERIFY_SSL", "True").lower() not in ("false", "0", "no")
WORKER_VERSION = "1.2.0"
ENGINE_VERSION = "rule_based_mvp_v1"
PROGRESS_LOG = Path(os.environ.get("CV_WORKER_PROGRESS_LOG", "worker_progress.jsonl"))
MAX_FILE_BYTES = int(os.environ.get("CV_WORKER_MAX_FILE_BYTES", str(25 * 1024 * 1024)))
OPENAI_MODEL = os.environ.get("CV_WORKER_OPENAI_MODEL", "gpt-5.2")
SKILL_SYNONYMS = {
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "react": ["reactjs", "react.js"],
    "node": ["nodejs", "node.js", "expressjs", "express.js"],
    "postgresql": ["postgres", "psql"],
    "machine learning": ["ml", "deep learning", "nlp", "llm", "neural networks", "pytorch", "tensorflow"],
    "artificial intelligence": ["ai", "openai", "gemini", "claude", "deepseek", "chatgpt"],
    "continuous integration": ["ci", "github actions", "gitlab ci", "jenkins"],
    "continuous deployment": ["cd", "github actions", "gitlab ci", "jenkins"],
    "amazon web services": ["aws"],
    "google cloud": ["gcp", "google cloud platform"],
    "microsoft azure": ["azure"],
    "object oriented programming": ["oop", "oops"],
    "backend": ["django", "fastapi", "flask", "spring boot", "asp.net", "expressjs", "laravel", "symfony", "back-end", "database", "api", "node"],
    "frontend": ["react", "angular", "vue", "nextjs", "html", "css", "javascript", "typescript", "front-end", "ui", "ux", "tailwind"],
    "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "sqlite", "oracle", "mssql", "db"],
    "mobile": ["flutter", "react native", "android", "ios", "swift", "kotlin", "objective-c"],
    "devops": ["docker", "kubernetes", "jenkins", "ci/cd", "terraform", "ansible", "aws", "gcp", "azure"],
}

STOPWORDS = {
    # English
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "with", "that", "this", "have", "from",
    "they", "will", "each", "make", "like", "been", "has", "its", "who",
    "did", "get", "may", "him", "his", "how", "let", "say", "she", "too",
    "use", "way", "about", "would", "there", "their", "what", "could",
    "other", "than", "then", "them", "these", "some", "which", "into",
    "over", "under", "between", "within", "without", "your", "role",
    "team", "work", "job", "experience", "years", "looking", "candidate",
    "ability", "skills", "must", "should",
    # Turkish
    "ve", "veya", "ile", "için", "icin", "bir", "bu", "şu", "su", "da",
    "de", "mi", "mı", "mu", "mü", "olan", "olarak", "gibi", "çok", "cok",
    "daha", "en", "her", "tüm", "tum", "ise", "hem", "ya", "ki",
    # German
    "und", "oder", "mit", "für", "fur", "der", "die", "das", "ein", "eine",
    "einen", "einem", "zu", "im", "in", "von", "den", "dem", "des", "als",
    # French
    "et", "ou", "avec", "pour", "les", "des", "une", "un", "du", "de",
    "la", "le", "dans", "sur", "par", "aux", "au", "ce", "cette",
    # Spanish
    "y", "o", "con", "para", "los", "las", "una", "uno", "del", "de",
    "el", "la", "en", "por", "como", "que", "este", "esta",
    # Portuguese / Italian / Dutch
    "e", "com", "para", "os", "as", "um", "uma", "do", "da", "no", "na",
    "il", "lo", "gli", "le", "di", "per", "che", "een", "het", "van",
    "voor", "met", "op", "aan", "als",
}
MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "â€™", "â€œ", "â€", "Â")


class LocalWorkerError(RuntimeError):
    pass


def _log_progress(event: str, **fields):
    payload = {"event": event, "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"), **fields}
    with PROGRESS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _clean_lower(text: str) -> str:
    """Global and language-independent lowercase conversion.
    Prevents corruption of dotted uppercase İ (U+0130) in Turkish and missing regex matches.
    """
    if not text:
        return ""
    text = text.replace("\u0130", "i")
    lowered = text.lower()
    lowered = lowered.replace("i\u0307", "i").replace("i̇", "i")
    return lowered


def _normalize(text: str) -> str:
    # Use clean_lower and keep Unicode letters/digits plus +, #, ., /, -
    # \w includes alphanumeric and underscore, so we replace underscore with space
    cleaned = _clean_lower(text or "")
    normalized = re.sub(r"[^\w+#./-]+", " ", cleaned)
    return normalized.replace("_", " ").strip()


def _contains_term(text_norm: str, term: str) -> bool:
    term_norm = _normalize(term)
    if not term_norm:
        return False
    return f" {term_norm} " in f" {text_norm} "


def _term_variants(term: str) -> list[str]:
    base = _normalize(term)
    variants = [base] if base else []
    variants.extend(_normalize(value) for value in SKILL_SYNONYMS.get(base, []))
    for canonical, aliases in SKILL_SYNONYMS.items():
        alias_values = [_normalize(alias) for alias in aliases]
        if base in alias_values:
            variants.append(canonical)
            variants.extend(alias_values)
    return list(dict.fromkeys(value for value in variants if value))


def _token_set(text_norm: str) -> set[str]:
    # Since text_norm is already normalized (and has no underscores), \w is perfect
    return set(re.findall(r"[\w+#./-]{2,}", text_norm or ""))


def _matches_term(text_norm: str, text_tokens: set[str], term: str) -> bool:
    for variant in _term_variants(term):
        if f" {variant} " in f" {text_norm} ":
            return True
        variant_tokens = variant.split()
        if len(variant_tokens) == 1:
            token = variant_tokens[0]
            if token in text_tokens:
                return True
            if len(token) >= 5 and difflib.get_close_matches(token, text_tokens, n=1, cutoff=0.86):
                return True
        elif all(token in text_tokens for token in variant_tokens):
            return True
    return False


def _derive_keywords(job_description: str, max_items: int = 12) -> list[str]:
    # Match words starting with any Unicode letter followed by Unicode alphanumeric/symbols
    words = re.findall(r"[^\W\d_][\w+#./-]{2,}", job_description or "")
    seen = set()
    keywords = []
    for word in words:
        key = _clean_lower(word)
        if key in STOPWORDS or key in seen:
            continue
        seen.add(key)
        keywords.append(word)
        if len(keywords) >= max_items:
            break
    return keywords


def _mojibake_score(text: str) -> int:
    return sum((text or "").count(marker) for marker in MOJIBAKE_MARKERS)


def _fix_common_mojibake(text: str) -> str:
    if not text or _mojibake_score(text) == 0:
        return text
    try:
        repaired = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if _mojibake_score(repaired) < _mojibake_score(text) else text


def _words_to_lines(words: list[dict]) -> list[str]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (float(w.get("top", 0)), float(w.get("x0", 0))))
    lines: list[str] = []
    current: list[dict] = []
    current_top = float(ordered[0].get("top", 0))
    for word in ordered:
        top = float(word.get("top", 0))
        if current and abs(top - current_top) > 4.5:
            lines.append(" ".join(str(w.get("text", "")) for w in sorted(current, key=lambda w: float(w.get("x0", 0)))))
            current = [word]
            current_top = top
        else:
            current.append(word)
            current_top = (current_top + top) / 2.0
    if current:
        lines.append(" ".join(str(w.get("text", "")) for w in sorted(current, key=lambda w: float(w.get("x0", 0)))))
    return [line.strip() for line in lines if line.strip()]


def _detect_columns(words: list[dict], page_width: float) -> list[tuple[float, float]]:
    if len(words) < 35 or page_width <= 0:
        return []
    centers = sorted((float(w.get("x0", 0)) + float(w.get("x1", 0))) / 2.0 for w in words)
    gap_threshold = max(36.0, page_width * 0.06)
    clusters: list[list[float]] = []
    for center in centers:
        if not clusters or center - clusters[-1][-1] > gap_threshold:
            clusters.append([center])
        else:
            clusters[-1].append(center)
    min_words = max(8, int(len(words) * 0.08))
    ranges: list[tuple[float, float, int]] = []
    for cluster in clusters:
        if len(cluster) >= min_words and max(cluster) - min(cluster) >= page_width * 0.04:
            ranges.append((max(0.0, min(cluster) - 12.0), min(page_width, max(cluster) + 12.0), len(cluster)))
    ranges.sort(key=lambda item: item[0])
    if len(ranges) < 2 or sum(item[2] for item in ranges) < len(words) * 0.45:
        return []
    return [(left, right) for left, right, _ in ranges[:3]]


def _extract_pdf_with_pdfplumber(file_bytes: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False) or []
            columns = _detect_columns(words, float(page.width))
            if len(columns) < 2:
                page_lines = _words_to_lines(words)
            else:
                buckets: list[list[dict]] = [[] for _ in columns]
                for word in words:
                    center = (float(word.get("x0", 0)) + float(word.get("x1", 0))) / 2.0
                    chosen = min(
                        range(len(columns)),
                        key=lambda idx: 0
                        if columns[idx][0] <= center <= columns[idx][1]
                        else min(abs(center - columns[idx][0]), abs(center - columns[idx][1])),
                    )
                    buckets[chosen].append(word)
                page_lines = []
                for bucket in buckets:
                    if page_lines:
                        page_lines.append("")
                    page_lines.extend(_words_to_lines(bucket))
            if page_lines:
                pages.append("\n".join(page_lines))
    return _fix_common_mojibake("\n\n".join(pages).strip())


def _looks_like_pdf(file_bytes: bytes) -> bool:
    return file_bytes.lstrip().startswith(b"%PDF")


def extract_text(file_bytes: bytes, file_type: str, file_name: str = "") -> str:
    kind = (file_type or Path(file_name).suffix.lstrip(".") or "txt").lower()
    if kind in {"txt", "text", "plain"}:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="replace")

    if kind == "pdf":
        text = ""
        try:
            text = _extract_pdf_with_pdfplumber(file_bytes)
        except Exception:
            pass
        if not text.strip() and _looks_like_pdf(file_bytes):
            try:
                try:
                    from pypdf import PdfReader
                except ImportError:
                    from PyPDF2 import PdfReader
                reader = PdfReader(BytesIO(file_bytes))
                text = _fix_common_mojibake("\n".join((page.extract_text() or "") for page in reader.pages))
            except Exception:
                pass
        if text.strip():
            return text
            
        # OCR Fallback path (Phase 7)
        try:
            from PIL import Image
            import fitz  # PyMuPDF
            import pytesseract
            
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            ocr_pages = []
            for page in doc:
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img)
                if page_text:
                    ocr_pages.append(page_text)
            ocr_text = "\n".join(ocr_pages).strip()
            if ocr_text:
                return _fix_common_mojibake(ocr_text)
        except Exception:
            pass

        raise LocalWorkerError("PDF extraction failed: no text could be extracted (scanned PDF without OCR or invalid file)")

    if kind == "docx":
        try:
            from docx import Document
            doc = Document(BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception as exc:
            raise LocalWorkerError(f"DOCX extraction failed: {exc}") from exc

    raise LocalWorkerError(f"Unsupported file type: {kind}")


def score_cv(cv_text: str, config: dict) -> dict:
    text_norm = _normalize(cv_text)
    text_tokens = _token_set(text_norm)
    required = list(config.get("required_skills") or [])
    nice = list(config.get("nice_to_have_skills") or [])
    hard_reject = list(config.get("hard_reject_criteria") or [])
    if not required:
        required = _derive_keywords(config.get("description", ""))

    matched_required = [skill for skill in required if _matches_term(text_norm, text_tokens, skill)]
    missing_required = [skill for skill in required if skill not in matched_required]
    matched_nice = [skill for skill in nice if _matches_term(text_norm, text_tokens, skill)]
    risk_flags = [criterion for criterion in hard_reject if _matches_term(text_norm, text_tokens, criterion)]

    weights = dict(config.get("scoring_weights") or {})
    required_weight = float(weights.get("required_skills", 70.0))
    nice_weight = float(weights.get("nice_to_have_skills", 20.0))
    content_weight = float(weights.get("content_quality", 10.0))
    total_weight = max(1.0, required_weight + nice_weight + content_weight)
    scale = 100.0 / total_weight

    required_score = required_weight if not required else required_weight * (len(matched_required) / len(required))
    nice_score = nice_weight if not nice else nice_weight * (len(matched_nice) / len(nice))
    content_score = min(content_weight, max(0.0, len(cv_text or "") / 300.0 * (content_weight / 10.0)))
    penalty = 25.0 if risk_flags else 0.0
    score = max(0.0, min(100.0, ((required_score + nice_score + content_score) * scale) - penalty))

    accept_threshold = int(config.get("accept_threshold") or 75)
    review_threshold = int(config.get("review_threshold") or 50)
    if risk_flags:
        decision = "recommended_reject"
    elif score >= accept_threshold:
        decision = "recommended_accept"
    elif score >= review_threshold:
        decision = "recommended_review"
    else:
        decision = "recommended_reject"

    if len(cv_text or "") < 250 or not required:
        confidence = "low"
    elif score >= accept_threshold or score < review_threshold:
        confidence = "high"
    else:
        confidence = "medium"

    matched_skills = matched_required + matched_nice
    summary = (
        f"Matched {len(matched_required)}/{len(required)} required skills"
        + (f" and {len(matched_nice)}/{len(nice)} nice-to-have skills." if nice else ".")
    )
    explanation = summary
    if missing_required:
        explanation += " Missing required skills: " + ", ".join(missing_required[:8]) + "."
    if risk_flags:
        explanation += " Hard reject criteria detected: " + ", ".join(risk_flags[:5]) + "."

    return {
        "score": round(score, 2),
        "decision": decision,
        "confidence": confidence,
        "summary": summary,
        "matched_skills": matched_skills,
        "missing_skills": missing_required,
        "risk_flags": risk_flags,
        "explanation": explanation,
        "score_breakdown": {
            "required_skills": round(required_score, 2),
            "nice_to_have": round(nice_score, 2),
            "content_quality": round(content_score, 2),
            "risk_penalty": round(penalty, 2),
        },
    }


def _is_uncertain_score(score: dict, config: dict) -> bool:
    value = float(score.get("score") or 0)
    accept = float(config.get("accept_threshold") or 75)
    review = float(config.get("review_threshold") or 50)
    return abs(value - accept) <= 8 or abs(value - review) <= 8 or score.get("confidence") == "low"


def _extract_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def maybe_apply_ai_review(cv_text: str, config: dict, score: dict, ai_mode: str) -> dict:
    if ai_mode != "customer_openai_key" or not _is_uncertain_score(score, config):
        return score
    api_key = os.environ.get("CV_WORKER_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {**score, "ai_review_status": "skipped_missing_customer_key"}

    trimmed_cv = (cv_text or "")[:6000]
    prompt = {
        "job": {
            "title": config.get("title"),
            "description": (config.get("description") or "")[:3000],
            "required_skills": config.get("required_skills") or [],
            "nice_to_have_skills": config.get("nice_to_have_skills") or [],
            "hard_reject_criteria": config.get("hard_reject_criteria") or [],
        },
        "rule_based_score": score,
        "cv_text_excerpt": trimmed_cv,
    }
    try:
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "instructions": (
                    "You are reviewing a local CV screening result. Do not invent facts. "
                    "Return concise JSON with keys: decision, confidence, explanation, risk_flags."
                ),
                "input": json.dumps(prompt, ensure_ascii=False),
                "store": False,
            },
            timeout=45,
            verify=VERIFY_SSL,
        )
        if resp.status_code >= 400:
            return {**score, "ai_review_status": f"failed_{resp.status_code}"}
        text = _extract_response_text(resp.json())
        return {
            **score,
            "ai_review_status": "completed",
            "ai_review_model": OPENAI_MODEL,
            "ai_review": text[:2500],
        }
    except Exception as exc:
        return {**score, "ai_review_status": f"failed_{type(exc).__name__}"}
def _generate_html_report(ranked_rows: list[dict], config: dict, html_path: Path):
    rows_json = json.dumps(ranked_rows, ensure_ascii=False)
    config_json = json.dumps(config, ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CV Değerlendirme Sonuçları - {config.get('title', 'Yerel Değerlendirme')}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: hsl(230, 25%, 8%);
      --surface: rgba(255, 255, 255, 0.03);
      --surface-border: rgba(255, 255, 255, 0.08);
      --text: hsl(210, 20%, 98%);
      --text-muted: hsl(210, 10%, 70%);
      --primary: hsl(262, 85%, 60%);
      --primary-glow: hsla(262, 85%, 60%, 0.35);
      --secondary: hsl(316, 80%, 55%);
      
      --color-accept: hsl(142, 70%, 45%);
      --color-accept-bg: rgba(22, 163, 74, 0.15);
      --color-review: hsl(38, 92%, 50%);
      --color-review-bg: rgba(217, 119, 6, 0.15);
      --color-reject: hsl(0, 84%, 60%);
      --color-reject-bg: rgba(220, 38, 38, 0.15);
      
      --font: 'Outfit', sans-serif;
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font);
      min-height: 100vh;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 10% 20%, hsla(262, 80%, 20%, 0.15) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, hsla(316, 70%, 20%, 0.1) 0%, transparent 40%);
      background-attachment: fixed;
    }}
    
    header {{
      padding: 3rem 2rem 2rem;
      max-width: 1400px;
      margin: 0 auto;
    }}
    
    .header-content {{
      display: flex;
      flex-direction: column;
      gap: 1rem;
      border-bottom: 1px solid var(--surface-border);
      padding-bottom: 2rem;
    }}
    
    h1 {{
      font-size: 2.5rem;
      font-weight: 700;
      background: linear-gradient(135deg, #fff 40%, var(--secondary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }}
    
    .job-badge {{
      display: inline-flex;
      align-items: center;
      padding: 0.5rem 1rem;
      border-radius: 50px;
      background: var(--surface);
      border: 1px solid var(--surface-border);
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text-muted);
      width: fit-content;
    }}
    
    .job-desc {{
      font-size: 1rem;
      color: var(--text-muted);
      line-height: 1.6;
      max-width: 900px;
    }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
      max-width: 1400px;
      margin: 0 auto 3rem;
      padding: 0 2rem;
    }}
    
    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 1.5rem;
      backdrop-filter: blur(16px);
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      position: relative;
      overflow: hidden;
      transition: transform 0.3s ease, border-color 0.3s ease;
    }}
    
    .stat-card:hover {{
      transform: translateY(-3px);
      border-color: rgba(255, 255, 255, 0.15);
    }}
    
    .stat-card::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; width: 4px; height: 100%;
      background: var(--primary);
    }}
    
    .stat-card.accept::before {{ background: var(--color-accept); }}
    .stat-card.review::before {{ background: var(--color-review); }}
    .stat-card.reject::before {{ background: var(--color-reject); }}
    .stat-card.avg::before {{ background: var(--secondary); }}
    
    .stat-val {{
      font-size: 2.25rem;
      font-weight: 700;
      color: var(--text);
    }}
    
    .stat-label {{
      font-size: 0.875rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      font-weight: 500;
    }}

    .controls-container {{
      max-width: 1400px;
      margin: 0 auto 2rem;
      padding: 0 2rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
    }}
    
    .search-wrapper {{
      position: relative;
      flex: 1;
      min-width: 300px;
    }}
    
    .search-input {{
      width: 100%;
      padding: 0.85rem 1.25rem;
      border-radius: 12px;
      background: var(--surface);
      border: 1px solid var(--surface-border);
      color: var(--text);
      font-family: var(--font);
      font-size: 1rem;
      outline: none;
      transition: all 0.3s ease;
      backdrop-filter: blur(8px);
    }}
    
    .search-input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 15px var(--primary-glow);
    }}
    
    .filter-buttons {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}
    
    .filter-btn {{
      padding: 0.75rem 1.25rem;
      border-radius: 10px;
      border: 1px solid var(--surface-border);
      background: var(--surface);
      color: var(--text);
      font-family: var(--font);
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      backdrop-filter: blur(8px);
    }}
    
    .filter-btn:hover {{
      border-color: rgba(255, 255, 255, 0.2);
      background: rgba(255, 255, 255, 0.05);
    }}
    
    .filter-btn.active {{
      background: var(--primary);
      border-color: var(--primary);
      box-shadow: 0 0 15px var(--primary-glow);
    }}
    
    .candidate-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 2rem;
      max-width: 1400px;
      margin: 0 auto 4rem;
      padding: 0 2rem;
    }}
    
    .candidate-card {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 20px;
      padding: 1.75rem;
      backdrop-filter: blur(16px);
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      position: relative;
      cursor: pointer;
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease, box-shadow 0.3s ease;
    }}
    
    .candidate-card:hover {{
      transform: translateY(-5px);
      border-color: rgba(255, 255, 255, 0.2);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }}
    
    .candidate-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }}
    
    .candidate-info-top {{
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      overflow: hidden;
    }}
    
    .candidate-rank {{
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    
    .candidate-name {{
      font-size: 1.15rem;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    
    .score-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      font-size: 1.1rem;
      font-weight: 700;
      border: 2px solid;
      flex-shrink: 0;
    }}
    
    .score-badge.recommended_accept {{
      border-color: var(--color-accept);
      color: var(--color-accept);
      box-shadow: 0 0 10px rgba(22, 163, 74, 0.2);
    }}
    
    .score-badge.recommended_review {{
      border-color: var(--color-review);
      color: var(--color-review);
      box-shadow: 0 0 10px rgba(217, 119, 6, 0.2);
    }}
    
    .score-badge.recommended_reject {{
      border-color: var(--color-reject);
      color: var(--color-reject);
      box-shadow: 0 0 10px rgba(220, 38, 38, 0.2);
    }}
    
    .decision-pill {{
      align-self: flex-start;
      padding: 0.35rem 0.75rem;
      border-radius: 50px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    
    .decision-pill.recommended_accept {{
      background: var(--color-accept-bg);
      color: var(--color-accept);
    }}
    
    .decision-pill.recommended_review {{
      background: var(--color-review-bg);
      color: var(--color-review);
    }}
    
    .decision-pill.recommended_reject {{
      background: var(--color-reject-bg);
      color: var(--color-reject);
    }}
    
    .card-section {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}
    
    .section-label {{
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 600;
    }}
    
    .badge-container {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }}
    
    .skill-badge {{
      font-size: 0.75rem;
      padding: 0.25rem 0.5rem;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.06);
      color: var(--text);
    }}
    
    .skill-badge.matched {{
      background: rgba(22, 163, 74, 0.08);
      border-color: rgba(22, 163, 74, 0.2);
      color: hsl(142, 70%, 75%);
    }}
    
    .skill-badge.missing {{
      background: rgba(220, 38, 38, 0.05);
      border-color: rgba(220, 38, 38, 0.15);
      color: hsl(0, 84%, 80%);
    }}
    
    .risk-badge {{
      background: rgba(220, 38, 38, 0.12);
      border: 1px solid rgba(220, 38, 38, 0.25);
      color: var(--color-reject);
      font-size: 0.75rem;
      padding: 0.25rem 0.5rem;
      border-radius: 6px;
      font-weight: 500;
    }}
    
    .summary-text {{
      font-size: 0.875rem;
      color: var(--text-muted);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    .modal-overlay {{
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(10, 11, 18, 0.85);
      backdrop-filter: blur(20px);
      z-index: 1000;
      display: flex;
      justify-content: center;
      align-items: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.3s ease;
      padding: 1.5rem;
    }}
    
    .modal-overlay.active {{
      opacity: 1;
      pointer-events: auto;
    }}
    
    .modal-container {{
      background: hsl(230, 25%, 11%);
      border: 1px solid var(--surface-border);
      border-radius: 24px;
      width: 100%;
      max-width: 750px;
      max-height: 90vh;
      overflow-y: auto;
      position: relative;
      transform: scale(0.9) translateY(20px);
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    
    .modal-overlay.active .modal-container {{
      transform: scale(1) translateY(0);
    }}
    
    .modal-header {{
      padding: 2rem;
      border-bottom: 1px solid var(--surface-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      background: hsl(230, 25%, 11%);
      z-index: 2;
    }}
    
    .modal-title-wrapper {{
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      overflow: hidden;
      padding-right: 1rem;
    }}
    
    .modal-title {{
      font-size: 1.4rem;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    
    .modal-subtitle {{
      font-size: 0.8rem;
      color: var(--text-muted);
      font-family: monospace;
      word-break: break-all;
    }}
    
    .close-btn {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      color: var(--text);
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 1.25rem;
      transition: all 0.2s ease;
      flex-shrink: 0;
    }}
    
    .close-btn:hover {{
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }}
    
    .modal-body {{
      padding: 2rem;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }}
    
    .modal-row-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
    }}
    
    .modal-block {{
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 1.5rem;
    }}
    
    .score-breakdown-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.6rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-size: 0.875rem;
    }}
    
    .score-breakdown-row:last-child {{
      border-bottom: none;
    }}
    
    .explanation-box {{
      background: rgba(255, 255, 255, 0.02);
      border-left: 3px solid var(--primary);
      border-radius: 0 12px 12px 0;
      padding: 1.25rem;
      font-size: 0.95rem;
      line-height: 1.6;
      color: var(--text);
    }}
    
    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 4rem 2rem;
      background: var(--surface);
      border: 1px dashed var(--surface-border);
      border-radius: 20px;
      color: var(--text-muted);
    }}
    
    ::-webkit-scrollbar {{
      width: 8px;
    }}
    ::-webkit-scrollbar-track {{
      background: var(--bg);
    }}
    ::-webkit-scrollbar-thumb {{
      background: var(--surface-border);
      border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: rgba(255, 255, 255, 0.2);
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-content">
      <div class="job-badge" id="jobTitleBadge">Kriter: {config.get('title', 'Yerel Değerlendirme')}</div>
      <h1 id="mainTitle">CV Değerlendirme Raporu</h1>
      <p class="job-desc" id="jobDescText"></p>
    </div>
  </header>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-val" id="statTotal">0</div>
      <div class="stat-label">Toplam Aday</div>
    </div>
    <div class="stat-card accept">
      <div class="stat-val" id="statAccept">0</div>
      <div class="stat-label">Kabul Önerilen</div>
    </div>
    <div class="stat-card review">
      <div class="stat-val" id="statReview">0</div>
      <div class="stat-label">İnceleme Önerilen</div>
    </div>
    <div class="stat-card reject">
      <div class="stat-val" id="statReject">0</div>
      <div class="stat-label">Red Önerilen</div>
    </div>
    <div class="stat-card avg">
      <div class="stat-val" id="statAvg">0</div>
      <div class="stat-label">Ortalama Skor</div>
    </div>
  </div>

  <div class="controls-container">
    <div class="search-wrapper">
      <input type="text" id="searchBar" class="search-input" placeholder="Aday adı, dosya veya yetenek ara..." oninput="filterAndRender()">
    </div>
    <div class="filter-buttons">
      <button class="filter-btn active" id="btn-all" onclick="setFilter('all')">Tümü</button>
      <button class="filter-btn" id="btn-accept" onclick="setFilter('recommended_accept')">Kabul</button>
      <button class="filter-btn" id="btn-review" onclick="setFilter('recommended_review')">İnceleme</button>
      <button class="filter-btn" id="btn-reject" onclick="setFilter('recommended_reject')">Red</button>
    </div>
  </div>

  <div class="candidate-grid" id="candidateGrid">
    <!-- Rendered dynamically -->
  </div>

  <div class="modal-overlay" id="detailModal" onclick="closeModal(event)">
    <div class="modal-container" onclick="event.stopPropagation()">
      <div class="modal-header">
        <div class="modal-title-wrapper">
          <div class="modal-title" id="modalTitle">Aday Detayı</div>
          <div class="modal-subtitle" id="modalSubtitle">Dosya yolu</div>
        </div>
        <button class="close-btn" onclick="closeModal(null)">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-row-grid">
          <div class="modal-block" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem;">
            <div class="score-badge" id="modalScoreBadge" style="width: 100px; height: 100px; font-size: 2.25rem;">0</div>
            <div class="decision-pill" id="modalDecisionPill">KABUL</div>
          </div>
          <div class="modal-block">
            <h3 class="section-label" style="margin-bottom: 0.75rem;">Skor Dağılımı</h3>
            <div class="score-breakdown-row">
              <span>Zorunlu Yetenekler</span>
              <span id="breakdownRequired">0</span>
            </div>
            <div class="score-breakdown-row">
              <span>Artı Yetenekler</span>
              <span id="breakdownNice">0</span>
            </div>
            <div class="score-breakdown-row">
              <span>İçerik Kalitesi</span>
              <span id="breakdownContent">0</span>
            </div>
            <div class="score-breakdown-row" style="color: var(--color-reject);">
              <span>Risk Cezası</span>
              <span id="breakdownPenalty">0</span>
            </div>
          </div>
        </div>

        <div class="modal-block">
          <h3 class="section-label" style="margin-bottom: 1rem;">Detaylı Açıklama</h3>
          <div class="explanation-box" id="modalExplanation">Açıklama yükleniyor...</div>
        </div>

        <div class="modal-block" id="modalRiskBlock" style="display: none;">
          <h3 class="section-label" style="margin-bottom: 0.75rem; color: var(--color-reject);">Risk Bayrakları</h3>
          <div class="badge-container" id="modalRiskContainer"></div>
        </div>

        <div class="modal-row-grid">
          <div class="modal-block">
            <h3 class="section-label" style="margin-bottom: 1rem;">Eşleşen Yetenekler</h3>
            <div class="badge-container" id="modalMatchedSkills"></div>
          </div>
          <div class="modal-block">
            <h3 class="section-label" style="margin-bottom: 1rem;">Eksik Yetenekler</h3>
            <div class="badge-container" id="modalMissingSkills"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const candidates = {rows_json};
    const jobConfig = {config_json};
    let currentFilter = 'all';

    if (jobConfig.description) {{
      document.getElementById('jobDescText').textContent = jobConfig.description;
    }} else {{
      document.getElementById('jobDescText').textContent = 'Bu iş tanımı için herhangi bir detaylı açıklama girilmemiş.';
    }}

    function initStats() {{
      const total = candidates.length;
      const accept = candidates.filter(c => c.decision === 'recommended_accept').length;
      const review = candidates.filter(c => c.decision === 'recommended_review').length;
      const reject = candidates.filter(c => c.decision === 'recommended_reject').length;
      
      const sumScores = candidates.reduce((acc, c) => acc + (c.score || 0), 0);
      const avg = total > 0 ? (sumScores / total).toFixed(1) : 0;
      
      document.getElementById('statTotal').textContent = total;
      document.getElementById('statAccept').textContent = accept;
      document.getElementById('statReview').textContent = review;
      document.getElementById('statReject').textContent = reject;
      document.getElementById('statAvg').textContent = avg;
    }}

    function getFileName(path) {{
      if (!path) return 'Bilinmeyen Aday';
      const parts = path.split(/[\\\\/]/);
      return parts[parts.length - 1];
    }}

    function translateDecision(decision) {{
      switch(decision) {{
        case 'recommended_accept': return 'Kabul Önerilir';
        case 'recommended_review': return 'İnceleme Önerilir';
        case 'recommended_reject': return 'Red Önerilir';
        default: return decision;
      }}
    }}

    function renderCandidates(list) {{
      const grid = document.getElementById('candidateGrid');
      grid.innerHTML = '';
      
      if (list.length === 0) {{
        grid.innerHTML = '<div class="empty-state"><h3>Kriterlere uygun aday bulunamadı</h3><p>Filtrelerinizi değiştirmeyi veya arama sorgunuzu temizlemeyi deneyin.</p></div>';
        return;
      }}
      
      list.forEach((c, index) => {{
        const card = document.createElement('div');
        card.className = 'candidate-card';
        card.onclick = () => openModal(c);
        
        const fileName = getFileName(c.file);
        
        let matchedBadges = '';
        if (c.matched_skills && c.matched_skills.length > 0) {{
          matchedBadges = c.matched_skills.slice(0, 4).map(s => '<span class="skill-badge matched">' + s + '</span>').join('');
          if (c.matched_skills.length > 4) {{
            matchedBadges += '<span class="skill-badge">+' + (c.matched_skills.length - 4) + '</span>';
          }}
        }} else {{
          matchedBadges = '<span class="skill-badge" style="opacity:0.5;">Yok</span>';
        }}
        
        let riskBadges = '';
        if (c.risk_flags && c.risk_flags.length > 0) {{
          riskBadges = c.risk_flags.map(r => '<span class="risk-badge">' + r + '</span>').join('');
        }}
        
        let riskSection = '';
        if (riskBadges) {{
          riskSection = `
          <div class="card-section">
            <span class="section-label" style="color: var(--color-reject);">Risk Tespitleri</span>
            <div class="badge-container">${{riskBadges}}</div>
          </div>`;
        }}
        
        card.innerHTML = `
          <div class="candidate-header">
            <div class="candidate-info-top">
              <span class="candidate-rank">SIRA #${{c.rank || (index + 1)}}</span>
              <h2 class="candidate-name" title="${{fileName}}">${{fileName}}</h2>
            </div>
            <div class="score-badge ${{c.decision}}">${{c.score}}</div>
          </div>
          <div class="decision-pill ${{c.decision}}">${{translateDecision(c.decision)}}</div>
          
          <div class="card-section">
            <span class="section-label">Eşleşen Yetenekler</span>
            <div class="badge-container">${{matchedBadges}}</div>
          </div>
          
          ${{riskSection}}
          
          <div class="card-section">
            <span class="section-label">Özet</span>
            <p class="summary-text">${{c.summary || c.explanation || ''}}</p>
          </div>
        `;
        
        grid.appendChild(card);
      }});
    }}

    function filterAndRender() {{
      const query = document.getElementById('searchBar').value.toLowerCase().trim();
      
      const filtered = candidates.filter(c => {{
        if (currentFilter !== 'all' && c.decision !== currentFilter) return false;
        
        if (query) {{
          const fileName = getFileName(c.file).toLowerCase();
          const matchesFile = fileName.includes(query);
          const matchesSkills = c.matched_skills && c.matched_skills.some(s => s.toLowerCase().includes(query));
          const matchesMissing = c.missing_skills && c.missing_skills.some(s => s.toLowerCase().includes(query));
          const matchesExplanation = c.explanation && c.explanation.toLowerCase().includes(query);
          return matchesFile || matchesSkills || matchesMissing || matchesExplanation;
        }}
        
        return true;
      }});
      
      renderCandidates(filtered);
    }}

    function setFilter(filter) {{
      currentFilter = filter;
      
      document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtnId = filter === 'all' ? 'btn-all' : 
                          filter === 'recommended_accept' ? 'btn-accept' :
                          filter === 'recommended_review' ? 'btn-review' : 'btn-reject';
      document.getElementById(activeBtnId).classList.add('active');
      
      filterAndRender();
    }}

    function openModal(candidate) {{
      document.getElementById('modalTitle').textContent = getFileName(candidate.file);
      document.getElementById('modalSubtitle').textContent = candidate.file;
      
      const scoreBadge = document.getElementById('modalScoreBadge');
      scoreBadge.className = 'score-badge ' + candidate.decision;
      scoreBadge.textContent = candidate.score;
      
      const decisionPill = document.getElementById('modalDecisionPill');
      decisionPill.className = 'decision-pill ' + candidate.decision;
      decisionPill.textContent = translateDecision(candidate.decision);
      
      const breakdown = candidate.score_breakdown || {{}};
      const reqWeight = jobConfig.scoring_weights?.required_skills !== undefined ? jobConfig.scoring_weights.required_skills : 70;
      const niceWeight = jobConfig.scoring_weights?.nice_to_have_skills !== undefined ? jobConfig.scoring_weights.nice_to_have_skills : 20;
      const contentWeight = jobConfig.scoring_weights?.content_quality !== undefined ? jobConfig.scoring_weights.content_quality : 10;
      
      document.getElementById('breakdownRequired').textContent = (breakdown.required_skills !== undefined ? breakdown.required_skills : 0) + ' / ' + reqWeight;
      document.getElementById('breakdownNice').textContent = (breakdown.nice_to_have !== undefined ? breakdown.nice_to_have : 0) + ' / ' + niceWeight;
      document.getElementById('breakdownContent').textContent = (breakdown.content_quality !== undefined ? breakdown.content_quality : 0) + ' / ' + contentWeight;
      document.getElementById('breakdownPenalty').textContent = '-' + (breakdown.risk_penalty !== undefined ? breakdown.risk_penalty : 0);
      
      document.getElementById('modalExplanation').textContent = candidate.explanation || candidate.summary || 'Herhangi bir detaylı açıklama yok.';
      
      const riskBlock = document.getElementById('modalRiskBlock');
      const riskContainer = document.getElementById('modalRiskContainer');
      riskContainer.innerHTML = '';
      if (candidate.risk_flags && candidate.risk_flags.length > 0) {{
        riskBlock.style.display = 'block';
        candidate.risk_flags.forEach(r => {{
          const b = document.createElement('span');
          b.className = 'risk-badge';
          b.textContent = r;
          riskContainer.appendChild(b);
        }});
      }} else {{
        riskBlock.style.display = 'none';
      }}
      
      const matchedContainer = document.getElementById('modalMatchedSkills');
      matchedContainer.innerHTML = '';
      if (candidate.matched_skills && candidate.matched_skills.length > 0) {{
        candidate.matched_skills.forEach(s => {{
          const b = document.createElement('span');
          b.className = 'skill-badge matched';
          b.textContent = s;
          matchedContainer.appendChild(b);
        }});
      }} else {{
        matchedContainer.innerHTML = '<span class="skill-badge" style="opacity: 0.5;">Uyumlu yetenek bulunamadı</span>';
      }}
      
      const missingContainer = document.getElementById('modalMissingSkills');
      missingContainer.innerHTML = '';
      if (candidate.missing_skills && candidate.missing_skills.length > 0) {{
        candidate.missing_skills.forEach(s => {{
          const b = document.createElement('span');
          b.className = 'skill-badge missing';
          b.textContent = s;
          missingContainer.appendChild(b);
        }});
      }} else {{
        missingContainer.innerHTML = '<span class="skill-badge matched">Zorunlu yetenek eksiği yok</span>';
      }}
      
      document.getElementById('detailModal').classList.add('active');
    }}

    function closeModal(event) {{
      if (event && event.target !== document.getElementById('detailModal')) return;
      document.getElementById('detailModal').classList.remove('active');
    }}

    window.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') closeModal(null);
    }});

    initStats();
    renderCandidates(candidates);
  </script>
</body>
</html>"""
    
    html_path.write_text(html_content, encoding="utf-8")


class LocalWorker:
    def __init__(self, api_key: str, processing_mode: str, ai_mode: str, device_name: str, verify_ssl: bool = True):
        self.api_key = api_key
        self.processing_mode = processing_mode
        self.ai_mode = ai_mode
        self.device_name = device_name
        self.verify_ssl = verify_ssl
        self.access_token = None
        self.company_id = None
        self.allowed_jobs = []
        self.quota_remaining = 0
        self.session = requests.Session()
        self.session.verify = self.verify_ssl

    def _request(self, method: str, path_or_url: str, *, absolute: bool = False, allow_reauth: bool = True, **kwargs):
        url = path_or_url if absolute else f"{API_BASE_URL}{path_or_url}"
        last_error = None
        timeout = kwargs.pop("timeout", 30)
        for attempt in range(4):
            try:
                resp = self.session.request(method, url, timeout=timeout, **kwargs)
                if (
                    resp.status_code == 401
                    and allow_reauth
                    and not absolute
                    and path_or_url != "/auth"
                    and self.api_key
                ):
                    self.login()
                    resp = self.session.request(method, url, timeout=timeout, **kwargs)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                return resp
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
        raise LocalWorkerError(f"Request failed: {last_error}")

    def login(self):
        if not self.api_key:
            raise LocalWorkerError("Missing API key. Pass --api-key or set CV_WORKER_API_KEY.")
        resp = self._request("POST", "/auth", allow_reauth=False, json={
            "api_key": self.api_key,
            "device_name": self.device_name,
            "worker_version": WORKER_VERSION,
        })
        if resp.status_code != 200:
            raise LocalWorkerError(f"Login failed: {resp.text}")

        data = resp.json()
        self.access_token = data["access_token"]
        self.company_id = data["company_id"]
        self.allowed_jobs = data["allowed_jobs"]
        self.quota_remaining = data["quota_remaining"]
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        _log_progress("login", company_id=self.company_id, quota_remaining=self.quota_remaining)
        print(f"Login successful. Company={self.company_id} Quota remaining={self.quota_remaining}")

    def list_jobs(self):
        resp = self._request("GET", "/jobs")
        if resp.status_code != 200:
            raise LocalWorkerError(f"Failed to list jobs: {resp.text}")
        jobs = resp.json().get("jobs", [])
        print(json.dumps({"jobs": jobs}, indent=2))

    def run(
        self,
        job_id: int,
        batch_size: int = 10,
        local_folder: str | None = None,
        max_empty_polls: int = 1,
        local_config: dict | None = None,
        output_folder: str | None = None,
    ):
        if self.processing_mode == "local_folder":
            if not self.access_token:
                self.login()
            self._run_local_folder(job_id, local_folder, local_config, output_folder)
            return

        config_resp = self._request("GET", f"/jobs/{job_id}/config")
        if config_resp.status_code != 200:
            raise LocalWorkerError(f"Failed to get job config: {config_resp.text}")
        config = config_resp.json()
        print(f"Loaded job config: {config.get('title')}")

        empty_polls = 0
        while empty_polls < max_empty_polls:
            processed = self._process_server_batch(job_id, config, batch_size)
            if processed == 0:
                empty_polls += 1
                if empty_polls < max_empty_polls:
                    time.sleep(15)
            else:
                empty_polls = 0
            self._heartbeat()
        print("No more pending claims for now.")

    def _process_server_batch(self, job_id: int, config: dict, batch_size: int) -> int:
        claim_resp = self._request("POST", f"/jobs/{job_id}/claim", json={"limit": batch_size})
        if claim_resp.status_code == 402:
            print("Quota exhausted.")
            return 0
        if claim_resp.status_code != 200:
            raise LocalWorkerError(f"Failed to claim CVs: {claim_resp.text}")

        items = claim_resp.json().get("items", [])
        if not items:
            return 0

        print(f"Claimed {len(items)} CV(s).")
        processed = 0
        for item in items:
            try:
                self.process_item(job_id, config, item)
                processed += 1
            except Exception as exc:
                print(f"Failed item candidate={item.get('candidate_id')}: {exc}")
                _log_progress("item_failed", job_id=job_id, candidate_id=item.get("candidate_id"), error=str(exc))
        return processed

    def _download_item(self, item: dict) -> bytes:
        resp = self._request("GET", item["download_url"], absolute=True, timeout=60)
        if resp.status_code != 200:
            raise LocalWorkerError(f"Download failed for candidate {item.get('candidate_id')}: {resp.text}")
        if len(resp.content) > MAX_FILE_BYTES:
            raise LocalWorkerError(
                f"Downloaded file is too large for candidate {item.get('candidate_id')}: "
                f"{len(resp.content)} bytes > {MAX_FILE_BYTES} bytes"
            )
        return resp.content

    def process_item(self, job_id: int, config: dict, item: dict):
        cv_id = item.get("cv_id")
        candidate_id = item.get("candidate_id")
        print(f"Processing candidate={candidate_id} file={item.get('file_name')}")
        try:
            file_bytes = self._download_item(item)
            cv_text = extract_text(file_bytes, item.get("file_type", "txt"), item.get("file_name", "cv.txt"))
            if cv_text.strip():
                score = maybe_apply_ai_review(cv_text, config, score_cv(cv_text, config), self.ai_mode)
            else:
                score = self._failed_score(
                    "No readable text could be extracted from this CV.",
                    risk_flag="empty_text",
                    config=config,
                )
        except Exception as exc:
            score = self._failed_score(
                f"Local worker could not process this CV safely: {exc}",
                risk_flag="extraction_failed",
                config=config,
            )
        payload = {
            "cv_id": cv_id,
            "candidate_id": candidate_id,
            "worker_version": WORKER_VERSION,
            "engine_version": ENGINE_VERSION,
            **score,
        }
        resp = self._request("POST", f"/jobs/{job_id}/results", json=payload)
        if resp.status_code not in {200, 201}:
            raise LocalWorkerError(f"Result submit failed: {resp.text}")
        _log_progress(
            "result_submitted",
            job_id=job_id,
            candidate_id=candidate_id,
            cv_id=cv_id,
            score=score["score"],
            decision=score["decision"],
        )
        print(f"Submitted candidate={candidate_id} score={score['score']} decision={score['decision']}")

    def _failed_score(self, message: str, *, risk_flag: str, config: dict) -> dict:
        required = list(config.get("required_skills") or [])
        return {
            "score": 0,
            "decision": "recommended_reject",
            "confidence": "low",
            "summary": message,
            "matched_skills": [],
            "missing_skills": required[:20],
            "risk_flags": [risk_flag],
            "explanation": message,
        }

    def _run_local_folder(self, job_id: int, folder_path: str | None, config: dict | None = None, output_folder: str | None = None):
        if not folder_path:
            raise LocalWorkerError("--local-folder is required with local_folder mode")
        config = config or {
            "title": f"Local job {job_id}",
            "description": "",
            "required_skills": [],
            "nice_to_have_skills": [],
            "hard_reject_criteria": [],
            "accept_threshold": 75,
            "review_threshold": 50,
            "reject_threshold": 30,
        }
        if not config.get("description") and not config.get("required_skills"):
            raise LocalWorkerError("Local folder mode requires --job-description, --required-skills, or --job-config.")

        folder = Path(folder_path).expanduser()
        output = Path(output_folder or (folder / "cv_analyzer_results")).expanduser()
        output.mkdir(parents=True, exist_ok=True)

        files = []
        for pattern in ("*.pdf", "*.docx", "*.txt"):
            files.extend(glob.glob(str(folder / "**" / pattern), recursive=True))
        files = sorted({str(Path(path)) for path in files})
        print(f"Found {len(files)} local file(s).")
        if self.quota_remaining <= 0:
            raise LocalWorkerError("No remaining CV scan quota. Renew your worker key or wait for quota reset.")
        if len(files) > self.quota_remaining:
            raise LocalWorkerError(
                f"Folder has {len(files)} CV file(s), but this worker key has "
                f"{self.quota_remaining} scan(s) left."
            )
        rows = []
        failed_files = []
        seen_hashes: dict[str, str] = {}
        ai_reviews_used = 0
        ai_review_limit = int(config.get("ai_max_reviews") or os.environ.get("CV_WORKER_AI_MAX_REVIEWS", "25") or "25")
        for file_path in files:
            path = Path(file_path)
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise LocalWorkerError(f"File exceeds max size: {MAX_FILE_BYTES} bytes")
                data = path.read_bytes()
                file_hash = hashlib.sha256(data).hexdigest()
                duplicate_of = seen_hashes.get(file_hash)
                if not duplicate_of:
                    seen_hashes[file_hash] = str(path)
                text = extract_text(data, path.suffix.lstrip("."), path.name)
                base_score = score_cv(text, config)
                ai_mode = self.ai_mode
                if ai_mode == "customer_openai_key" and ai_reviews_used >= ai_review_limit:
                    result = {**base_score, "ai_review_status": "skipped_ai_review_limit"}
                else:
                    result = maybe_apply_ai_review(text, config, base_score, ai_mode)
                    if result.get("ai_review_status") == "completed":
                        ai_reviews_used += 1
            except Exception as exc:
                failed_files.append(str(path))
                file_hash = ""
                duplicate_of = ""
                text = ""
                result = self._failed_score(str(exc), risk_flag="extraction_failed", config=config)
            row = {
                "file": str(path),
                "file_hash": file_hash,
                "is_duplicate": bool(duplicate_of),
                "duplicate_of": duplicate_of or "",
                "worker_version": WORKER_VERSION,
                "engine_version": ENGINE_VERSION,
                "processed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "sync_status": "pending",
                "cv_text": text,
                **result,
            }
            row = enrich_row_with_owner_workflow(row, config, actor_name=self.device_name or "Local Worker")
            rows.append(row)
            print(json.dumps({
                "file": str(path),
                "score": row["score"],
                "decision": row["decision"],
                "candidate_status": row["candidate_status"],
            }, ensure_ascii=False))

        ranked_rows = sorted(rows, key=lambda item: float(item.get("score") or 0), reverse=True)
        for rank, row in enumerate(ranked_rows, start=1):
            row["rank"] = rank

        json_path = output / "local_worker_results.json"
        csv_path = output / "local_worker_results.csv"
        html_path = output / "local_worker_results.html"
        sync_path = output / "sync_manifest.json"
        failed_path = output / "failed_files.txt"
        workspace_path = output / "local_worker_workspace.sqlite3"

        json_path.write_text(json.dumps(ranked_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "rank", "file", "score", "decision", "confidence", "is_duplicate",
                    "candidate_status", "notification_event_type",
                    "duplicate_of", "file_hash", "worker_version", "engine_version", "sync_status",
                    "summary", "score_breakdown", "matched_skills", "missing_skills",
                    "risk_flags", "explanation", "notification_title", "notification_message", "processed_at",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in ranked_rows:
                writer.writerow({
                    **row,
                    "matched_skills": ", ".join(row.get("matched_skills") or []),
                    "missing_skills": ", ".join(row.get("missing_skills") or []),
                    "risk_flags": ", ".join(row.get("risk_flags") or []),
                    "score_breakdown": json.dumps(row.get("score_breakdown") or {}, ensure_ascii=False),
                })
        if failed_files:
            failed_path.write_text("\n".join(failed_files), encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()

        sync_path.write_text(
            json.dumps(
                {
                    "schema": "cv_analyzer.local_worker.sync_manifest.v1",
                    "mode": "local_folder",
                    "job_id": job_id,
                    "job_config": config,
                    "results_file": str(json_path),
                    "csv_file": str(csv_path),
                    "failed_files": failed_files,
                    "ai_reviews_used": ai_reviews_used,
                    "ai_review_limit": ai_review_limit,
                    "sync_status": "offline_ready",
                    "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        store = WorkspaceStore(workspace_path)
        saved_job_id = store.save_job(config.get("title") or f"Local job {job_id}", config)
        run_id = store.create_run(saved_job_id, config.get("title") or f"Local job {job_id}", str(folder), str(output), len(files))
        notification_count = 0
        for row in ranked_rows:
            result_id = store.add_result(run_id, row)
            store.create_audit_log(
                run_id=run_id,
                result_id=result_id,
                action_type=row.get("notification_event_type", "cv_analysis_completed"),
                module="local_worker",
                resource_type="analysis_result",
                resource_id=row.get("file", ""),
                description=f"Local CV analysis completed for {row.get('file', '')}",
                after_data={
                    "score": row.get("score"),
                    "decision": row.get("decision"),
                    "candidate_status": row.get("candidate_status"),
                    "rank": row.get("rank"),
                },
            )
            notification = build_candidate_notification(row, config, actor_name=self.device_name or "Local Worker")
            if notification:
                store.create_notification(
                    run_id=run_id,
                    result_id=result_id,
                    title=notification["title"],
                    message=notification["message"],
                    type=notification["event_type"],
                    channel=notification["channel"],
                    candidate_name=notification["candidate_name"],
                    file_path=row.get("file", ""),
                )
                notification_count += 1
        _generate_html_report(ranked_rows, config, html_path)
        self.quota_remaining = max(0, self.quota_remaining - len(files))
        print(f"Results saved: {json_path}")
        print(f"CSV saved: {csv_path}")
        print(f"HTML Report saved: {html_path}")
        print(f"Local workspace saved: {workspace_path}")
        print(f"Owner notifications created: {notification_count}")
        print(f"Quota remaining locally: {self.quota_remaining}")

    def _heartbeat(self):
        try:
            self._request("POST", "/heartbeat", json={})
        except Exception:
            pass


def _add_common_args(parser):
    parser.add_argument("--api-key", default=None, help="Worker API key. Defaults to CV_WORKER_API_KEY.")
    parser.add_argument("--save-api-key", action="store_true", help="Save the provided API key to the OS credential store.")
    parser.add_argument("--device-name", default=os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "Local Worker")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Bypass SSL verification for SaaS backend request calls.")


def _split_cli_terms(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()]


def _load_local_config(args) -> dict:
    config = {}
    if getattr(args, "job_config", None):
        config = json.loads(Path(args.job_config).read_text(encoding="utf-8"))
    config.setdefault("title", f"Local job {args.job_id}")
    if args.job_description:
        config["description"] = args.job_description
    config.setdefault("description", "")
    if args.required_skills:
        config["required_skills"] = _split_cli_terms(args.required_skills)
    config.setdefault("required_skills", [])
    if args.nice_to_have_skills:
        config["nice_to_have_skills"] = _split_cli_terms(args.nice_to_have_skills)
    config.setdefault("nice_to_have_skills", [])
    if args.hard_reject_criteria:
        config["hard_reject_criteria"] = _split_cli_terms(args.hard_reject_criteria)
    config.setdefault("hard_reject_criteria", [])
    config["accept_threshold"] = args.accept_threshold
    config["review_threshold"] = args.review_threshold
    config.setdefault("ai_max_reviews", int(os.environ.get("CV_WORKER_AI_MAX_REVIEWS", "25") or "25"))
    config.setdefault("reject_threshold", 30)
    config.setdefault("scoring_weights", {
        "required_skills": 70.0,
        "nice_to_have_skills": 20.0,
        "content_quality": 10.0,
    })
    return config


def main():
    parser = argparse.ArgumentParser(description="CV Analyzer Local Worker MVP")
    parser.add_argument("--processing-mode", choices=["server_files", "local_folder"], default="server_files")
    parser.add_argument("--ai-mode", choices=["none", "customer_openai_key", "platform_openai_proxy"], default="none")

    subparsers = parser.add_subparsers(dest="command", required=True)
    login_parser = subparsers.add_parser("login")
    _add_common_args(login_parser)
    jobs_parser = subparsers.add_parser("jobs")
    _add_common_args(jobs_parser)
    run_parser = subparsers.add_parser("run")
    _add_common_args(run_parser)
    run_parser.add_argument("--job-id", type=int, required=True)
    run_parser.add_argument("--batch-size", type=int, default=10)
    run_parser.add_argument("--local-folder", type=str)
    run_parser.add_argument("--output-folder", type=str)
    run_parser.add_argument("--job-config", type=str, help="JSON file with local job criteria for local_folder mode.")
    run_parser.add_argument("--job-description", type=str, help="Local job description for local_folder mode.")
    run_parser.add_argument("--required-skills", type=str, help="Comma-separated required skills for local_folder mode.")
    run_parser.add_argument("--nice-to-have-skills", type=str, help="Comma-separated nice-to-have skills for local_folder mode.")
    run_parser.add_argument("--hard-reject-criteria", type=str, help="Comma-separated rejection criteria for local_folder mode.")
    run_parser.add_argument("--accept-threshold", type=int, default=75)
    run_parser.add_argument("--review-threshold", type=int, default=50)
    run_parser.add_argument("--max-empty-polls", type=int, default=1)
    status_parser = subparsers.add_parser("status")
    _add_common_args(status_parser)

    args = parser.parse_args()
    api_key = args.api_key or os.environ.get("CV_WORKER_API_KEY") or load_worker_api_key()
    if args.api_key and args.save_api_key:
        saved = save_worker_api_key(args.api_key)
        print("API key saved to OS credential store." if saved else "API key could not be saved to OS credential store.")
    verify_ssl = VERIFY_SSL and not getattr(args, "no_verify_ssl", False)
    worker = LocalWorker(api_key, args.processing_mode, args.ai_mode, args.device_name, verify_ssl=verify_ssl)

    try:
        if args.command == "login":
            worker.login()
        elif args.command == "jobs":
            worker.login()
            worker.list_jobs()
        elif args.command == "run":
            if args.processing_mode == "local_folder":
                worker.login()
                worker.run(
                    args.job_id,
                    args.batch_size,
                    args.local_folder,
                    args.max_empty_polls,
                    _load_local_config(args),
                    args.output_folder,
                )
            else:
                worker.login()
                worker.run(args.job_id, args.batch_size, args.local_folder, args.max_empty_polls)
        elif args.command == "status":
            worker.login()
            print(json.dumps({
                "company_id": worker.company_id,
                "allowed_jobs": worker.allowed_jobs,
                "quota_remaining": worker.quota_remaining,
                "processing_mode": worker.processing_mode,
                "ai_mode": worker.ai_mode,
            }, indent=2))
    except LocalWorkerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
