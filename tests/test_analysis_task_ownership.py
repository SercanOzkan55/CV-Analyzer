import pytest
from fastapi import HTTPException

from models import AsyncTaskOwner, User
from routes.analysis import _record_analysis_task_owner, _require_analysis_task_owner


def test_analysis_task_owner_is_persisted(db_session, recruiter_user):
    db_user = db_session.query(User).filter(User.id == recruiter_user["user_id"]).first()

    _record_analysis_task_owner("task-db-1", db_user, db_session)

    owner = db_session.query(AsyncTaskOwner).filter(AsyncTaskOwner.task_id == "task-db-1").first()
    assert owner is not None
    assert owner.user_id == db_user.id
    assert owner.organization_id == db_user.organization_id


def test_analysis_task_owner_rejects_other_user(db_session, recruiter_user):
    db_user = db_session.query(User).filter(User.id == recruiter_user["user_id"]).first()
    other = User(
        supabase_id="other-owner-user",
        email="other-owner@example.com",
        organization_id=db_user.organization_id,
        role="individual",
    )
    db_session.add(other)
    db_session.commit()

    _record_analysis_task_owner("task-db-2", db_user, db_session)

    with pytest.raises(HTTPException) as exc:
        _require_analysis_task_owner("task-db-2", other, db_session)

    assert exc.value.status_code == 403
