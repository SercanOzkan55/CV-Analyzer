"""AI tooling, rewrite, interview, keyword, and CV version endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

from core.timeutils import utcnow
from fastapi import APIRouter
from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403
from services.ai_feature_service import ensure_ai_rewrite_allowed
from services.owner_workflow_service import create_owner_notification
from typing import List, Optional


router = APIRouter(tags=["ai-tools"])


class SemanticSearchRequest(BaseModel):
    job_text: str | None = None
    job_id: int | None = None
    k: int = 10
    persist_job: bool = False


class IndexCVEmbeddingRequest(BaseModel):
    cv_text: str
    name: str | None = None
    email: str | None = None


class FindCandidatesEmbeddingRequest(BaseModel):
    job_text: str
    top_k: int = 10


@router.post("/api/v1/embeddings/index-cv")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PER_MIN}/minute")
def index_cv_embedding(
    body: IndexCVEmbeddingRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Index a CV embedding for later semantic candidate search."""
    _ensure_not_expired(user)
    text_value = (body.cv_text or "").strip()
    if not text_value:
        raise HTTPException(status_code=400, detail="cv_text is required")

    embedding = _main_module().get_embedding(text_value)
    if not embedding:
        raise HTTPException(status_code=500, detail="Failed to compute CV embedding")

    db_user = get_or_create_user(db, user.get("user_id"), user.get("email"))
    organization_id = getattr(db_user, "organization_id", None)
    if organization_id is None:
        # Candidate search is org-scoped; an org-less row can never be
        # retrieved and would retain raw CV text past account deletion.
        raise HTTPException(status_code=400, detail="Candidate indexing requires an organization account")
    candidate = Candidate(
        name=body.name,
        email=body.email,
        cv_text=text_value,
        organization_id=organization_id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    try:
        _main_module().save_candidate_embedding(db, candidate.id, embedding)
    except Exception:
        # Keep the candidate row even if the vector backend is unavailable locally.
        pass

    return {"candidate_id": candidate.id, "indexed": True}


@router.post("/api/v1/embeddings/find-candidates")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def find_candidate_embeddings(
    body: FindCandidatesEmbeddingRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Find candidates semantically similar to a job text."""
    _ensure_not_expired(user)
    job_text = (body.job_text or "").strip()
    if not job_text:
        raise HTTPException(status_code=400, detail="job_text is required")

    db_user = get_or_create_user(db, user.get("user_id"), user.get("email"))
    organization_id = getattr(db_user, "organization_id", None)
    if organization_id is None:
        return {"matches": []}

    job_vec = _main_module().get_embedding(job_text)
    if not job_vec:
        raise HTTPException(status_code=500, detail="Failed to compute job embedding")

    matches = _main_module().find_similar_candidates(
        db,
        job_vec,
        k=max(1, min(body.top_k or 10, 50)),
        organization_id=organization_id,
    )
    candidate_ids = [cid for cid, _score in matches]
    rows_map = {}
    if candidate_ids:
        rows = (
            db.query(Candidate)
            .filter(
                Candidate.id.in_(candidate_ids),
                Candidate.organization_id == organization_id,
            )
            .all()
        )
        rows_map = {row.id: row for row in rows}

    return {
        "matches": [
            {
                "id": cid,
                "score": float(score),
                "name": getattr(rows_map.get(cid), "name", None),
                "email": getattr(rows_map.get(cid), "email", None),
                "cv_text": (
                    (rows_map[cid].cv_text[:200] + "...")
                    if rows_map.get(cid) is not None and rows_map[cid].cv_text and len(rows_map[cid].cv_text) > 200
                    else (rows_map[cid].cv_text if rows_map.get(cid) is not None else None)
                ),
            }
            for cid, score in matches
        ]
    }


@router.post("/api/v1/semantic-search")
@rate_limit("20/minute")
def semantic_search(body: SemanticSearchRequest, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    _ensure_not_expired(user)
    db_user = get_or_create_user(db, user.get("user_id"), user.get("email"))
    organization_id = getattr(db_user, "organization_id", None)
    if organization_id is None:
        return {"matches": []}

    # Require either job_text or job_id
    if not body.job_text and not body.job_id:
        raise HTTPException(status_code=400, detail="Provide job_text or job_id")

    # Resolve job embedding
    job_vec = None
    if body.job_id:
        job = (
            db.query(Job)
            .filter(
                Job.id == body.job_id,
                Job.organization_id == organization_id,
            )
            .one_or_none()
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_vec = job.job_embedding
        if not job_vec:
            job_vec = get_embedding(job.raw_text or "")
            if job_vec:
                try:
                    save_job_embedding(db, job.id, job_vec)
                except Exception:
                    pass
    else:
        # job_text provided
        job_vec = get_embedding(body.job_text or "")
        if body.persist_job and job_vec:
            try:
                new_job = Job(
                    raw_text=body.job_text,
                    job_embedding=job_vec,
                    organization_id=organization_id,
                )
                db.add(new_job)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

    if not job_vec:
        raise HTTPException(status_code=500, detail="Failed to compute job embedding")

    # Find top-k similar candidates (returns list of (id, score))
    matches = find_similar_candidates(
        db,
        job_vec,
        k=body.k,
        organization_id=organization_id,
    )
    candidate_ids = [m[0] for m in matches]

    # Fetch candidate rows preserving order
    candidates = []
    if candidate_ids:
        rows = (
            db.query(Candidate)
            .filter(
                Candidate.id.in_(candidate_ids),
                Candidate.organization_id == organization_id,
            )
            .all()
        )
        rows_map = {r.id: r for r in rows}
        for cid, score in matches:
            r = rows_map.get(cid)
            if r:
                candidates.append(
                    {
                        "id": r.id,
                        "cv_text": ((r.cv_text[:200] + "...") if r.cv_text and len(r.cv_text) > 200 else r.cv_text),
                        "organization_id": r.organization_id,
                        "score": float(score),
                    }
                )

    return {"matches": candidates}


# =====================================================
# AI REWRITE ENDPOINTS
# =====================================================


def _detect_cv_sections_from_text(text: str) -> list[str]:
    section_map = {
        "summary": ("summary", "profile", "objective", "ozet", "profil"),
        "experience": ("experience", "deneyim", "work history", "employment"),
        "education": ("education", "egitim", "eğitim", "academic"),
        "skills": ("skills", "yetenek", "technical skills", "competencies"),
        "projects": ("projects", "projeler", "project"),
        "languages": ("languages", "diller", "language"),
        "certifications": ("certifications", "certificates", "sertifika"),
    }
    lower = str(text or "").lower()
    detected = []
    for key, aliases in section_map.items():
        if any(alias in lower for alias in aliases):
            detected.append(key)
    return detected


def _describe_cv_change_summary(added_count: int, removed_count: int, added_sections: list[str]) -> list[str]:
    notes = []
    if added_count:
        notes.append(f"{added_count} clearer or newly structured line added")
    if removed_count:
        notes.append(f"{removed_count} noisy/repeated line removed")
    if added_sections:
        notes.append("Newly detected sections: " + ", ".join(added_sections[:5]))
    if not notes:
        notes.append("Structure preserved with minimal wording changes")
    return notes


def _build_cv_change_summary(original_text: str, optimized_text: str, max_items: int = 8) -> dict:
    """Return a compact before/after CV text summary for the UI."""
    original_lines = [
        re.sub(r"\s+", " ", line.strip()) for line in str(original_text or "").splitlines() if line and line.strip()
    ]
    optimized_lines = [
        re.sub(r"\s+", " ", line.strip()) for line in str(optimized_text or "").splitlines() if line and line.strip()
    ]

    before_set = set(original_lines)
    after_set = set(optimized_lines)
    added = [line for line in optimized_lines if line not in before_set]
    removed = [line for line in original_lines if line not in after_set]
    added_sections = sorted(
        set(_detect_cv_sections_from_text(optimized_text)) - set(_detect_cv_sections_from_text(original_text))
    )

    return {
        "original_lines": len(original_lines),
        "optimized_lines": len(optimized_lines),
        "added_line_count": len(added),
        "removed_line_count": len(removed),
        "added_sections": added_sections,
        "added_examples": added[:max_items],
        "removed_examples": removed[:max_items],
        "summary": _describe_cv_change_summary(len(added), len(removed), added_sections),
    }


@router.post("/api/v1/cv/auto-fix")
@rate_limit(f"{RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN}/minute")
async def auto_fix_cv_pdf(
    file: UploadFile = File(...),
    job_description: str = Form(""),
    lang: str = Form("en"),
    use_ai: bool = Form(True),
    mode: str = Form("safe"),
    response: Response = None,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Extract a CV from PDF and rewrite it into a cleaner ATS-friendly format."""
    if not _get_flag("auto_fix"):
        raise HTTPException(status_code=503, detail="auto-fix feature is disabled")
    if _cb_is_open("s3"):
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    _ensure_not_expired(user)
    _metric_request("cv-auto-fix")
    try:
        OPTIMIZES_TOTAL.inc()
    except Exception:
        pass
    _check_cost_guard("optimize", COST_OPTIMIZE_PER_DAY)

    supabase_id = (user or {}).get("user_id", "mock-user") if _main_module().MOCK_SERVICES_ON else user.get("user_id")
    email = (user or {}).get("email", "dev@example.com") if _main_module().MOCK_SERVICES_ON else user.get("email")
    db_user = get_or_create_user(db, str(supabase_id or "mock-user"), email)
    _consume_billable_usage(db, db_user, "cv-auto-fix", response=response)

    # Per-user + global optimize concurrency guard
    from security.runtime_guard import OptimizeConcurrencyGuard

    try:
        guard = OptimizeConcurrencyGuard(supabase_id or "anon")
        guard.__enter__()
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        contents = await _read_upload_or_400(file)
        _validate_pdf_upload(contents, file.content_type)
        cv_text, _cv_truncated = _main_module()._extract_pdf_text(contents)

        try:
            result = await run_in_threadpool(
                auto_fix_cv_text,
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
                use_ai=use_ai,
                mode=mode,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.exception("auto_fix_cv_text unexpected error")
            raise HTTPException(status_code=500, detail=f"Auto-fix error: {e}")
    finally:
        guard.__exit__(None, None, None)

    try:
        audit_payload = {
            "source": "pdf",
            "used_ai": bool(result.get("used_ai")),
            "score_delta": float(result.get("score_delta", 0.0)),
        }
        if db_user is not None:
            audit_payload["user_id"] = db_user.id
            audit_payload["organization_id"] = db_user.organization_id
        audit_log("cv_auto_fix", **audit_payload)
    except Exception:
        pass

    if _cv_truncated:
        result["truncated"] = True
        result["truncation_warning"] = (
            f"CV content exceeded {_MAX_PDF_EXTRACTED_CHARS:,} characters and was truncated. "
            "Analysis may be incomplete for very long documents."
        )

    optimized_text = str(result.get("optimized_cv_text") or result.get("optimized_text") or "")
    result["change_summary"] = _build_cv_change_summary(cv_text, optimized_text)
    _record_ai_usage(
        endpoint="cv-auto-fix",
        user_id=getattr(db_user, "id", None),
        input_chars=len(cv_text or "") + len(job_description or ""),
        output_chars=len(optimized_text or ""),
        used_ai=bool(result.get("used_ai")),
    )

    return result


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = "en"
    tone: str = "professional"
    mode: str = "senior"


class CVAutoFixExportRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = "en"
    font_family: str = ""


class CVAutoFixParseRequest(BaseModel):
    optimized_cv_text: str
    job_description: str | None = ""
    lang: str = "en"


class BulletRewriteRequest(BaseModel):
    bullets: list[str]
    job_description: str | None = ""
    lang: str = "en"
    tone: str = "professional"


class CoverLetterRewriteRequest(BaseModel):
    cv_text: str
    job_description: str
    company_name: str | None = ""
    lang: str = "en"
    tone: str = "professional"
    mode: str = "senior"
    low_token: bool = True


class LinkedInOptimizeRequest(BaseModel):
    cv_text: str
    target_role: str | None = ""
    lang: str = "en"
    mode: str = "senior"
    headline: str | None = ""


class JobMatchScoreRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = "en"
    mode: str = "senior"  # junior | senior | manager | tech | academic


class JobDescriptionQualityRequest(BaseModel):
    job_description: str
    jd_skills: list[str] | None = None


class CVDiffRequest(BaseModel):
    original_text: str
    optimized_text: str


class SaveCVVersionRequest(BaseModel):
    cv_text: str
    optimized_cv_text: str | None = ""
    job_description: str | None = ""
    version_label: str | None = ""
    source: str = "manual"
    lang: str = "en"
    notes: str | None = ""


def _stored_text_value(value: str | None, field_name: str) -> str | None:
    """Optionally store only metadata for privacy-sensitive CV text fields."""
    text_value = str(value or "")
    mode = os.getenv("CV_VERSION_TEXT_STORAGE_MODE", "full").strip().lower()
    if mode not in ("metadata_only", "hash_only"):
        return text_value or None
    if not text_value:
        return None
    return json.dumps(
        {
            "storage": "metadata_only",
            "field": field_name,
            "sha256": hashlib.sha256(text_value.encode("utf-8")).hexdigest(),
            "chars": len(text_value),
        },
        ensure_ascii=True,
    )


class KeywordGapRequest(BaseModel):
    cv_text: str
    job_description: str


class SkillRoadmapRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = "en"


class CVRewriteRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    lang: str = "en"


class KeywordOptimizeRequest(BaseModel):
    cv_text: str
    job_description: str
    lang: str = "en"


class RecruiterAdvancedSearchRequest(BaseModel):
    skills: list[str] = []
    min_score: float = 0.0
    min_experience: int = 0
    limit: int = 20
    use_semantic: bool = False
    job_text: str = ""


class FeedbackRequest(BaseModel):
    category: str = "bug"
    message: str
    page: str | None = ""
    lang: str | None = ""
    score: int | None = None
    context: dict | None = None


_ensure_ai_rewrite_allowed = ensure_ai_rewrite_allowed


def _next_cv_version_label(db, user_id: int) -> str:
    try:
        total = db.query(CVVersion).filter(CVVersion.user_id == user_id).count()
        return f"v{total + 1}"
    except Exception:
        return "v1"


@router.post("/api/v1/rewrite/cv")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_cv_endpoint(
    body: CVRewriteRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "rewrite-cv", response=response)

    from security.runtime_guard import OptimizeConcurrencyGuard

    try:
        with OptimizeConcurrencyGuard(supabase_id):
            try:
                text = rewrite_service.ai_rewrite_cv(
                    cv_text=body.cv_text,
                    job_description=body.job_description or "",
                    lang=body.lang,
                    tone=body.tone,
                    mode=body.mode,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except RuntimeError as e:
                raise HTTPException(status_code=503, detail=str(e))
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        audit_log(
            "ai_rewrite_cv",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"result": text, "plan": plan}


@router.post("/api/v1/cv/auto-fix/export")
@rate_limit(f"{RATE_LIMIT_IP_RENDER_PER_MIN}/minute")
def export_auto_fixed_cv(
    body: CVAutoFixExportRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from fastapi.responses import StreamingResponse

    _ensure_not_expired(user)

    if body.output_format not in ("docx", "pdf", "html"):
        raise HTTPException(status_code=400, detail="output_format must be 'docx', 'pdf' or 'html'")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    effective_plan = _resolve_effective_plan(db, db_user)

    cv_model = structured_text_to_builder_payload(
        body.optimized_cv_text,
        job_description=body.job_description or "",
        lang=body.lang,
    )
    cv_data = cv_model.model_dump()
    cv_data["template"] = body.template
    cv_data["output_format"] = body.output_format

    try:
        _t0 = time.time()
        # Font selection: only premium plans can override font
        _font = body.font_family if _is_premium_plan(effective_plan) else ""
        result = build_cv(
            cv_data=cv_data,
            job_description=body.job_description or "",
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=effective_plan,
            font_family=_font,
        )
        _metric_parse_latency("build_cv", time.time() - _t0)
    except Exception as exc:
        if "overloaded" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc))
        logger.exception("build_cv failed in auto-fix export")
        raise HTTPException(status_code=500, detail="CV generation failed")

    try:
        audit_log(
            "cv_auto_fix_export",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            output_format=body.output_format,
            template=body.template,
        )
    except Exception:
        pass

    buf = result["buffer"]
    if hasattr(buf, "getbuffer") and buf.getbuffer().nbytes > _MAX_RESPONSE_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Generated file too large")

    return StreamingResponse(
        buf,
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.post("/api/v1/cv/auto-fix/parse")
def parse_auto_fixed_cv(
    body: CVAutoFixParseRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    try:
        builder_payload = structured_text_to_builder_payload(
            body.optimized_cv_text,
            job_description=body.job_description or "",
            lang=body.lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        audit_log(
            "cv_auto_fix_parse",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            lang=body.lang,
        )
    except Exception:
        pass

    return {"builder_payload": builder_payload.model_dump()}


@router.post("/api/v1/feedback")
def submit_feedback(
    body: FeedbackRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    message = str(body.message or "").strip()
    if len(message) < 5:
        raise HTTPException(status_code=400, detail="Feedback message is too short")
    if len(message) > 3000:
        raise HTTPException(status_code=400, detail="Feedback message is too long")

    category = str(body.category or "bug").strip().lower()
    allowed_categories = {"bug", "feature", "ux", "other"}
    if category not in allowed_categories:
        category = "other"

    score = body.score
    if score is not None and (score < 1 or score > 5):
        raise HTTPException(status_code=400, detail="score must be between 1 and 5")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    payload = {
        "timestamp": utcnow().isoformat() + "Z",
        "user_id": str(db_user.id) if getattr(db_user, "id", None) is not None else None,
        "supabase_id": supabase_id,
        "email": email,
        "category": category,
        "page": str(body.page or "").strip()[:120],
        "lang": str(body.lang or "").strip()[:12],
        "score": score,
        "message": message,
        "context": body.context if isinstance(body.context, dict) else {},
    }

    _append_feedback_record(payload)
    emailed = _send_feedback_email(payload)

    try:
        organization_id = getattr(db_user, "organization_id", None)
        if organization_id:
            submitter = email or "Unknown user"
            preview = message.replace("\n", " ").strip()
            if len(preview) > 160:
                preview = preview[:157].rstrip() + "..."
            create_owner_notification(
                db,
                organization_id=organization_id,
                event_type="feedback_submitted",
                title="New complaint submitted",
                message=f"{category.title()} complaint from {submitter}: {preview}",
                actor_user_id=getattr(db_user, "id", None),
                metadata={
                    "category": category,
                    "page": payload.get("page"),
                    "lang": payload.get("lang"),
                    "score": score,
                    "email": email,
                    "feedback_timestamp": payload.get("timestamp"),
                },
            )
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("feedback owner notification failed")

    try:
        audit_log(
            "user_feedback",
            user_id=payload.get("user_id"),
            organization_id=getattr(db_user, "organization_id", None),
            category=category,
            page=payload.get("page"),
            score=score,
        )
    except Exception:
        pass

    return {"ok": True, "message": "Feedback received", "emailed": emailed}


@router.get("/api/v1/feedback")
def list_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    role = (getattr(db_user, "role", "individual") or "individual").lower()

    include_all = role in {"admin", "owner", "recruiter"}
    items = _read_feedback_records(
        limit=limit,
        supabase_id=str(supabase_id) if supabase_id else None,
        include_all=include_all,
    )

    # Hide sensitive fields from API consumers.
    cleaned = []
    for row in items:
        cleaned.append(
            {
                "timestamp": row.get("timestamp"),
                "category": row.get("category"),
                "page": row.get("page"),
                "lang": row.get("lang"),
                "score": row.get("score"),
                "message": row.get("message"),
                "context": row.get("context") or {},
                "submitter": row.get("email") if include_all else None,
            }
        )

    return {"items": cleaned, "count": len(cleaned), "scope": "all" if include_all else "self"}


@router.post("/api/v1/rewrite/bullets")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_bullets_endpoint(
    body: BulletRewriteRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "rewrite-bullets", response=response)

    try:
        bullets = rewrite_service.rewrite_bullets(
            bullets=body.bullets,
            job_description=body.job_description or "",
            lang=body.lang,
            tone=body.tone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_rewrite_bullets",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            bullet_count=len(body.bullets or []),
        )
    except Exception:
        pass

    return {"results": bullets, "plan": plan}


@router.post("/api/v1/rewrite/cover-letter")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def rewrite_cover_letter_endpoint(
    body: CoverLetterRewriteRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "rewrite-cover-letter", response=response)

    try:
        detected_lang = detect_language(body.cv_text)
        output_lang = detected_lang or body.lang or "en"
        builder_payload = structured_text_to_builder_payload(
            body.cv_text,
            job_description=body.job_description,
            lang=output_lang,
        )
        letter = rewrite_service.rewrite_cover_letter_from_builder_payload(
            builder_payload=builder_payload.model_dump(),
            job_description=body.job_description,
            company_name=body.company_name or "",
            lang=output_lang,
            tone=body.tone,
            mode=body.mode,
            low_token=body.low_token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_rewrite_cover_letter",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {
        "result": letter,
        "plan": plan,
        "builder_payload": builder_payload.model_dump(),
        "language": output_lang,
        "low_token": body.low_token,
    }


class InterviewQuestionsRequest(BaseModel):
    cv_text: str
    job_description: str | None = ""
    lang: str = "en"
    mode: str = "senior"
    count: int = 5


class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str
    cv_text: str | None = ""
    job_description: str | None = ""
    lang: str = "en"


@router.post("/api/v1/interview/questions")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def interview_questions_endpoint(
    body: InterviewQuestionsRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "interview-questions", response=response)

    try:
        questions = rewrite_service.generate_interview_questions(
            cv_text=body.cv_text,
            job_description=body.job_description or "",
            lang=body.lang,
            mode=body.mode,
            count=body.count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "interview_questions_generated",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            count=len(questions),
        )
    except Exception:
        pass

    return {"questions": questions, "plan": plan}


@router.post("/api/v1/interview/evaluate")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def interview_evaluate_endpoint(
    body: InterviewEvaluateRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "interview-evaluate", response=response)

    try:
        evaluation = rewrite_service.evaluate_interview_answer(
            question=body.question,
            answer=body.answer,
            cv_text=body.cv_text or "",
            job_description=body.job_description or "",
            lang=body.lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "interview_answer_evaluated",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
        )
    except Exception:
        pass

    return {"evaluation": evaluation, "plan": plan}


@router.post("/api/v1/linkedin/optimize")
@rate_limit(f"{RATE_LIMIT_IP_REWRITE_PER_MIN}/minute")
def optimize_linkedin_endpoint(
    body: LinkedInOptimizeRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    plan = ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "linkedin-optimize", response=response)

    try:
        result = rewrite_service.optimize_linkedin_profile(
            cv_text=body.cv_text,
            target_role=body.target_role or "",
            lang=body.lang,
            mode=body.mode,
            current_headline=body.headline or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        audit_log(
            "ai_optimize_linkedin",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            plan=plan,
            mode=result.get("mode"),
        )
    except Exception:
        pass

    return {"result": result, "plan": plan}


@router.post("/api/v1/job/match-score")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def job_match_score_endpoint(
    body: JobMatchScoreRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _consume_billable_usage(db, db_user, "job-match-score", response=response)

    try:
        result = _main_module().run_pipeline(
            cv_text=body.cv_text,
            job_description=body.job_description,
            lang=body.lang,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job match scoring failed: {e}")

    # ── Mode-specific score adjustment ───────────────────────────────
    # Each career mode has different weight expectations so the same CV
    # gets evaluated differently for junior vs senior vs manager roles.
    mode = (body.mode or "senior").lower().strip()
    raw_score = float(result.get("score", result.get("final_score", 0)) or 0)

    def _as_percent(value):
        value = float(value or 0)
        return value * 100 if 0 < value <= 1 else value

    exp_match = _as_percent((result.get("match_score_v2") or {}).get("experience_match", 0))
    title_match_val = _as_percent((result.get("match_score_v2") or {}).get("title_match", 0))
    seniority_match_val = _as_percent((result.get("match_score_v2") or {}).get("seniority_match", 0))
    kw_coverage = float((result.get("match_score_v2") or {}).get("keyword_coverage_pct", 0) or 0)
    skill_score_val = _as_percent(result.get("skill_score", 0))

    # Mode weights: (keyword, experience, title, seniority, skill)
    _MODE_WEIGHTS = {
        "junior": {"keyword": 0.35, "experience": 0.10, "title": 0.15, "seniority": 0.10, "skill": 0.30},
        "senior": {"keyword": 0.25, "experience": 0.25, "title": 0.15, "seniority": 0.15, "skill": 0.20},
        "manager": {"keyword": 0.20, "experience": 0.30, "title": 0.20, "seniority": 0.15, "skill": 0.15},
        "tech": {"keyword": 0.30, "experience": 0.15, "title": 0.10, "seniority": 0.10, "skill": 0.35},
        "academic": {"keyword": 0.25, "experience": 0.20, "title": 0.20, "seniority": 0.10, "skill": 0.25},
    }
    w = _MODE_WEIGHTS.get(mode, _MODE_WEIGHTS["senior"])
    mode_score = round(
        kw_coverage * w["keyword"]
        + exp_match * w["experience"]
        + title_match_val * w["title"]
        + seniority_match_val * w["seniority"]
        + skill_score_val * w["skill"],
        2,
    )
    mode_score = max(0.0, min(100.0, mode_score))
    jd_quality = result.get("job_description_quality") or {}
    display_score = raw_score
    if jd_quality.get("status") == "invalid":
        mode_score = 0.0
        display_score = 0.0
    elif jd_quality.get("status") == "weak":
        mode_score = min(mode_score, float(result.get("final_score") or mode_score))
        display_score = min(display_score, float(result.get("final_score") or display_score))
    mode_interpretation = interpret_score_localized(mode_score, body.lang)

    try:
        audit_log(
            "job_match_score",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            lang=body.lang,
            score=result.get("score"),
        )
    except Exception:
        pass

    return {
        "score": display_score,
        "raw_score": raw_score,
        "mode_score": mode_score,
        "mode": mode,
        "confidence": result.get("confidence"),
        "risk_level": result.get("risk_level"),
        "interpretation": mode_interpretation,
        "keyword_gap": result.get("keyword_gap"),
        "keyword_gap_v2": result.get("keyword_gap_v2") or {},
        "match_score_v2": result.get("match_score_v2") or {},
        "keyword_coverage_pct": kw_coverage,
        "experience_match": exp_match,
        "title_match": title_match_val,
        "seniority_match": seniority_match_val,
        "skill_match": skill_score_val,
        "mode_weights": w,
        "missing_keywords": ((result.get("keyword_gap_v2") or {}).get("missing_keywords") or []),
        "weak_keywords": ((result.get("keyword_gap_v2") or {}).get("weak_keywords") or []),
        "strong_keywords": ((result.get("keyword_gap_v2") or {}).get("strong_keywords") or []),
        "suggested_keywords": ((result.get("keyword_gap_v2") or {}).get("suggested_keywords") or []),
        "missing_skills": result.get("missing_skills", []),
        "extra_skills": result.get("extra_skills", []),
        "recommendations": result.get("recommendations", []),
    }


@router.post("/api/v1/job-description/quality")
def job_description_quality_endpoint(
    body: JobDescriptionQualityRequest,
    user=Depends(verify_supabase_jwt),
):
    _ensure_not_expired(user)
    quality = _assess_job_description_quality(body.job_description, body.jd_skills or [])
    suggestions = []
    if quality.get("status") in {"missing", "invalid"}:
        suggestions.extend(
            [
                "Add a real role title.",
                "List 5-10 required skills or tools.",
                "Add responsibilities, seniority, and expected outcomes.",
            ]
        )
    elif quality.get("status") == "weak":
        suggestions.extend(
            [
                "Add concrete responsibilities.",
                "Mention seniority and required years only if relevant.",
                "Add must-have and nice-to-have skills separately.",
            ]
        )
    else:
        suggestions.append("Job description is specific enough for matching.")

    return {
        "quality": quality,
        "suggestions": suggestions,
        "can_rank_candidates": bool(quality.get("valid")) and quality.get("status") != "invalid",
    }


@router.post("/api/v1/cv/diff")
def cv_diff_endpoint(
    body: CVDiffRequest,
    user=Depends(verify_supabase_jwt),
):
    _ensure_not_expired(user)
    return {
        "change_summary": _build_cv_change_summary(body.original_text, body.optimized_text),
    }


@router.post("/api/v1/job/keyword-gap")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def keyword_gap_detector_endpoint(
    body: KeywordGapRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _consume_billable_usage(db, db_user, "keyword-gap", response=response)

    try:
        result = compare(body.cv_text, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Keyword gap detection failed: {e}")

    try:
        audit_log(
            "keyword_gap_detector",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            keyword_coverage_pct=result.get("keyword_coverage_pct"),
        )
    except Exception:
        pass

    return {
        "missing_keywords": result.get("missing_keywords", []),
        "weak_keywords": result.get("weak_keywords", []),
        "strong_keywords": result.get("strong_keywords", []),
        "suggested_keywords": result.get("suggested_keywords", []),
        "extra_keywords": result.get("extra_keywords", []),
        "keyword_coverage_pct": result.get("keyword_coverage_pct", 0.0),
        "message": "Add these to increase ATS score",
    }


def _skill_roadmap_for_gap(missing: list[str], weak: list[str], lang: str) -> list[dict]:
    names = [str(item).strip() for item in (missing or []) + (weak or []) if str(item).strip()]
    unique = []
    seen = set()
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    if not unique:
        return []

    is_tr = str(lang or "en").lower().startswith("tr")
    roadmap = []
    for index, skill in enumerate(unique[:8], start=1):
        roadmap.append(
            {
                "skill": skill,
                "priority": "high" if index <= 3 else "medium",
                "proof": (
                    f"{skill} icin bir proje/deneyim maddesi ekle"
                    if is_tr
                    else f"Add one project or experience bullet that proves {skill}"
                ),
                "practice": (
                    f"{skill} ile kucuk bir uygulama veya vaka calismasi hazirla"
                    if is_tr
                    else f"Build a small project or case study using {skill}"
                ),
                "cv_action": (
                    f"{skill} bilgisini becerilerde listele ve deneyim/proje icinde baglamla kullan"
                    if is_tr
                    else f"List {skill} in skills and use it with context in experience or projects"
                ),
            }
        )
    return roadmap


@router.post("/api/v1/job/skill-roadmap")
@rate_limit(f"{RATE_LIMIT_IP_MATCH_PER_MIN}/minute")
def skill_roadmap_endpoint(
    body: SkillRoadmapRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _consume_billable_usage(db, db_user, "skill-roadmap", response=response)

    result = compare(body.cv_text, body.job_description)
    missing = result.get("missing_keywords", []) or []
    weak = result.get("weak_keywords", []) or []
    roadmap = _skill_roadmap_for_gap(missing, weak, body.lang)
    return {
        "keyword_coverage_pct": result.get("keyword_coverage_pct", 0.0),
        "missing_keywords": missing,
        "weak_keywords": weak,
        "roadmap": roadmap,
        "message": "Roadmap generated from job-description gaps",
    }


@router.post("/api/v1/cv/versions")
def save_cv_version(
    body: SaveCVVersionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    cv_text = str(body.cv_text or "").strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="cv_text cannot be empty")

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    version_label = (body.version_label or "").strip() or _next_cv_version_label(db, db_user.id)

    match_score = None
    if body.job_description and str(body.job_description).strip():
        try:
            pipeline = _main_module().run_pipeline(cv_text, body.job_description, lang=body.lang)
            match_score = float(
                (pipeline.get("match_score_v2") or {}).get("match_score") or pipeline.get("final_score") or 0.0
            )
        except Exception:
            match_score = None

    row = CVVersion(
        user_id=db_user.id,
        organization_id=getattr(db_user, "organization_id", None),
        version_label=version_label[:40],
        source=str(body.source or "manual")[:40],
        lang=str(body.lang or "en")[:10],
        cv_text=_stored_text_value(cv_text, "cv_text") or "",
        optimized_cv_text=_stored_text_value(body.optimized_cv_text, "optimized_cv_text"),
        job_description=_stored_text_value(body.job_description, "job_description"),
        match_score=match_score,
        notes=str(body.notes or "") or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        audit_log(
            "cv_version_saved",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            version_label=row.version_label,
            source=row.source,
        )
    except Exception:
        pass

    return {
        "id": row.id,
        "version_label": row.version_label,
        "source": row.source,
        "lang": row.lang,
        "match_score": row.match_score,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.delete("/api/v1/cv/versions/{version_id}")
def delete_cv_version(
    version_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    row = db.query(CVVersion).filter(CVVersion.id == version_id, CVVersion.user_id == db_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="CV version not found")
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": version_id}


@router.get("/api/v1/cv/versions")
def list_cv_versions(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    rows = (
        db.query(CVVersion)
        .filter(CVVersion.user_id == db_user.id)
        .order_by(CVVersion.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": row.id,
                "version_label": row.version_label,
                "source": row.source,
                "lang": row.lang,
                "match_score": row.match_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/api/v1/cv/versions/{version_id}")
def get_cv_version(
    version_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    row = db.query(CVVersion).filter(CVVersion.id == version_id, CVVersion.user_id == db_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="CV version not found")

    return {
        "id": row.id,
        "version_label": row.version_label,
        "source": row.source,
        "lang": row.lang,
        "cv_text": row.cv_text,
        "optimized_cv_text": row.optimized_cv_text,
        "job_description": row.job_description,
        "match_score": row.match_score,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class AgentChatRequest(BaseModel):
    message: str
    agent_type: str  # recruiter | tech_lead | coach
    cv_context: Optional[str] = ""
    history: Optional[List[dict]] = []  # [{"role": "user"|"assistant", "content": "..."}]


@router.post("/api/v1/agents/chat")
def agent_chat_endpoint(
    body: AgentChatRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    # Resolve system prompt based on agent type
    system_prompts = {
        "recruiter": (
            "You are Selin, an expert HR Recruiter Agent. You speak in a highly professional, "
            "evaluative, yet friendly recruiting tone. Your job is to screen candidates, ask "
            "targeted interview questions, analyze their CV experience, and find potential red flags "
            "or outstanding achievements.\n"
            "Keep your answers structured, encouraging, and focused on career pathing."
        ),
        "tech_lead": (
            "You are Devrim, a Senior Tech Lead and Software Architect Agent. You speak in a direct, "
            "highly technical, pragmatic engineering tone. Your job is to evaluate coding skills, "
            "discuss tech stacks, system design trade-offs, and ask deep technical questions.\n"
            "Keep your answers technically accurate, analytical, and structured with bullet points or code blocks where relevant."
        ),
        "coach": (
            "You are Canan, a supportive and strategic Career Coach Agent. You speak in an encouraging, "
            "empathetic, and guiding tone. Your job is to help the candidate brainstorm career goals, "
            "improve their resume summary, optimize keyword placement, and suggest action-oriented next steps.\n"
            "Keep your answers inspirational, constructive, and action-focused."
        ),
    }

    agent_prompt = system_prompts.get(body.agent_type, system_prompts["coach"])

    # Build messages array for OpenAI/Gemini
    messages = [{"role": "system", "content": agent_prompt}]

    # If CV context is provided, inject it as context
    if body.cv_context:
        messages.append({"role": "system", "content": f"Candidate CV Context for Reference:\n{body.cv_context[:5000]}"})

    # Append history
    for msg in body.history or []:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    # Append current message
    messages.append({"role": "user", "content": body.message})

    # Query the LLM client
    from services.ai_client_factory import get_ai_client_and_model

    client, model = get_ai_client_and_model()

    if not client:
        # Mock mode fallback
        return {
            "response": f"[Mock Agent: {body.agent_type.upper()}] Hello! I read your message: '{body.message}'. "
            "To use real agent features, configure GEMINI_API_KEY or OPENAI_API_KEY."
        }

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )
        return {"response": (response.choices[0].message.content or "").strip()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Agent service error: {str(e)}")
