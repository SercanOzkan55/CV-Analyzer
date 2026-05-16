"""CV builder endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import verify_supabase_jwt
from database import get_db
from models import User
from services import rewrite_service
from core.runtime_bridge import main_module as _main_module
from services.ai_feature_service import ensure_ai_rewrite_allowed as _ensure_ai_rewrite_allowed
from services.cv_builder_service import build_cv, compile_cv_model, get_available_templates


logger = logging.getLogger("app.cv_builder")


def _legacy(name: str):
    return getattr(_main_module(), name)


def get_or_create_user(*args, **kwargs):
    return _legacy("get_or_create_user")(*args, **kwargs)


def _ensure_not_expired(*args, **kwargs):
    return _legacy("_ensure_not_expired")(*args, **kwargs)


def _resolve_effective_plan(*args, **kwargs):
    return _legacy("_resolve_effective_plan")(*args, **kwargs)


def _is_premium_plan(*args, **kwargs):
    return _legacy("_is_premium_plan")(*args, **kwargs)


def _consume_billable_usage(*args, **kwargs):
    return _legacy("_consume_billable_usage")(*args, **kwargs)


def audit_log(*args, **kwargs):
    return _legacy("audit_log")(*args, **kwargs)


def _max_response_body_bytes() -> int:
    return int(getattr(_main_module(), "_MAX_RESPONSE_BODY_BYTES", 50 * 1024 * 1024))

router = APIRouter(tags=["cv-builder"])

class CVBuilderRequest(BaseModel):
    full_name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    summary: str = ""
    experiences: list = []
    education: list = []
    skills: list = []
    certifications: list = []
    projects: list = []
    languages: list = []
    social_links: list = []
    job_description: str = ""
    template: str = "classic"
    output_format: str = "docx"
    lang: str = "en"
    font_family: str = ""


class CVSummarySuggestRequest(BaseModel):
    summary: str
    job_description: str = ""
    lang: str = "en"
    count: int = 3


def _cv_builder_payload(body: CVBuilderRequest) -> dict:
    """Convert CV builder request models into the dict expected by the renderer."""
    data = body.model_dump()
    data["experiences"] = data.get("experiences") or []
    data["projects"] = data.get("projects") or []
    data["languages"] = data.get("languages") or []
    data["language"] = data.get("lang") or "en"
    data["template"] = body.template
    data["output_format"] = body.output_format
    return data


def _resolve_request_user(db, user_payload: dict) -> User:
    supabase_id = user_payload.get("user_id")
    email = user_payload.get("email")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    return get_or_create_user(db, supabase_id, email)


@router.get("/api/v1/cv-builder/templates")
def cv_builder_templates(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)
    templates = get_available_templates(plan)
    return {"plan": plan, "templates": templates}


@router.get("/api/v1/cv-builder/template-marketplace")
def cv_builder_template_marketplace(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)
    available = set(get_available_templates(plan))
    catalog = [
        {
            "id": "classic",
            "name": "Classic ATS",
            "category": "ATS",
            "best_for": ["software", "engineering", "operations"],
            "description": "Single-column, high compatibility template for applicant tracking systems.",
            "available": "classic" in available,
        },
        {
            "id": "modern",
            "name": "Modern Compact",
            "category": "General",
            "best_for": ["early-career", "product", "business"],
            "description": "Compact layout for stronger scanability without decorative columns.",
            "available": "modern" in available,
        },
        {
            "id": "executive",
            "name": "Executive",
            "category": "Leadership",
            "best_for": ["manager", "director", "senior"],
            "description": "Achievement-forward layout for leadership and senior profiles.",
            "available": "executive" in available,
        },
    ]
    return {"plan": plan, "templates": catalog}


@router.post("/api/v1/cv-builder/preview")
def cv_builder_preview(
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)

    payload = _cv_builder_payload(body)
    cv_model = compile_cv_model(payload)
    template = body.template if body.template in get_available_templates(plan) else "classic"
    return {
        "template": template,
        "enhanced_data": cv_model.model_dump(),
        "cache_hit": False,
    }


@router.post("/api/v1/cv-builder/preview-html")
def cv_builder_preview_html(
    body: CVBuilderRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    _resolve_request_user(db, user)

    payload = _cv_builder_payload(body)
    cv_model = compile_cv_model(payload)
    try:
        from renderers.preview_renderer import render_html_preview

        html = render_html_preview(cv_model, body.template, font_override=body.font_family)
    except Exception:
        logger.exception("CV builder HTML preview failed")
        raise HTTPException(status_code=500, detail="CV preview failed")

    return {
        "template": body.template,
        "html": html,
        "enhanced_data": cv_model.model_dump(),
    }


@router.post("/api/v1/cv-builder/generate")
def cv_builder_generate(
    body: CVBuilderRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    if body.output_format not in ("docx", "pdf", "html", "typst"):
        raise HTTPException(status_code=400, detail="Unsupported output_format")

    db_user = _resolve_request_user(db, user)
    plan = _resolve_effective_plan(db, db_user)
    font_family = body.font_family if _is_premium_plan(plan) else ""
    _consume_billable_usage(db, db_user, "cv-builder-generate", response=response)

    try:
        result = build_cv(
            cv_data=_cv_builder_payload(body),
            job_description=body.job_description or "",
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=plan,
            font_family=font_family,
        )
    except RuntimeError as exc:
        if "overloaded" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc))
        raise HTTPException(status_code=500, detail="CV generation failed")
    except Exception:
        logger.exception("CV builder generation failed")
        raise HTTPException(status_code=500, detail="CV generation failed")

    buf = result["buffer"]
    if hasattr(buf, "getbuffer") and buf.getbuffer().nbytes > _max_response_body_bytes():
        raise HTTPException(status_code=413, detail="Generated file too large")

    try:
        audit_log(
            "cv_builder_generate",
            user_id=db_user.id,
            organization_id=db_user.organization_id,
            output_format=body.output_format,
            template=body.template,
            plan=plan,
        )
    except Exception:
        pass

    return StreamingResponse(
        buf,
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.post("/api/v1/cv-builder/suggest-summary")
def cv_builder_suggest_summary(
    body: CVSummarySuggestRequest,
    response: Response,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    db_user = _resolve_request_user(db, user)
    plan = _ensure_ai_rewrite_allowed(db, db_user)
    _consume_billable_usage(db, db_user, "cv-builder-suggest-summary", response=response)

    count = max(1, min(int(body.count or 3), 5))
    try:
        suggestions = rewrite_service.suggest_summaries(
            summary=body.summary,
            job_description=body.job_description or "",
            lang=body.lang,
            count=count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"suggestions": suggestions, "plan": plan}


