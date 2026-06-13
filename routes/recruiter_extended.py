"""
Extended Recruiter Endpoints
Features 4-9, 12-13 implementations
"""

import asyncio
import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import verify_supabase_jwt
from database import SessionLocal, get_db
from models import Candidate, CandidateAction, Organization, User
from routes.recruiter import (
    recruiter_required,
    _rc_get_actions,
    _rc_get_tpl,
    _rc_validate_email,
    _rc_render,
    _do_send_email,
    _log_event,
    _get_limiter,
    _get_batch_task_owner,
)

logger = logging.getLogger("app.recruiter.extended")

router = APIRouter(prefix="/api/v1/recruiter")

RANKING_EXPORT_FIELDS = ["name", "email", "final_score", "ats_score", "action", "created_at"]
CANDIDATE_EXPORT_FIELDS = ["name", "email", "phone", "created_at"]


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 4: PAGINATION WITH OFFSET - Updated endpoints with pagination
# ════════════════════════════════════════════════════════════════════════════

# Note: Update existing GET /candidates, /jobs, /search endpoints to include offset
# This is documented in IMPLEMENTATION_GUIDE.md
# The key addition is the `offset` parameter and `hasMore` field


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 5: BULK EMAIL SEND
# ════════════════════════════════════════════════════════════════════════════

class BulkEmailRequest(BaseModel):
    template_id: int
    candidate_emails: list[str]  # List of email addresses
    job_id: int | None = None
    sender_email: str | None = None


class BulkEmailResult(BaseModel):
    email: str
    status: str  # "success" or "failed"
    error: str | None = None


class BulkEmailResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: list[BulkEmailResult]


@_get_limiter().limit("60/minute")
@router.post("/send-email-bulk")
def recruiter_send_email_bulk(
    body: BulkEmailRequest,
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
) -> BulkEmailResponse:
    """
    Send email to multiple candidates at once.
    
    **Parameters:**
    - `template_id`: Email template to use
    - `candidate_emails`: List of email addresses (max 100)
    - `job_id`: Optional job ID for context
    - `sender_email`: Optional sender email (defaults to recruiter email)
    
    **Returns:**
    - Summary of sent emails with success/failure details for each recipient
    
    **Raises:**
    - 400: Invalid request (too many emails, invalid template, empty list)
    - 404: Template not found
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )
    
    # Validate emails list
    if not body.candidate_emails:
        raise HTTPException(
            status_code=400,
            detail="At least one email address required"
        )
    
    if len(body.candidate_emails) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 email addresses per request"
        )
    
    # Validate template exists
    tpl = _rc_get_tpl(db, body.template_id, org_id)
    if not tpl:
        raise HTTPException(
            status_code=404,
            detail="Email template not found or you do not have permission to use it"
        )
    
    # Send to each recipient
    results = []
    successful = 0
    failed = 0
    sender = body.sender_email or recruiter.email or ""
    
    _log_event(
        "recruiter.bulk_email_start",
        org_id=org_id,
        template_id=body.template_id,
        recipient_count=len(body.candidate_emails)
    )
    
    for email in body.candidate_emails:
        try:
            # Validate email format
            err = _rc_validate_email("", email)
            if err:
                results.append(BulkEmailResult(email=email, status="failed", error=err))
                failed += 1
                logger.warning("bulk_email: invalid_email email=%s error=%s", email, err)
                continue
            
            # Render template with email variable
            try:
                rendered = _rc_render(tpl.body, tpl.subject, {"email": email})
            except Exception as e:
                results.append(BulkEmailResult(email=email, status="failed", error=f"Template error: {str(e)}"))
                failed += 1
                logger.error("bulk_email: render_failed email=%s error=%s", email, e)
                continue
            
            # Send email
            try:
                _send_ok = _do_send_email(
                    to_email=email,
                    subject=rendered["subject"],
                    body=rendered["body"],
                    recruiter_email=sender
                )
                
                if _send_ok:
                    results.append(BulkEmailResult(email=email, status="success"))
                    successful += 1
                    _log_event("recruiter.bulk_email_sent", org_id=org_id, email=email)
                    logger.info("bulk_email: sent email=%s", email)
                else:
                    results.append(BulkEmailResult(email=email, status="failed", error="Provider returned failure"))
                    failed += 1
                    logger.warning("bulk_email: provider_failed email=%s", email)
            except Exception as e:
                results.append(BulkEmailResult(email=email, status="failed", error=f"Send error: {str(e)}"))
                failed += 1
                logger.error("bulk_email: send_failed email=%s error=%s", email, e)
        
        except Exception as e:
            results.append(BulkEmailResult(email=email, status="failed", error=str(e)))
            failed += 1
            logger.error("bulk_email: unexpected_error email=%s error=%s", email, e)
    
    _log_event(
        "recruiter.bulk_email_completed",
        org_id=org_id,
        total=len(body.candidate_emails),
        successful=successful,
        failed=failed
    )
    
    logger.info(
        "bulk_email: completed total=%d successful=%d failed=%d org_id=%s",
        len(body.candidate_emails), successful, failed, org_id
    )
    
    return BulkEmailResponse(
        total=len(body.candidate_emails),
        successful=successful,
        failed=failed,
        results=results
    )


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 6: EXPORT FEATURES (CSV/JSON)
# ════════════════════════════════════════════════════════════════════════════

@_get_limiter().limit("60/minute")
@router.get("/export/rankings")
def recruiter_export_rankings(
    job_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
):
    """
    Export ranked candidates as CSV or JSON.
    
    **Parameters:**
    - `job_id`: ID of the job to export rankings for
    - `format`: Export format - "csv" or "json"
    
    **Returns:**
    - File stream (CSV or JSON format)
    
    **Raises:**
    - 404: Job not found or no candidates ranked for this job
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )
    
    # Get ranked candidates (actions) for this job
    try:
        actions = _rc_get_actions(db, job_id, org_id)
    except Exception as e:
        logger.error("export_rankings: get_actions_failed job_id=%d org_id=%s error=%s", job_id, org_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve rankings"
        )
    
    # Prepare data
    data = [
        {
            "name": a.candidate_name or "",
            "email": a.candidate_email or "",
            "final_score": a.final_score or 0,
            "ats_score": a.ats_score or 0,
            "action": a.action or "pending",
            "created_at": str(a.created_at) if a.created_at else "",
        }
        for a in actions
    ]
    
    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=RANKING_EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(data)
        
        _log_event("recruiter.export_rankings", org_id=org_id, job_id=job_id, format="csv", count=len(data))
        logger.info("export_rankings: csv exported job_id=%d count=%d", job_id, len(data))
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=rankings_job_{job_id}.csv"}
        )
    else:  # JSON
        _log_event("recruiter.export_rankings", org_id=org_id, job_id=job_id, format="json", count=len(data))
        logger.info("export_rankings: json exported job_id=%d count=%d", job_id, len(data))
        
        return StreamingResponse(
            iter([json.dumps(data, indent=2, default=str)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=rankings_job_{job_id}.json"}
        )


@_get_limiter().limit("60/minute")
@router.get("/export/candidates")
def recruiter_export_candidates(
    format: str = Query("csv", pattern="^(csv|json)$"),
    db=Depends(get_db),
    recruiter=Depends(recruiter_required),
    request: Request = None,
):
    """
    Export all candidates from recruiter's organization.
    
    **Parameters:**
    - `format`: Export format - "csv" or "json"
    
    **Returns:**
    - File stream (CSV or JSON format) with all candidates
    """
    org_id = recruiter.organization_id
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Recruiter profile is incomplete (no organization assigned)"
        )
    
    # Get all candidates for this organization
    try:
        candidates = db.query(Candidate).filter(
            Candidate.organization_id == org_id
        ).all()
    except Exception as e:
        logger.error("export_candidates: query_failed org_id=%s error=%s", org_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve candidates"
        )
    
    # Prepare data
    data = [
        {
            "name": c.name or "",
            "email": c.email or "",
            "phone": c.phone or "",
            "created_at": str(c.created_at) if c.created_at else "",
        }
        for c in candidates
    ]
    
    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CANDIDATE_EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(data)
        
        _log_event("recruiter.export_candidates", org_id=org_id, format="csv", count=len(data))
        logger.info("export_candidates: csv exported org_id=%s count=%d", org_id, len(data))
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=candidates.csv"}
        )
    else:  # JSON
        _log_event("recruiter.export_candidates", org_id=org_id, format="json", count=len(data))
        logger.info("export_candidates: json exported org_id=%s count=%d", org_id, len(data))
        
        return data


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 13: PROGRESS TRACKING - WebSocket for batch upload
# ════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/batch-upload/{task_id}")
async def websocket_batch_upload_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time batch upload progress tracking.
    
    **Usage:**
    - Connect to ws://localhost:8001/api/v1/recruiter/ws/batch-upload/{task_id}
    - Receive JSON progress updates every second
    
    **Response format:**
    ```json
    {
        "status": "PENDING|PROGRESS|SUCCESS|FAILURE",
        "processed": 5,
        "total": 10,
        "percent": 50.0,
        "current_file": "resume_1.pdf",
        "error": null
    }
    ```
    
    **Connection closes when:**
    - Task completes (SUCCESS or FAILURE)
    - Client disconnects
    - Error occurs
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        try:
            user_payload = verify_supabase_jwt(f"Bearer {token}")
        except Exception:
            await websocket.close(code=1008)
            return

        db_user = db.query(User).filter(User.supabase_id == user_payload.get("user_id")).first()
        owner = _get_batch_task_owner(task_id)
        if (
            not db_user
            or not owner
            or int(owner.get("organization_id") or 0) != int(db_user.organization_id or 0)
        ):
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    await websocket.accept()
    logger.info("websocket: batch_upload progress connected task_id=%s", task_id)
    
    try:
        # Import here to avoid circular dependencies
        from services.tasks import batch_recruiter_task
        
        max_iterations = 3600  # Max 1 hour of polling
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Get task status from Celery
                task = batch_recruiter_task.AsyncResult(task_id)
                
                progress = {
                    "status": task.state,  # PENDING, PROGRESS, SUCCESS, FAILURE
                    "processed": 0,
                    "total": 0,
                    "percent": 0.0,
                    "current_file": None,
                    "error": None
                }
                
                # Extract progress from task result
                if task.result:
                    if isinstance(task.result, dict):
                        progress["processed"] = task.result.get("processed", 0)
                        progress["total"] = task.result.get("total", 0)
                        progress["current_file"] = task.result.get("current_file")
                        
                        if progress["total"] > 0:
                            progress["percent"] = (progress["processed"] / progress["total"]) * 100
                
                # Include error if task failed
                if task.state == "FAILURE":
                    progress["error"] = str(task.info)
                    logger.warning("websocket: batch_upload failed task_id=%s error=%s", task_id, task.info)
                
                # Send progress to client
                await websocket.send_json(progress)
                logger.debug("websocket: progress sent task_id=%s status=%s progress=%d/%d", 
                           task_id, task.state, progress["processed"], progress["total"])
                
                # Stop when task completes
                if task.state in ["SUCCESS", "FAILURE"]:
                    logger.info("websocket: batch_upload completed task_id=%s status=%s", task_id, task.state)
                    break
                
                # Check every 1 second
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error("websocket: error polling task task_id=%s error=%s", task_id, e)
                await websocket.send_json({"error": f"Polling error: {str(e)}"})
                break
    
    except WebSocketDisconnect:
        logger.info("websocket: client disconnected task_id=%s", task_id)
    except Exception as e:
        logger.error("websocket: unexpected error task_id=%s error=%s", task_id, e)
        try:
            await websocket.send_json({"error": f"Unexpected error: {str(e)}"})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# ════════════════════════════════════════════════════════════════════════════
# NOTE: Features not included in this file:
# - Feature 4: Pagination - Requires updating existing endpoints
# - Feature 7: Rate Limiting - Requires @limiter decorators on existing endpoints
# - Feature 8: Audit Logging - Already integrated in main recruiter.py endpoints
# - Feature 9: Response Models - Pagination fields added to existing models
# - Feature 10: Caching - Requires Redis setup and @cache decorators
# - Feature 12: Email Retry - Requires Celery task in services/tasks.py
# ════════════════════════════════════════════════════════════════════════════
