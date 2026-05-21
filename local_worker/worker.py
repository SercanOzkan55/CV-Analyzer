import argparse
import difflib
import glob
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import requests

from credentials import load_worker_api_key, save_worker_api_key


API_BASE_URL = os.environ.get("CV_ANALYZER_API_URL", "http://127.0.0.1:8001/api/worker")
WORKER_VERSION = "1.2.0"
ENGINE_VERSION = "rule_based_mvp_v1"
PROGRESS_LOG = Path(os.environ.get("CV_WORKER_PROGRESS_LOG", "worker_progress.jsonl"))
MAX_FILE_BYTES = int(os.environ.get("CV_WORKER_MAX_FILE_BYTES", str(25 * 1024 * 1024)))
OPENAI_MODEL = os.environ.get("CV_WORKER_OPENAI_MODEL", "gpt-5.2")
SKILL_SYNONYMS = {
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "react": ["reactjs", "react.js"],
    "node": ["nodejs", "node.js"],
    "postgresql": ["postgres", "psql"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "continuous integration": ["ci"],
    "continuous deployment": ["cd"],
    "amazon web services": ["aws"],
    "google cloud": ["gcp"],
    "microsoft azure": ["azure"],
    "object oriented programming": ["oop"],
}

STOPWORDS = {
    "and", "or", "the", "with", "for", "from", "that", "this", "are", "you", "our",
    "your", "will", "have", "has", "must", "should", "role", "team", "work", "job",
    "experience", "years", "looking", "candidate", "ability", "skills",
}
MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "â€™", "â€œ", "â€", "Â")


class LocalWorkerError(RuntimeError):
    pass


def _log_progress(event: str, **fields):
    payload = {"event": event, "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"), **fields}
    with PROGRESS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#./-]+", " ", (text or "").lower()).strip()


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
    return set(re.findall(r"[a-z0-9+#./-]{2,}", text_norm or ""))


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
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{2,}", job_description or "")
    seen = set()
    keywords = []
    for word in words:
        key = word.lower()
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
        try:
            text = _extract_pdf_with_pdfplumber(file_bytes)
            if text.strip():
                return text
        except Exception:
            pass
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(file_bytes))
            return _fix_common_mojibake("\n".join((page.extract_text() or "") for page in reader.pages))
        except Exception as exc:
            raise LocalWorkerError(f"PDF extraction failed: {exc}") from exc

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

    required_score = 70.0 if not required else 70.0 * (len(matched_required) / len(required))
    nice_score = 20.0 if not nice else 20.0 * (len(matched_nice) / len(nice))
    content_score = min(10.0, max(0.0, len(cv_text or "") / 300.0))
    penalty = 25.0 if risk_flags else 0.0
    score = max(0.0, min(100.0, required_score + nice_score + content_score - penalty))

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


class LocalWorker:
    def __init__(self, api_key: str, processing_mode: str, ai_mode: str, device_name: str):
        self.api_key = api_key
        self.processing_mode = processing_mode
        self.ai_mode = ai_mode
        self.device_name = device_name
        self.access_token = None
        self.company_id = None
        self.allowed_jobs = []
        self.quota_remaining = 0
        self.session = requests.Session()

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

    def run(self, job_id: int, batch_size: int = 10, local_folder: str | None = None, max_empty_polls: int = 1):
        if self.processing_mode == "local_folder":
            self._run_local_folder(job_id, local_folder)
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

    def _run_local_folder(self, job_id: int, folder_path: str | None):
        if not folder_path:
            raise LocalWorkerError("--local-folder is required with local_folder mode")
        files = []
        for pattern in ("*.pdf", "*.docx", "*.txt"):
            files.extend(glob.glob(os.path.join(folder_path, pattern)))
        print(f"Found {len(files)} local file(s). Local-folder result sync is planned for the next phase.")
        for file_path in files:
            data = Path(file_path).read_bytes()
            text = extract_text(data, Path(file_path).suffix.lstrip("."), Path(file_path).name)
            print(json.dumps({"file": file_path, "chars": len(text)}, ensure_ascii=False))

    def _heartbeat(self):
        try:
            self._request("POST", "/heartbeat", json={})
        except Exception:
            pass


def _add_common_args(parser):
    parser.add_argument("--api-key", default=None, help="Worker API key. Defaults to CV_WORKER_API_KEY.")
    parser.add_argument("--save-api-key", action="store_true", help="Save the provided API key to the OS credential store.")
    parser.add_argument("--device-name", default=os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "Local Worker")


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
    run_parser.add_argument("--max-empty-polls", type=int, default=1)
    status_parser = subparsers.add_parser("status")
    _add_common_args(status_parser)

    args = parser.parse_args()
    api_key = args.api_key or os.environ.get("CV_WORKER_API_KEY") or load_worker_api_key()
    if args.api_key and args.save_api_key:
        saved = save_worker_api_key(args.api_key)
        print("API key saved to OS credential store." if saved else "API key could not be saved to OS credential store.")
    worker = LocalWorker(api_key, args.processing_mode, args.ai_mode, args.device_name)

    try:
        if args.command == "login":
            worker.login()
        elif args.command == "jobs":
            worker.login()
            worker.list_jobs()
        elif args.command == "run":
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
