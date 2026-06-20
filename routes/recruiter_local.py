"""
Local processing mode for recruiters - zero data retention.
CVs are processed and results returned without saving to database.
"""

import secrets
import os
import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile, Request
from sqlalchemy.orm import Session

from config.aws import MAX_UPLOAD_BYTES
from database import get_db
from models import APISubscription, Organization, RecruiterJob
from routes.recruiter import recruiter_required
from security.file_guard import read_upload_limited
from utils.cv_processor import process_cv_batch
from utils.csv_exporter import generate_csv_download
from utils.json_exporter import generate_json_download

router = APIRouter(prefix="/api/v1/recruiter", tags=["recruiter-local"])

_MAX_LOCAL_BATCH_FILES = int(os.getenv("RECRUITER_LOCAL_MAX_BATCH_FILES", "100"))


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

    import hashlib
    hashed_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    query = db.query(APISubscription)
    if lock:
        query = query.with_for_update()

    subscription = query.filter(
        (APISubscription.api_key == hashed_key) | (APISubscription.api_key == api_key),
        APISubscription.is_active == True
    ).first()

    if not subscription:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Check expiration
    if subscription.expires_at and subscription.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API key expired")

    return subscription


def check_monthly_quota(subscription: APISubscription, requested_cvs: int):
    """Check if subscription has enough monthly quota."""
    remaining = subscription.monthly_limit - subscription.monthly_usage
    if remaining < requested_cvs:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly quota exceeded. Remaining: {remaining}, Requested: {requested_cvs}"
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
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )

    # Check if organization already has an active subscription
    existing = db.query(APISubscription).filter(
        APISubscription.organization_id == org_id,
        APISubscription.is_active == True
    ).first()

    if existing:
        masked_key = "cv_***"
        if len(existing.api_key) > 8:
            masked_key = f"cv_***{existing.api_key[-6:]}"
        return {
            "api_key": masked_key,
            "monthly_limit": existing.monthly_limit,
            "monthly_usage": existing.monthly_usage,
            "expires_at": existing.expires_at.isoformat() if existing.expires_at else None,
            "message": "Existing active subscription found. API key is hidden for security."
        }

    # Create new subscription
    raw_key = generate_api_key()
    import hashlib
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    subscription = APISubscription(
        organization_id=org_id,
        api_key=hashed_key,
        monthly_limit=1000,  # Default 1000 CVs/month
        expires_at=datetime.utcnow() + timedelta(days=365),  # 1 year
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "api_key": raw_key,  # Returned only once
        "monthly_limit": subscription.monthly_limit,
        "monthly_usage": subscription.monthly_usage,
        "expires_at": subscription.expires_at.isoformat(),
        "message": "New API key generated successfully. Please copy it now as it won't be shown again."
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
        APISubscription.organization_id == org_id,
        APISubscription.is_active == True
    ).update({"is_active": False})

    # Generate new key
    raw_key = generate_api_key()
    import hashlib
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    subscription = APISubscription(
        organization_id=org_id,
        api_key=hashed_key,
        monthly_limit=1000,
        expires_at=datetime.utcnow() + timedelta(days=365),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "api_key": raw_key,  # Returned only once
        "monthly_limit": subscription.monthly_limit,
        "monthly_usage": subscription.monthly_usage,
        "expires_at": subscription.expires_at.isoformat(),
        "message": "New API key generated and old keys deactivated. Please copy it now as it won't be shown again."
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

    updated = db.query(APISubscription).filter(
        APISubscription.organization_id == org_id,
        APISubscription.is_active == True
    ).update({"is_active": False})

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
        "is_active": subscription.is_active
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
    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == job_id,
        RecruiterJob.organization_id == subscription.organization_id
    ).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or you do not have permission to access it"
        )

    # Validate files
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if len(files) > _MAX_LOCAL_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_LOCAL_BATCH_FILES} files per request (you provided {len(files)})"
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
            cv_files.append({
                'filename': file.filename,
                'content': content,
                'size': len(content)
            })

        results = await process_cv_batch_ultra_fast(
            files=cv_files,
            job_description=job.description,
            job_id=job_id,
            use_cache=True,
            workers=None  # Auto-detect CPU cores
        )
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Large batch processing failed due to an unexpected error"
        )

    # Update usage
    subscription.monthly_usage += len(files)
    subscription.last_used_at = datetime.utcnow()
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
            "processed_at": datetime.utcnow().isoformat()
        },
        "downloads": {
            "json": json_url,
            "csv": csv_url
        },
        "usage": {
            "monthly_limit": subscription.monthly_limit,
            "monthly_usage": subscription.monthly_usage,
            "remaining": subscription.monthly_limit - subscription.monthly_usage
        }
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
    if not zip_file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Get job details
    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == job_id,
        RecruiterJob.organization_id == subscription.organization_id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check quota (we'll estimate based on typical LinkedIn exports)
    # LinkedIn exports usually contain 50-500 CVs
    estimated_cvs = 250  # Conservative estimate
    check_monthly_quota(subscription, estimated_cvs)

    # Process LinkedIn export
    try:
        from utils.cv_processor import process_cv_batch_chunked
        results, summary = await process_cv_batch_chunked(
            zip_file=zip_file,
            job_description=job.description,
            job_id=job_id,
            chunk_size=chunk_size,
            progress_callback=None  # Could integrate with WebSocket
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Large batch processing failed due to an unexpected error"
        )

    # Update usage with actual count
    actual_cvs = len(results)
    check_monthly_quota(subscription, actual_cvs)  # Final check

    subscription.monthly_usage += actual_cvs
    subscription.last_used_at = datetime.utcnow()
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
            "processed_at": datetime.utcnow().isoformat()
        },
        "downloads": {
            "json": json_url,
            "csv": csv_url
        },
        "usage": {
            "monthly_limit": subscription.monthly_limit,
            "monthly_usage": subscription.monthly_usage,
            "remaining": subscription.monthly_limit - subscription.monthly_usage
        }
    }


@router.post("/process-linkedin-export-large")
async def process_linkedin_export_large(
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
    if not zip_file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Get job details
    job = db.query(RecruiterJob).filter(
        RecruiterJob.id == job_id,
        RecruiterJob.organization_id == subscription.organization_id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # For large batches, check quota more generously
    max_csv_estimate = 2000  # Conservative estimate for 1000-5000 CVs
    if subscription.monthly_limit - subscription.monthly_usage < max_csv_estimate:
        raise HTTPException(
            status_code=429,
            detail=f"Insufficient quota for large batch processing. Remaining: {subscription.monthly_limit - subscription.monthly_usage}"
        )

    # Process in chunks
    from utils.cv_processor import process_cv_batch_chunked
    
    session_id = str(datetime.utcnow().timestamp())

    try:
        results, summary = await process_cv_batch_chunked(
            zip_file=zip_file,
            job_description=job.description,
            job_id=job_id,
            chunk_size=chunk_size,
            progress_callback=None  # Could integrate with WebSocket
        )

        # Update usage with actual count
        actual_cvs = len(results)
        check_monthly_quota(subscription, actual_cvs)

        subscription.monthly_usage += actual_cvs
        subscription.last_used_at = datetime.utcnow()
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
            "status": "success",
            "session_id": session_id,
            "summary": {
                **summary,
                "job_id": job_id,
                "job_title": job.title,
                "processed_at": datetime.utcnow().isoformat()
            },
            "results": results[:100],  # Return top 100 for preview
            "total_results": len(results),
            "downloads": {
                "json": json_url,
                "csv": csv_url,
                "note": "Full results available in JSON/CSV downloads"
            },
            "usage": {
                "monthly_limit": subscription.monthly_limit,
                "monthly_usage": subscription.monthly_usage,
                "remaining": subscription.monthly_limit - subscription.monthly_usage
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Large batch processing failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Large batch processing failed due to an unexpected error"
        )


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
    validate_api_key(api_key, db)

    from utils.cv_processor import get_processing_status
    
    status = await get_processing_status(session_id)

    return {
        "session_id": session_id,
        "status": status.get('status', 'unknown'),
        "progress": status,
        "eta_seconds": status.get('eta', 'unknown')
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
    updated = db.query(APISubscription).filter(
        APISubscription.organization_id == org_id
    ).update({"monthly_usage": 0})

    db.commit()

    return {"message": f"Reset usage for {updated} subscription(s)"}
