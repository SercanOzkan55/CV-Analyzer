from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from models import AuditLog, Notification, NotificationRule, RolePermission, User


PERMISSIONS = {
    "candidates.view": "View candidates",
    "candidates.manage": "Manage candidates",
    "candidate_comments.view": "View candidate comments",
    "candidate_comments.create": "Add candidate comments",
    "candidate_status.update": "Update candidate status",
    "jobs.view": "View jobs",
    "jobs.manage": "Manage jobs",
    "users.view": "View team members",
    "users.manage": "Manage team members",
    "audit.view": "View audit logs",
    "notifications.view": "View notifications",
    "notifications.manage": "Manage notification rules",
    "permissions.manage": "Manage role permissions",
}

DEFAULT_ROLE_PERMISSIONS = {
    "admin": set(PERMISSIONS),
    "owner": set(PERMISSIONS),
    "recruiter": {
        "candidates.view",
        "candidates.manage",
        "candidate_comments.view",
        "candidate_comments.create",
        "candidate_status.update",
        "jobs.view",
        "jobs.manage",
        "users.view",
        "users.manage",
        "audit.view",
        "notifications.view",
        "notifications.manage",
        "permissions.manage",
    },
    "hr": {
        "candidates.view",
        "candidates.manage",
        "candidate_comments.view",
        "candidate_comments.create",
        "candidate_status.update",
        "jobs.view",
        "audit.view",
        "notifications.view",
    },
    "limited": {
        "candidates.view",
        "candidate_comments.view",
        "candidate_comments.create",
        "jobs.view",
        "notifications.view",
    },
    "individual": set(),
}

IMPORTANT_EVENTS = {
    "new_candidate_added",
    "cv_analysis_completed",
    "candidate_accepted",
    "candidate_rejected",
    "candidate_needs_manual_review",
    "candidate_decision_changed",
    "candidate_score_changed",
    "candidate_comment_added",
    "candidate_deleted",
    "user_permission_changed",
    "new_hr_user_added",
}

DECISION_STATUS_MAP = {
    "recommended_accept": "accepted",
    "accept": "accepted",
    "accepted": "accepted",
    "shortlist": "accepted",
    "recommended_reject": "rejected",
    "reject": "rejected",
    "rejected": "rejected",
    "recommended_review": "needs_manual_review",
    "manual_review": "needs_manual_review",
    "needs_manual_review": "needs_manual_review",
    "pending": "needs_manual_review",
}

STATUS_EVENT_MAP = {
    "accepted": "candidate_accepted",
    "rejected": "candidate_rejected",
    "needs_manual_review": "candidate_needs_manual_review",
}

STAGE_STATUS_MAP = {
    "accepted": "accepted",
    "rejected": "rejected",
    "pending": "pending_review",
    "shortlist": "waiting_list",
    "interview": "waiting_list",
    "offer": "waiting_list",
    "withdrawn": "rejected",
}

EVENT_TITLES = {
    "new_candidate_added": "New candidate added",
    "cv_analysis_completed": "CV analysis completed",
    "candidate_accepted": "Candidate accepted",
    "candidate_rejected": "Candidate rejected",
    "candidate_needs_manual_review": "Candidate needs manual review",
    "candidate_decision_changed": "Candidate decision changed",
    "candidate_score_changed": "Candidate score changed",
    "candidate_comment_added": "Candidate comment added",
    "candidate_deleted": "Candidate deleted",
    "user_permission_changed": "User permission changed",
    "new_hr_user_added": "New HR user added",
}


def normalize_role(role: str | None) -> str:
    return str(role or "individual").strip().lower() or "individual"


def decision_to_candidate_status(decision: str | None) -> str:
    key = str(decision or "").strip().lower()
    return DECISION_STATUS_MAP.get(key, "needs_manual_review")


def stage_to_candidate_status(stage: str | None) -> str:
    key = str(stage or "").strip().lower()
    return STAGE_STATUS_MAP.get(key, "needs_manual_review")


def event_type_for_status(candidate_status: str | None) -> str:
    key = str(candidate_status or "").strip().lower()
    return STATUS_EVENT_MAP.get(key, "candidate_needs_manual_review")


def check_permission(db: Session, user: User, permission_key: str) -> bool:
    role = normalize_role(getattr(user, "role", None))
    allowed = permission_key in DEFAULT_ROLE_PERMISSIONS.get(role, set())
    org_id = getattr(user, "organization_id", None)

    if not org_id:
        return role == "admin" and permission_key in DEFAULT_ROLE_PERMISSIONS["admin"]

    override = (
        db.query(RolePermission)
        .filter(
            RolePermission.organization_id == org_id,
            RolePermission.role == role,
            RolePermission.permission_key == permission_key,
        )
        .first()
    )
    if override is not None:
        return bool(override.is_allowed)
    return allowed


def check_tenant_access(user: User, organization_id: int | None) -> bool:
    if normalize_role(getattr(user, "role", None)) == "admin":
        return True
    return bool(organization_id and getattr(user, "organization_id", None) == organization_id)


def permission_snapshot(db: Session, user: User) -> dict[str, bool]:
    return {key: check_permission(db, user, key) for key in sorted(PERMISSIONS)}


def should_notify_owner(
    db: Session,
    organization_id: int,
    event_type: str,
    channel: str = "in_app",
) -> bool:
    if event_type not in IMPORTANT_EVENTS:
        return False
    rule = (
        db.query(NotificationRule)
        .filter(
            NotificationRule.organization_id == organization_id,
            NotificationRule.event_type == event_type,
            NotificationRule.channel == channel,
        )
        .first()
    )
    return True if rule is None else bool(rule.is_enabled)


def candidate_event_title(event_type: str) -> str:
    return EVENT_TITLES.get(event_type, "Candidate status updated")


def candidate_event_message(
    *,
    candidate_name: str | None,
    candidate_status: str,
    decision: str | None = None,
    score: float | None = None,
) -> str:
    name = (candidate_name or "Candidate").strip() or "Candidate"
    if candidate_status == "accepted":
        base = f"{name} was marked as accepted"
    elif candidate_status == "rejected":
        base = f"{name} was marked as rejected"
    else:
        base = f"{name} needs manual review"

    details = []
    if decision:
        details.append(f"decision: {decision}")
    if score is not None:
        details.append(f"score: {score:g}")
    if details:
        return f"{base} ({', '.join(details)})."
    return f"{base}."


def create_audit_log(
    db: Session,
    *,
    organization_id: int,
    event_type: str,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    description: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        old_values=old_values,
        new_values=new_values,
        status=status,
        metadata_=metadata,
    )
    db.add(row)
    db.flush()
    return row


def create_owner_notification(
    db: Session,
    *,
    organization_id: int,
    event_type: str,
    title: str,
    message: str,
    recipient_user_id: int | None = None,
    actor_user_id: int | None = None,
    audit_log_id: int | None = None,
    candidate_id: int | None = None,
    candidate_action_id: int | None = None,
    analysis_result_id: int | None = None,
    channel: str = "in_app",
    metadata: dict[str, Any] | None = None,
) -> Notification | None:
    if not should_notify_owner(db, organization_id, event_type, channel=channel):
        return None
    row = Notification(
        organization_id=organization_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        audit_log_id=audit_log_id,
        candidate_id=candidate_id,
        candidate_action_id=candidate_action_id,
        analysis_result_id=analysis_result_id,
        type=event_type,
        title=title,
        message=message,
        channel=channel,
        metadata_=metadata,
    )
    db.add(row)
    db.flush()
    return row


def record_candidate_status_event(
    db: Session,
    *,
    organization_id: int,
    candidate_status: str,
    candidate_name: str | None = None,
    decision: str | None = None,
    score: float | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    candidate_id: int | None = None,
    candidate_action_id: int | None = None,
    analysis_result_id: int | None = None,
    recipient_user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[AuditLog, Notification | None]:
    event_type = event_type_for_status(candidate_status)
    message = candidate_event_message(
        candidate_name=candidate_name,
        candidate_status=candidate_status,
        decision=decision,
        score=score,
    )
    resource_id = candidate_action_id or candidate_id or analysis_result_id
    audit = create_audit_log(
        db,
        organization_id=organization_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        resource_type="candidate",
        resource_id=resource_id,
        description=message,
        new_values={
            "candidate_status": candidate_status,
            "decision": decision,
            "score": score,
        },
        metadata=metadata,
    )
    notification = create_owner_notification(
        db,
        organization_id=organization_id,
        event_type=event_type,
        title=candidate_event_title(event_type),
        message=message,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        audit_log_id=audit.id,
        candidate_id=candidate_id,
        candidate_action_id=candidate_action_id,
        analysis_result_id=analysis_result_id,
        metadata=metadata,
    )
    return audit, notification


def mark_notification_read(notification: Notification) -> None:
    notification.is_read = True
    notification.read_at = datetime.utcnow()
