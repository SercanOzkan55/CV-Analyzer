"""Billing, admin operations, and Stripe endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

from fastapi import APIRouter
import requests

from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403


router = APIRouter(tags=["billing"])

from routes.ai_tools import _detect_cv_sections_from_text  # noqa: E402

# =====================================================
# BILLING ENDPOINTS (STRIPE)
# =====================================================


class CreateCheckoutSessionRequest(BaseModel):
    plan_type: str | None = "pro"
    price_id: str | None = None
    success_url: str | None = None
    cancel_url: str | None = None
    billing_period: str | None = None
    price: float | None = None
    currency: str | None = None
    coupon_code: str | None = None
    source: str | None = None


class CreatePortalSessionRequest(BaseModel):
    return_url: str | None = None


class ContactSalesRequest(BaseModel):
    plan_type: str | None = "enterprise"
    company_name: str | None = None
    message: str | None = None
    contact_email: str | None = None
    source: str | None = None


class ActivatePremiumTrialRequest(BaseModel):
    plan_type: str | None = "pro"


class AdminSetUserPlanRequest(BaseModel):
    supabase_id: str | None = None
    email: str | None = None
    plan_type: str | None = None
    billing_status: str | None = None
    role: str | None = None
    update_organization: bool = False


class AdminEmailTestRequest(BaseModel):
    to_email: str
    subject: str | None = "CV Analyzer test email"
    body: str | None = "This is a delivery test from CV Analyzer operations center."


class ParserRegressionCase(BaseModel):
    name: str
    cv_text: str
    expected_language: str | None = None
    expected_sections: list[str] | None = None


class ParserRegressionRequest(BaseModel):
    cases: list[ParserRegressionCase] | None = None


def _stripe_price_map() -> dict[str, str]:
    return {
        "free": os.getenv("STRIPE_PRICE_ID_FREE", "").strip(),
        "pro": os.getenv("STRIPE_PRICE_ID_PRO", "").strip(),
        "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE", "").strip(),
    }


def _normalize_plan_type(plan_type: str | None) -> str:
    normalized = _normalize_plan(plan_type)
    if normalized not in User.PLAN_TYPES:
        return "free"
    return normalized


def _parse_plan_type_or_400(plan_type: str | None) -> str:
    value = (plan_type or "").strip().lower()
    if value not in User.PLAN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan_type. Allowed: {', '.join(User.PLAN_TYPES)}",
        )
    return value


def _parse_billing_status_or_400(billing_status: str | None) -> str:
    if billing_status is None:
        return "active"
    value = billing_status.strip().lower()
    if value not in User.BILLING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(f"Invalid billing_status. Allowed: {', '.join(User.BILLING_STATUSES)}"),
        )
    return value


def _parse_user_role_or_400(role: str | None) -> str:
    value = str(role or "").strip().lower()
    allowed_roles = {"individual", "recruiter", "admin"}
    if value not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=(f"Invalid role. Allowed: {', '.join(sorted(allowed_roles))}"),
        )
    return value


def _require_billing_admin_token(x_billing_admin_token: str | None):
    expected = os.getenv("BILLING_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Billing admin endpoint is not configured",
        )
    provided = (x_billing_admin_token or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid billing admin token")


def _parse_billing_admin_allowed_emails() -> set[str]:
    raw = str(os.getenv("BILLING_ADMIN_ALLOWED_EMAILS", "")).strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item and item.strip()}


def _require_billing_admin_access(
    user_payload: dict,
    x_billing_admin_token: str | None,
    request: Request | None = None,
):
    _require_billing_admin_token(x_billing_admin_token)

    if request is not None:
        if not _admin_ip_allowed(request):
            audit_log("billing_admin_access_denied", reason="ip_not_allowed", path=request.url.path)
            _record_security_event("billing_admin_access_denied", "high", request, reason="ip_not_allowed")
            raise HTTPException(status_code=403, detail="Billing admin access denied")
        if _admin_rate_limited(request):
            audit_log("billing_admin_access_denied", reason="rate_limited", path=request.url.path)
            _record_security_event("billing_admin_access_denied", "medium", request, reason="rate_limited")
            raise HTTPException(status_code=429, detail="Billing admin rate limited")

    allowed_emails = _parse_billing_admin_allowed_emails()
    if not allowed_emails:
        raise HTTPException(
            status_code=503,
            detail="Billing admin allow-list is not configured",
        )

    email = str((user_payload or {}).get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    if email not in allowed_emails:
        _record_security_event("billing_admin_access_denied", "high", request, reason="email_not_allowed", email=email)
        raise HTTPException(status_code=403, detail="Billing admin access denied")


@router.get("/api/v1/billing/admin/me")
def billing_admin_me(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)
    return {
        "status": "ok",
        "email": str((user or {}).get("email") or ""),
    }


def _email_backend_status() -> dict:
    return {
        "from_email": bool(
            os.getenv("REMINDER_EMAIL_FROM") or os.getenv("SMTP_FROM") or os.getenv("SENDGRID_FROM_EMAIL")
        ),
        "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
        "smtp_configured": bool(os.getenv("SMTP_HOST")),
        "default_from": os.getenv("REMINDER_EMAIL_FROM") or os.getenv("SMTP_FROM") or "sikayet.cvanalizor@gmail.com",
    }


def _ops_storage_status() -> dict:
    return {
        "backend": os.getenv("STORAGE_BACKEND", "s3"),
        "s3_bucket_configured": bool(os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET")),
        "s3_sse_algorithm": os.getenv("S3_SSE_ALGORITHM", "AES256"),
        "kms_configured": bool(os.getenv("S3_KMS_KEY_ID")),
        "backup_bucket_configured": bool(os.getenv("BACKUP_S3_BUCKET")),
        "backup_kms_configured": bool(os.getenv("BACKUP_S3_KMS_KEY_ID")),
        "clamav_enabled": bool(os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes")),
    }


def _aggregate_ai_usage(limit: int = 300) -> dict:
    events = _recent_events(_ai_usage_events, limit)
    today = datetime.utcnow().date().isoformat()
    today_events = [event for event in _ai_usage_events if str(event.get("timestamp", "")).startswith(today)]
    by_endpoint: dict[str, dict] = {}
    for event in today_events:
        endpoint = str(event.get("endpoint") or "unknown")
        item = by_endpoint.setdefault(
            endpoint,
            {"calls": 0, "billable_units": 0, "estimated_tokens": 0, "estimated_cost_usd": 0.0},
        )
        item["calls"] += 1
        item["billable_units"] += int(event.get("billable_units") or 0)
        item["estimated_tokens"] += int(event.get("estimated_tokens") or 0)
        item["estimated_cost_usd"] += float(event.get("estimated_cost_usd") or 0.0)
    for item in by_endpoint.values():
        item["estimated_cost_usd"] = round(float(item["estimated_cost_usd"]), 6)
    return {
        "today": {
            "calls": len(today_events),
            "estimated_tokens": sum(int(event.get("estimated_tokens") or 0) for event in today_events),
            "estimated_cost_usd": round(sum(float(event.get("estimated_cost_usd") or 0) for event in today_events), 6),
            "by_endpoint": by_endpoint,
        },
        "recent_events": events,
        "pricing": {
            "ai_cost_per_1k_tokens_usd": float(os.getenv("AI_COST_PER_1K_TOKENS_USD", "0.002") or "0.002"),
            "optimize_daily_cap": COST_OPTIMIZE_PER_DAY,
            "analyze_daily_cap": COST_ANALYZE_PER_DAY,
        },
    }


def _builtin_parser_regression_cases() -> list[ParserRegressionCase]:
    return [
        ParserRegressionCase(
            name="english_multi_section",
            expected_language="en",
            expected_sections=["summary", "experience", "education", "skills"],
            cv_text=(
                "Alex Carter\nSoftware Engineer\nalex@example.com\n"
                "Summary\nBackend engineer with Python and API experience.\n"
                "Experience\nSoftware Engineer - Example Co\nBuilt APIs and improved latency.\n"
                "Education\nBSc Computer Engineering\n"
                "Skills\nPython, FastAPI, SQL\nLanguages\nEnglish"
            ),
        ),
        ParserRegressionCase(
            name="turkish_entry_level",
            expected_language="tr",
            expected_sections=["summary", "education", "skills", "languages"],
            cv_text=(
                "Ayse Yilmaz\nEndustri Muhendisligi Ogrencisi\nayse@example.com\n"
                "Profil\nAnalitik dusunme ve surec iyilestirme odakli aday.\n"
                "Egitim\nIstanbul Universitesi - Endustri Muhendisligi\n"
                "Yetenekler\nExcel, Python, veri analizi\nDiller\nTurkce, Ingilizce"
            ),
        ),
    ]


def _sections_from_builder_payload(payload: dict) -> list[str]:
    sections = []
    if payload.get("summary"):
        sections.append("summary")
    if payload.get("experiences") or payload.get("experience"):
        sections.append("experience")
    if payload.get("education"):
        sections.append("education")
    if payload.get("skills") or payload.get("technical_skills"):
        sections.append("skills")
    if payload.get("projects"):
        sections.append("projects")
    if payload.get("languages"):
        sections.append("languages")
    if payload.get("certifications"):
        sections.append("certifications")
    return sections


@router.get("/api/v1/admin/ops/health")
def admin_ops_health(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(default=None, alias="X-Billing-Admin-Token"),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)

    db_status = "ok"
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)[:240]

    counts = {}
    for name, model in {
        "users": User,
        "analyses": Analysis,
        "cv_versions": CVVersion,
        "reminders": Reminder,
        "recruiter_jobs": RecruiterJob,
    }.items():
        try:
            counts[name] = int(db.query(model).count())
        except Exception:
            counts[name] = None

    disk_pct = None
    try:
        disk_pct = _get_disk_usage()
    except Exception:
        pass

    status = "ok" if db_status == "ok" and not _panic_mode else "degraded"
    return {
        "status": status,
        "ready": bool(_app_ready),
        "panic_mode": bool(_panic_mode),
        "instance": {
            "build_id": BUILD_ID,
            "git_sha": GIT_SHA,
            "parser_build": PARSER_BUILD,
            "instance_id": INSTANCE_ID,
        },
        "dependencies": {"database": {"status": db_status, "error": db_error}},
        "disk_usage_percent": disk_pct,
        "counts": counts,
        "email": _email_backend_status(),
        "storage": _ops_storage_status(),
        "recent_events": _recent_events(_ops_events, 40),
    }


@router.get("/api/v1/admin/ops/cost")
def admin_ops_cost(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(default=None, alias="X-Billing-Admin-Token"),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)
    return _aggregate_ai_usage()


@router.get("/api/v1/admin/ops/security")
def admin_ops_security(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(default=None, alias="X-Billing-Admin-Token"),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)
    return {
        "config": {
            "csrf_enabled": bool(_CSRF_PROTECTION_ENABLED),
            "admin_ip_allowlist_enabled": bool(_ADMIN_IP_ALLOWLIST),
            "abuse_protection_enabled": bool(ABUSE_PROTECTION_ENABLED),
            "clamav_enabled": bool(CLAMAV_ENABLED),
            "trusted_proxy_count": int(os.getenv("TRUSTED_PROXY_COUNT", "0") or "0"),
        },
        "storage": _ops_storage_status(),
        "recent_events": _recent_events(_security_events, 80),
    }


@router.post("/api/v1/admin/ops/email/test")
def admin_ops_email_test(
    body: AdminEmailTestRequest,
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(default=None, alias="X-Billing-Admin-Token"),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)
    to_email = _validate_reminder_email(body.to_email)
    sent = _do_send_email(
        to_email=to_email,
        subject=str(body.subject or "CV Analyzer test email"),
        body=str(body.body or "This is a delivery test from CV Analyzer operations center."),
        recruiter_email="",
    )
    _record_ops_event("email_test", "ok" if sent else "failed", to_email=to_email)
    return {"sent": bool(sent), "email": _email_backend_status()}


@router.post("/api/v1/admin/parser/regression")
def admin_parser_regression(
    body: ParserRegressionRequest,
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(default=None, alias="X-Billing-Admin-Token"),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)

    cases = body.cases or _builtin_parser_regression_cases()
    results = []
    for case in cases[:20]:
        expected_sections = {str(item).lower() for item in (case.expected_sections or [])}
        detected_language = detect_language(case.cv_text)
        sections = _detect_cv_sections_from_text(case.cv_text)
        error = ""
        try:
            payload = structured_text_to_builder_payload(
                case.cv_text,
                job_description="",
                lang=case.expected_language or detected_language or "en",
            ).model_dump()
            sections = sorted(set(sections) | set(_sections_from_builder_payload(payload)))
        except Exception as exc:
            payload = {}
            error = str(exc)[:240]

        missing_sections = sorted(expected_sections - {item.lower() for item in sections})
        lang_ok = not case.expected_language or str(detected_language).lower().startswith(
            str(case.expected_language).lower()
        )
        passed = bool(lang_ok and not missing_sections and not error)
        results.append(
            {
                "name": case.name,
                "passed": passed,
                "detected_language": detected_language,
                "expected_language": case.expected_language,
                "sections": sections,
                "missing_sections": missing_sections,
                "candidate_name": payload.get("full_name") or payload.get("name") or "",
                "error": error,
            }
        )

    passed_count = sum(1 for item in results if item["passed"])
    return {
        "passed": passed_count == len(results),
        "passed_count": passed_count,
        "total": len(results),
        "results": results,
    }


@router.get("/api/v1/billing/admin/users")
def billing_admin_list_users(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    email: str | None = Query(default=None),
    plan_type: str | None = Query(default=None),
    db=Depends(get_db),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)

    query = db.query(User)
    if email:
        query = query.filter(User.email.ilike(f"%{email.strip()}%"))
    if plan_type:
        normalized_plan = _parse_plan_type_or_400(plan_type)
        query = query.filter(User.plan_type == normalized_plan)

    total = int(query.count())
    rows = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        {
            "id": row.id,
            "supabase_id": row.supabase_id,
            "email": row.email,
            "plan_type": row.plan_type,
            "billing_status": row.billing_status,
            "role": row.role,
            "organization_id": row.organization_id,
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
            "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/api/v1/billing/admin/feedback")
def billing_admin_list_feedback(
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)

    items = _read_feedback_records(limit=limit, include_all=True)

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
                "submitter": row.get("email"),
                "supabase_id": row.get("supabase_id"),
            }
        )

    return {"status": "ok", "items": cleaned, "count": len(cleaned)}


def _resolve_checkout_price_and_plan(
    requested_plan: str | None,
    explicit_price_id: str | None,
) -> tuple[str, str]:
    prices = _stripe_price_map()
    plan = _normalize_plan_type(requested_plan)

    if explicit_price_id and explicit_price_id.strip():
        price_id = explicit_price_id.strip()
        for mapped_plan, mapped_price in prices.items():
            if mapped_price and mapped_price == price_id:
                return price_id, mapped_plan
        return price_id, plan

    mapped_price = prices.get(plan) or ""
    if not mapped_price:
        raise HTTPException(
            status_code=400,
            detail=f"No Stripe price configured for plan '{plan}'",
        )
    return mapped_price, plan


def _stripe_api_post(path: str, form_data: dict[str, str]) -> dict:
    def _get_secret_or_file(env_name: str, file_env_name: str) -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    secret_key = _get_secret_or_file("STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_FILE")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    try:
        response = requests.post(
            f"https://api.stripe.com{path}",
            data=form_data,
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        try:
            payload = exc.response.json() if exc.response is not None else {}
            message = payload.get("error", {}).get("message")
            if message:
                raise HTTPException(status_code=502, detail=f"Stripe error: {message}")
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Stripe request failed")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Stripe connection failed")
    except ValueError:
        raise HTTPException(status_code=502, detail="Stripe response was invalid")


def _stripe_api_get(
    path: str,
    query_params: dict[str, str] | list[tuple[str, str]] | None = None,
) -> dict:
    def _get_secret_or_file(env_name: str, file_env_name: str) -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    secret_key = _get_secret_or_file("STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_FILE")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    try:
        response = requests.get(
            f"https://api.stripe.com{path}",
            params=query_params,
            headers={
                "Authorization": f"Bearer {secret_key}",
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        try:
            payload = exc.response.json() if exc.response is not None else {}
            message = payload.get("error", {}).get("message")
            if message:
                raise HTTPException(status_code=502, detail=f"Stripe error: {message}")
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Stripe request failed")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Stripe connection failed")
    except ValueError:
        raise HTTPException(status_code=502, detail="Stripe response was invalid")


def _get_billing_owner(db, db_user: User):
    """Return (owner_type, owner_model) for billing operations."""
    if db_user.role == "recruiter" and db_user.organization_id:
        org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        if org:
            return "organization", org
    return "user", db_user


def _ensure_stripe_customer(db, owner_type: str, owner, email: str | None, supabase_id: str):
    existing = getattr(owner, "stripe_customer_id", None)
    if existing:
        return existing

    customer_payload = {
        "email": email or "",
        "metadata[supabase_id]": supabase_id,
        "metadata[owner_type]": owner_type,
    }
    if owner_type == "organization":
        customer_payload["metadata[organization_id]"] = str(getattr(owner, "id", ""))
        customer_payload["name"] = getattr(owner, "name", "") or "CV Analyzer Organization"
    else:
        customer_payload["metadata[user_id]"] = str(getattr(owner, "id", ""))

    customer = _stripe_api_post("/v1/customers", customer_payload)
    customer_id = str(customer.get("id", "")).strip()
    if not customer_id:
        raise HTTPException(status_code=502, detail="Stripe customer creation failed")

    owner.stripe_customer_id = customer_id
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return customer_id


def _build_contact_sales_mailto_url(
    plan_type: str,
    user_email: str,
    company_name: str,
    owner_type: str,
    message: str,
) -> str:
    sales_email = os.getenv("CONTACT_SALES_EMAIL", "sales@cvanalyzer.local").strip()
    subject = f"Enterprise plan inquiry ({plan_type})"
    body = (
        f"Email: {user_email}\n"
        f"Company: {company_name}\n"
        f"Owner Type: {owner_type}\n"
        f"Plan: {plan_type}\n\n"
        f"Message:\n{message}\n"
    )
    encoded_email = urllib.parse.quote(sales_email, safe="@")
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    return f"mailto:{encoded_email}?subject={encoded_subject}&body={encoded_body}"


def _billing_redirect_allowed_origins() -> set[str]:
    raw_values = [
        os.getenv("BILLING_REDIRECT_ALLOWED_ORIGINS", ""),
        os.getenv("CORS_ORIGINS", ""),
        os.getenv("FRONTEND_URL", ""),
        os.getenv("APP_URL", ""),
        os.getenv("OWNER_APP_URL", ""),
        os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", ""),
        os.getenv("STRIPE_CHECKOUT_CANCEL_URL", ""),
        os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL", ""),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    origins: set[str] = set()
    for raw in raw_values:
        for item in str(raw or "").split(","):
            value = item.strip()
            if not value or value == "*":
                continue
            parsed = urllib.parse.urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                origins.add(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}")
    return origins


def _validate_billing_redirect_url(url: str | None, default_url: str, field_name: str) -> str:
    candidate = str(url or default_url or "").strip()
    parsed = urllib.parse.urlparse(candidate)
    if (
        not candidate
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")

    host = str(parsed.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1", "::1"}
    if _ENV_MODE in ("production", "prod") and parsed.scheme != "https" and not is_local:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")

    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    if origin not in _billing_redirect_allowed_origins():
        raise HTTPException(status_code=400, detail=f"Untrusted {field_name}")

    return candidate


@router.post("/api/v1/billing/checkout-session")
def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    success_url = _validate_billing_redirect_url(
        body.success_url,
        os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", "http://localhost:5173/billing/success"),
        "success_url",
    )
    cancel_url = _validate_billing_redirect_url(
        body.cancel_url,
        os.getenv("STRIPE_CHECKOUT_CANCEL_URL", "http://localhost:5173/billing/cancel"),
        "cancel_url",
    )

    # Development shortcut for local UI testing without external Stripe calls.
    if _main_module().MOCK_SERVICES_ON:
        desired_plan = _normalize_plan_type(body.plan_type)
        if desired_plan == "free":
            desired_plan = "pro"

        db_user.plan_type = desired_plan
        db_user.billing_status = "active"
        db.add(db_user)

        if owner_type == "organization" and owner is not None:
            owner.plan_type = desired_plan
            owner.billing_status = "active"
            db.add(owner)

        db.commit()
        db.refresh(db_user)

        event_context = {
            "user_id": db_user.id,
            "owner_type": owner_type,
            "plan_type": desired_plan,
            "billing_period": body.billing_period or "monthly",
            "price": body.price,
            "currency": (body.currency or "USD").upper(),
            "coupon_code": body.coupon_code,
            "source": body.source or "web_pricing_page",
            "stripe_customer_id": str(getattr(owner, "stripe_customer_id", "") or "mock_customer"),
            "stripe_price_id": body.price_id or f"price_mock_{desired_plan}",
        }

        track_event("purchase_intent", **event_context)
        track_event("checkout_started", **event_context, session_id="cs_test_mock_123")
        track_event(
            "checkout_completed",
            **event_context,
            session_id="cs_test_mock_123",
            stripe_subscription_id=f"sub_mock_{desired_plan}",
        )

        return {
            "session_id": "cs_test_mock_123",
            "url": "",
            "plan_type": desired_plan,
            "mode": "mock",
        }

    price_id, desired_plan = _resolve_checkout_price_and_plan(
        body.plan_type,
        body.price_id,
    )

    customer_id = _ensure_stripe_customer(db, owner_type, owner, email, supabase_id)

    event_context = {
        "user_id": db_user.id,
        "owner_type": owner_type,
        "plan_type": desired_plan,
        "billing_period": body.billing_period or "monthly",
        "price": body.price,
        "currency": (body.currency or "USD").upper(),
        "coupon_code": body.coupon_code,
        "source": body.source or "web_pricing_page",
        "stripe_customer_id": customer_id,
        "stripe_price_id": price_id,
    }

    track_event("purchase_intent", **event_context)

    payload = {
        "mode": "subscription",
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[plan_type]": desired_plan,
        "metadata[owner_type]": owner_type,
        "metadata[billing_period]": body.billing_period or "monthly",
        "metadata[currency]": (body.currency or "USD").upper(),
        "metadata[source]": body.source or "web_pricing_page",
    }
    if body.price is not None:
        payload["metadata[price]"] = str(body.price)
    if body.coupon_code:
        payload["metadata[coupon_code]"] = str(body.coupon_code)

    try:
        session = _stripe_api_post("/v1/checkout/sessions", payload)
    except HTTPException as exc:
        track_event(
            "checkout_failed",
            **event_context,
            error_code=str(exc.status_code),
            error_message=str(exc.detail),
        )
        raise

    session_id = str(session.get("id", ""))
    checkout_url = str(session.get("url", ""))
    if not session_id or not checkout_url:
        track_event(
            "checkout_failed",
            **event_context,
            error_code="502",
            error_message="missing_session_or_url",
        )
        raise HTTPException(status_code=502, detail="Stripe checkout session failed")

    track_event("checkout_started", **event_context, session_id=session_id)

    result = {
        "session_id": session_id,
        "url": checkout_url,
        "customer_id": customer_id,
        "plan_type": desired_plan,
        "owner_type": owner_type,
    }

    # Audit payment event
    try:
        audit_log(
            "billing_checkout_session_created",
            user_id=db_user.id,
            owner_type=owner_type,
            plan_type=desired_plan,
            stripe_customer_id=customer_id,
            session_id=session_id,
        )
    except Exception:
        pass

    return result


@router.post("/api/v1/billing/portal-session")
def create_billing_portal_session(
    body: CreatePortalSessionRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    return_url = _validate_billing_redirect_url(
        body.return_url,
        os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL", "http://localhost:5173/dashboard"),
        "return_url",
    )

    if _main_module().MOCK_SERVICES_ON:
        return {
            "url": return_url,
            "mode": "mock",
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    customer_id = _ensure_stripe_customer(db, owner_type, owner, email, supabase_id)

    session = _stripe_api_post(
        "/v1/billing_portal/sessions",
        {
            "customer": customer_id,
            "return_url": return_url,
        },
    )
    portal_url = str(session.get("url", ""))
    if not portal_url:
        raise HTTPException(status_code=502, detail="Stripe billing portal session failed")

    result = {
        "url": portal_url,
        "customer_id": customer_id,
        "owner_type": owner_type,
    }

    try:
        audit_log(
            "billing_portal_session_created",
            user_id=db_user.id,
            owner_type=owner_type,
            stripe_customer_id=customer_id,
        )
    except Exception:
        pass

    return result


@router.post("/api/v1/billing/contact-sales")
def create_contact_sales_request(
    body: ContactSalesRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    _ensure_not_expired(user)

    plan_type = _normalize_plan_type(body.plan_type or "enterprise")
    if plan_type == "free":
        plan_type = "enterprise"

    # Development shortcut for local testing.
    if _main_module().MOCK_SERVICES_ON:
        contact_url = _build_contact_sales_mailto_url(
            plan_type=plan_type,
            user_email=str((user or {}).get("email") or "dev@example.com"),
            company_name=str(body.company_name or ""),
            owner_type="mock",
            message=str(body.message or ""),
        )
        return {
            "status": "accepted",
            "mode": "mock",
            "contact_url": contact_url,
            "plan_type": plan_type,
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    owner_type, owner = _get_billing_owner(db, db_user)

    company_name = str(body.company_name or getattr(owner, "name", "") or "")
    owner_plan = str(getattr(owner, "plan_type", "") or "")
    message = str(body.message or "")
    contact_email = str(body.contact_email or email or "")

    track_event(
        "purchase_intent",
        user_id=db_user.id,
        owner_type=owner_type,
        plan_type=plan_type,
        billing_period="custom",
        price=None,
        currency="USD",
        coupon_code=None,
        source=body.source or "web_pricing_page",
    )

    crm_webhook_url = os.getenv("CRM_WEBHOOK_URL", "").strip()
    parsed_crm_webhook = urllib.parse.urlparse(crm_webhook_url) if crm_webhook_url else None
    if parsed_crm_webhook and parsed_crm_webhook.scheme == "https" and parsed_crm_webhook.netloc:
        payload = {
            "event": "contact_sales",
            "supabase_id": supabase_id,
            "email": contact_email,
            "owner_type": owner_type,
            "owner_plan": owner_plan,
            "requested_plan": plan_type,
            "company_name": company_name,
            "message": message,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        try:
            response = requests.post(crm_webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return {
                "status": "accepted",
                "mode": "crm_webhook",
                "plan_type": plan_type,
            }
        except requests.RequestException:
            # Fall through to mailto fallback so the user can still reach sales.
            pass

    contact_url = _build_contact_sales_mailto_url(
        plan_type=plan_type,
        user_email=contact_email,
        company_name=company_name,
        owner_type=owner_type,
        message=message,
    )
    result = {
        "status": "accepted",
        "mode": "mailto",
        "contact_url": contact_url,
        "plan_type": plan_type,
    }

    try:
        audit_log(
            "billing_contact_sales",
            user_id=db_user.id,
            owner_type=owner_type,
            requested_plan=plan_type,
            company_name=company_name,
        )
    except Exception:
        pass

    return result


@router.post("/api/v1/billing/activate-trial")
def activate_premium_trial(
    body: ActivatePremiumTrialRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Developer convenience endpoint: upgrade current account to pro/enterprise trial.

    Controlled by `DEV_ALLOW_SELF_PREMIUM` (default enabled in local/dev setups).
    """
    _ensure_not_expired(user)

    allow_self_premium = os.getenv("DEV_ALLOW_SELF_PREMIUM", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    if not allow_self_premium:
        raise HTTPException(status_code=403, detail="Self premium activation disabled")

    requested = _normalize_plan_type(body.plan_type or "pro")
    if requested == "free":
        requested = "pro"

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    db_user.plan_type = requested
    db_user.billing_status = "trialing"
    db.add(db_user)

    org_updated = False
    if db_user.role == "recruiter" and db_user.organization_id:
        org = db.query(Organization).filter(Organization.id == db_user.organization_id).first()
        if org:
            org.plan_type = requested
            org.billing_status = "trialing"
            db.add(org)
            org_updated = True

    db.commit()
    db.refresh(db_user)

    result = {
        "status": "ok",
        "user_id": db_user.supabase_id,
        "plan_type": db_user.plan_type,
        "billing_status": db_user.billing_status,
        "organization_updated": org_updated,
    }

    try:
        audit_log(
            "billing_trial_activated",
            user_id=db_user.id,
            plan_type=db_user.plan_type,
            billing_status=db_user.billing_status,
            organization_updated=org_updated,
        )
    except Exception:
        pass

    return result


@router.post("/api/v1/billing/admin/set-user-plan")
def admin_set_user_plan(
    body: AdminSetUserPlanRequest,
    request: Request,
    user=Depends(verify_supabase_jwt),
    x_billing_admin_token: str | None = Header(
        default=None,
        alias="X-Billing-Admin-Token",
    ),
    db=Depends(get_db),
):
    """Admin-only override for user membership stored in DB.

    Intended for support/manual recovery scenarios (payment provider bugs,
    one-off grants, rollback of incorrect upgrades).
    """
    _ensure_not_expired(user)
    _require_billing_admin_access(user, x_billing_admin_token, request)

    supabase_id = str(body.supabase_id or "").strip()
    email = str(body.email or "").strip().lower()
    if not supabase_id and not email:
        raise HTTPException(status_code=400, detail="supabase_id or email is required")

    has_plan_update = body.plan_type is not None
    has_status_update = body.billing_status is not None
    has_role_update = body.role is not None
    if not (has_plan_update or has_status_update or has_role_update):
        raise HTTPException(
            status_code=400,
            detail="At least one of plan_type, billing_status, or role is required",
        )

    desired_plan = _parse_plan_type_or_400(body.plan_type) if has_plan_update else None
    desired_status = _parse_billing_status_or_400(body.billing_status) if has_status_update else None
    desired_role = _parse_user_role_or_400(body.role) if has_role_update else None

    query = db.query(User)
    if supabase_id:
        query = query.filter(User.supabase_id == supabase_id)
    else:
        query = query.filter(User.email == email)

    db_user = query.first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if desired_plan is not None:
        db_user.plan_type = desired_plan
    if desired_status is not None:
        db_user.billing_status = desired_status
    if desired_role is not None:
        db_user.role = desired_role
    db.add(db_user)

    organization_updated = False
    organization_id = getattr(db_user, "organization_id", None)
    if body.update_organization and organization_id and (desired_plan is not None or desired_status is not None):
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if org:
            if desired_plan is not None:
                org.plan_type = desired_plan
            if desired_status is not None:
                org.billing_status = desired_status
            db.add(org)
            organization_updated = True

    db.commit()
    db.refresh(db_user)

    try:
        audit_log(
            "billing_admin_plan_override",
            user_id=db_user.id,
            supabase_id=db_user.supabase_id,
            email=db_user.email,
            plan_type=db_user.plan_type,
            billing_status=db_user.billing_status,
            role=db_user.role,
            organization_updated=organization_updated,
            source="admin_endpoint",
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "user_id": db_user.supabase_id,
        "email": db_user.email,
        "plan_type": db_user.plan_type,
        "billing_status": db_user.billing_status,
        "role": db_user.role,
        "organization_updated": organization_updated,
    }


# =====================================================
# STRIPE WEBHOOK ENDPOINT
# =====================================================


@router.post("/stripe/webhook")
@rate_limit("30/minute")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    """
    Stripe webhook endpoint for billing events.
    Verifies Stripe signature and processes event.
    In development (MOCK_SERVICES=true), signature validation is skipped for testing.
    """

    def _get_secret_or_file(env_name: str, file_env_name: str, default: str = "") -> str:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        file_path = os.getenv(file_env_name, "").strip()
        if not file_path:
            return default
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip() or default
        except Exception:
            return default

    STRIPE_WEBHOOK_SECRET = _get_secret_or_file("STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_FILE", "")
    IS_TEST_MODE = _main_module().MOCK_SERVICES_ON

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = json.loads(payload)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Invalid payload"})

    # Signature verification (skip ONLY in non-production test mode)
    if not IS_TEST_MODE or _ENV_MODE in ("production", "prod"):
        if not STRIPE_WEBHOOK_SECRET:
            logger.error("stripe_webhook: STRIPE_WEBHOOK_SECRET not configured")
            return JSONResponse(status_code=500, content={"error": "Webhook not configured"})
        if not sig_header:
            return JSONResponse(status_code=401, content={"error": "Missing Stripe-Signature"})
        try:
            # Parse timestamp and signatures from Stripe header
            sig_parts = {}
            for part in sig_header.split(","):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    sig_parts.setdefault(k.strip(), []).append(v.strip())

            timestamp = sig_parts.get("t", [None])[0]
            signatures = sig_parts.get("v1", [])

            if not timestamp or not signatures:
                return JSONResponse(status_code=401, content={"error": "Invalid signature header"})

            # Reject if timestamp is too old (5 minute tolerance)
            try:
                ts_int = int(timestamp)
                if abs(time.time() - ts_int) > 300:
                    return JSONResponse(status_code=401, content={"error": "Timestamp too old"})
            except (ValueError, TypeError):
                return JSONResponse(status_code=401, content={"error": "Invalid timestamp"})

            # Compute expected signature per Stripe's scheme
            signed_payload = f"{timestamp}.".encode() + payload
            expected_sig = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()

            if not any(hmac.compare_digest(expected_sig, s) for s in signatures):
                return JSONResponse(status_code=401, content={"error": "Invalid signature"})
        except Exception as e:
            logger.warning("stripe_webhook: signature verification error: %s", e)
            return JSONResponse(status_code=400, content={"error": "Signature verification failed"})

    # Process event type
    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "checkout.session.completed":
        obj = data.get("object", {})
        metadata = obj.get("metadata", {}) if isinstance(obj.get("metadata"), dict) else {}
        amount_total = obj.get("amount_total")
        price_value = None
        if isinstance(amount_total, (int, float)):
            price_value = round(float(amount_total) / 100.0, 2)

        billing_period_value = str(metadata.get("billing_period") or "monthly")
        currency_value = str(obj.get("currency") or metadata.get("currency") or "usd").upper()
        stripe_price_id = None
        coupon_code_value = str(metadata.get("coupon_code") or "") or None

        session_id = str(obj.get("id") or "").strip()
        if session_id:
            try:
                session_details = _stripe_api_get(
                    f"/v1/checkout/sessions/{urllib.parse.quote(session_id, safe='')}",
                    [
                        ("expand[]", "line_items.data.price"),
                        ("expand[]", "total_details.breakdown.discounts.discount.coupon"),
                    ],
                )
                line_items_obj = session_details.get("line_items", {})
                line_items = line_items_obj.get("data", []) if isinstance(line_items_obj, dict) else []
                first_item = line_items[0] if isinstance(line_items, list) and line_items else {}
                price_obj = first_item.get("price", {}) if isinstance(first_item, dict) else {}
                if isinstance(price_obj, dict):
                    stripe_price_id = str(price_obj.get("id") or "") or None
                    recurring = price_obj.get("recurring", {})
                    if isinstance(recurring, dict):
                        interval = str(recurring.get("interval") or "").lower()
                        if interval == "year":
                            billing_period_value = "yearly"
                        elif interval in ("month", "week", "day"):
                            billing_period_value = interval

                    unit_amount = price_obj.get("unit_amount")
                    if isinstance(unit_amount, (int, float)):
                        price_value = round(float(unit_amount) / 100.0, 2)

                    price_currency = str(price_obj.get("currency") or "").strip()
                    if price_currency:
                        currency_value = price_currency.upper()

                total_details = session_details.get("total_details", {})
                if isinstance(total_details, dict):
                    breakdown = total_details.get("breakdown", {})
                    if isinstance(breakdown, dict):
                        discounts = breakdown.get("discounts", [])
                        first_discount = discounts[0] if isinstance(discounts, list) and discounts else {}
                        discount_obj = first_discount.get("discount", {}) if isinstance(first_discount, dict) else {}
                        coupon_obj = discount_obj.get("coupon", {}) if isinstance(discount_obj, dict) else {}
                        if isinstance(coupon_obj, dict):
                            code = str(coupon_obj.get("id") or coupon_obj.get("name") or "").strip()
                            if code:
                                coupon_code_value = code
            except Exception:
                # Keep webhook resilient; fallback to event payload values.
                pass

        track_event(
            "checkout_completed",
            owner_type=str(metadata.get("owner_type") or "unknown"),
            plan_type=str(metadata.get("plan_type") or "free"),
            billing_period=billing_period_value,
            price=price_value,
            currency=currency_value,
            coupon_code=coupon_code_value,
            source=str(metadata.get("source") or "stripe_webhook"),
            stripe_customer_id=str(obj.get("customer") or ""),
            session_id=session_id,
            stripe_subscription_id=str(obj.get("subscription") or ""),
            stripe_price_id=stripe_price_id,
        )

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        # Extract Stripe customer ID and subscription details
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        status = obj.get("status")  # active, past_due, canceled, trialing
        metadata = obj.get("metadata", {}) if isinstance(obj.get("metadata"), dict) else {}
        plan_hint = str(metadata.get("plan_type", "")).strip().lower()
        if plan_hint not in User.PLAN_TYPES:
            plan_hint = None

        if customer_id:
            # Update user or organization billing_status and stripe_customer_id
            try:
                owner_type = "unknown"
                tracked_user_id = None
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                if user:
                    owner_type = "user"
                    tracked_user_id = user.id
                    user.billing_status = status or "active"
                    if plan_hint:
                        user.plan_type = plan_hint
                    db.add(user)
                    db.commit()
                else:
                    org = db.query(Organization).filter(Organization.stripe_customer_id == customer_id).first()
                    if org:
                        owner_type = "organization"
                        org.billing_status = status or "active"
                        if plan_hint:
                            org.plan_type = plan_hint
                        db.add(org)
                        db.commit()

                if event_type == "customer.subscription.updated" and (status or "").lower() == "active":
                    track_event(
                        "subscription_renewed",
                        user_id=tracked_user_id,
                        owner_type=owner_type,
                        plan_type=plan_hint,
                        billing_period=str(metadata.get("billing_period") or "monthly"),
                        price=None,
                        currency=str(metadata.get("currency") or "USD").upper(),
                        coupon_code=str(metadata.get("coupon_code") or "") or None,
                        source=str(metadata.get("source") or "stripe_webhook"),
                        stripe_customer_id=str(customer_id),
                        stripe_subscription_id=str(obj.get("id") or ""),
                        subscription_status=status,
                    )
            except Exception as e:
                print(f"Error updating billing status: {str(e)}")
                db.rollback()

    elif event_type == "customer.subscription.deleted":
        obj = data.get("object", {})
        customer_id = obj.get("customer")
        if customer_id:
            try:
                owner_type = "unknown"
                tracked_user_id = None
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                if user:
                    owner_type = "user"
                    tracked_user_id = user.id
                    user.billing_status = "canceled"
                    db.add(user)
                    db.commit()
                else:
                    org = db.query(Organization).filter(Organization.stripe_customer_id == customer_id).first()
                    if org:
                        owner_type = "organization"
                        org.billing_status = "canceled"
                        db.add(org)
                        db.commit()

                track_event(
                    "subscription_canceled",
                    user_id=tracked_user_id,
                    owner_type=owner_type,
                    plan_type=None,
                    billing_period=None,
                    price=None,
                    currency="USD",
                    coupon_code=None,
                    source="stripe_webhook",
                    stripe_customer_id=str(customer_id),
                    stripe_subscription_id=str(obj.get("id") or ""),
                    subscription_status="canceled",
                )
            except Exception as e:
                print(f"Error canceling subscription: {str(e)}")
                db.rollback()

    try:
        audit_log("billing_webhook_event", event_type=event_type)
    except Exception:
        pass

    return {"status": "success", "event_type": event_type}


# =====================================================
# RECRUITER DASHBOARD ENDPOINTS
# =====================================================


# Recruiter routes moved to routes/recruiter.py
# ================================================
