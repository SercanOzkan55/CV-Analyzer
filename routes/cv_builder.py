import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from services.cv_builder_service import build_cv, get_available_templates
from services.language_service import DEFAULT_LANG


def create_router(
    *,
    verify_supabase_jwt,
    get_db,
    rate_limit,
    require_captcha,
    require_abuse_check,
    current_db_user,
    ensure_not_expired,
    metric_request,
    get_or_create_user,
    resolve_effective_plan,
    consume_user_rate_limit,
    consume_daily_quota,
    resolve_daily_limit_for_plan,
    is_premium_plan,
    audit_log,
    mock_services_on: bool,
    user_plan_limits_daily: dict,
) -> APIRouter:
    router = APIRouter()

    class CVBuilderRequest(BaseModel):
        full_name: str
        email: str = ""
        phone: str = ""
        location: str = ""
        linkedin: str = ""
        professional_profile: str = ""
        summary: str = ""
        experiences: list = []
        education: list = []
        skills: list = []
        certifications: list = []
        projects: list = []
        languages: list = []
        job_description: str = ""
        template: str = "classic"
        output_format: str = "docx"
        lang: str = DEFAULT_LANG

    # =====================================================
    # CV BUILDER
    # =====================================================

    RATE_LIMIT_IP_CV_BUILDER_PER_MIN = int(
        os.getenv("RATE_LIMIT_IP_CV_BUILDER_PER_MIN", "10")
    )
    RATE_LIMIT_USER_CV_BUILDER_PER_MIN = int(
        os.getenv("RATE_LIMIT_USER_CV_BUILDER_PER_MIN", "5")
    )


    @router.get("/api/v1/fonts")
    def list_fonts():
        return {
            "fonts": [
                {"id": "arial", "name": "Arial", "ats_safe": True},
                {"id": "calibri", "name": "Calibri", "ats_safe": True},
                {"id": "times", "name": "Times New Roman", "ats_safe": True},
                {"id": "helvetica", "name": "Helvetica", "ats_safe": True},
            ]
        }


    @router.get("/api/v1/cv-builder/template-marketplace")
    def cv_template_marketplace(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        plan = resolve_effective_plan(db, db_user)
        allowed = set(get_available_templates(plan))
        catalog = [
            ("classic", "Classic", "General", "Simple ATS-safe format for most roles.", ["ATS", "General", "Entry to senior"]),
            ("modern", "Modern", "Product", "Clean hierarchy for SaaS, product, and operations roles.", ["SaaS", "Product", "Operations"]),
            ("executive", "Executive", "Leadership", "Focused on impact, strategy, and leadership outcomes.", ["Leadership", "Director", "Executive"]),
            ("professional", "Professional", "Corporate", "Conservative corporate layout with strong readability.", ["Finance", "Consulting", "Corporate"]),
            ("creative", "Creative", "Portfolio", "A tasteful format for design, marketing, and portfolio-led roles.", ["Design", "Marketing", "Portfolio"]),
            ("corporate", "Corporate", "Enterprise", "Enterprise-ready template for formal hiring processes.", ["Enterprise", "Procurement", "Operations"]),
            ("tech", "Tech", "Engineering", "Dense technical skills and project-friendly structure.", ["Engineering", "Data", "Security"]),
            ("consulting", "Consulting", "Consulting", "Case-impact focused structure for consulting applications.", ["Consulting", "Strategy", "MBA"]),
        ]
        return {
            "plan": plan,
            "templates": [
                {
                    "id": template_id,
                    "name": name,
                    "category": category,
                    "description": description,
                    "best_for": tags,
                    "available": template_id in allowed,
                }
                for template_id, name, category, description, tags in catalog
            ],
        }


    @router.get("/api/v1/cv-builder/templates")
    def cv_builder_templates(
        request: Request,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        """Return available CV templates for the user's plan."""
        ensure_not_expired(user)

        if mock_services_on:
            # Even in mock mode, respect actual user plan for templates
            supabase_id = user.get("user_id")
            email = user.get("email") 
            db_user = get_or_create_user(db, supabase_id, email)
            plan = resolve_effective_plan(db, db_user)
            # Fallback to free if no plan resolved
            if not plan or plan == "unknown":
                plan = "free"
        else:
            supabase_id = user.get("user_id")
            email = user.get("email")
            db_user = get_or_create_user(db, supabase_id, email)
            plan = resolve_effective_plan(db, db_user)

        templates = get_available_templates(plan)
        return {
            "templates": templates,
            "plan": plan,
        }


    @router.post("/api/v1/cv-builder/generate")
    @rate_limit(f"{RATE_LIMIT_IP_CV_BUILDER_PER_MIN}/minute")
    async def cv_builder_generate(
        request: Request,
        response: Response,
        body: CVBuilderRequest,
        _: None = Depends(require_captcha),
        __: None = Depends(require_abuse_check),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        """
        Generate an ATS-optimized CV document (DOCX or PDF).
        Uses the same daily quota as analyze-pdf.
        """
        from fastapi.responses import StreamingResponse

        ensure_not_expired(user)
        metric_request("cv-builder")

        # Validate output format
        if body.output_format not in ("docx", "pdf"):
            raise HTTPException(status_code=400, detail="output_format must be 'docx' or 'pdf'")

        # Validate name
        if not body.full_name or not body.full_name.strip():
            raise HTTPException(status_code=400, detail="full_name is required")

        # ---- MOCK MODE ----
        if mock_services_on:
            mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
            if not mock_user_id:
                mock_user_id = "mock-user"
            mock_email = (user or {}).get("email") if isinstance(user, dict) else None
            mock_db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
            mock_plan = resolve_effective_plan(db, mock_db_user)

            user_throttle = consume_user_rate_limit(
                str(mock_user_id), RATE_LIMIT_USER_CV_BUILDER_PER_MIN, "cv-builder"
            )
            if user_throttle is not None:
                response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
                response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
                response.headers["X-User-RateLimit-Remaining"] = str(
                    user_throttle["remaining"]
                )
                if not user_throttle["allowed"]:
                    raise HTTPException(
                        status_code=429,
                        detail=f"User rate limit exceeded ({user_throttle['limit']}/minute)",
                    )

            # Premium users: unlimited CV generation (skip quota)
            if not is_premium_plan(mock_plan):
                redis_quota = consume_daily_quota(
                    str(mock_user_id), limit=resolve_daily_limit_for_plan(mock_plan)
                )
                if redis_quota is not None:
                    response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
                    response.headers["X-Daily-Used"] = str(redis_quota["used"])
                    response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
                    if not redis_quota["allowed"]:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                        )

            cv_data = body.model_dump()
            result = build_cv(
                cv_data=cv_data,
                job_description=body.job_description,
                template=body.template,
                output_format=body.output_format,
                lang=body.lang,
                plan=mock_plan,
            )

            return StreamingResponse(
                result["buffer"],
                media_type=result["content_type"],
                headers={
                    "Content-Disposition": f'attachment; filename="{result["filename"]}"'
                },
            )

        # ---- NORMAL MODE ----
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        effective_plan = resolve_effective_plan(db, db_user)

        # Per-user throttle
        user_throttle = consume_user_rate_limit(
            db_user.supabase_id or str(db_user.id),
            RATE_LIMIT_USER_CV_BUILDER_PER_MIN,
            "cv-builder",
        )
        if user_throttle is not None:
            response.headers["X-User-RateLimit-Limit"] = str(user_throttle["limit"])
            response.headers["X-User-RateLimit-Used"] = str(user_throttle["used"])
            response.headers["X-User-RateLimit-Remaining"] = str(
                user_throttle["remaining"]
            )
            if not user_throttle["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail=f"User rate limit exceeded ({user_throttle['limit']}/minute)",
                )

        # Daily quota (shared with analyze)
        if db_user.last_reset is None or db_user.last_reset.date() < datetime.utcnow().date():
            db_user.daily_usage = 0
            db_user.last_reset = datetime.utcnow()

        if db_user.role != "recruiter" and not is_premium_plan(effective_plan):
            user_daily_limit = user_plan_limits_daily.get(
                db_user.plan_type or "free", user_plan_limits_daily["free"]
            )
            redis_quota = consume_daily_quota(
                db_user.supabase_id or str(db_user.id),
                limit=resolve_daily_limit_for_plan(db_user.plan_type),
            )
            if redis_quota is not None:
                response.headers["X-Daily-Limit"] = str(redis_quota["limit"])
                response.headers["X-Daily-Used"] = str(redis_quota["used"])
                response.headers["X-Daily-Remaining"] = str(redis_quota["remaining"])
                if not redis_quota["allowed"]:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Daily limit reached ({redis_quota['limit']}/day)",
                    )
            elif (db_user.daily_usage or 0) >= user_daily_limit:
                raise HTTPException(status_code=403, detail="Daily quota exceeded")

            db_user.daily_usage = (db_user.daily_usage or 0) + 1
            db_user.monthly_usage = (db_user.monthly_usage or 0) + 1
            db.add(db_user)
            db.commit()

        # Build the CV
        cv_data = body.model_dump()
        result = build_cv(
            cv_data=cv_data,
            job_description=body.job_description,
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=effective_plan,
        )

        response_stream = StreamingResponse(
            result["buffer"],
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            },
        )

        try:
            audit_log(
                "cv_builder_generate",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                output_format=body.output_format,
                template=body.template,
                plan=effective_plan,
            )
        except Exception:
            pass

        return response_stream


    @router.post("/api/v1/cv-builder/preview")
    @rate_limit(f"{RATE_LIMIT_IP_CV_BUILDER_PER_MIN}/minute")
    async def cv_builder_preview(
        request: Request,
        response: Response,
        body: CVBuilderRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        """
        Preview: enhance CV data with AI and return structured JSON
        (no document generation, no quota consumption).
        """
        ensure_not_expired(user)

        if mock_services_on:
            plan = "free"
        else:
            supabase_id = user.get("user_id")
            email = user.get("email")
            db_user = get_or_create_user(db, supabase_id, email)
            plan = resolve_effective_plan(db, db_user)

        from services.cv_builder_service import _enhance_cv_with_ai, _mock_enhance

        cv_data = body.model_dump()
        if mock_services_on:
            enhanced = _mock_enhance(cv_data, body.job_description, body.lang)
        else:
            enhanced = _enhance_cv_with_ai(cv_data, body.job_description, body.lang)

        # Remove non-serializable fields
        enhanced.pop("buffer", None)

        return {
            "enhanced_data": enhanced,
            "available_templates": get_available_templates(plan),
            "plan": plan,
        }

    return router
