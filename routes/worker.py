import secrets
import hashlib
import hmac
import base64
import os
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
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
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
security = HTTPBearer()

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
            cv_text=action.cv_text,
        )
        db.add(candidate)
        db.flush()
    elif action.cv_text and candidate.cv_text != action.cv_text:
        candidate.cv_text = action.cv_text
        db.flush()
    return candidate


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
        "permissions": wk.permissions or {},
    }

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
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    return {**_worker_key_payload(new_key), "api_key": raw_key}

@router.get("/worker-keys", response_model=list[WorkerKeyResponse])
def list_worker_keys(
    db: Session = Depends(get_db),
    recruiter = Depends(recruiter_required)
):
    keys = db.query(WorkerKey).filter(WorkerKey.organization_id == recruiter.organization_id).all()
    return [_worker_key_payload(k) for k in keys]

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
        quota_remaining=quota_remaining
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

    result = WorkerAnalysisResult(
        organization_id=wk.organization_id,
        job_id=jobId,
        candidate_id=req.candidate_id,
        candidate_action_id=claim.candidate_action_id,
        cv_id=req.cv_id,
        score=req.score,
        decision=req.decision,
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
