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
from core.request_utils import _read_upload_or_400
from core.runtime_bridge import is_mock_services_on, main_module
from database import SessionLocal, get_db
from models import Analysis, CVVersion, Candidate, Job, JobApplication, Organization, RecruiterJob, Reminder, User
from services import rewrite_service
from services.ai_feature_service import ensure_ai_rewrite_allowed as _ensure_ai_rewrite_allowed
from services.billing_service import is_feature_enabled
from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload
from services.cv_builder_service import build_cv, compile_cv_model, get_available_templates
from services.embedding_service import (
    find_similar_candidates,
    get_embedding,
    save_candidate_embedding,
    save_job_embedding,
)
from services.keyword_service import compare
from services.language_service import detect_language, interpret_score_localized
from services.pdf_runtime import (
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


def _legacy(name: str):
    return getattr(main_module(), name)


def _legacy_call(name: str):
    def _wrapped(*args, **kwargs):
        return _legacy(name)(*args, **kwargs)

    return _wrapped


# Decorators/dependencies must keep their original call signatures, so these are
# direct references rather than variadic wrappers.
rate_limit = _legacy("rate_limit")
require_abuse_check = _legacy("require_abuse_check")
require_user_global_rate = _legacy("require_user_global_rate")
require_search_rate = getattr(main_module(), "require_search_rate", lambda *a, **k: None)
require_embed_rate = getattr(main_module(), "require_embed_rate", lambda *a, **k: None)

# Frequently used legacy helpers. They are centralized here while the remaining
# app/account/quota services are split out in smaller follow-up passes.
audit_log = _legacy_call("audit_log")
track_event = _legacy_call("track_event")
get_or_create_user = _legacy_call("get_or_create_user")
_ensure_not_expired = _legacy_call("_ensure_not_expired")
_normalize_plan = _legacy_call("_normalize_plan")
_resolve_effective_plan = _legacy_call("_resolve_effective_plan")
_resolve_daily_limit_for_plan = _legacy_call("_resolve_daily_limit_for_plan")
_quota_today_date = _legacy_call("_quota_today_date")
_is_premium_plan = _legacy_call("_is_premium_plan")
_is_admin_user = _legacy_call("_is_admin_user")
_consume_daily_quota = _legacy_call("_consume_daily_quota")
_get_daily_quota_status = _legacy_call("_get_daily_quota_status")
_consume_user_rate_limit = _legacy_call("_consume_user_rate_limit")
_consume_billable_usage = _legacy_call("_consume_billable_usage")
_apply_daily_quota_headers = _legacy_call("_apply_daily_quota_headers")
_record_usage_daily = _legacy_call("_record_usage_daily")
_get_owned_analysis_or_404 = _legacy_call("_get_owned_analysis_or_404")
_build_analysis_benchmark = _legacy_call("_build_analysis_benchmark")
_apply_plan_based_result_features = _legacy_call("_apply_plan_based_result_features")
_check_cost_guard = _legacy_call("_check_cost_guard")
_check_disk_safety = _legacy_call("_check_disk_safety")
_get_disk_usage = _legacy_call("_get_disk_usage")
_get_flag = _legacy_call("_get_flag")
_set_flag = _legacy_call("_set_flag")
_metric_request = _legacy_call("_metric_request")
_metric_error = _legacy_call("_metric_error")
_metric_quota_hit = _legacy_call("_metric_quota_hit")
_metric_parse_latency = _legacy_call("_metric_parse_latency")
_record_ai_usage = _legacy_call("_record_ai_usage")
_record_ops_event = _legacy_call("_record_ops_event")
_record_security_event = _legacy_call("_record_security_event")
_recent_events = _legacy_call("_recent_events")
_read_feedback_records = _legacy_call("_read_feedback_records")
_append_feedback_record = _legacy_call("_append_feedback_record")
_send_feedback_email = _legacy_call("_send_feedback_email")
_do_send_email = _legacy_call("_do_send_email")
_validate_reminder_email = _legacy_call("_validate_reminder_email")
_send_reminder_email = _legacy_call("_send_reminder_email")
_admin_access_error = _legacy_call("_admin_access_error")
_admin_ip_allowed = _legacy_call("_admin_ip_allowed")
_admin_rate_limited = _legacy_call("_admin_rate_limited")
_audit_event = _legacy_call("_audit_event")
_alert = _legacy_call("_alert")
_cb_record_failure = _legacy_call("_cb_record_failure")
_cb_record_success = _legacy_call("_cb_record_success")
_cb_is_open = _legacy_call("_cb_is_open")
_observe_dep = _legacy_call("_observe_dep")
_get_cpu_percent = _legacy_call("_get_cpu_percent")
_get_rss_bytes = _legacy_call("_get_rss_bytes")
_is_killed = _legacy_call("_is_killed")
_set_kill_switch = _legacy_call("_set_kill_switch")
_is_draining = _legacy_call("_is_draining")
_set_drain = _legacy_call("_set_drain")
_is_panic = _legacy_call("_is_panic")
_clear_panic = _legacy_call("_clear_panic")
_inflight_get = _legacy_call("_inflight_get")
_is_duplicate_request = _legacy_call("_is_duplicate_request")
_make_dedup_key = _legacy_call("_make_dedup_key")


def _legacy_value(name: str, default=None):
    return getattr(main_module(), name, default)


MOCK_SERVICES_ON = is_mock_services_on()
ABUSE_PROTECTION_ENABLED = _legacy_value("ABUSE_PROTECTION_ENABLED", False)
CLAMAV_ENABLED = _legacy_value("CLAMAV_ENABLED", False)
MAINTENANCE_MODE = _legacy_value("MAINTENANCE_MODE", False)
BENCHMARK_MIN_PEERS = _legacy_value("BENCHMARK_MIN_PEERS", 5)
BUILD_ID = _legacy_value("BUILD_ID", "dev")
GIT_SHA = _legacy_value("GIT_SHA", "unknown")
PARSER_BUILD = _legacy_value("PARSER_BUILD", "local")
INSTANCE_ID = _legacy_value("INSTANCE_ID", "local")

RATE_LIMIT_IP_ANALYZE_PER_MIN = _legacy_value("RATE_LIMIT_IP_ANALYZE_PER_MIN", 10)
RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN = _legacy_value("RATE_LIMIT_IP_ANALYZE_PDF_PER_MIN", 10)
RATE_LIMIT_USER_ANALYZE_PER_MIN = _legacy_value("RATE_LIMIT_USER_ANALYZE_PER_MIN", 10)
RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN = _legacy_value("RATE_LIMIT_USER_ANALYZE_PDF_PER_MIN", 10)
RATE_LIMIT_IP_UPLOAD_PER_MIN = _legacy_value("RATE_LIMIT_IP_UPLOAD_PER_MIN", 5)
RATE_LIMIT_IP_RENDER_PER_MIN = _legacy_value("RATE_LIMIT_IP_RENDER_PER_MIN", 10)
RATE_LIMIT_IP_MATCH_PER_MIN = _legacy_value("RATE_LIMIT_IP_MATCH_PER_MIN", 10)
RATE_LIMIT_IP_REWRITE_PER_MIN = _legacy_value("RATE_LIMIT_IP_REWRITE_PER_MIN", 5)

USER_PLAN_LIMITS_DAILY = _legacy_value("USER_PLAN_LIMITS_DAILY", {})
USER_PLAN_LIMITS_MONTHLY = _legacy_value("USER_PLAN_LIMITS_MONTHLY", {})
ORG_PLAN_LIMITS_DAILY = _legacy_value("ORG_PLAN_LIMITS_DAILY", {})
ORG_PLAN_LIMITS_MONTHLY = _legacy_value("ORG_PLAN_LIMITS_MONTHLY", {})
COST_UPLOAD_PER_DAY = _legacy_value("COST_UPLOAD_PER_DAY", 1000)
COST_ANALYZE_PER_DAY = _legacy_value("COST_ANALYZE_PER_DAY", COST_UPLOAD_PER_DAY)
COST_OPTIMIZE_PER_DAY = _legacy_value("COST_OPTIMIZE_PER_DAY", 500)

_MAX_RESPONSE_BODY_BYTES = _legacy_value("_MAX_RESPONSE_BODY_BYTES", 50 * 1024 * 1024)
_MAX_PDF_EXTRACTED_CHARS = _legacy_value("_MAX_PDF_EXTRACTED_CHARS", 100_000)
_APP_START_TIME = _legacy_value("_APP_START_TIME", time.time())
_ENV_MODE = _legacy_value("_ENV_MODE", os.getenv("ENV", "development").lower())
_CSRF_PROTECTION_ENABLED = _legacy_value("_CSRF_PROTECTION_ENABLED", False)
_ADMIN_IP_ALLOWLIST = _legacy_value("_ADMIN_IP_ALLOWLIST", [])
_CPU_USAGE_LIMIT = _legacy_value("_CPU_USAGE_LIMIT", 100.0)
_MEMORY_RSS_LIMIT_MB = _legacy_value("_MEMORY_RSS_LIMIT_MB", 1024)
_GLOBAL_CONCURRENCY_LIMIT = _legacy_value("_GLOBAL_CONCURRENCY_LIMIT", 20)
_REQUEST_QUEUE_SIZE = _legacy_value("_REQUEST_QUEUE_SIZE", 100)
_REQUEST_TIMEOUT_SECONDS = _legacy_value("_REQUEST_TIMEOUT_SECONDS", 600)
_CB_FAILURE_THRESHOLD = _legacy_value("_CB_FAILURE_THRESHOLD", 5)
_CB_COOLDOWN_SECONDS = _legacy_value("_CB_COOLDOWN_SECONDS", 30)
_PANIC_ERROR_THRESHOLD = _legacy_value("_PANIC_ERROR_THRESHOLD", 20)
_PANIC_ERROR_WINDOW = _legacy_value("_PANIC_ERROR_WINDOW", 60)
_SAMPLE_RATE = _legacy_value("_SAMPLE_RATE", 0.01)
_app_ready = _legacy_value("_app_ready", False)
_panic_mode = _legacy_value("_panic_mode", False)
_guard_logger = _legacy_value("_guard_logger", logging.getLogger("app.guard"))

UPLOADS_TOTAL = _legacy_value("UPLOADS_TOTAL")
DOWNLOADS_TOTAL = _legacy_value("DOWNLOADS_TOTAL")
OPTIMIZES_TOTAL = _legacy_value("OPTIMIZES_TOTAL")
ADMIN_ACTIONS_TOTAL = _legacy_value("ADMIN_ACTIONS_TOTAL")
UPTIME_SECONDS = _legacy_value("UPTIME_SECONDS")
BREAKER_OPEN = _legacy_value("BREAKER_OPEN")

_ops_events = _legacy_value("_ops_events", [])
_security_events = _legacy_value("_security_events", [])
_ai_usage_events = _legacy_value("_ai_usage_events", [])
_live_flags = _legacy_value("_live_flags", {})
_live_flags_lock = _legacy_value("_live_flags_lock")
_circuit_breaker_state = _legacy_value("_circuit_breaker_state", {})
_global_parse_semaphore = _legacy_value("_global_parse_semaphore")
_GLOBAL_PARSE_LIMIT = _legacy_value("_GLOBAL_PARSE_LIMIT", 10)
_LOCAL_ABUSE_BANS = _legacy_value("_LOCAL_ABUSE_BANS", {})
_ip_global_counts = _legacy_value("_ip_global_counts", {})
_user_global_counts = _legacy_value("_user_global_counts", {})
_user_embed_counts = _legacy_value("_user_embed_counts", {})
_search_counts = _legacy_value("_search_counts", {})

ENABLE_CLASSIFIER = _legacy_value("ENABLE_CLASSIFIER", True)
ENABLE_AI_REVIEW = _legacy_value("ENABLE_AI_REVIEW", True)
ENABLE_SANITIZER = _legacy_value("ENABLE_SANITIZER", True)
ENABLE_FALLBACK = _legacy_value("ENABLE_FALLBACK", True)
_is_safe_mode = _legacy_value("_is_safe_mode", lambda: False)

share_tokens = _legacy_value("share_tokens", {})

__all__ = [name for name in globals() if not name.startswith("__")]
