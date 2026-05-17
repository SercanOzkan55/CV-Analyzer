import pytest
from unittest.mock import MagicMock
from services.recruiter_service import (
    create_job,
    get_jobs,
    save_candidate_action,
    mark_email_sent,
    get_actions_for_job,
    create_email_template,
    get_email_templates,
    get_email_template,
    delete_email_template
)
import json

def test_create_job():
    db = MagicMock()
    mock_job = MagicMock()
    # We just need to mock what db.add and db.commit do.
    create_job(db, org_id=1, user_id=2, title="Title", description="Desc")
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

def test_get_jobs():
    db = MagicMock()
    get_jobs(db, org_id=1)
    db.query.assert_called_once()
    db.query().filter().order_by().all.assert_called_once()

def test_save_candidate_action():
    db = MagicMock()
    save_candidate_action(
        db,
        org_id=2,
        job_id=1,
        recruiter_id=4,
        candidate_name="John",
        candidate_email="john@example.com",
        cv_text="Text",
        final_score=80.0,
        ats_score=75.0,
        action="email",
        analysis_snapshot={"score": 80}
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

def test_mark_email_sent():
    db = MagicMock()
    mock_action = MagicMock()
    db.query().filter().first.return_value = mock_action
    
    mark_email_sent(db, action_id=1)
    assert mock_action.email_sent is True
    db.commit.assert_called_once()

def test_get_actions_for_job():
    db = MagicMock()
    get_actions_for_job(db, job_id=1, org_id=2)
    db.query.assert_called_once()

def test_create_email_template():
    db = MagicMock()
    create_email_template(
        db, 
        org_id=1, 
        user_id=2, 
        name="Temp", 
        template_type="reject", 
        subject="Sub", 
        body="Body"
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()

def test_get_email_templates():
    db = MagicMock()
    get_email_templates(db, org_id=1)
    db.query.assert_called_once()

def test_get_email_template():
    db = MagicMock()
    get_email_template(db, template_id=1, org_id=2)
    db.query.assert_called_once()

def test_delete_email_template():
    db = MagicMock()
    mock_temp = MagicMock()
    db.query().filter().first.return_value = mock_temp
    
    result = delete_email_template(db, template_id=1, org_id=2)
    assert result is True
    db.delete.assert_called_once_with(mock_temp)
    db.commit.assert_called_once()
