from datetime import datetime
import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth import verify_supabase_jwt
from database import get_db
from models import AuditLog, Notification, NotificationRule, RolePermission, User
from services.user_service import get_or_create_user
from services.owner_workflow_service import (
    DEFAULT_ROLE_PERMISSIONS,
    IMPORTANT_EVENTS,
    PERMISSIONS,
    candidate_event_title,
    check_permission,
    create_audit_log,
    create_owner_notification,
    mark_notification_read,
    normalize_role,
    permission_snapshot,
)


router = APIRouter(prefix="/api/v1/owner", tags=["owner-workflow"])
OWNER_WORKFLOW_ROLES = {"admin", "owner", "recruiter", "hr", "limited"}
MANAGED_MEMBER_ROLES = {"owner", "recruiter", "hr", "limited"}


class NotificationRuleUpdate(BaseModel):
    is_enabled: bool
    channel: str = "in_app"


class OwnerMemberCreate(BaseModel):
    email: str
    role: str = "hr"
    supabase_id: str | None = None


class OwnerMemberRoleUpdate(BaseModel):
    role: str


class RolePermissionUpdate(BaseModel):
    is_allowed: bool


def _require_permission(db: Session, user, permission_key: str) -> None:
    if not check_permission(db, user, permission_key):
        raise HTTPException(status_code=403, detail="Permission denied")


def owner_workflow_user(user=Depends(verify_supabase_jwt), db: Session = Depends(get_db)):
    supabase_id = user.get("user_id")
    email = user.get("email", "")
    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    db_user = get_or_create_user(db, supabase_id, email)
    role = str(db_user.role or "individual").strip().lower()
    if role not in OWNER_WORKFLOW_ROLES:
        raise HTTPException(status_code=403, detail="Owner workflow role required")
    if role != "admin" and not db_user.organization_id:
        raise HTTPException(status_code=400, detail="Organization profile is incomplete")
    return db_user


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _metadata(row) -> dict[str, Any] | None:
    return getattr(row, "metadata_", None)


def _normalize_member_role(role: str | None) -> str:
    value = normalize_role(role)
    if value not in MANAGED_MEMBER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of {', '.join(sorted(MANAGED_MEMBER_ROLES))}",
        )
    return value


def _pending_supabase_id(organization_id: int, email: str) -> str:
    digest = hashlib.sha256(f"{organization_id}:{email.lower()}".encode("utf-8")).hexdigest()[:20]
    return f"pending-owner-{organization_id}-{digest}"


def _audit_payload(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "actor_user_id": row.actor_user_id,
        "actor_role": row.actor_role,
        "event_type": row.event_type,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "description": row.description,
        "old_values": row.old_values,
        "new_values": row.new_values,
        "status": row.status,
        "metadata": _metadata(row),
        "created_at": _iso(row.created_at),
    }


def _notification_payload(row: Notification) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "recipient_user_id": row.recipient_user_id,
        "actor_user_id": row.actor_user_id,
        "audit_log_id": row.audit_log_id,
        "candidate_id": row.candidate_id,
        "candidate_action_id": row.candidate_action_id,
        "analysis_result_id": row.analysis_result_id,
        "type": row.type,
        "title": row.title,
        "message": row.message,
        "channel": row.channel,
        "is_read": row.is_read,
        "read_at": _iso(row.read_at),
        "metadata": _metadata(row),
        "created_at": _iso(row.created_at),
    }


def _user_payload(row: User, db: Session | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "supabase_id": row.supabase_id,
        "email": row.email,
        "role": row.role or "individual",
        "organization_id": row.organization_id,
        "plan_type": row.plan_type,
        "billing_status": row.billing_status,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
    if db is not None:
        data["permissions"] = permission_snapshot(db, row)
    return data


def _role_permission_payload(row: RolePermission) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "role": row.role,
        "permission_key": row.permission_key,
        "is_allowed": row.is_allowed,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


@router.get("/permissions")
def owner_permissions(
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    permissions = permission_snapshot(db, recruiter)
    return {
        "role": recruiter.role or "individual",
        "organization_id": recruiter.organization_id,
        "permissions": permissions,
        "available_permissions": PERMISSIONS,
    }


@router.get("/users")
def owner_users(
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "users.view")
    rows = (
        db.query(User)
        .filter(User.organization_id == recruiter.organization_id)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_user_payload(row, db) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/users")
def owner_create_user(
    body: OwnerMemberCreate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "users.manage")
    email = str(body.email or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    role = _normalize_member_role(body.role)
    supabase_id = str(body.supabase_id or "").strip() or _pending_supabase_id(recruiter.organization_id, email)

    existing = db.query(User).filter(User.email == email).first()
    old_values = None
    if existing:
        if existing.organization_id not in (None, recruiter.organization_id):
            raise HTTPException(status_code=409, detail="User already belongs to another organization")
        old_values = {
            "role": existing.role,
            "organization_id": existing.organization_id,
        }
        existing.organization_id = recruiter.organization_id
        existing.role = role
        row = existing
    else:
        row = User(
            supabase_id=supabase_id,
            email=email,
            organization_id=recruiter.organization_id,
            role=role,
        )
        db.add(row)

    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="new_hr_user_added",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="user",
        resource_id=row.id,
        description=f"{email} added as {role}.",
        old_values=old_values,
        new_values={
            "email": email,
            "role": role,
            "organization_id": recruiter.organization_id,
        },
        metadata={"source": "owner_create_user"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="new_hr_user_added",
        title=candidate_event_title("new_hr_user_added"),
        message=f"{email} added as {role}.",
        recipient_user_id=recruiter.id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        metadata={"source": "owner_create_user", "member_user_id": row.id},
    )
    db.commit()
    db.refresh(row)
    return {"user": _user_payload(row, db)}


@router.put("/users/{user_id}/role")
def owner_update_user_role(
    user_id: int,
    body: OwnerMemberRoleUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "users.manage")
    role = _normalize_member_role(body.role)
    row = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == recruiter.organization_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = row.role or "individual"
    row.role = role
    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="user_permission_changed",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="user",
        resource_id=row.id,
        description=f"{row.email} role changed from {old_role} to {role}.",
        old_values={"role": old_role},
        new_values={"role": role},
        metadata={"source": "owner_update_user_role"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="user_permission_changed",
        title=candidate_event_title("user_permission_changed"),
        message=f"{row.email} role changed from {old_role} to {role}.",
        recipient_user_id=recruiter.id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        metadata={"source": "owner_update_user_role", "member_user_id": row.id},
    )
    db.commit()
    db.refresh(row)
    return {"user": _user_payload(row, db)}


@router.get("/role-permissions")
def owner_role_permissions(
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "permissions.manage")
    rows = (
        db.query(RolePermission)
        .filter(RolePermission.organization_id == recruiter.organization_id)
        .order_by(RolePermission.role.asc(), RolePermission.permission_key.asc())
        .all()
    )
    defaults = {
        role: {key: key in DEFAULT_ROLE_PERMISSIONS.get(role, set()) for key in sorted(PERMISSIONS)}
        for role in sorted(MANAGED_MEMBER_ROLES)
    }
    return {
        "roles": sorted(MANAGED_MEMBER_ROLES),
        "permissions": PERMISSIONS,
        "defaults": defaults,
        "overrides": [_role_permission_payload(row) for row in rows],
    }


@router.put("/role-permissions/{role}/{permission_key}")
def owner_update_role_permission(
    role: str,
    permission_key: str,
    body: RolePermissionUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "permissions.manage")
    normalized_role = _normalize_member_role(role)
    if permission_key not in PERMISSIONS:
        raise HTTPException(status_code=400, detail="Unsupported permission key")
    row = (
        db.query(RolePermission)
        .filter(
            RolePermission.organization_id == recruiter.organization_id,
            RolePermission.role == normalized_role,
            RolePermission.permission_key == permission_key,
        )
        .first()
    )
    old_value = None if row is None else bool(row.is_allowed)
    if row:
        row.is_allowed = bool(body.is_allowed)
    else:
        row = RolePermission(
            organization_id=recruiter.organization_id,
            role=normalized_role,
            permission_key=permission_key,
            is_allowed=bool(body.is_allowed),
        )
        db.add(row)
    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="user_permission_changed",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="role_permission",
        resource_id=row.id,
        description=f"{normalized_role} permission {permission_key} set to {bool(body.is_allowed)}.",
        old_values={"is_allowed": old_value},
        new_values={
            "role": normalized_role,
            "permission_key": permission_key,
            "is_allowed": bool(body.is_allowed),
        },
        metadata={"source": "owner_update_role_permission"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="user_permission_changed",
        title=candidate_event_title("user_permission_changed"),
        message=f"{normalized_role} permission {permission_key} set to {bool(body.is_allowed)}.",
        recipient_user_id=recruiter.id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        metadata={"source": "owner_update_role_permission", "role": normalized_role},
    )
    db.commit()
    db.refresh(row)
    return {"permission": _role_permission_payload(row)}


@router.get("/audit-logs")
def owner_audit_logs(
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "audit.view")
    query = db.query(AuditLog).filter(AuditLog.organization_id == recruiter.organization_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_audit_payload(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/notifications")
def owner_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "notifications.view")
    query = db.query(Notification).filter(
        Notification.organization_id == recruiter.organization_id,
        or_(
            Notification.recipient_user_id == None,
            Notification.recipient_user_id == recruiter.id,
        ),
    )
    if unread_only:
        query = query.filter(Notification.is_read == False)
    rows = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_notification_payload(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/notifications/{notification_id}/read")
def owner_mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "notifications.view")
    row = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.organization_id == recruiter.organization_id,
            or_(
                Notification.recipient_user_id == None,
                Notification.recipient_user_id == recruiter.id,
            ),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    mark_notification_read(row)
    db.commit()
    db.refresh(row)
    return _notification_payload(row)


@router.get("/notification-rules")
def owner_notification_rules(
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "notifications.manage")
    rows = (
        db.query(NotificationRule)
        .filter(NotificationRule.organization_id == recruiter.organization_id)
        .order_by(NotificationRule.event_type.asc(), NotificationRule.channel.asc())
        .all()
    )
    configured = {
        (row.event_type, row.channel): {
            "event_type": row.event_type,
            "channel": row.channel,
            "is_enabled": row.is_enabled,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }
        for row in rows
    }
    defaults = [
        configured.get(
            (event_type, "in_app"),
            {
                "event_type": event_type,
                "channel": "in_app",
                "is_enabled": True,
                "created_at": None,
                "updated_at": None,
            },
        )
        for event_type in sorted(IMPORTANT_EVENTS)
    ]
    return {"items": defaults}


@router.put("/notification-rules/{event_type}")
def owner_update_notification_rule(
    event_type: str,
    body: NotificationRuleUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "notifications.manage")
    if event_type not in IMPORTANT_EVENTS:
        raise HTTPException(status_code=400, detail="Unsupported notification event")
    channel = (body.channel or "in_app").strip().lower()
    row = (
        db.query(NotificationRule)
        .filter(
            NotificationRule.organization_id == recruiter.organization_id,
            NotificationRule.event_type == event_type,
            NotificationRule.channel == channel,
        )
        .first()
    )
    if row:
        row.is_enabled = bool(body.is_enabled)
    else:
        row = NotificationRule(
            organization_id=recruiter.organization_id,
            event_type=event_type,
            channel=channel,
            is_enabled=bool(body.is_enabled),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "event_type": row.event_type,
        "channel": row.channel,
        "is_enabled": row.is_enabled,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
