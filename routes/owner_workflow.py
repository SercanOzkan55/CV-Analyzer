from core.timeutils import utcnow
from datetime import datetime
import hashlib
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth import verify_supabase_jwt
from database import get_db
from models import AuditLog, CandidateAction, CandidateComment, Notification, NotificationRule, RolePermission, User
from services.email_service import _do_send_email
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


class CandidateAssignmentUpdate(BaseModel):
    assigned_user_id: int | None = None


class CandidateScoreUpdate(BaseModel):
    final_score: float | None = None
    ats_score: float | None = None


class CandidateCommentCreate(BaseModel):
    body: str


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


def _env_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _owner_app_url() -> str:
    return (os.getenv("OWNER_APP_URL") or os.getenv("FRONTEND_URL") or os.getenv("APP_URL") or "").strip().rstrip("/")


def _owner_invite_email_enabled() -> bool:
    explicit = os.getenv("OWNER_INVITE_EMAIL_ENABLED")
    if explicit is not None:
        return _env_bool(explicit)
    return bool(os.getenv("SENDGRID_API_KEY") or os.getenv("SMTP_HOST"))


def _send_owner_invite_email(email: str, role: str, recruiter_email: str, organization_id: int) -> dict[str, Any]:
    if not _owner_invite_email_enabled():
        return {"requested": False, "sent": False, "reason": "email_backend_not_configured"}

    app_url = _owner_app_url()
    lines = [
        "Hello,",
        "",
        f"You have been invited to CV Analyzer as {role}.",
        "Sign in with this email address to activate your access.",
    ]
    if app_url:
        lines.extend(["", f"Sign in: {app_url}"])
    lines.extend(["", f"Organization ID: {organization_id}", "", "CV Analyzer"])

    sent = _do_send_email(
        email,
        "CV Analyzer team access",
        "\n".join(lines),
        recruiter_email=recruiter_email or "",
    )
    return {"requested": True, "sent": bool(sent), "reason": "sent" if sent else "send_failed"}


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


def _candidate_comment_payload(row: CandidateComment) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "candidate_action_id": row.candidate_action_id,
        "author_user_id": row.author_user_id,
        "author_email": row.author.email if row.author else None,
        "body": row.body,
        "created_at": _iso(row.created_at),
    }


def _candidate_action_payload(row: CandidateAction, db: Session | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "organization_id": row.organization_id,
        "job_id": row.job_id,
        "recruiter_id": row.recruiter_id,
        "assigned_user_id": row.assigned_user_id,
        "candidate_name": row.candidate_name,
        "candidate_email": row.candidate_email,
        "final_score": row.final_score,
        "ats_score": row.ats_score,
        "action": row.action,
        "email_sent": row.email_sent,
        "notes": row.notes,
        "created_at": _iso(row.created_at),
        "deleted_at": _iso(row.deleted_at),
        "anonymized_at": _iso(row.anonymized_at),
    }
    if db is not None:
        data["comment_count"] = (
            db.query(CandidateComment).filter(CandidateComment.candidate_action_id == row.id).count()
        )
        latest_comment = (
            db.query(CandidateComment)
            .filter(CandidateComment.candidate_action_id == row.id)
            .order_by(CandidateComment.created_at.desc(), CandidateComment.id.desc())
            .first()
        )
        data["latest_comment"] = _candidate_comment_payload(latest_comment) if latest_comment else None
    return data


def _candidate_action_query_for_user(db: Session, recruiter, action_id: int):
    query = db.query(CandidateAction).filter(
        CandidateAction.id == action_id,
        CandidateAction.organization_id == recruiter.organization_id,
    )
    if normalize_role(recruiter.role) == "limited":
        query = query.filter(CandidateAction.assigned_user_id == recruiter.id)
    return query


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
    invite_email_status = _send_owner_invite_email(
        email,
        role,
        recruiter.email or "",
        recruiter.organization_id,
    )
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
            "invite_email_requested": invite_email_status["requested"],
            "invite_email_sent": invite_email_status["sent"],
        },
        metadata={"source": "owner_create_user", "invite_email": invite_email_status},
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
        metadata={"source": "owner_create_user", "member_user_id": row.id, "invite_email": invite_email_status},
    )
    db.commit()
    db.refresh(row)
    return {"user": _user_payload(row, db), "invite_email": invite_email_status}


@router.put("/users/{user_id}/role")
def owner_update_user_role(
    user_id: int,
    body: OwnerMemberRoleUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "users.manage")
    role = _normalize_member_role(body.role)
    row = db.query(User).filter(User.id == user_id, User.organization_id == recruiter.organization_id).first()
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


@router.get("/candidate-actions")
def owner_candidate_actions(
    include_deleted: bool = Query(False),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidates.view")
    query = db.query(CandidateAction).filter(CandidateAction.organization_id == recruiter.organization_id)
    if normalize_role(recruiter.role) == "limited":
        query = query.filter(CandidateAction.assigned_user_id == recruiter.id)
    if not include_deleted:
        query = query.filter(CandidateAction.deleted_at == None)
    rows = (
        query.order_by(CandidateAction.created_at.desc(), CandidateAction.id.desc()).offset(offset).limit(limit).all()
    )
    return {
        "items": [_candidate_action_payload(row, db) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/candidate-actions/{action_id}/comments")
def owner_candidate_comments(
    action_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidate_comments.view")
    action = _candidate_action_query_for_user(db, recruiter, action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    rows = (
        db.query(CandidateComment)
        .filter(
            CandidateComment.organization_id == recruiter.organization_id,
            CandidateComment.candidate_action_id == action.id,
        )
        .order_by(CandidateComment.created_at.desc(), CandidateComment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_candidate_comment_payload(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/candidate-actions/{action_id}/comments")
def owner_create_candidate_comment(
    action_id: int,
    body: CandidateCommentCreate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidate_comments.create")
    action = (
        _candidate_action_query_for_user(db, recruiter, action_id).filter(CandidateAction.deleted_at == None).first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    text = str(body.body or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment body is required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Comment body must be 2000 characters or fewer")
    row = CandidateComment(
        organization_id=recruiter.organization_id,
        candidate_action_id=action.id,
        author_user_id=recruiter.id,
        body=text,
    )
    db.add(row)
    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_comment_added",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="candidate",
        resource_id=action.id,
        description=f"{action.candidate_name} comment added.",
        new_values={"comment_id": row.id, "body": text[:500]},
        metadata={"source": "owner_create_candidate_comment"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_comment_added",
        title=candidate_event_title("candidate_comment_added"),
        message=f"{action.candidate_name} has a new comment.",
        recipient_user_id=action.recruiter_id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        candidate_action_id=action.id,
        metadata={"source": "owner_create_candidate_comment", "comment_id": row.id},
    )
    db.commit()
    db.refresh(row)
    return {"comment": _candidate_comment_payload(row), "action": _candidate_action_payload(action, db)}


@router.put("/candidate-actions/{action_id}/assignment")
def owner_assign_candidate_action(
    action_id: int,
    body: CandidateAssignmentUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidates.manage")
    row = (
        db.query(CandidateAction)
        .filter(CandidateAction.id == action_id, CandidateAction.organization_id == recruiter.organization_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    assigned_user_id = body.assigned_user_id
    if assigned_user_id is not None:
        assignee = (
            db.query(User)
            .filter(User.id == assigned_user_id, User.organization_id == recruiter.organization_id)
            .first()
        )
        if not assignee:
            raise HTTPException(status_code=404, detail="Assigned user not found")
    old_assigned_user_id = row.assigned_user_id
    row.assigned_user_id = assigned_user_id
    db.flush()
    create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_decision_changed",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="candidate",
        resource_id=row.id,
        description=f"{row.candidate_name} assignment updated.",
        old_values={"assigned_user_id": old_assigned_user_id},
        new_values={"assigned_user_id": assigned_user_id},
        metadata={"source": "owner_assign_candidate_action"},
    )
    db.commit()
    db.refresh(row)
    return {"action": _candidate_action_payload(row, db)}


@router.put("/candidate-actions/{action_id}/score")
def owner_update_candidate_score(
    action_id: int,
    body: CandidateScoreUpdate,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidate_status.update")
    row = (
        db.query(CandidateAction)
        .filter(
            CandidateAction.id == action_id,
            CandidateAction.organization_id == recruiter.organization_id,
            CandidateAction.deleted_at == None,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    old_values = {"final_score": row.final_score, "ats_score": row.ats_score}
    if body.final_score is not None:
        row.final_score = body.final_score
    if body.ats_score is not None:
        row.ats_score = body.ats_score
    new_values = {"final_score": row.final_score, "ats_score": row.ats_score}
    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_score_changed",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="candidate",
        resource_id=row.id,
        description=f"{row.candidate_name} score updated.",
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "owner_update_candidate_score"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_score_changed",
        title=candidate_event_title("candidate_score_changed"),
        message=f"{row.candidate_name} score updated.",
        recipient_user_id=row.recruiter_id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        candidate_action_id=row.id,
        metadata={"source": "owner_update_candidate_score"},
    )
    db.commit()
    db.refresh(row)
    return {"action": _candidate_action_payload(row, db)}


@router.delete("/candidate-actions/{action_id}")
def owner_soft_delete_candidate_action(
    action_id: int,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidates.manage")
    row = (
        db.query(CandidateAction)
        .filter(
            CandidateAction.id == action_id,
            CandidateAction.organization_id == recruiter.organization_id,
            CandidateAction.deleted_at == None,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    row.deleted_at = utcnow()
    db.flush()
    audit = create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_deleted",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="candidate",
        resource_id=row.id,
        description=f"{row.candidate_name} soft deleted.",
        old_values={"deleted_at": None},
        new_values={"deleted_at": _iso(row.deleted_at)},
        metadata={"source": "owner_soft_delete_candidate_action"},
    )
    create_owner_notification(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_deleted",
        title=candidate_event_title("candidate_deleted"),
        message=f"{row.candidate_name} soft deleted.",
        recipient_user_id=row.recruiter_id,
        actor_user_id=recruiter.id,
        audit_log_id=audit.id,
        candidate_action_id=row.id,
        metadata={"source": "owner_soft_delete_candidate_action"},
    )
    db.commit()
    db.refresh(row)
    return {"action": _candidate_action_payload(row, db)}


@router.post("/candidate-actions/{action_id}/anonymize")
def owner_anonymize_candidate_action(
    action_id: int,
    db: Session = Depends(get_db),
    recruiter=Depends(owner_workflow_user),
):
    _require_permission(db, recruiter, "candidates.manage")
    row = (
        db.query(CandidateAction)
        .filter(CandidateAction.id == action_id, CandidateAction.organization_id == recruiter.organization_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Candidate action not found")
    old_values = {
        "candidate_name": row.candidate_name,
        "candidate_email": row.candidate_email,
        "candidate_phone": None,
        "has_cv_text": bool(row.cv_text),
    }
    row.candidate_name = f"Anonymized Candidate #{row.id}"
    row.candidate_email = None
    row.cv_text = None
    row.cv_file_key = None
    row.cv_file_name = None
    row.cv_file_type = None
    row.anonymized_at = utcnow()
    db.flush()
    create_audit_log(
        db,
        organization_id=recruiter.organization_id,
        event_type="candidate_deleted",
        actor_user_id=recruiter.id,
        actor_role=recruiter.role,
        resource_type="candidate",
        resource_id=row.id,
        description=f"Candidate #{row.id} anonymized.",
        old_values=old_values,
        new_values={
            "candidate_name": row.candidate_name,
            "candidate_email": row.candidate_email,
            "has_cv_text": bool(row.cv_text),
            "anonymized_at": _iso(row.anonymized_at),
        },
        metadata={"source": "owner_anonymize_candidate_action"},
    )
    db.commit()
    db.refresh(row)
    return {"action": _candidate_action_payload(row, db)}


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
