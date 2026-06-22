"""Shared imports and transitional dependencies for extracted API routers.

The routers should eventually import every business helper from first-class
services. This module keeps the remaining legacy app-owned helpers centralized
so individual route modules no longer copy the whole ``main`` namespace.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import (
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from auth import verify_supabase_jwt
from core.http_runtime import (
    ABUSE_PROTECTION_ENABLED,
    RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN,
    RATE_LIMIT_IP_ANALYZE_PER_MIN,
    RATE_LIMIT_IP_MATCH_PER_MIN,
    RATE_LIMIT_IP_RENDER_PER_MIN,
    RATE_LIMIT_IP_REWRITE_PER_MIN,
    RATE_LIMIT_IP_UPLOAD_PER_MIN,
    RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN,
    RATE_LIMIT_USER_ANALYZE_PER_MIN,
    _ADMIN_IP_ALLOWLIST,
    _CB_COOLDOWN_SECONDS,
    _CB_FAILURE_THRESHOLD,
    _CSRF_PROTECTION_ENABLED,
    _ENV_MODE,
    _GLOBAL_CONCURRENCY_LIMIT,
    _MAX_RESPONSE_BODY_BYTES,
    _REQUEST_QUEUE_SIZE,
    _REQUEST_TIMEOUT_SECONDS,
    _admin_access_error,
    _admin_ip_allowed,
    _admin_rate_limited,
    _is_duplicate_request,
    _make_dedup_key,
    audit_log,
    rate_limit,
    require_abuse_check,
    require_embed_rate,
    require_search_rate,
    require_user_global_rate,
    track_event,
)
from core.metrics import (
    ADMIN_ACTIONS_TOTAL,
    BREAKER_OPEN,
    DOWNLOADS_TOTAL,
    OPTIMIZES_TOTAL,
    UPLOADS_TOTAL,
    UPTIME_SECONDS,
    _APP_START_TIME,
    _metric_error,
    _metric_parse_latency,
    _metric_quota_hit,
    _metric_request,
    _observe_dep,
)
from core.ops_runtime import (
    MAINTENANCE_MODE,
    _CPU_USAGE_LIMIT,
    _MEMORY_RSS_LIMIT_MB,
    _PANIC_ERROR_THRESHOLD,
    _PANIC_ERROR_WINDOW,
    _SAMPLE_RATE,
    _audit_event,
    _check_disk_safety,
    _clear_panic,
    _get_cpu_percent,
    _get_disk_usage,
    _get_flag,
    _get_rss_bytes,
    _inflight_get,
    _is_draining,
    _is_killed,
    _is_panic,
    _recent_events,
    _record_ai_usage,
    _record_ops_event,
    _record_security_event,
    _set_drain,
    _set_flag,
    _set_kill_switch,
)
from core.request_utils import _read_upload_or_400
from core.quota import (
    COST_ANALYZE_PER_DAY,
    COST_OPTIMIZE_PER_DAY,
    COST_UPLOAD_PER_DAY,
    ORG_PLAN_LIMITS_DAILY,
    ORG_PLAN_LIMITS_MONTHLY,
    USER_PLAN_LIMITS_DAILY,
    USER_PLAN_LIMITS_MONTHLY,
    _apply_daily_quota_headers,
    _check_cost_guard,
    _consume_billable_usage,
    _consume_daily_quota,
    _consume_user_rate_limit,
    _get_daily_quota_status,
    _is_admin_user,
    _is_premium_plan,
    _normalize_plan,
    _quota_today_date,
    _record_usage_daily,
    _resolve_daily_limit_for_plan,
    _resolve_effective_plan,
)
from core.runtime_bridge import is_mock_services_on, main_module
from database import SessionLocal, get_db
from models import Analysis, CVVersion, Candidate, Job, JobApplication, Organization, RecruiterJob, Reminder, User
from services import rewrite_service
from services.ai_feature_service import ensure_ai_rewrite_allowed as _ensure_ai_rewrite_allowed
from services.billing_service import is_feature_enabled
from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload
from services.cv_builder_service import (
    BUILD_ID,
    ENABLE_AI_REVIEW,
    ENABLE_CLASSIFIER,
    ENABLE_FALLBACK,
    ENABLE_SANITIZER,
    GIT_SHA,
    INSTANCE_ID,
    PARSER_BUILD,
    _GLOBAL_PARSE_LIMIT,
    _is_safe_mode,
    build_cv,
    compile_cv_model,
    get_available_templates,
)
from services.email_service import (
    _append_feedback_record,
    _do_send_email,
    _read_feedback_records,
    _send_feedback_email,
    _send_reminder_email,
    _validate_reminder_email,
)
from services.user_service import (
    BENCHMARK_MIN_PEERS,
    _apply_plan_based_result_features,
    _build_analysis_benchmark,
    _ensure_not_expired,
    _get_owned_analysis_or_404,
    get_or_create_user,
)
from shared import _alert, _cb_is_open, _cb_record_failure, _cb_record_success
from services.embedding_service import (
    find_similar_candidates,
    get_embedding,
    save_candidate_embedding,
    save_job_embedding,
)
from services.keyword_service import compare
from services.language_service import detect_language, interpret_score_localized
from services.pdf_runtime import (
    CLAMAV_ENABLED,
    _MAX_PDF_EXTRACTED_CHARS,
    _extract_pdf_text,
    _scan_upload_for_viruses,
    _validate_pdf_upload,
    require_captcha,
)
from services.pipeline_runtime import (
    run_pipeline,
    _assess_job_description_quality,
    _extract_job_title_from_jd,
)
from services.tasks import analyze_pdf_task, analyze_text_task, celery_app


logger = logging.getLogger("app.routes")
_main_module = main_module


class AnalyzeRequest(BaseModel):
    cv_text: str
    job_description: str = ""
    job_text: str | None = None
    lang: str = "en"

    def model_post_init(self, __context):
        if (not self.job_description) and self.job_text:
            self.job_description = self.job_text


MOCK_SERVICES_ON = is_mock_services_on()
_guard_logger = logging.getLogger("app.guard")


# ── Mutable runtime state ──────────────────────────────────────────────────
# These reference live objects owned by main.py. Replacing them with source-
# module imports risks state desync — intentionally deferred.
def _legacy_value(name: str, default=None):
    return getattr(main_module(), name, default)


_app_ready = _legacy_value("_app_ready", False)
_panic_mode = _legacy_value("_panic_mode", False)
_ops_events = _legacy_value("_ops_events", [])
_security_events = _legacy_value("_security_events", [])
_ai_usage_events = _legacy_value("_ai_usage_events", [])
_live_flags = _legacy_value("_live_flags", {})
_live_flags_lock = _legacy_value("_live_flags_lock")
_circuit_breaker_state = _legacy_value("_circuit_breaker_state", {})
_global_parse_semaphore = _legacy_value("_global_parse_semaphore")
_LOCAL_ABUSE_BANS = _legacy_value("_LOCAL_ABUSE_BANS", {})
_ip_global_counts = _legacy_value("_ip_global_counts", {})
_user_global_counts = _legacy_value("_user_global_counts", {})
_user_embed_counts = _legacy_value("_user_embed_counts", {})
_search_counts = _legacy_value("_search_counts", {})
share_tokens = _legacy_value("share_tokens", {})

__all__ = [name for name in globals() if not name.startswith("__")]
