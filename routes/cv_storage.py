"""Score breakdown and CV storage endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from auth import verify_supabase_jwt
from core.request_utils import _read_upload_or_400
from core.http_runtime import (
    RATE_LIMIT_IP_ANALYZE_PER_MIN,
    RATE_LIMIT_IP_UPLOAD_PER_MIN,
    audit_log,
    rate_limit,
    require_abuse_check,
)
from core.metrics import DOWNLOADS_TOTAL
from core.quota import _consume_billable_usage
from database import get_db
from services.pdf_runtime import _scan_upload_for_viruses
from services.user_service import _ensure_not_expired, get_or_create_user


logger = logging.getLogger("app.cv_storage")


router = APIRouter(tags=["cv-storage"])

from routes.user_data import _storage_key_fingerprint  # noqa: E402
from routes.ai_tools import JobMatchScoreRequest  # noqa: E402


def _text_to_cvmodel(cv_text: str, lang: str = "en"):
    """Parse raw CV text into a CVModel via the autofix pipeline."""
    from schemas.cv_model import CVModel
    from services.cv_autofix_service import structured_text_to_builder_payload

    payload = structured_text_to_builder_payload(cv_text, job_description="", lang=lang)
    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    elif isinstance(payload, dict):
        data = payload
    else:
        data = dict(payload or {})
    data.setdefault("language", lang)
    return CVModel.from_mapping(data)


@router.post("/api/v1/score/breakdown")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PER_MIN}/minute")
def score_breakdown_endpoint(
    request: Request,
    response: Response,
    body: JobMatchScoreRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Full score breakdown: ATS scores + job match + recruiter score + feedback."""
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _consume_billable_usage(db, db_user, "score-breakdown", response=response)

    from services.ats_scoring import score_cv
    from services.job_match_service import match_cv_to_job, generate_feedback, recruiter_score

    try:
        model = _text_to_cvmodel(body.cv_text, body.lang)

        ats = score_cv(model)
        match = match_cv_to_job(model, body.job_description)
        feedback = generate_feedback(model, body.job_description, match)
        rec = recruiter_score(model, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Score breakdown failed: {e}")

    return {
        "ats_scores": {
            "overall": ats.overall,
            "structure": ats.structure,
            "keywords": ats.keywords,
            "experience": ats.experience,
            "education": ats.education,
            "languages": ats.languages,
            "ats": ats.ats,
            "length": ats.length,
        },
        "job_match": {
            "match_score": match.match_score,
            "keyword_score": match.keyword_score,
            "semantic_score": match.semantic_score,
            "keyword_coverage_pct": match.keyword_coverage_pct,
            "missing_keywords": match.missing_keywords[:15],
            "weak_keywords": match.weak_keywords[:10],
            "strong_keywords": match.strong_keywords[:10],
            "suggested_keywords": match.suggested_keywords[:15],
        },
        "recruiter": {
            "interest": rec.recruiter_interest,
            "hireability": rec.hireability,
            "shortlist_probability": rec.shortlist_probability,
            "strengths": rec.strengths,
            "concerns": rec.concerns,
        },
        "feedback": {
            "score_before": feedback.score_before,
            "potential_score": feedback.potential_score,
            "items": [{"category": f.category, "priority": f.priority, "message": f.message} for f in feedback.items],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# S3 STORAGE — Upload / Download / Delete CVs
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/api/v1/cv/upload")
@rate_limit(f"{RATE_LIMIT_IP_UPLOAD_PER_MIN}/minute")
async def upload_cv(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    _: None = Depends(require_abuse_check),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Upload original CV (PDF/DOCX) to S3.  Returns the S3 key only."""
    from services.storage_service import upload_original_cv
    from security.file_guard import validate_file_upload
    from security.s3_guard import enforce_user_cv_limit
    from security.rate_limit import check_upload_rate

    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    # Per-user upload rate guard
    try:
        check_upload_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    # Per-user CV count limit
    try:
        enforce_user_cv_limit(db, db_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    content_type = file.content_type or "application/pdf"
    contents = await _read_upload_or_400(file)

    # Full file validation (size, extension, mime, magic bytes, PDF complexity)
    try:
        validate_file_upload(contents, file.filename, content_type)
        _scan_upload_for_viruses(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise

    # ── Duplicate prevention: compute normalized-text fingerprint and check user's existing CVs
    try:
        try:
            from services.pdf_text_extractor import extract_pdf_text
            import hashlib
            from models import CVVersion

            raw_text, _ = extract_pdf_text(contents, max_pages=20, max_chars=300000, ocr_extract_text=None)
            fp = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

            existing = db.query(CVVersion).filter(CVVersion.user_id == db_user.id).all()
            for row in existing:
                txt = row.cv_text or row.optimized_cv_text or ""
                if not txt:
                    continue
                existing_fp = hashlib.sha256(txt.encode("utf-8")).hexdigest()
                if existing_fp == fp:
                    raise HTTPException(status_code=409, detail=f"duplicate_cv: existing_cv_version_id={row.id}")
        except HTTPException:
            raise
        except Exception:
            logger.exception("duplicate_check_failed user=%s", supabase_id)
            # fall back to upload if duplicate check fails unexpectedly

        key = upload_original_cv(contents, supabase_id, content_type, file.filename)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    except Exception:
        logger.exception("s3:upload_route_error user=%s", supabase_id)
        raise HTTPException(status_code=500, detail="Upload failed")

    return {"key": key, "filename": file.filename, "size": len(contents)}


@router.post("/api/v1/cv/upload-optimized")
@rate_limit(f"{RATE_LIMIT_IP_UPLOAD_PER_MIN}/minute")
async def upload_optimized_cv_route(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    _: None = Depends(require_abuse_check),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Upload an optimized/generated CV to S3."""
    from services.storage_service import upload_optimized_cv
    from security.file_guard import validate_file_upload
    from security.s3_guard import enforce_user_cv_limit
    from security.rate_limit import check_upload_rate

    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        check_upload_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        enforce_user_cv_limit(db, db_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    content_type = file.content_type or "application/pdf"
    contents = await _read_upload_or_400(file)

    try:
        validate_file_upload(contents, file.filename, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise

    try:
        key = upload_optimized_cv(contents, supabase_id, content_type, file.filename)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    except Exception:
        logger.exception("s3:upload_optimized_error user=%s", supabase_id)
        raise HTTPException(status_code=500, detail="Upload failed")

    return {"key": key, "filename": file.filename, "size": len(contents)}


@router.get("/api/v1/cv/download")
def download_cv(
    request: Request,
    key: str = Query(..., min_length=10, max_length=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Get a presigned download URL for a stored CV.

    Only allows downloading files that belong to the requesting user.
    Presigned URLs expire in 60 seconds.
    """
    from services.storage_service import get_download_url, exists
    from security.s3_guard import validate_s3_key, enforce_ownership
    from security.runtime_guard import check_download_rate, check_signed_url_rate

    _ensure_not_expired(user)
    supabase_id = user.get("user_id")
    try:
        DOWNLOADS_TOTAL.inc()
    except Exception:
        pass

    # Per-user download + signed URL rate guards
    try:
        check_download_rate(supabase_id)
        check_signed_url_rate(supabase_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        validate_s3_key(key)
        enforce_ownership(key, supabase_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if not exists(key):
            raise HTTPException(status_code=404, detail="File not found")
        url_or_path = get_download_url(key, supabase_id)

        from services.storage_service import STORAGE_BACKEND

        if STORAGE_BACKEND == "local":
            return FileResponse(url_or_path, filename=os.path.basename(key))

        audit_log("cv_download", user_id=supabase_id, key_hash=_storage_key_fingerprint(key))
        return {"url": url_or_path}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key format")
    except HTTPException:
        raise
    except Exception:
        logger.exception("s3:download_error user=%s key_hash=%s", supabase_id, _storage_key_fingerprint(key))
        raise HTTPException(status_code=500, detail="Download failed")


@router.delete("/api/v1/cv/file")
def delete_cv_file(
    request: Request,
    key: str = Query(..., min_length=10, max_length=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Delete a CV file from S3.  Only the owner can delete."""
    from services.storage_service import delete_cv
    from security.s3_guard import validate_s3_key, enforce_ownership

    _ensure_not_expired(user)
    supabase_id = user.get("user_id")

    try:
        validate_s3_key(key)
        enforce_ownership(key, supabase_id)
    except (ValueError, PermissionError):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        delete_cv(key, supabase_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key format")
    except Exception:
        logger.exception("s3:delete_error user=%s key_hash=%s", supabase_id, _storage_key_fingerprint(key))
        raise HTTPException(status_code=500, detail="Delete failed")

    return {"deleted": key}
