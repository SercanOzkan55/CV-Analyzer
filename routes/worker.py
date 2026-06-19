import secrets
import hashlib
import hmac
import base64
import io
import json
import os
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from database import get_db
from models import WorkerKey, WorkerSession, WorkerClaim, WorkerAnalysisResult, QuotaEvent, RecruiterJob, Candidate, CandidateAction
from schemas.worker import (
    WorkerKeyCreate, WorkerKeyResponse, WorkerKeyCreateResponse,
    WorkerAuthRequest, WorkerAuthResponse, JobConfigResponse,
    ClaimRequest, ClaimResponse, ClaimItem, AnalysisResultRequest
)
from routes.recruiter import recruiter_required
from core.http_runtime import audit_log, limiter
from services.owner_workflow_service import (
    decision_to_candidate_status,
    record_candidate_status_event,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
security = HTTPBearer()

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_WORKER_DIR = _PROJECT_ROOT / "local_worker"
LOCAL_WORKER_PLAN_LIMITS = {
    "free": int(os.getenv("LOCAL_WORKER_MONTHLY_LIMIT_FREE", "0")),
    "pro": int(os.getenv("LOCAL_WORKER_MONTHLY_LIMIT_PRO", "4000")),
    "enterprise": int(os.getenv("LOCAL_WORKER_MONTHLY_LIMIT_ENTERPRISE", "4000")),
}

def hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _download_token_ttl_seconds() -> int:
    raw = os.getenv("WORKER_DOWNLOAD_URL_TTL_SECONDS", "600")
    try:
        ttl = int(raw)
    except ValueError as exc:
        raise RuntimeError("WORKER_DOWNLOAD_URL_TTL_SECONDS must be an integer") from exc
    if ttl < 60 or ttl > 3600:
        raise RuntimeError("WORKER_DOWNLOAD_URL_TTL_SECONDS must be between 60 and 3600 seconds")
    return ttl


_DOWNLOAD_TOKEN_TTL_SECONDS = _download_token_ttl_seconds()
_KNOWN_SKILLS = [
    "python", "javascript", "typescript", "react", "node", "fastapi", "django",
    "flask", "sql", "postgresql", "mysql", "mongodb", "redis", "docker",
    "kubernetes", "aws", "azure", "gcp", "linux", "git", "ci/cd", "machine learning",
    "data analysis", "excel", "power bi", "tableau", "salesforce", "seo", "crm",
    "project management", "agile", "scrum", "communication", "leadership",
]


def _download_signing_secret() -> bytes:
    explicit = os.getenv("WORKER_DOWNLOAD_SIGNING_SECRET")
    if explicit:
        return explicit.encode("utf-8")

    app_env = (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("STAGE")
        or ""
    ).lower()
    if app_env in {"prod", "production"}:
        raise RuntimeError("WORKER_DOWNLOAD_SIGNING_SECRET is required in production")

    raw = os.getenv("SECRET_KEY") or os.getenv("API_KEY") or "dev-worker-download-secret"
    return raw.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign_download_token(claim_id: int, cv_id: int | None, expires_at: datetime) -> str:
    exp = int(expires_at.timestamp())
    payload = f"{claim_id}:{cv_id or 0}:{exp}"
    signature = hmac.new(_download_signing_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return _b64(f"{payload}:{signature}".encode("utf-8"))


def _verify_download_token(token: str) -> tuple[int, int | None, datetime]:
    try:
        decoded = _unb64(token).decode("utf-8")
        claim_raw, cv_raw, exp_raw, signature = decoded.split(":", 3)
        payload = f"{claim_raw}:{cv_raw}:{exp_raw}"
        expected = hmac.new(_download_signing_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        expires_at = datetime.fromtimestamp(int(exp_raw))
        if expires_at < datetime.utcnow():
            raise ValueError("expired")
        return int(claim_raw), (int(cv_raw) if int(cv_raw) > 0 else None), expires_at
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid or expired download URL")


def _safe_download_filename(name: str | None, claim_id: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._-")
    return f"{cleaned or 'candidate'}_{claim_id}.txt"


def _safe_file_name(name: str | None, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._-")
    return cleaned or fallback


def _file_type_from_name(name: str | None, fallback: str = "txt") -> str:
    suffix = os.path.splitext(str(name or ""))[1].lower().lstrip(".")
    return suffix or fallback


def _storage_download_url(action: CandidateAction) -> str | None:
    key = getattr(action, "cv_file_key", None)
    if not key:
        return None
    try:
        from services.storage_service import get_download_url
        url = get_download_url(key, str(action.recruiter_id), expires=_DOWNLOAD_TOKEN_TTL_SECONDS)
        if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
            return url
    except Exception:
        return None
    return None


def _extract_job_skills(description: str | None) -> list[str]:
    text = f" {description or ''} ".lower()
    found = []
    for skill in _KNOWN_SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        if re.search(pattern, text):
            found.append(skill.title() if skill.islower() else skill)
    return found[:20]


def _ensure_candidate_for_action(db: Session, action: CandidateAction) -> Candidate:
    email = (action.candidate_email or "").strip().lower()
    candidate = None
    if email:
        candidate = db.query(Candidate).filter(
            Candidate.organization_id == action.organization_id,
            func.lower(Candidate.email) == email,
        ).first()
    if not candidate:
        candidate = Candidate(
            organization_id=action.organization_id,
            name=action.candidate_name,
            email=action.candidate_email,
        )
        db.add(candidate)
        db.flush()
    return candidate


def _safe_permissions(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _worker_key_payload(wk: WorkerKey) -> dict:
    remaining = max(0, int(wk.quota_limit or 0) - int(wk.quota_used or 0) - int(wk.quota_reserved or 0))
    return {
        "id": wk.id,
        "name": wk.name,
        "company_id": wk.organization_id,
        "job_id": wk.job_id,
        "key_prefix": wk.key_prefix,
        "quota_limit": wk.quota_limit,
        "quota_used": wk.quota_used,
        "quota_reserved": wk.quota_reserved,
        "quota_remaining": remaining,
        "expires_at": wk.expires_at,
        "revoked_at": wk.revoked_at,
        "last_used_at": wk.last_used_at,
        "created_at": wk.created_at,
        "permissions": _safe_permissions(wk.permissions),
    }


def _normalize_worker_plan(plan: str | None) -> str:
    value = (plan or "free").strip().lower()
    if value == "premium":
        value = "pro"
    return value if value in LOCAL_WORKER_PLAN_LIMITS else "free"


def _resolve_worker_plan(db: Session, organization_id: int, recruiter=None) -> str:
    org_plan = None
    if organization_id:
        from models import Organization

        org = db.query(Organization).filter(Organization.id == organization_id).first()
        org_plan = getattr(org, "plan_type", None) if org else None
    return _normalize_worker_plan(org_plan or getattr(recruiter, "plan_type", None))


def _active_worker_key_filter(now: datetime):
    return and_(
        WorkerKey.revoked_at == None,
        or_(WorkerKey.expires_at == None, WorkerKey.expires_at > now),
    )


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return datetime(now.year, now.month, 1)


def _completed_this_month_for_keys(db: Session, organization_id: int, key_ids: set[int], now: datetime) -> int:
    if not key_ids:
        return 0
    amount = db.query(func.coalesce(func.sum(QuotaEvent.amount), 0)).filter(
        QuotaEvent.organization_id == organization_id,
        QuotaEvent.worker_key_id.in_(key_ids),
        QuotaEvent.event_type == "completed",
        QuotaEvent.created_at >= _month_start(now),
    ).scalar()
    return int(amount or 0)


def _worker_quota_snapshot(db: Session, organization_id: int, plan: str | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    normalized_plan = _normalize_worker_plan(plan)
    monthly_limit = int(LOCAL_WORKER_PLAN_LIMITS.get(normalized_plan, 0))

    all_keys = db.query(WorkerKey).filter(WorkerKey.organization_id == organization_id).all()
    active_keys = [
        key for key in all_keys
        if key.revoked_at is None and (key.expires_at is None or key.expires_at > now)
    ]
    active_key_ids = {key.id for key in active_keys}
    inactive_key_ids = {key.id for key in all_keys if key.id not in active_key_ids}

    active_quota_limit = sum(int(key.quota_limit or 0) for key in active_keys)
    active_used_reserved = sum(
        int(key.quota_used or 0) + int(key.quota_reserved or 0)
        for key in active_keys
    )
    inactive_completed_this_month = _completed_this_month_for_keys(db, organization_id, inactive_key_ids, now)

    allocated = active_quota_limit + inactive_completed_this_month
    used_reserved = active_used_reserved + inactive_completed_this_month
    quota_remaining = max(0, monthly_limit - allocated)
    runtime_remaining = max(0, monthly_limit - used_reserved)

    return {
        "plan": normalized_plan,
        "monthly_limit": monthly_limit,
        "quota_allocated": allocated,
        "quota_used_reserved": used_reserved,
        "quota_remaining": quota_remaining,
        "runtime_quota_remaining": runtime_remaining,
        "active_quota_limit": active_quota_limit,
        "inactive_completed_this_month": inactive_completed_this_month,
        "month_start": _month_start(now),
    }


def _worker_exe_path() -> Path:
    configured = os.getenv("WORKER_EXE_PATH")
    if configured:
        return Path(configured)
    return _LOCAL_WORKER_DIR / "dist" / "CV Analyzer Local Worker.exe"


def _worker_package_readme(api_base_url: str) -> str:
    return f"""# CV Analyzer Local Worker

Most employers should download the one-file Windows app from the Recruiter Local Worker tab:

```text
CV Analyzer Local Worker.exe
```

This ZIP package is the fallback/developer package for machines that need to install Python dependencies or rebuild the executable locally.

This package has two modes:

1. **Local app mode**: one-click Windows setup, modern tabbed Qt UI, local job description, local CV folder, local CSV/JSON output. This mode does not require site-side jobs.
2. **Server worker mode**: authenticate with a worker API key, claim site-side CVs, process them locally, and submit results back to CV Analyzer.

## Recommended Windows setup

1. Extract the ZIP.
2. Double-click `start_here.cmd`.
3. The app opens after dependencies are installed.
4. In the app, paste or type the job description, choose a CV folder, and click **Analyze local folder**.

The installer also creates a desktop shortcut named **CV Analyzer Local Worker**.

If the app closes immediately, open:

```text
%LOCALAPPDATA%\\CV Analyzer Local Worker\\crash.log
```

The startup script keeps the terminal open when Python exits with an error, so the exact issue is visible instead of disappearing.

The local app writes:

- `local_worker_results.csv`
- `local_worker_results.json`
- `failed_files.txt` when one or more files could not be processed
- `sync_manifest.json` for future optional site sync/import
- `local_worker_workspace.sqlite3` for saved local jobs and local analysis history

These files stay on your device.

Optional AI review can be enabled inside the app by selecting `customer_openai_key`. It only runs for uncertain or low-confidence results and uses a key stored in your local environment:

```powershell
$env:CV_WORKER_OPENAI_API_KEY="sk-..."
```

## Manual install

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

Then open the local visual app:

```powershell
.\\.venv\\Scripts\\python.exe qml_gui.py
```

## Optional server worker mode

Use this only when you want the local worker to claim CVs from the CV Analyzer website and sync results back.

Set the backend URL and your one-time worker API key:

```powershell
$env:CV_ANALYZER_API_URL="{api_base_url}"
$env:CV_WORKER_API_KEY="sk_worker_live_xxx"
```

The API key is only shown once in the web app when it is created. It is not stored in this package.

To store the worker key in the OS credential store instead of an environment variable:

```powershell
.\\.venv\\Scripts\\python.exe worker.py login --api-key sk_worker_live_xxx --save-api-key
```

Run server-side claim processing:

```powershell
.\\.venv\\Scripts\\python.exe worker.py login
.\\.venv\\Scripts\\python.exe worker.py jobs
.\\.venv\\Scripts\\python.exe worker.py run --job-id YOUR_JOB_ID --batch-size 1
```

The worker writes local progress events to `worker_progress.jsonl`.

## Optional executable build

For an `.exe` build on a Windows machine, double-click:

```text
build_windows_exe.cmd
```

The generated executable is written under `dist/`. This build step installs PyInstaller into the worker-local `.venv`; it does not add PyInstaller to the CV Analyzer server application.

The build output is a single file:

```text
dist\\CV Analyzer Local Worker.exe
```

The executable and desktop shortcut use the bundled `assets\\cv_analyzer_worker.ico` icon.
"""


def _worker_run_script(api_base_url: str) -> str:
    return f"""param(
  [Parameter(Mandatory=$true)][string]$ApiKey,
  [Parameter(Mandatory=$true)][int]$JobId,
  [int]$BatchSize = 1
)

$ErrorActionPreference = "Stop"
$env:CV_ANALYZER_API_URL = "{api_base_url}"
$env:CV_WORKER_API_KEY = $ApiKey

if (!(Test-Path ".venv")) {{
  python -m venv .venv
}}

.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe worker.py login
.\\.venv\\Scripts\\python.exe worker.py jobs
.\\.venv\\Scripts\\python.exe worker.py run --job-id $JobId --batch-size $BatchSize
"""


def _worker_env_example(api_base_url: str) -> str:
    return f"""CV_ANALYZER_API_URL={api_base_url}
CV_WORKER_API_KEY=sk_worker_live_xxx
CV_WORKER_MAX_FILE_BYTES=26214400
CV_WORKER_PROGRESS_LOG=worker_progress.jsonl
CV_WORKER_OPENAI_API_KEY=
CV_WORKER_OPENAI_MODEL=gpt-5.2
CV_WORKER_AI_MAX_REVIEWS=25
"""


def _worker_config_example(api_base_url: str) -> str:
    return json.dumps(
        {
            "api_base_url": api_base_url,
            "server_mode": {
                "enabled": False,
                "worker_api_key": "paste-created-worker-key-at-runtime",
                "batch_size": 1,
            },
            "local_mode": {
                "enabled": True,
                "cv_folder": "C:/path/to/cv-folder",
                "output_folder": "C:/path/to/local-results",
                "ai_mode": "none",
            },
            "limits": {
                "max_file_bytes": 26214400,
                "ai_max_reviews": 25,
            },
        },
        indent=2,
    )

def _release_expired_claims(db: Session, organization_id: int, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    expired_claims = db.query(WorkerClaim).filter(
        WorkerClaim.organization_id == organization_id,
        WorkerClaim.status == "claimed",
        WorkerClaim.claim_expires_at < now
    ).with_for_update().all()

    released = 0
    for claim in expired_claims:
        wk = db.query(WorkerKey).filter(WorkerKey.id == claim.worker_key_id).with_for_update().first()
        if wk:
            wk.quota_reserved = max(0, int(wk.quota_reserved or 0) - 1)
            db.add(QuotaEvent(
                worker_key_id=wk.id,
                organization_id=claim.organization_id,
                job_id=claim.job_id,
                cv_id=claim.cv_id,
                event_type="expired",
                amount=1,
                metadata_={"claim_id": claim.id},
            ))
        claim.status = "expired"
        released += 1
    return released

def get_current_worker(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    session_hash = hash_key(credentials.credentials)
    ws = db.query(WorkerSession).filter(WorkerSession.access_token_hash == session_hash).first()
    if not ws or ws.revoked_at or ws.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    wk = db.query(WorkerKey).filter(WorkerKey.id == ws.worker_key_id).first()
    if not wk or wk.revoked_at or (wk.expires_at and wk.expires_at < datetime.utcnow()):
        raise HTTPException(status_code=401, detail="Worker key revoked or expired")

    ws.last_seen_at = datetime.utcnow()
    db.commit()
    return {"session": ws, "key": wk}

@router.post("/worker-keys", response_model=WorkerKeyCreateResponse)
@limiter.limit("5/minute")
def create_worker_key(
    request: Request,
    req: WorkerKeyCreate,
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required)
):
    org_id = req.company_id or recruiter.organization_id
    if org_id != recruiter.organization_id:
        raise HTTPException(status_code=403, detail="Cannot create key for another company")
    if not recruiter.organization_id:
        raise HTTPException(status_code=400, detail="Recruiter profile is incomplete")
    if req.job_id:
        job = db.query(RecruiterJob).filter(
            RecruiterJob.id == req.job_id,
            RecruiterJob.organization_id == recruiter.organization_id,
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found for this company")

    plan = _resolve_worker_plan(db, org_id, recruiter)
    quota = _worker_quota_snapshot(db, org_id, plan=plan)
    if quota["monthly_limit"] <= 0:
        raise HTTPException(status_code=403, detail="Local Worker is available for premium plans only")
    if req.quota_limit > quota["quota_remaining"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Monthly Local Worker quota exceeded. "
                f"Remaining: {quota['quota_remaining']} of {quota['monthly_limit']}"
            ),
        )

    raw_key = "sk_worker_live_" + secrets.token_urlsafe(32)
    key_hash = hash_key(raw_key)

    new_key = WorkerKey(
        name=req.name,
        organization_id=org_id,
        job_id=req.job_id,
        key_prefix=raw_key[:20],
        key_hash=key_hash,
        quota_limit=req.quota_limit,
        quota_used=0,
        quota_reserved=0,
        expires_at=req.expires_at,
        created_by_user_id=recruiter.id,
        permissions=req.permissions,
    )
    try:
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Worker key could not be created")

    return {**_worker_key_payload(new_key), "api_key": raw_key}

@router.get("/worker-keys", response_model=list[WorkerKeyResponse])
def list_worker_keys(
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required)
):
    keys = db.query(WorkerKey).filter(WorkerKey.organization_id == recruiter.organization_id).all()
    return [_worker_key_payload(k) for k in keys]


@router.get("/worker/quota")
def worker_quota_summary(
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required),
):
    if not recruiter.organization_id:
        raise HTTPException(status_code=400, detail="Recruiter profile is incomplete")
    plan = _resolve_worker_plan(db, recruiter.organization_id, recruiter)
    quota = _worker_quota_snapshot(db, recruiter.organization_id, plan=plan)
    return {
        **quota,
        "organization_id": recruiter.organization_id,
    }


@router.get("/worker/download-package")
@limiter.limit("10/minute")
def download_worker_package(
    request: Request,
    recruiter = Depends(recruiter_required),
):
    """Return a self-contained Local Worker ZIP for employers.

    The package intentionally does not include API keys or bearer tokens. Users
    must paste the one-time worker key created in the Recruiter Local Worker tab.
    """
    package_files = [
        ("worker.py", _LOCAL_WORKER_DIR / "worker.py"),
        ("qml_gui.py", _LOCAL_WORKER_DIR / "qml_gui.py"),
        ("qt_gui.py", _LOCAL_WORKER_DIR / "qt_gui.py"),
        ("gui.py", _LOCAL_WORKER_DIR / "gui.py"),
        ("workspace.py", _LOCAL_WORKER_DIR / "workspace.py"),
        ("credentials.py", _LOCAL_WORKER_DIR / "credentials.py"),
        ("requirements.txt", _LOCAL_WORKER_DIR / "requirements.txt"),
        ("start_here.cmd", _LOCAL_WORKER_DIR / "start_here.cmd"),
        ("install_windows.cmd", _LOCAL_WORKER_DIR / "install_windows.cmd"),
        ("run_gui.cmd", _LOCAL_WORKER_DIR / "run_gui.cmd"),
        ("build_windows_exe.cmd", _LOCAL_WORKER_DIR / "build_windows_exe.cmd"),
        ("CV Analyzer Local Worker.spec", _LOCAL_WORKER_DIR / "CV Analyzer Local Worker.spec"),
        ("assets/cv_analyzer_worker.ico", _LOCAL_WORKER_DIR / "assets" / "cv_analyzer_worker.ico"),
        ("VERSION", _LOCAL_WORKER_DIR / "VERSION"),
    ]
    missing = [name for name, path in package_files if not path.exists()]
    qml_dir = _LOCAL_WORKER_DIR / "qml"
    if not qml_dir.exists():
        missing.append("qml/")
    if missing:
        raise HTTPException(status_code=500, detail="Local worker package files are missing")

    api_base_url = str(request.base_url).rstrip("/") + "/api/worker"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, path in package_files:
            archive.write(path, arcname=arcname)
        for path in qml_dir.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=str(Path("qml") / path.relative_to(qml_dir)))
        archive.writestr("README.md", _worker_package_readme(api_base_url))
        archive.writestr("run-worker.ps1", _worker_run_script(api_base_url))
        archive.writestr(".env.example", _worker_env_example(api_base_url))
        archive.writestr("config.example.json", _worker_config_example(api_base_url))

    audit_log(
        "worker_package_downloaded",
        organization_id=recruiter.organization_id,
        user_id=recruiter.id,
    )
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="cv-analyzer-local-worker.zip"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/worker/download-exe")
@limiter.limit("10/minute")
def download_worker_exe(
    request: Request,
    recruiter = Depends(recruiter_required),
):
    """Return the prebuilt one-file Windows Local Worker executable."""
    exe_path = _worker_exe_path()
    if not exe_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "The one-file Local Worker executable has not been built on this server yet. "
                "Run local_worker/build_windows_exe.cmd on a Windows build machine and publish the dist executable, "
                "or set WORKER_EXE_PATH to the published executable path."
            ),
        )

    audit_log(
        "worker_exe_downloaded",
        organization_id=recruiter.organization_id,
        user_id=recruiter.id,
    )
    return FileResponse(
        exe_path,
        media_type="application/vnd.microsoft.portable-executable",
        filename="CV Analyzer Local Worker.exe",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.post("/worker-keys/{key_id}/revoke")
def revoke_worker_key(
    key_id: int,
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required)
):
    wk = db.query(WorkerKey).filter(WorkerKey.id == key_id, WorkerKey.organization_id == recruiter.organization_id).first()
    if not wk:
        raise HTTPException(status_code=404, detail="Key not found")

    wk.revoked_at = datetime.utcnow()
    db.query(WorkerSession).filter(WorkerSession.worker_key_id == key_id).update({"revoked_at": datetime.utcnow()})
    db.commit()
    audit_log("worker_key_revoked", worker_key_id=key_id, organization_id=recruiter.organization_id)
    return {"message": "Revoked"}


@router.get("/worker/sessions")
def list_worker_sessions(
    db: Session = Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    now = datetime.utcnow()
    rows = (
        db.query(WorkerSession, WorkerKey)
        .join(WorkerKey, WorkerSession.worker_key_id == WorkerKey.id)
        .filter(WorkerSession.organization_id == recruiter.organization_id)
        .order_by(WorkerSession.last_seen_at.desc().nullslast(), WorkerSession.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "sessions": [
            {
                "id": session.id,
                "worker_key_id": session.worker_key_id,
                "key_name": key.name,
                "device_name": session.device_name,
                "worker_version": session.worker_version,
                "created_at": session.created_at,
                "last_seen_at": session.last_seen_at,
                "expires_at": session.expires_at,
                "revoked_at": session.revoked_at or key.revoked_at,
                "is_expired": bool(session.expires_at and session.expires_at < now),
            }
            for session, key in rows
        ]
    }

@router.post("/worker/auth", response_model=WorkerAuthResponse)
@limiter.limit("10/minute")
def worker_auth(request: Request, req: WorkerAuthRequest, db: Session = Depends(get_db)):
    key_hash = hash_key(req.api_key)
    wk = db.query(WorkerKey).filter(WorkerKey.key_hash == key_hash).first()

    if not wk or wk.revoked_at:
        audit_log("worker_auth_failed", reason="invalid_or_revoked", key_hash_prefix=key_hash[:12])
        raise HTTPException(status_code=401, detail="Invalid or revoked key")
    if wk.expires_at and wk.expires_at < datetime.utcnow():
        audit_log("worker_auth_failed", reason="expired", worker_key_id=wk.id, organization_id=wk.organization_id)
        raise HTTPException(status_code=401, detail="Key expired")

    session_token = "sess_" + secrets.token_urlsafe(32)
    session_hash = hash_key(session_token)
    expires_in = 3600
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    ws = WorkerSession(
        worker_key_id=wk.id,
        organization_id=wk.organization_id,
        device_name=req.device_name,
        worker_version=req.worker_version,
        access_token_hash=session_hash,
        expires_at=expires_at
    )
    wk.last_used_at = datetime.utcnow()
    db.add(ws)
    db.commit()
    audit_log(
        "worker_auth_success",
        worker_key_id=wk.id,
        organization_id=wk.organization_id,
        session_id=ws.id,
        worker_version=req.worker_version,
    )

    allowed_jobs = [wk.job_id] if wk.job_id else [j.id for j in db.query(RecruiterJob).filter(RecruiterJob.organization_id == wk.organization_id, RecruiterJob.is_active == True).all()]
    quota_remaining = max(0, int(wk.quota_limit or 0) - int(wk.quota_used or 0) - int(wk.quota_reserved or 0))

    return WorkerAuthResponse(
        access_token=session_token,
        expires_in=expires_in,
        company_id=wk.organization_id,
        allowed_jobs=allowed_jobs,
        quota_remaining=quota_remaining,
        permissions=_safe_permissions(wk.permissions),
    )

@router.get("/worker/jobs")
def worker_get_jobs(worker=Depends(get_current_worker), db: Session = Depends(get_db)):
    wk = worker["key"]
    if wk.job_id:
        return {"jobs": [wk.job_id]}
    jobs = db.query(RecruiterJob).filter(RecruiterJob.organization_id == wk.organization_id, RecruiterJob.is_active == True).all()
    return {"jobs": [j.id for j in jobs]}

@router.get("/worker/jobs/{jobId}/config", response_model=JobConfigResponse)
def worker_job_config(jobId: int, worker=Depends(get_current_worker), db: Session = Depends(get_db)):
    wk = worker["key"]
    if wk.job_id and wk.job_id != jobId:
        raise HTTPException(status_code=403, detail="Key not allowed for this job")
    job = db.query(RecruiterJob).filter(RecruiterJob.id == jobId, RecruiterJob.organization_id == wk.organization_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobConfigResponse(
        job_id=job.id,
        title=job.title,
        description=job.description,
        required_skills=_extract_job_skills(job.description),
        nice_to_have_skills=[],
        hard_reject_criteria=[],
        scoring_weights={"required_skills": 0.7, "nice_to_have_skills": 0.2, "hard_reject": 0.1},
    )

@router.post("/worker/jobs/{jobId}/claim", response_model=ClaimResponse)
@limiter.limit("60/minute")
def worker_claim(jobId: int, request: Request, req: ClaimRequest, worker=Depends(get_current_worker), db: Session = Depends(get_db)):
    wk = worker["key"]
    ws = worker["session"]
    if wk.job_id and wk.job_id != jobId:
        raise HTTPException(status_code=403, detail="Not authorized for this job")
    if not (wk.permissions or {}).get("claim", True):
        raise HTTPException(status_code=403, detail="Worker key cannot claim CVs")
    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == jobId,
        RecruiterJob.organization_id == wk.organization_id,
        RecruiterJob.is_active == True,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    _release_expired_claims(db, wk.organization_id)
    db.commit()

    # Atomically reserve quota
    quota_remaining = max(0, int(wk.quota_limit or 0) - int(wk.quota_used or 0) - int(wk.quota_reserved or 0))
    claim_count = min(req.limit, 50, quota_remaining) # max 50 per batch
    if claim_count <= 0:
        raise HTTPException(status_code=402, detail="Quota exceeded")

    # Select only candidates explicitly attached to this job via candidate_actions.
    # Falling back to the global candidate pool would leak unrelated company/job data.
    active_action_subq = db.query(WorkerClaim.candidate_action_id).filter(
        WorkerClaim.job_id == jobId,
        WorkerClaim.organization_id == wk.organization_id,
        WorkerClaim.candidate_action_id != None,
        WorkerClaim.status == "claimed",
        WorkerClaim.claim_expires_at >= datetime.utcnow(),
    )
    completed_action_subq = db.query(WorkerAnalysisResult.candidate_action_id).filter(
        WorkerAnalysisResult.job_id == jobId,
        WorkerAnalysisResult.organization_id == wk.organization_id,
        WorkerAnalysisResult.candidate_action_id != None,
    )

    actions = db.query(CandidateAction).filter(
        CandidateAction.organization_id == wk.organization_id,
        CandidateAction.job_id == jobId,
        or_(
            and_(CandidateAction.cv_text != None, func.length(func.trim(CandidateAction.cv_text)) > 0),
            CandidateAction.cv_file_key != None,
        ),
        CandidateAction.id.notin_(active_action_subq),
        CandidateAction.id.notin_(completed_action_subq),
    ).order_by(CandidateAction.created_at.asc()).with_for_update(skip_locked=True).limit(claim_count).all()

    if not actions:
        return ClaimResponse(items=[], claim_expires_at=datetime.utcnow())

    candidates = [(_ensure_candidate_for_action(db, action), action) for action in actions]
    db.flush()

    candidate_ids = [candidate.id for candidate, _ in candidates]
    active_candidate_ids = {
        row[0] for row in db.query(WorkerClaim.candidate_id).filter(
            WorkerClaim.job_id == jobId,
            WorkerClaim.organization_id == wk.organization_id,
            WorkerClaim.candidate_id.in_(candidate_ids),
            WorkerClaim.status == "claimed",
            WorkerClaim.claim_expires_at >= datetime.utcnow(),
        ).all()
    }
    completed_candidate_ids = {
        row[0] for row in db.query(WorkerAnalysisResult.candidate_id).filter(
            WorkerAnalysisResult.job_id == jobId,
            WorkerAnalysisResult.organization_id == wk.organization_id,
            WorkerAnalysisResult.candidate_id.in_(candidate_ids),
        ).all()
    }
    candidates = [
        (candidate, action)
        for candidate, action in candidates
        if candidate.id not in active_candidate_ids and candidate.id not in completed_candidate_ids
    ]

    if not candidates:
        return ClaimResponse(items=[], claim_expires_at=datetime.utcnow())

    actual_count = len(candidates)
    db.query(WorkerKey).filter(WorkerKey.organization_id == wk.organization_id).with_for_update().all()
    org_plan = _resolve_worker_plan(db, wk.organization_id)
    org_quota = _worker_quota_snapshot(db, wk.organization_id, plan=org_plan)
    if org_quota["monthly_limit"] <= 0 or org_quota["runtime_quota_remaining"] < actual_count:
        db.rollback()
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly Local Worker quota exceeded. "
                f"Remaining: {org_quota['runtime_quota_remaining']} of {org_quota['monthly_limit']}"
            ),
        )

    # Atomic quota check and reserve
    updated_rows = db.query(WorkerKey).filter(
        WorkerKey.id == wk.id,
        WorkerKey.revoked_at == None,
        or_(WorkerKey.expires_at == None, WorkerKey.expires_at > datetime.utcnow()),
        (WorkerKey.quota_used + WorkerKey.quota_reserved + actual_count) <= WorkerKey.quota_limit
    ).update({
        WorkerKey.quota_reserved: WorkerKey.quota_reserved + actual_count
    }, synchronize_session=False)

    if updated_rows == 0:
        db.rollback()
        raise HTTPException(status_code=402, detail="Quota exceeded or key revoked")

    items = []
    claim_expires_at = datetime.utcnow() + timedelta(minutes=30)
    for c, action in candidates:
        wc = WorkerClaim(
            worker_key_id=wk.id,
            worker_session_id=ws.id,
            organization_id=wk.organization_id,
            job_id=jobId,
            candidate_id=c.id,
            candidate_action_id=action.id,
            cv_id=c.id,
            claim_expires_at=claim_expires_at
        )
        db.add(wc)
        db.flush()

        download_url = _storage_download_url(action)
        if download_url:
            file_name = _safe_file_name(action.cv_file_name, f"candidate_{c.id}.{_file_type_from_name(action.cv_file_name, 'pdf')}")
            file_type = action.cv_file_type or _file_type_from_name(file_name, "pdf")
        else:
            signed_expires_at = min(claim_expires_at, datetime.utcnow() + timedelta(seconds=_DOWNLOAD_TOKEN_TTL_SECONDS))
            download_token = _sign_download_token(wc.id, c.id, signed_expires_at)
            download_url = f"{request.url_for('worker_download_cv', claim_id=wc.id)}?token={download_token}"
            file_name = _safe_download_filename(action.candidate_name, wc.id)
            file_type = "txt"

        items.append(ClaimItem(
            claim_id=wc.id,
            candidate_id=c.id,
            candidate_action_id=action.id,
            cv_id=c.id,
            download_url=download_url,
            file_name=file_name,
            file_type=file_type
        ))

    # Log quota event
    db.add(QuotaEvent(
        worker_key_id=wk.id, organization_id=wk.organization_id, job_id=jobId,
        event_type="reserved", amount=actual_count, metadata_={"session_id": ws.id}
    ))

    db.commit()
    audit_log(
        "worker_claim_created",
        worker_key_id=wk.id,
        organization_id=wk.organization_id,
        session_id=ws.id,
        job_id=jobId,
        amount=actual_count,
    )

    return ClaimResponse(items=items, claim_expires_at=claim_expires_at)

@router.get("/worker/download/{claim_id}", name="worker_download_cv")
def worker_download_cv(claim_id: int, token: str, db: Session = Depends(get_db)):
    token_claim_id, token_cv_id, _expires_at = _verify_download_token(token)
    if token_claim_id != claim_id:
        raise HTTPException(status_code=403, detail="Invalid download URL")

    claim = db.query(WorkerClaim).filter(WorkerClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    now = datetime.utcnow()
    session = db.query(WorkerSession).filter(WorkerSession.id == claim.worker_session_id).first()
    key = db.query(WorkerKey).filter(WorkerKey.id == claim.worker_key_id).first()
    if not session or session.revoked_at or session.expires_at < now:
        raise HTTPException(status_code=401, detail="Worker session is no longer active")
    if not key or key.revoked_at or (key.expires_at and key.expires_at < now):
        raise HTTPException(status_code=401, detail="Worker key is no longer active")
    if session.worker_key_id != claim.worker_key_id or key.organization_id != claim.organization_id:
        raise HTTPException(status_code=403, detail="Invalid download scope")
    if claim.status != "claimed":
        raise HTTPException(status_code=409, detail="Claim is no longer active")
    if claim.claim_expires_at < now:
        raise HTTPException(status_code=410, detail="Claim expired")
    if token_cv_id is not None and claim.cv_id is not None and token_cv_id != claim.cv_id:
        raise HTTPException(status_code=403, detail="Invalid download URL")

    action = None
    if claim.candidate_action_id:
        action = db.query(CandidateAction).filter(
            CandidateAction.id == claim.candidate_action_id,
            CandidateAction.organization_id == claim.organization_id,
            CandidateAction.job_id == claim.job_id,
        ).first()
    candidate = db.query(Candidate).filter(
        Candidate.id == claim.candidate_id,
        Candidate.organization_id == claim.organization_id,
    ).first()

    cv_text = (action.cv_text if action else None) or (candidate.cv_text if candidate else None)
    if not cv_text or not cv_text.strip():
        raise HTTPException(status_code=404, detail="CV text is not available for this claim")

    filename = _safe_download_filename(
        (action.candidate_name if action else None) or (candidate.name if candidate else None),
        claim.id,
    )
    return Response(
        content=cv_text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.post("/worker/jobs/{jobId}/results")
@limiter.limit("120/minute")
def worker_submit_results(jobId: int, request: Request, req: AnalysisResultRequest, worker=Depends(get_current_worker), db: Session = Depends(get_db)):
    wk = worker["key"]
    ws = worker["session"]
    if not (wk.permissions or {}).get("submit_results", True):
        raise HTTPException(status_code=403, detail="Worker key cannot submit results")

    # Verify active claim
    claim = db.query(WorkerClaim).filter(
        WorkerClaim.candidate_id == req.candidate_id,
        WorkerClaim.job_id == jobId,
        WorkerClaim.worker_key_id == wk.id,
        WorkerClaim.worker_session_id == ws.id,
        WorkerClaim.status == "claimed"
    ).with_for_update().first()

    if not claim:
        existing_result = db.query(WorkerAnalysisResult).filter(
            WorkerAnalysisResult.candidate_id == req.candidate_id,
            WorkerAnalysisResult.job_id == jobId,
            WorkerAnalysisResult.organization_id == wk.organization_id,
        ).first()
        if existing_result:
            return {"status": "already_processed"}
        raise HTTPException(status_code=400, detail="No active claim found for candidate")
    if req.cv_id is not None and claim.cv_id is not None and req.cv_id != claim.cv_id:
        raise HTTPException(status_code=400, detail="Result CV does not match active claim")
    if claim.claim_expires_at < datetime.utcnow():
        claim.status = "expired"
        wk_locked = db.query(WorkerKey).filter(WorkerKey.id == wk.id).with_for_update().first()
        if wk_locked:
            wk_locked.quota_reserved = max(0, int(wk_locked.quota_reserved or 0) - 1)
            db.add(QuotaEvent(
                worker_key_id=wk.id,
                organization_id=wk.organization_id,
                job_id=jobId,
                cv_id=req.cv_id,
                event_type="expired",
                amount=1,
                metadata_={"claim_id": claim.id, "reason": "late_result"},
            ))
        db.commit()
        raise HTTPException(status_code=409, detail="Claim expired; request a new claim")

    # Check if duplicate completion
    existing_result = db.query(WorkerAnalysisResult).filter(
        WorkerAnalysisResult.job_id == jobId,
        WorkerAnalysisResult.organization_id == wk.organization_id,
        or_(
            and_(
                WorkerAnalysisResult.candidate_action_id != None,
                WorkerAnalysisResult.candidate_action_id == claim.candidate_action_id,
            ),
            and_(
                WorkerAnalysisResult.candidate_action_id == None,
                WorkerAnalysisResult.candidate_id == req.candidate_id,
            ),
        ),
    ).first()

    if existing_result:
        # Already processed, maybe by another crashed worker that recovered, just mark claim expired to refund.
        claim.status = "expired"
        wk_locked = db.query(WorkerKey).filter(WorkerKey.id == wk.id).with_for_update().first()
        if wk_locked:
            wk_locked.quota_reserved = max(0, int(wk_locked.quota_reserved or 0) - 1)
            db.add(QuotaEvent(
                worker_key_id=wk.id,
                organization_id=wk.organization_id,
                job_id=jobId,
                cv_id=req.cv_id,
                event_type="refunded",
                amount=1,
                metadata_={"claim_id": claim.id, "reason": "already_processed"},
            ))
        db.commit()
        audit_log(
            "worker_quota_refunded",
            worker_key_id=wk.id,
            organization_id=wk.organization_id,
            job_id=jobId,
            claim_id=claim.id,
            reason="already_processed",
        )
        return {"status": "already_processed"}

    candidate_status = decision_to_candidate_status(req.decision)
    result = WorkerAnalysisResult(
        organization_id=wk.organization_id,
        job_id=jobId,
        candidate_id=req.candidate_id,
        candidate_action_id=claim.candidate_action_id,
        cv_id=req.cv_id,
        score=req.score,
        decision=req.decision,
        candidate_status=candidate_status,
        confidence=req.confidence,
        summary=req.summary,
        matched_skills=req.matched_skills,
        missing_skills=req.missing_skills,
        risk_flags=req.risk_flags,
        explanation=req.explanation,
        worker_key_id=wk.id,
        worker_version=req.worker_version,
        engine_version=req.engine_version
    )
    db.add(result)
    db.flush()
    candidate_name = None
    if claim.candidate_action_id:
        action = db.query(CandidateAction).filter(
            CandidateAction.id == claim.candidate_action_id,
            CandidateAction.organization_id == wk.organization_id,
        ).first()
        if action:
            candidate_name = action.candidate_name
    if not candidate_name:
        candidate = db.query(Candidate).filter(
            Candidate.id == req.candidate_id,
            Candidate.organization_id == wk.organization_id,
        ).first()
        candidate_name = candidate.name if candidate else None
    record_candidate_status_event(
        db,
        organization_id=wk.organization_id,
        candidate_status=candidate_status,
        candidate_name=candidate_name,
        decision=req.decision,
        score=req.score,
        actor_user_id=wk.created_by_user_id,
        actor_role="local_worker",
        candidate_id=req.candidate_id,
        candidate_action_id=claim.candidate_action_id,
        analysis_result_id=result.id,
        recipient_user_id=wk.created_by_user_id,
        metadata={
            "job_id": jobId,
            "worker_key_id": wk.id,
            "worker_session_id": ws.id,
            "source": "worker_submit_results",
        },
    )

    claim.status = "completed"
    claim.completed_at = datetime.utcnow()

    # Atomic transfer from reserved to used
    updated = db.query(WorkerKey).filter(
        WorkerKey.id == wk.id,
        WorkerKey.quota_reserved > 0
    ).update({
        WorkerKey.quota_reserved: WorkerKey.quota_reserved - 1,
        WorkerKey.quota_used: WorkerKey.quota_used + 1
    }, synchronize_session=False)

    if updated == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reserved quota not found for this claim")
    db.add(QuotaEvent(
        worker_key_id=wk.id, organization_id=wk.organization_id, job_id=jobId, cv_id=req.cv_id,
        event_type="completed", amount=1, metadata_={"claim_id": claim.id}
    ))
    db.commit()
    audit_log(
        "worker_result_submitted",
        worker_key_id=wk.id,
        organization_id=wk.organization_id,
        session_id=ws.id,
        job_id=jobId,
        claim_id=claim.id,
        score=req.score,
        decision=req.decision,
    )

    return {"status": "ok"}

@router.post("/worker/heartbeat")
def worker_heartbeat(worker=Depends(get_current_worker), db: Session = Depends(get_db)):
    ws = worker["session"]
    ws.last_seen_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}

@router.get("/worker/dashboard-progress/{job_id}")
def worker_dashboard_progress(
    job_id: int,
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required)
):
    # Verify job belongs to org
    job = db.query(RecruiterJob).filter(RecruiterJob.id == job_id, RecruiterJob.organization_id == recruiter.organization_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    total_cvs = db.query(CandidateAction).filter(
        CandidateAction.organization_id == recruiter.organization_id,
        CandidateAction.job_id == job_id,
        or_(
            and_(CandidateAction.cv_text != None, func.length(func.trim(CandidateAction.cv_text)) > 0),
            CandidateAction.cv_file_key != None,
        ),
    ).count()
    claimed = db.query(WorkerClaim).filter(
        WorkerClaim.organization_id == recruiter.organization_id,
        WorkerClaim.job_id == job_id,
        WorkerClaim.status == "claimed",
        WorkerClaim.claim_expires_at >= datetime.utcnow(),
    ).count()

    results = db.query(WorkerAnalysisResult).filter(
        WorkerAnalysisResult.organization_id == recruiter.organization_id,
        WorkerAnalysisResult.job_id == job_id,
    ).all()
    processed = len(results)
    failed = db.query(WorkerClaim).filter(
        WorkerClaim.organization_id == recruiter.organization_id,
        WorkerClaim.job_id == job_id,
        WorkerClaim.status == "failed",
    ).count()

    rec_accept = sum(1 for r in results if r.decision == "recommended_accept")
    rec_review = sum(1 for r in results if r.decision == "recommended_review")
    rec_reject = sum(1 for r in results if r.decision == "recommended_reject")

    keys = db.query(WorkerKey).filter(
        WorkerKey.organization_id == recruiter.organization_id,
        or_(WorkerKey.job_id == job_id, WorkerKey.job_id == None),
    ).all()
    quota_limit = sum(k.quota_limit for k in keys)
    quota_used = sum(k.quota_used for k in keys)
    quota_reserved = sum(k.quota_reserved for k in keys)
    quota_remaining = max(0, quota_limit - quota_used - quota_reserved)

    return {
      "total_cvs": total_cvs,
      "total": total_cvs,
      "claimed": claimed,
      "processed": processed,
      "failed": failed,
      "recommended_accept": rec_accept,
      "recommended_review": rec_review,
      "recommended_reject": rec_reject,
      "quota_limit": quota_limit,
      "quota_used": quota_used,
      "quota_reserved": quota_reserved,
      "quota_remaining": quota_remaining
    }


from pydantic import BaseModel
from typing import List, Optional

class OfflineSyncResultItem(BaseModel):
    file_name: str
    file_type: str
    file_hash: Optional[str] = None
    duplicate_of: Optional[str] = None
    score: float
    decision: str
    confidence: str
    summary: str
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    risk_flags: List[str] = []
    explanation: str
    cv_text: Optional[str] = None
    candidate_name: str
    candidate_email: Optional[str] = None
    worker_version: Optional[str] = None
    engine_version: Optional[str] = None

class OfflineSyncRequest(BaseModel):
    job_id: int
    results: List[OfflineSyncResultItem]

@router.post("/worker/offline-sync")
@limiter.limit("10/minute")
def worker_offline_sync(
    req: OfflineSyncRequest,
    worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    wk = worker["key"]
    ws = worker["session"]

    if not (wk.permissions or {}).get("submit_results", True):
        raise HTTPException(status_code=403, detail="Worker key cannot submit results")

    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == req.job_id,
        RecruiterJob.organization_id == wk.organization_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job description not found on server")

    actual_count = len(req.results)
    if actual_count == 0:
        return {"status": "ok", "synced_count": 0}

    db.query(WorkerKey).filter(WorkerKey.organization_id == wk.organization_id).with_for_update().all()
    org_plan = _resolve_worker_plan(db, wk.organization_id)
    org_quota = _worker_quota_snapshot(db, wk.organization_id, plan=org_plan)
    if org_quota["monthly_limit"] <= 0 or org_quota["runtime_quota_remaining"] < actual_count:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly Local Worker quota exceeded. "
                f"Remaining: {org_quota['runtime_quota_remaining']} of {org_quota['monthly_limit']}"
            ),
        )

    # Atomic quota check and increment
    updated_rows = db.query(WorkerKey).filter(
        WorkerKey.id == wk.id,
        WorkerKey.revoked_at == None,
        or_(WorkerKey.expires_at == None, WorkerKey.expires_at > datetime.utcnow()),
        (WorkerKey.quota_used + WorkerKey.quota_reserved + actual_count) <= WorkerKey.quota_limit
    ).update({
        WorkerKey.quota_used: WorkerKey.quota_used + actual_count
    }, synchronize_session=False)

    if updated_rows == 0:
        raise HTTPException(status_code=402, detail="Quota limit exceeded or key revoked")

    synced_count = 0
    for item in req.results:
        candidate = None
        if item.candidate_email:
            candidate = db.query(Candidate).filter(
                Candidate.organization_id == wk.organization_id,
                Candidate.email == item.candidate_email
            ).first()

        if not candidate:
            candidate = Candidate(
                organization_id=wk.organization_id,
                name=item.candidate_name,
                email=item.candidate_email,
            )
            db.add(candidate)
            db.flush()

        # Check if CandidateAction exists
        action_record = db.query(CandidateAction).filter(
            CandidateAction.job_id == req.job_id,
            CandidateAction.organization_id == wk.organization_id,
            CandidateAction.candidate_email == item.candidate_email
        ).first() if item.candidate_email else None

        if not action_record:
            stage = "pending"
            if item.decision == "recommended_accept":
                stage = "shortlist"
            elif item.decision == "recommended_reject":
                stage = "rejected"

            action_record = CandidateAction(
                organization_id=wk.organization_id,
                job_id=req.job_id,
                recruiter_id=job.created_by,
                candidate_name=item.candidate_name,
                candidate_email=item.candidate_email,
                final_score=item.score,
                ats_score=item.score,
                action=stage,
                analysis_snapshot=json.dumps({
                    "score": item.score,
                    "decision": item.decision,
                    "confidence": item.confidence,
                    "summary": item.summary,
                    "matched_skills": item.matched_skills,
                    "missing_skills": item.missing_skills,
                    "risk_flags": item.risk_flags,
                    "explanation": item.explanation,
                }, default=str),
                cv_file_name=item.file_name,
                cv_file_type=item.file_type,
            )
            db.add(action_record)
            db.flush()

        candidate_status = decision_to_candidate_status(item.decision)

        # Create WorkerAnalysisResult
        result_record = WorkerAnalysisResult(
            organization_id=wk.organization_id,
            job_id=req.job_id,
            candidate_id=candidate.id,
            candidate_action_id=action_record.id,
            cv_id=candidate.id,
            score=item.score,
            decision=item.decision,
            candidate_status=candidate_status,
            confidence=item.confidence,
            summary=item.summary,
            matched_skills=item.matched_skills,
            missing_skills=item.missing_skills,
            risk_flags=item.risk_flags,
            explanation=item.explanation,
            source="offline_sync",
            worker_key_id=wk.id,
            worker_version=item.worker_version or "1.0.0",
            engine_version=item.engine_version or "1.0.0",
        )
        db.add(result_record)
        db.flush()
        record_candidate_status_event(
            db,
            organization_id=wk.organization_id,
            candidate_status=candidate_status,
            candidate_name=item.candidate_name,
            decision=item.decision,
            score=item.score,
            actor_user_id=wk.created_by_user_id,
            actor_role="local_worker",
            candidate_id=candidate.id,
            candidate_action_id=action_record.id,
            analysis_result_id=result_record.id,
            recipient_user_id=job.created_by,
            metadata={
                "job_id": req.job_id,
                "worker_key_id": wk.id,
                "worker_session_id": ws.id,
                "source": "offline_sync",
            },
        )

        # Log quota event
        db.add(QuotaEvent(
            worker_key_id=wk.id,
            organization_id=wk.organization_id,
            job_id=req.job_id,
            cv_id=candidate.id,
            event_type="completed",
            amount=1,
            metadata_={"sync_type": "offline_first"},
        ))

        synced_count += 1

    db.commit()
    audit_log(
        "worker_offline_sync",
        worker_key_id=wk.id,
        organization_id=wk.organization_id,
        session_id=ws.id,
        job_id=req.job_id,
        synced_count=synced_count,
    )
    return {"status": "ok", "synced_count": synced_count}
