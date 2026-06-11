"""add_owner_workflow_models

Revision ID: a0b1c2d3e4f5
Revises: fbfa3b84d7c1
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'fbfa3b84d7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('worker_analysis_results', sa.Column('candidate_status', sa.String(), nullable=True))
    op.create_index(op.f('ix_worker_analysis_results_candidate_status'), 'worker_analysis_results', ['candidate_status'], unique=False)

    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('permission_key', sa.String(), nullable=False),
        sa.Column('is_allowed', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'role', 'permission_key', name='uq_role_permissions_org_role_permission'),
    )
    op.create_index(op.f('ix_role_permissions_organization_id'), 'role_permissions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_role_permissions_permission_key'), 'role_permissions', ['permission_key'], unique=False)
    op.create_index(op.f('ix_role_permissions_role'), 'role_permissions', ['role'], unique=False)

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('actor_role', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='success'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['app_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_event_type'), 'audit_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_status'), 'audit_logs', ['status'], unique=False)

    op.create_table(
        'notification_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False, server_default='in_app'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'event_type', 'channel', name='uq_notification_rules_org_event_channel'),
    )
    op.create_index(op.f('ix_notification_rules_event_type'), 'notification_rules', ['event_type'], unique=False)
    op.create_index(op.f('ix_notification_rules_organization_id'), 'notification_rules', ['organization_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('recipient_user_id', sa.Integer(), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('audit_log_id', sa.Integer(), nullable=True),
        sa.Column('candidate_id', sa.Integer(), nullable=True),
        sa.Column('candidate_action_id', sa.Integer(), nullable=True),
        sa.Column('analysis_result_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False, server_default='in_app'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['app_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['analysis_result_id'], ['worker_analysis_results.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['audit_log_id'], ['audit_logs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['candidate_action_id'], ['candidate_actions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['app_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_actor_user_id'), 'notifications', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_notifications_analysis_result_id'), 'notifications', ['analysis_result_id'], unique=False)
    op.create_index(op.f('ix_notifications_audit_log_id'), 'notifications', ['audit_log_id'], unique=False)
    op.create_index(op.f('ix_notifications_candidate_action_id'), 'notifications', ['candidate_action_id'], unique=False)
    op.create_index(op.f('ix_notifications_candidate_id'), 'notifications', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_organization_id'), 'notifications', ['organization_id'], unique=False)
    op.create_index(op.f('ix_notifications_recipient_user_id'), 'notifications', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_organization_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_candidate_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_candidate_action_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_audit_log_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_analysis_result_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_actor_user_id'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_notification_rules_organization_id'), table_name='notification_rules')
    op.drop_index(op.f('ix_notification_rules_event_type'), table_name='notification_rules')
    op.drop_table('notification_rules')

    op.drop_index(op.f('ix_audit_logs_status'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_organization_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_event_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_user_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index(op.f('ix_role_permissions_role'), table_name='role_permissions')
    op.drop_index(op.f('ix_role_permissions_permission_key'), table_name='role_permissions')
    op.drop_index(op.f('ix_role_permissions_organization_id'), table_name='role_permissions')
    op.drop_table('role_permissions')

    op.drop_index(op.f('ix_worker_analysis_results_candidate_status'), table_name='worker_analysis_results')
    op.drop_column('worker_analysis_results', 'candidate_status')
