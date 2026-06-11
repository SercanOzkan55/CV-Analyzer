from pathlib import Path


CANDIDATE_STATUSES = {
    "pending_review",
    "analyzing",
    "accepted",
    "rejected",
    "waiting_list",
    "needs_manual_review",
}

PERMISSIONS = {
    "candidate.view",
    "candidate.create",
    "candidate.update",
    "candidate.delete",
    "candidate.assign",
    "cv.upload",
    "cv.analyze",
    "cv.view_analysis",
    "cv.change_decision",
    "cv.manual_score_update",
    "position.create",
    "position.update",
    "position.delete",
    "user.invite",
    "user.update_role",
    "user.disable",
    "notification.view",
    "notification.manage",
    "audit_log.view",
}

IMPORTANT_EVENTS = {
    "candidate_created",
    "cv_analysis_completed",
    "candidate_accepted",
    "candidate_rejected",
    "candidate_needs_manual_review",
    "candidate_score_changed",
    "candidate_decision_changed",
    "candidate_deleted",
    "user_permission_changed",
    "hr_user_created",
}

DECISION_STATUS_MAP = {
    "recommended_accept": "accepted",
    "recommended_review": "needs_manual_review",
    "recommended_reject": "rejected",
}

STATUS_EVENT_MAP = {
    "accepted": "candidate_accepted",
    "rejected": "candidate_rejected",
    "needs_manual_review": "candidate_needs_manual_review",
}

EVENT_TITLES = {
    "cv_analysis_completed": "Yeni CV Analizi Tamamlandi",
    "candidate_accepted": "Aday Kabul Edildi",
    "candidate_rejected": "Aday Reddedildi",
    "candidate_needs_manual_review": "Manuel Inceleme Gerekiyor",
    "candidate_decision_changed": "Aday Karari Degistirildi",
}


def check_permission(user: dict, permission_key: str) -> bool:
    if not permission_key:
        return False
    if user.get("role") == "owner":
        return True
    permissions = set(user.get("permissions") or [])
    return permission_key in permissions


def check_tenant_access(user: dict, owner_id: str | int | None) -> bool:
    if owner_id is None:
        return False
    if user.get("role") == "owner" and str(user.get("id")) == str(owner_id):
        return True
    return str(user.get("owner_id")) == str(owner_id)


def decision_to_candidate_status(decision: str, risk_flags: list[str] | None = None) -> str:
    risk_flags = risk_flags or []
    if "extraction_failed" in risk_flags or "empty_text" in risk_flags:
        return "needs_manual_review"
    return DECISION_STATUS_MAP.get(decision, "pending_review")


def event_type_for_status(candidate_status: str) -> str:
    return STATUS_EVENT_MAP.get(candidate_status, "cv_analysis_completed")


def should_notify_owner(event_type: str) -> bool:
    return event_type in IMPORTANT_EVENTS


def infer_candidate_name(row: dict) -> str:
    for key in ("candidate_name", "full_name", "name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    file_name = Path(str(row.get("file") or "candidate")).stem
    return file_name or "Aday"


def generate_candidate_decision_message(data: dict) -> str:
    actor = data.get("actor_name") or "Local Worker"
    candidate = data.get("candidate_name") or "Aday"
    position = data.get("position_title") or "ilgili"
    score = data.get("score")
    status = data.get("candidate_status") or "pending_review"
    rejection_reason = data.get("rejection_reason") or data.get("explanation") or ""

    if status == "accepted":
        return (
            f"{actor} adli kullanici, {candidate} isimli adayin CV analizini tamamladi. "
            f"Aday {position} pozisyonu icin kabul edildi. Uygunluk skoru: %{score}."
        )
    if status == "rejected":
        message = (
            f"{actor} adli kullanici, {candidate} isimli adayin CV analizini tamamladi. "
            f"Aday {position} pozisyonu icin reddedildi. Uygunluk skoru: %{score}."
        )
        if rejection_reason:
            message += f" Red sebebi: {rejection_reason}"
        return message
    if status == "needs_manual_review":
        return (
            f"{actor} adli kullanici, {candidate} isimli adayin CV analizini tamamladi. "
            f"Sistem bu adayi {position} pozisyonu icin manuel inceleme gerekli olarak isaretledi. "
            f"Uygunluk skoru: %{score}."
        )
    return (
        f"{actor} adli kullanici, {candidate} isimli adayin CV analizini tamamladi. "
        f"Aday {position} pozisyonu icin {status} durumuna alindi. Uygunluk skoru: %{score}."
    )


def build_candidate_notification(row: dict, config: dict, actor_name: str = "Local Worker") -> dict | None:
    candidate_status = row.get("candidate_status") or decision_to_candidate_status(
        row.get("decision", ""),
        row.get("risk_flags") or [],
    )
    event_type = row.get("notification_event_type") or event_type_for_status(candidate_status)
    if not should_notify_owner(event_type):
        return None

    candidate_name = infer_candidate_name(row)
    payload = {
        "actor_name": actor_name,
        "candidate_name": candidate_name,
        "position_title": config.get("title") or "ilgili",
        "score": row.get("score"),
        "candidate_status": candidate_status,
        "explanation": row.get("explanation") or row.get("summary") or "",
    }
    return {
        "event_type": event_type,
        "title": EVENT_TITLES.get(event_type, "Aday Bildirimi"),
        "message": generate_candidate_decision_message(payload),
        "candidate_name": candidate_name,
        "candidate_status": candidate_status,
        "channel": "in_app",
    }


def enrich_row_with_owner_workflow(row: dict, config: dict, actor_name: str = "Local Worker") -> dict:
    candidate_status = decision_to_candidate_status(row.get("decision", ""), row.get("risk_flags") or [])
    event_type = event_type_for_status(candidate_status)
    notification = build_candidate_notification(
        {**row, "candidate_status": candidate_status, "notification_event_type": event_type},
        config,
        actor_name=actor_name,
    )
    enriched = {
        **row,
        "candidate_status": candidate_status,
        "notification_event_type": event_type,
    }
    if notification:
        enriched["notification_title"] = notification["title"]
        enriched["notification_message"] = notification["message"]
    return enriched
