"""add_local_worker_models

Revision ID: e63b476f4381
Revises: d4e5f6a7b8c9
Create Date: 2026-05-18 00:56:34.675265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e63b476f4381'
down_revision: Union[str, Sequence[str], None] = 'e63b476f4380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidate_actions', sa.Column('cv_file_key', sa.String(), nullable=True))
    op.add_column('candidate_actions', sa.Column('cv_file_name', sa.String(), nullable=True))
    op.add_column('candidate_actions', sa.Column('cv_file_type', sa.String(), nullable=True))

    # WorkerKey
    op.create_table(
        'worker_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('key_prefix', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('quota_limit', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quota_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quota_reserved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['app_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['recruiter_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_keys_key_hash'), 'worker_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_worker_keys_organization_id'), 'worker_keys', ['organization_id'], unique=False)
    op.create_index(op.f('ix_worker_keys_job_id'), 'worker_keys', ['job_id'], unique=False)

    # WorkerSession
    op.create_table(
        'worker_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worker_key_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('worker_version', sa.String(), nullable=True),
        sa.Column('access_token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_key_id'], ['worker_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_sessions_access_token_hash'), 'worker_sessions', ['access_token_hash'], unique=True)
    op.create_index(op.f('ix_worker_sessions_organization_id'), 'worker_sessions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_worker_sessions_worker_key_id'), 'worker_sessions', ['worker_key_id'], unique=False)

    # WorkerClaim
    op.create_table(
        'worker_claims',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worker_key_id', sa.Integer(), nullable=False),
        sa.Column('worker_session_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('cv_id', sa.Integer(), nullable=True),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('candidate_action_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='claimed'),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_action_id'], ['candidate_actions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['recruiter_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_key_id'], ['worker_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_session_id'], ['worker_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_claims_candidate_id'), 'worker_claims', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_worker_claims_candidate_action_id'), 'worker_claims', ['candidate_action_id'], unique=False)
    op.create_index(op.f('ix_worker_claims_job_id'), 'worker_claims', ['job_id'], unique=False)
    op.create_index(op.f('ix_worker_claims_organization_id'), 'worker_claims', ['organization_id'], unique=False)
    op.create_index(op.f('ix_worker_claims_worker_key_id'), 'worker_claims', ['worker_key_id'], unique=False)
    op.create_index(op.f('ix_worker_claims_worker_session_id'), 'worker_claims', ['worker_session_id'], unique=False)
    op.create_index(
        'uq_worker_claims_active_job_candidate',
        'worker_claims',
        ['job_id', 'candidate_id'],
        unique=True,
        postgresql_where=sa.text("status = 'claimed'"),
    )
    op.create_index(
        'uq_worker_claims_active_job_action',
        'worker_claims',
        ['job_id', 'candidate_action_id'],
        unique=True,
        postgresql_where=sa.text("candidate_action_id IS NOT NULL AND status = 'claimed'"),
    )

    # WorkerAnalysisResult
    op.create_table(
        'worker_analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('candidate_action_id', sa.Integer(), nullable=True),
        sa.Column('cv_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('decision', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('matched_skills', sa.JSON(), nullable=True),
        sa.Column('missing_skills', sa.JSON(), nullable=True),
        sa.Column('risk_flags', sa.JSON(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='local_worker'),
        sa.Column('worker_key_id', sa.Integer(), nullable=True),
        sa.Column('worker_version', sa.String(), nullable=True),
        sa.Column('engine_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_action_id'], ['candidate_actions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['recruiter_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_key_id'], ['worker_keys.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_analysis_results_candidate_id'), 'worker_analysis_results', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_worker_analysis_results_candidate_action_id'), 'worker_analysis_results', ['candidate_action_id'], unique=False)
    op.create_index(op.f('ix_worker_analysis_results_job_id'), 'worker_analysis_results', ['job_id'], unique=False)
    op.create_index(op.f('ix_worker_analysis_results_organization_id'), 'worker_analysis_results', ['organization_id'], unique=False)
    op.create_index(op.f('ix_worker_analysis_results_worker_key_id'), 'worker_analysis_results', ['worker_key_id'], unique=False)
    op.create_index('uq_worker_results_job_candidate', 'worker_analysis_results', ['job_id', 'candidate_id'], unique=True)
    op.create_index('uq_worker_results_job_action', 'worker_analysis_results', ['job_id', 'candidate_action_id'], unique=True)

    # QuotaEvent
    op.create_table(
        'quota_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worker_key_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('cv_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_key_id'], ['worker_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quota_events_organization_id'), 'quota_events', ['organization_id'], unique=False)
    op.create_index(op.f('ix_quota_events_worker_key_id'), 'quota_events', ['worker_key_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_quota_events_worker_key_id'), table_name='quota_events')
    op.drop_index(op.f('ix_quota_events_organization_id'), table_name='quota_events')
    op.drop_table('quota_events')
    op.drop_index(op.f('ix_worker_analysis_results_worker_key_id'), table_name='worker_analysis_results')
    op.drop_index('uq_worker_results_job_action', table_name='worker_analysis_results')
    op.drop_index('uq_worker_results_job_candidate', table_name='worker_analysis_results')
    op.drop_index(op.f('ix_worker_analysis_results_organization_id'), table_name='worker_analysis_results')
    op.drop_index(op.f('ix_worker_analysis_results_job_id'), table_name='worker_analysis_results')
    op.drop_index(op.f('ix_worker_analysis_results_candidate_action_id'), table_name='worker_analysis_results')
    op.drop_index(op.f('ix_worker_analysis_results_candidate_id'), table_name='worker_analysis_results')
    op.drop_table('worker_analysis_results')
    op.drop_index(op.f('ix_worker_claims_worker_session_id'), table_name='worker_claims')
    op.drop_index('uq_worker_claims_active_job_action', table_name='worker_claims')
    op.drop_index('uq_worker_claims_active_job_candidate', table_name='worker_claims')
    op.drop_index(op.f('ix_worker_claims_worker_key_id'), table_name='worker_claims')
    op.drop_index(op.f('ix_worker_claims_organization_id'), table_name='worker_claims')
    op.drop_index(op.f('ix_worker_claims_job_id'), table_name='worker_claims')
    op.drop_index(op.f('ix_worker_claims_candidate_action_id'), table_name='worker_claims')
    op.drop_index(op.f('ix_worker_claims_candidate_id'), table_name='worker_claims')
    op.drop_table('worker_claims')
    op.drop_index(op.f('ix_worker_sessions_worker_key_id'), table_name='worker_sessions')
    op.drop_index(op.f('ix_worker_sessions_organization_id'), table_name='worker_sessions')
    op.drop_index(op.f('ix_worker_sessions_access_token_hash'), table_name='worker_sessions')
    op.drop_table('worker_sessions')
    op.drop_index(op.f('ix_worker_keys_job_id'), table_name='worker_keys')
    op.drop_index(op.f('ix_worker_keys_organization_id'), table_name='worker_keys')
    op.drop_index(op.f('ix_worker_keys_key_hash'), table_name='worker_keys')
    op.drop_table('worker_keys')
    op.drop_column('candidate_actions', 'cv_file_type')
    op.drop_column('candidate_actions', 'cv_file_name')
    op.drop_column('candidate_actions', 'cv_file_key')
