"""add recruiter tables

Revision ID: e63b476f4380
Revises: d4e5f6a7b8c9
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e63b476f4380'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RecruiterJob
    op.create_table(
        'recruiter_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_recruiter_jobs_organization_id'), 'recruiter_jobs', ['organization_id'])
    op.create_index(op.f('ix_recruiter_jobs_created_by'), 'recruiter_jobs', ['created_by'])
    op.create_index(op.f('ix_recruiter_jobs_created_at'), 'recruiter_jobs', ['created_at'])

    # EmailTemplate
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('template_type', sa.String(), server_default='accept', nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_email_templates_organization_id'), 'email_templates', ['organization_id'])

    # CandidateAction
    op.create_table(
        'candidate_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('recruiter_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recruiter_id', sa.Integer(), sa.ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('candidate_name', sa.String(), nullable=False),
        sa.Column('candidate_email', sa.String(), nullable=True),
        sa.Column('cv_text', sa.Text(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('ats_score', sa.Float(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('email_sent', sa.Boolean(), server_default='false'),
        sa.Column('email_sent_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('analysis_snapshot', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_candidate_actions_organization_id'), 'candidate_actions', ['organization_id'])
    op.create_index(op.f('ix_candidate_actions_job_id'), 'candidate_actions', ['job_id'])
    op.create_index(op.f('ix_candidate_actions_recruiter_id'), 'candidate_actions', ['recruiter_id'])
    op.create_index(op.f('ix_candidate_actions_created_at'), 'candidate_actions', ['created_at'])

def downgrade() -> None:
    op.drop_table('candidate_actions')
    op.drop_table('email_templates')
    op.drop_table('recruiter_jobs')
