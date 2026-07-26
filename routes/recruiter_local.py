"""
Local processing mode for recruiters - zero data retention.
CVs are processed and results returned without saving to database.
"""

from core.timeutils import utcnow
import secrets
import os
import logging
import hashlib
import io
import uuid

logger = logging.getLogger(__name__)
from datetime import timedelta
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Header, UploadFile, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config.aws import MAX_UPLOAD_BYTES
from database import SessionLocal, get_db
from models import APISubscription, RecruiterJob
from core.quota import _reset_api_subscription_usage_if_needed
from routes.recruiter import recruiter_required
from security.file_guard import read_upload_limited
from utils.csv_exporter import generate_csv_download
from utils.json_exporter import generate_json_download

router = APIRouter(prefix="/api/v1/recruiter", tags=["recruiter-local"])

_MAX_LOCAL_BATCH_FILES = int(os.getenv("RECRUITER_LOCAL_MAX_BATCH_FILES", "100"))
_MAX_LINKEDIN_ZIP_BYTES = min(
    50_000_000,
    max(1_000_000, int(os.getenv("RECRUITER_LINKEDIN_ZIP_MAX_BYTES", "50000000"))),
)


def _format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} bytes"


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"cv_{secrets.token_urlsafe(32)}"


def validate_api_key(api_key: str, db: Session, lock: bool = False) -> APISubscription:
    """Validate API key and return subscription."""
    if not api_key or not api_key.startswith("cv_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    legacy_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    display_tail = api_key[-8:] if len(api_key) > 8 else "****"

    query = db.query(APISubscription)
    if lock:
        query = query.with_for_update()

    candidates = query.filter(
        APISubscription.is_active == True,
        or_(
            APISubscription.api_key_display == display_tail,
            APISubscription.api_key_hash == legacy_hash,
            APISubscription.api_key_hash == api_key,
        ),
    ).all()

    subscription = None
    for candidate in candidates:
        try:
            verified = candidate.verify_api_key(api_key)
        except Exception:
            verified = False
        if candidate.api_key_hash in {legacy_hash, api_key} or verified:
            subscription = candidate
            break

    if not subscription:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Check expiration
    if subscription.expires_at and subscription.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="API key expired")

    if _reset_api_subscription_usage_if_needed(subscription):
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    return subscription


def check_monthly_quota(subscription: APISubscription, requested_cvs: int):
    """Check if subscription has enough monthly quota."""
    remaining = subscription.monthly_limit - subscription.monthly_usage
    if remaining < requested_cvs:
        raise HTTPException(
            status_code=429, detail=f"Monthly quota exceeded. Remaining: {remaining}, Requested: {requested_cvs}"
        )


@router.post("/subscriptions/generate-key")
async def generate_subscription_key(
    db: Session = Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """
    Generate a new API key for local processing mode.
    Returns the API key that can be used for local processing.
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Recruiter profile is incomplete (no organization assigned)")

    # Check if organization already has an active subscription
    existing = (
        db.query(APISubscription)
        .filter(APISubscription.organization_id == org_id, APISubscription.is_active == True)
        .first()
    )

    if existing:
        masked_key = f"cv_***{existing.api_key_display}" if existing.api_key_display else "cv_***"
        return {
            "api_key": masked_key,
            "monthly_limit": existing.monthly_limit,
            "monthly_usage": existing.monthly_usage,
            "expires_at": existing.expires_at.isoformat() if existing.expires_at else None,
            "message": "Existing active subscription found. API key is hidden for security.",
        }

    # Create new subscription
    raw_key = generate_api_key()

    subscription = APISubscription(
        organization_id=org_id,
        monthly_limit=1000,  # Default 1000 CVs/month
        expires_at=utcnow() + timedelta(days=365),  # 1 year
        usage_reset_at=utcnow(),
    )
    subscription.set_api_key(raw_key)

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "api_key": raw_key,  # Returned only once
        "monthly_limit": subscription.monthly_limit,
        "monthly_usage": subscription.monthly_usage,
        "expires_at": subscription.expires_at.isoformat(),
        "message": "New API key generated successfully. Please copy it now as it won't be shown again.",
    }


@router.post("/subscriptions/rotate-key")
async def rotate_subscription_key(
    db: Session = Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """
    Rotate the API key for the organization.
    Deactivates the old active key and generates a new one.
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization assigned")

    # Deactivate all existing subscriptions for this org
    db.query(APISubscription).filter(
        APISubscription.organization_id == org_id, APISubscription.is_active == True
    ).update({"is_active": False})

    # Generate new key
    raw_key = generate_api_key()

    subscription = APISubscription(
        organization_id=org_id,
        monthly_limit=1000,
        expires_at=utcnow() + timedelta(days=365),
        usage_reset_at=utcnow(),
    )
    subscription.set_api_key(raw_key)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "api_key": raw_key,  # Returned only once
        "monthly_limit": subscription.monthly_limit,
        "monthly_usage": subscription.monthly_usage,
        "expires_at": subscription.expires_at.isoformat(),
        "message": "New API key generated and old keys deactivated. Please copy it now as it won't be shown again.",
    }


@router.post("/subscriptions/revoke-key")
async def revoke_subscription_key(
    db: Session = Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """
    Revoke all API keys for the organization.
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization assigned")

    updated = (
        db.query(APISubscription)
        .filter(APISubscription.organization_id == org_id, APISubscription.is_active == True)
        .update({"is_active": False})
    )

    db.commit()
    return {"message": f"Revoked {updated} API key(s)"}


@router.get("/subscriptions/usage")
async def get_subscription_usage(
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Get current subscription usage and limits."""
    subscription = validate_api_key(api_key, db)

    return {
        "monthly_limit": subscription.monthly_limit,
        "monthly_usage": subscription.monthly_usage,
        "remaining": subscription.monthly_limit - subscription.monthly_usage,
        "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None,
        "is_active": subscription.is_active,
    }


@router.post("/process-local")
async def process_cvs_local_mode(
    job_id: int = Form(..., gt=0),
    files: List[UploadFile] | None = File(None),
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Process CVs locally without saving to database.
    Returns results as JSON that can be downloaded.

    **Parameters:**
    - `job_id`: Target job position ID
    - `files`: List of PDF/TXT/DOCX files
    - `X-API-Key`: API key for authentication

    **Returns:**
    - Processing results (rankings, scores)
    - Download URLs for JSON/CSV export

    **Notes:**
    - No data is saved to our database
    - Results are returned immediately
    - Files are processed in memory and discarded
    """
    # Validate API key and quota
    subscription = validate_api_key(api_key, db, lock=True)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    check_monthly_quota(subscription, len(files))

    # Validate job belongs to organization
    job = (
        db.query(RecruiterJob)
        .filter(RecruiterJob.id == job_id, RecruiterJob.organization_id == subscription.organization_id)
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or you do not have permission to access it")

    # Validate files
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if len(files) > _MAX_LOCAL_BATCH_FILES:
        raise HTTPException(
            status_code=400, detail=f"Maximum {_MAX_LOCAL_BATCH_FILES} files per request (you provided {len(files)})"
        )

    # Process CVs (no database save)
    try:
        from utils.cv_processor import process_cv_batch_ultra_fast

        # Convert UploadFile to dict format for ultra-fast processing
        cv_files = []
        for file in files:
            try:
                content = await read_upload_limited(file)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large (max {_format_bytes(MAX_UPLOAD_BYTES)}): {file.filename}",
                )
            cv_files.append({"filename": file.filename, "content": content, "size": len(content)})

        results = await process_cv_batch_ultra_fast(
            files=cv_files,
            job_description=job.description,
            job_id=job_id,
            use_cache=True,
            workers=None,  # Auto-detect CPU cores
        )
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Large batch processing failed due to an unexpected error")

    # Update usage
    subscription.monthly_usage += len(files)
    subscription.last_used_at = utcnow()
    db.add(subscription)
    db.commit()

    # Generate download links (temporary, expire in 1 hour)
    json_url = generate_json_download(
        results,
        job_id,
        owner_organization_id=subscription.organization_id,
        owner_subscription_id=subscription.id,
    )
    csv_url = generate_csv_download(
        results,
        job_id,
        owner_organization_id=subscription.organization_id,
        owner_subscription_id=subscription.id,
    )

    return {
        "results": results,
        "summary": {
            "total_cvs": len(results),
            "job_id": job_id,
            "job_title": job.title,
            "processed_at": utcnow().isoformat(),
        },
        "downloads": {"json": json_url, "csv": csv_url},
        "usage": {
            "monthly_limit": subscription.monthly_limit,
            "monthly_usage": subscription.monthly_usage,
            "remaining": subscription.monthly_limit - subscription.monthly_usage,
        },
    }


@router.post("/process-linkedin-export")
async def process_linkedin_export_zip(
    job_id: int = Form(..., gt=0),
    zip_file: UploadFile = File(...),
    api_key: str = Header(..., alias="X-API-Key"),
    chunk_size: int = Form(200, ge=50, le=500),
    db: Session = Depends(get_db),
):
    """
    Process LinkedIn export ZIP containing multiple CVs.
    Extracts and processes all CVs from the ZIP file.

    **Parameters:**
    - `job_id`: Target job position ID
    - `zip_file`: LinkedIn export ZIP file
    - `X-API-Key`: API key for authentication
    - `chunk_size`: CVs per batch (50-500, default 200)

    **Returns:**
    - Processing results for all CVs in the ZIP
    - Download URLs for JSON/CSV export

    **Notes:**
    - Supports LinkedIn Sales Navigator exports
    - No data is saved to our database
    - Results are returned immediately
    """
    # Validate API key
    subscription = validate_api_key(api_key, db, lock=True)

    # Validate ZIP file
    if not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Get job details
    job = (
        db.query(RecruiterJob)
        .filter(RecruiterJob.id == job_id, RecruiterJob.organization_id == subscription.organization_id)
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Process LinkedIn export
    try:
        from utils.cv_processor import process_cv_batch_chunked

        results, summary = await process_cv_batch_chunked(
            zip_file=zip_file,
            job_description=job.description,
            job_id=job_id,
            chunk_size=chunk_size,
            progress_callback=None,  # Could integrate with WebSocket
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Large batch processing failed due to an unexpected error")

    # Update usage with actual count
    actual_cvs = len(results)
    check_monthly_quota(subscription, actual_cvs)  # Final check

    subscription.monthly_usage += actual_cvs
    subscription.last_used_at = utcnow()
    db.add(subscription)
    db.commit()

    # Generate download links
    json_url = generate_json_download(
        results,
        job_id,
        owner_organization_id=subscription.organization_id,
        owner_subscription_id=subscription.id,
    )
    csv_url = generate_csv_download(
        results,
        job_id,
        owner_organization_id=subscription.organization_id,
        owner_subscription_id=subscription.id,
    )

    return {
        "results": results,
        "summary": {
            "total_cvs": len(results),
            "job_id": job_id,
            "job_title": job.title,
            "source": "LinkedIn Export",
            "processed_at": utcnow().isoformat(),
        },
        "downloads": {"json": json_url, "csv": csv_url},
        "usage": {
            "monthly_limit": subscription.monthly_limit,
            "monthly_usage": subscription.monthly_usage,
            "remaining": subscription.monthly_limit - subscription.monthly_usage,
        },
    }


async def _process_linkedin_export_background(
    *,
    session_id: str,
    zip_contents: bytes,
    filename: str,
    subscription_id: int,
    job_id: int,
    chunk_size: int,
) -> None:
    from utils.cv_processor import process_cv_batch_chunked, set_processing_status

    db = SessionLocal()
    try:
        subscription = db.query(APISubscription).filter(APISubscription.id == subscription_id).first()
        job = db.query(RecruiterJob).filter(RecruiterJob.id == job_id).first()
        if not subscription or not job or job.organization_id != subscription.organization_id:
            await set_processing_status(
                session_id,
                {"status": "failed", "error": "Subscription or job is no longer available"},
            )
            return

        async def progress(payload):
            await set_processing_status(
                session_id,
                {
                    **dict(payload or {}),
                    "subscription_id": subscription_id,
                    "job_id": job_id,
                },
            )

        upload = UploadFile(file=io.BytesIO(zip_contents), filename=filename)
        results, summary = await process_cv_batch_chunked(
            zip_file=upload,
            job_description=job.description,
            job_id=job_id,
            chunk_size=chunk_size,
            progress_callback=progress,
            session_id=session_id,
        )

        subscription = (
            db.query(APISubscription)
            .filter(APISubscription.id == subscription_id, APISubscription.is_active == True)
            .with_for_update()
            .first()
        )
        if not subscription:
            raise ValueError("Subscription is no longer active")
        _reset_api_subscription_usage_if_needed(subscription)
        actual_cvs = len(results)
        check_monthly_quota(subscription, actual_cvs)
        subscription.monthly_usage += actual_cvs
        subscription.last_used_at = utcnow()
        db.add(subscription)
        db.commit()

        json_url = generate_json_download(
            results,
            job_id,
            owner_organization_id=subscription.organization_id,
            owner_subscription_id=subscription.id,
        )
        csv_url = generate_csv_download(
            results,
            job_id,
            owner_organization_id=subscription.organization_id,
            owner_subscription_id=subscription.id,
        )
        await set_processing_status(
            session_id,
            {
                **summary,
                "status": "completed",
                "subscription_id": subscription_id,
                "job_id": job_id,
                "job_title": job.title,
                "total_results": len(results),
                "results": results[:100],
                "downloads": {"json": json_url, "csv": csv_url},
                "usage": {
                    "monthly_limit": subscription.monthly_limit,
                    "monthly_usage": subscription.monthly_usage,
                    "remaining": subscription.monthly_limit - subscription.monthly_usage,
                },
            },
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Background LinkedIn processing failed: %s", exc)
        await set_processing_status(
            session_id,
            {
                "status": "failed",
                "subscription_id": subscription_id,
                "job_id": job_id,
                "error": str(exc)[:300],
            },
        )
    finally:
        db.close()


@router.post("/process-linkedin-export-large")
async def process_linkedin_export_large(
    background_tasks: BackgroundTasks,
    job_id: int = Form(..., gt=0),
    zip_file: UploadFile = File(...),
    api_key: str = Header(..., alias="X-API-Key"),
    chunk_size: int = Form(200, ge=50, le=500),
    db: Session = Depends(get_db),
):
    """
    Process large LinkedIn exports (1000+ CVs) with chunking.
    Prevents memory overflow and timeouts.

    **Parameters:**
    - `job_id`: Target job position ID
    - `zip_file`: LinkedIn export ZIP file
    - `X-API-Key`: API key for authentication
    - `chunk_size`: CVs per batch (50-500, default 200)

    **Returns:**
    - Session ID for progress tracking
    - Estimated processing time
    - Instructions for getting results

    **Notes:**
    - Processing happens in background
    - Check status with `/processing-status/{session_id}`
    - Download results when `status: 'completed'`
    """
    # Validate API key
    subscription = validate_api_key(api_key, db, lock=True)

    # Validate ZIP file
    if not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Get job details
    job = (
        db.query(RecruiterJob)
        .filter(RecruiterJob.id == job_id, RecruiterJob.organization_id == subscription.organization_id)
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    remaining = subscription.monthly_limit - subscription.monthly_usage
    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail="Monthly quota exceeded",
        )

    try:
        zip_contents = await read_upload_limited(zip_file, max_bytes=_MAX_LINKEDIN_ZIP_BYTES)
        session_id = str(uuid.uuid4())
        from utils.cv_processor import set_processing_status

        await set_processing_status(
            session_id,
            {
                "status": "queued",
                "subscription_id": subscription.id,
                "job_id": job_id,
                "processed": 0,
                "errors": 0,
            },
        )
        background_tasks.add_task(
            _process_linkedin_export_background,
            session_id=session_id,
            zip_contents=zip_contents,
            filename=zip_file.filename or "linkedin-export.zip",
            subscription_id=subscription.id,
            job_id=job_id,
            chunk_size=chunk_size,
        )
        return {
            "status": "queued",
            "session_id": session_id,
            "job_id": job_id,
            "job_title": job.title,
            "message": "Background processing started",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Large batch processing failed due to an unexpected error")


@router.get("/processing-status/{session_id}")
async def get_processing_status(
    session_id: str,
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Get status of large batch processing.

    **Returns:**
    - `status`: 'processing' | 'completed' | 'failed'
    - `progress`: Current progress info
    - `eta`: Estimated time remaining
    """
    # Validate API key
    subscription = validate_api_key(api_key, db)

    from utils.cv_processor import get_processing_status

    status = await get_processing_status(session_id)
    status_subscription_id = status.get("subscription_id")
    if status_subscription_id is not None and int(status_subscription_id) != int(subscription.id):
        raise HTTPException(status_code=404, detail="Processing session not found")

    return {
        "session_id": session_id,
        "status": status.get("status", "unknown"),
        "progress": status,
        "eta_seconds": status.get("eta", "unknown"),
    }


@router.post("/subscriptions/reset-usage")
async def reset_monthly_usage(
    request: Request,
    db: Session = Depends(get_db),
    recruiter=Depends(recruiter_required),
):
    """
    Reset monthly usage counter (admin function).
    Normally this would be automated, but manual reset for testing.
    """
    from core.http_runtime import _admin_access_error

    admin_error = _admin_access_error(request)
    if admin_error:
        return admin_error

    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization assigned")

    # Reset all subscriptions for this org
    updated = db.query(APISubscription).filter(APISubscription.organization_id == org_id).update({"monthly_usage": 0})

    db.commit()

    return {"message": f"Reset usage for {updated} subscription(s)"}
