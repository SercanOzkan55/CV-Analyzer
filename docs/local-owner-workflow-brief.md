# Local Owner Workflow Brief

Source: `C:\Users\ASUS\Desktop\Yeni Microsoft Word Belgesi.docx`

## Goal

Add an owner-centered recruitment workflow to the local side of CV Analyzer.
The requested model has one main user who can manage HR users, roles,
permissions, candidate decisions, audit history, and important notifications.

## Core Flow

1. A user uploads a CV or adds candidate information.
2. The system analyzes the CV.
3. The system calculates the candidate match score for the position.
4. The candidate receives a decision status such as accepted, rejected, or
   needs manual review.
5. The actor and result are saved to audit history.
6. Important events notify the owner user.

## Roles

### Owner User

- View all candidates.
- Start CV analysis.
- Change candidate status.
- Add users.
- Assign roles.
- Change permissions.
- View all analysis results.
- View accepted and rejected decisions.
- View all audit history.
- Manage notification settings.

### Human Resources Role

- Add candidates.
- Upload CVs.
- Start CV analysis.
- View analysis results.
- Mark candidates as accepted, rejected, or needs manual review.
- Cannot change other users permissions.

### Limited User Role

- View only assigned candidates.
- View CV analysis results.
- Cannot make decisions, or can only add comments.

## Candidate Statuses

- `pending_review`
- `analyzing`
- `accepted`
- `rejected`
- `waiting_list`
- `needs_manual_review`

## Critical Notification Events

- New candidate added.
- CV analysis completed.
- Candidate accepted.
- Candidate rejected.
- Candidate score manually changed.
- Candidate decision changed.
- Candidate deleted.
- User permission changed.
- New HR user added.

## Local First Implementation Scope

The first safe local-worker integration should add:

- Local candidate statuses.
- Local decision/audit records.
- Local owner notification records.
- Deterministic notification message generation.
- Permission constants that can be shared with future backend role APIs.

This can be implemented without changing the hosted multi-user auth model yet.
The hosted backend can later receive a fuller migration for Users, Roles,
Permissions, RolePermissions, Candidates, Positions, CVAnalyses, AuditLogs,
Notifications, and NotificationRules.

## Services Requested By Brief

- AuthService
- UserService
- RoleService
- PermissionService
- CandidateService
- PositionService
- CVAnalysisService
- AuditLogService
- NotificationService
- NotificationRuleService

## Reusable Helpers Requested By Brief

- `checkPermission(userId, permissionKey)`
- `checkTenantAccess(userId, ownerId)`
- `createAuditLog(data)`
- `createCandidateNotification(data)`
- `notifyOwnerIfNeeded(eventType, data)`
- `generateCandidateDecisionMessage(data)`

## Security Rules

- Each user should only access data under their own `owner_id`.
- Only the owner can change user permissions.
- HR users can only perform actions granted by their permissions.
- Candidate decisions, score changes, and CV analyses must be logged.
- Decision changes must preserve before and after data.
- CV and personal data must be stored securely.
- Delete operations should prefer soft delete.
- Candidate data should be anonymizable or deletable for KVKK and GDPR support.

## Implemented Activation Note

- Owner-created HR or limited users start as `pending-owner-*` records.
- When the invited email signs in with a real Supabase user id, the pending
  record is adopted instead of creating a duplicate user.
- The adopted user keeps the owner-assigned organization and role.
- Activation is written to audit history and creates an owner notification.
