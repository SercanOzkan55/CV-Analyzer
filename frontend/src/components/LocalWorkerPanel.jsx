import React, { useEffect, useState } from 'react'
import {
  anonymizeOwnerCandidateAction,
  assignOwnerCandidateAction,
  createWorkerKey,
  createOwnerUser,
  deleteOwnerCandidateAction,
  downloadWorkerExecutable,
  fetchOwnerCandidateActions,
  fetchOwnerAuditLogs,
  fetchOwnerNotificationRules,
  fetchOwnerNotifications,
  fetchOwnerPermissions,
  fetchOwnerRolePermissions,
  fetchOwnerUsers,
  fetchWorkerProgress,
  fetchWorkerQuota,
  fetchWorkerSessions,
  listWorkerKeys,
  markOwnerNotificationRead,
  recruiterListJobs,
  revokeWorkerKey,
  updateOwnerCandidateScore,
  updateOwnerNotificationRule,
  updateOwnerRolePermission,
  updateOwnerUserRole,
} from '../api'
import { useAuth } from '../context/AuthContext'

export default function LocalWorkerPanel({ organizationId }) {
  const { token } = useAuth()
  const [keys, setKeys] = useState([])
  const [jobs, setJobs] = useState([])
  const [progressByJob, setProgressByJob] = useState({})
  const [sessions, setSessions] = useState([])
  const [quotaSummary, setQuotaSummary] = useState(null)
  const [ownerPermissions, setOwnerPermissions] = useState(null)
  const [ownerNotifications, setOwnerNotifications] = useState([])
  const [ownerAuditLogs, setOwnerAuditLogs] = useState([])
  const [ownerNotificationRules, setOwnerNotificationRules] = useState([])
  const [ownerUsers, setOwnerUsers] = useState([])
  const [ownerRolePermissions, setOwnerRolePermissions] = useState(null)
  const [ownerCandidateActions, setOwnerCandidateActions] = useState([])
  const [candidateScoreDrafts, setCandidateScoreDrafts] = useState({})
  const [showDeletedCandidates, setShowDeletedCandidates] = useState(false)
  const [loading, setLoading] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyJobId, setNewKeyJobId] = useState('')
  const [newKeyQuota, setNewKeyQuota] = useState(1000)
  const [newMemberEmail, setNewMemberEmail] = useState('')
  const [newMemberRole, setNewMemberRole] = useState('hr')
  const [permissionRole, setPermissionRole] = useState('hr')
  const [permissionKey, setPermissionKey] = useState('candidates.view')
  const [permissionAllowed, setPermissionAllowed] = useState(true)
  const [createdKeyData, setCreatedKeyData] = useState(null)

  useEffect(() => {
    if (!token) return
    fetchKeys()
    fetchQuota()
    fetchJobs()
    fetchSessions()
    fetchOwnerWorkflow()
  }, [token, showDeletedCandidates])

  async function fetchKeys() {
    try {
      setLoading(true)
      const data = await listWorkerKeys(token)
      setKeys(data || [])
    } catch (error) {
      console.error('Error fetching worker keys:', error)
    } finally {
      setLoading(false)
    }
  }

  async function fetchQuota() {
    try {
      const data = await fetchWorkerQuota(token)
      setQuotaSummary(data)
      const remaining = Number(data?.quota_remaining ?? 0)
      if (remaining > 0) {
        setNewKeyQuota((value) => Math.min(Number(value) || 1000, remaining))
      }
    } catch (error) {
      console.warn('Worker quota unavailable', error)
      setQuotaSummary(null)
    }
  }

  async function fetchSessions() {
    try {
      const data = await fetchWorkerSessions(token)
      setSessions(data.sessions || [])
    } catch (error) {
      console.warn('Worker sessions unavailable', error)
      setSessions([])
    }
  }

  async function fetchOwnerWorkflow() {
    try {
      const permissions = await fetchOwnerPermissions(token)
      const canViewNotifications = Boolean(permissions?.permissions?.['notifications.view'])
      const canViewAudit = Boolean(permissions?.permissions?.['audit.view'])
      const canManageRules = Boolean(permissions?.permissions?.['notifications.manage'])
      const canViewUsers = Boolean(permissions?.permissions?.['users.view'])
      const canManagePermissions = Boolean(permissions?.permissions?.['permissions.manage'])
      const canViewCandidates = Boolean(permissions?.permissions?.['candidates.view'])
      const [notifications, auditLogs, rules] = await Promise.all([
        canViewNotifications ? fetchOwnerNotifications(token, { limit: 5 }) : Promise.resolve({ items: [] }),
        canViewAudit ? fetchOwnerAuditLogs(token, { limit: 5 }) : Promise.resolve({ items: [] }),
        canManageRules ? fetchOwnerNotificationRules(token) : Promise.resolve({ items: [] }),
      ])
      const [users, rolePermissions, candidateActions] = await Promise.all([
        canViewUsers ? fetchOwnerUsers(token, { limit: 100 }) : Promise.resolve({ items: [] }),
        canManagePermissions ? fetchOwnerRolePermissions(token) : Promise.resolve(null),
        canViewCandidates
          ? fetchOwnerCandidateActions(token, { includeDeleted: showDeletedCandidates, limit: 20 })
          : Promise.resolve({ items: [] }),
      ])
      setOwnerPermissions(permissions)
      setOwnerNotifications(notifications.items || [])
      setOwnerAuditLogs(auditLogs.items || [])
      setOwnerNotificationRules(rules.items || [])
      setOwnerUsers(users.items || [])
      setOwnerRolePermissions(rolePermissions)
      setOwnerCandidateActions(candidateActions.items || [])
      setCandidateScoreDrafts(
        Object.fromEntries((candidateActions.items || []).map((item) => [
          item.id,
          {
            final_score: item.final_score ?? '',
            ats_score: item.ats_score ?? '',
          },
        ]))
      )
    } catch (error) {
      console.warn('Owner workflow unavailable', error)
      setOwnerPermissions(null)
      setOwnerNotifications([])
      setOwnerAuditLogs([])
      setOwnerNotificationRules([])
      setOwnerUsers([])
      setOwnerRolePermissions(null)
      setOwnerCandidateActions([])
      setCandidateScoreDrafts({})
    }
  }

  async function fetchJobs() {
    try {
      const data = await recruiterListJobs(token)
      const loadedJobs = data.jobs || []
      setJobs(loadedJobs)
      const progressEntries = await Promise.all(
        loadedJobs.map(async (job) => {
          try {
            return [job.id, await fetchWorkerProgress(token, job.id)]
          } catch (error) {
            console.warn('Worker progress unavailable for job', job.id, error)
            return [job.id, null]
          }
        })
      )
      setProgressByJob(Object.fromEntries(progressEntries))
    } catch (error) {
      console.error('Error fetching recruiter jobs:', error)
    }
  }

  async function handleCreateKey(event) {
    event.preventDefault()
    if (!newKeyName || !newKeyQuota) return
    try {
      setLoading(true)
      const data = await createWorkerKey(token, {
        name: newKeyName,
        job_id: newKeyJobId ? Number(newKeyJobId) : null,
        quota_limit: Number(newKeyQuota),
        company_id: organizationId || undefined,
      })
      setCreatedKeyData(data)
      setNewKeyName('')
      setNewKeyJobId('')
      setNewKeyQuota(1000)
      try {
        await Promise.all([fetchKeys(), fetchQuota()])
      } catch (refreshError) {
        console.warn('Worker key was created, but refresh failed:', refreshError)
      }
    } catch (error) {
      console.error('Error creating worker key:', error)
      window.alert(error.message || 'Failed to create worker key')
    } finally {
      setLoading(false)
    }
  }

  async function handleRevokeKey(id) {
    if (!window.confirm('Revoke this worker key? Active sessions will stop working.')) return
    try {
      setLoading(true)
      await revokeWorkerKey(token, id)
      await fetchKeys()
      await fetchQuota()
      await fetchSessions()
    } catch (error) {
      console.error('Error revoking worker key:', error)
      window.alert(error.message || 'Failed to revoke worker key')
    } finally {
      setLoading(false)
    }
  }

  async function handleMarkOwnerNotificationRead(notificationId) {
    try {
      await markOwnerNotificationRead(token, notificationId)
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not mark notification as read', error)
    }
  }

  async function handleToggleOwnerRule(rule) {
    try {
      await updateOwnerNotificationRule(token, rule.event_type, {
        channel: rule.channel || 'in_app',
        is_enabled: !rule.is_enabled,
      })
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not update notification rule', error)
      window.alert(error.message || 'Failed to update notification rule')
    }
  }

  async function handleCreateOwnerUser(event) {
    event.preventDefault()
    if (!newMemberEmail) return
    try {
      await createOwnerUser(token, {
        email: newMemberEmail,
        role: newMemberRole,
      })
      setNewMemberEmail('')
      setNewMemberRole('hr')
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not create owner user', error)
      window.alert(error.message || 'Failed to add team member')
    }
  }

  async function handleUpdateOwnerUserRole(userId, role) {
    try {
      await updateOwnerUserRole(token, userId, { role })
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not update owner user role', error)
      window.alert(error.message || 'Failed to update team member role')
    }
  }

  async function handleRolePermissionSubmit(event) {
    event.preventDefault()
    if (!permissionRole || !permissionKey) return
    try {
      await updateOwnerRolePermission(token, permissionRole, permissionKey, {
        is_allowed: permissionAllowed,
      })
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not update role permission', error)
      window.alert(error.message || 'Failed to update role permission')
    }
  }

  function handleCandidateScoreDraft(actionId, field, value) {
    setCandidateScoreDrafts((current) => ({
      ...current,
      [actionId]: {
        ...(current[actionId] || {}),
        [field]: value,
      },
    }))
  }

  async function handleAssignCandidateAction(actionId, assignedUserId) {
    try {
      await assignOwnerCandidateAction(token, actionId, {
        assigned_user_id: assignedUserId ? Number(assignedUserId) : null,
      })
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not assign candidate action', error)
      window.alert(error.message || 'Failed to assign candidate')
    }
  }

  async function handleSaveCandidateScore(action) {
    const draft = candidateScoreDrafts[action.id] || {}
    const finalScore = draft.final_score === '' ? null : Number(draft.final_score)
    const atsScore = draft.ats_score === '' ? null : Number(draft.ats_score)
    try {
      await updateOwnerCandidateScore(token, action.id, {
        final_score: Number.isFinite(finalScore) ? finalScore : null,
        ats_score: Number.isFinite(atsScore) ? atsScore : null,
      })
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not update candidate score', error)
      window.alert(error.message || 'Failed to update candidate score')
    }
  }

  async function handleDeleteCandidateAction(actionId) {
    if (!window.confirm('Soft delete this candidate action?')) return
    try {
      await deleteOwnerCandidateAction(token, actionId)
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not delete candidate action', error)
      window.alert(error.message || 'Failed to delete candidate')
    }
  }

  async function handleAnonymizeCandidateAction(actionId) {
    if (!window.confirm('Anonymize this candidate and remove stored CV text/file links?')) return
    try {
      await anonymizeOwnerCandidateAction(token, actionId)
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not anonymize candidate action', error)
      window.alert(error.message || 'Failed to anonymize candidate')
    }
  }

  async function handleDownloadPackage() {
    try {
      setLoading(true)
      const blob = await downloadWorkerExecutable(token)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'CV Analyzer Local Worker.exe'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Error downloading worker package:', error)
      window.alert(error.message || 'Failed to download worker app')
    } finally {
      setLoading(false)
    }
  }

  const monthlyLimit = Number(quotaSummary?.monthly_limit ?? 4000)
  const quotaAllocated = Number(quotaSummary?.quota_allocated ?? 0)
  const quotaUsedReserved = Number(quotaSummary?.quota_used_reserved ?? 0)
  const quotaRemaining = Math.max(0, Number(quotaSummary?.quota_remaining ?? monthlyLimit))
  const quotaPercent = monthlyLimit ? Math.min(100, Math.round((quotaAllocated / monthlyLimit) * 100)) : 0
  const isQuotaBlocked = Boolean(quotaSummary && quotaRemaining <= 0)
  const canViewOwnerWorkflow = Boolean(
    ownerPermissions?.permissions?.['notifications.view'] ||
    ownerPermissions?.permissions?.['audit.view'] ||
    ownerPermissions?.permissions?.['candidates.view']
  )
  const canManageOwnerRules = Boolean(ownerPermissions?.permissions?.['notifications.manage'])
  const canManageOwnerUsers = Boolean(ownerPermissions?.permissions?.['users.manage'])
  const canManageRolePermissions = Boolean(ownerPermissions?.permissions?.['permissions.manage'])
  const canViewCandidateActions = Boolean(ownerPermissions?.permissions?.['candidates.view'])
  const canManageCandidateActions = Boolean(ownerPermissions?.permissions?.['candidates.manage'])
  const canUpdateCandidateScores = Boolean(ownerPermissions?.permissions?.['candidate_status.update'])
  const unreadOwnerCount = ownerNotifications.filter((item) => !item.is_read).length
  const managedRoles = ownerRolePermissions?.roles || ['owner', 'recruiter', 'hr', 'limited']
  const permissionOptions = Object.entries(ownerRolePermissions?.permissions || ownerPermissions?.available_permissions || {})
  const permissionOverrides = ownerRolePermissions?.overrides || []
  const assignableUsers = ownerUsers.filter((member) => !member.deleted_at)

  return (
    <div className="card product-card worker-panel">
      <div className="worker-panel-header">
        <div>
          <span className="product-page-kicker">Local Worker</span>
          <h2>Local Worker Management</h2>
          <p className="text-muted">Generate scoped worker keys for secure local CV processing.</p>
        </div>
        <button type="button" className="btn-outline" onClick={handleDownloadPackage} disabled={loading || !token}>
          Download worker app (.exe)
        </button>
      </div>

      <div className={`worker-quota-summary ${isQuotaBlocked ? 'is-exhausted' : ''}`}>
        <div>
          <span className="product-page-kicker">Monthly quota</span>
          <strong>{quotaRemaining}/{monthlyLimit} CV left</strong>
          <p className="text-muted">
            Premium Local Worker keys can allocate up to {monthlyLimit} CVs per month.
          </p>
        </div>
        <div className="worker-quota-meter" aria-label={`Local Worker quota ${quotaPercent}% allocated`}>
          <span style={{ width: `${quotaPercent}%` }} />
        </div>
        <dl>
          <dt>Allocated</dt><dd>{quotaAllocated}</dd>
          <dt>Used + reserved</dt><dd>{quotaUsedReserved}</dd>
          <dt>Plan</dt><dd>{quotaSummary?.plan || 'pro'}</dd>
        </dl>
      </div>

      {createdKeyData && (
        <div className="worker-secret-box" role="status">
          <h3>Worker key created</h3>
          <p>Copy this API key now. It will not be shown again.</p>
          <code className="worker-secret-value">{createdKeyData.api_key}</code>
          <button type="button" className="btn-outline btn-sm" onClick={() => setCreatedKeyData(null)}>
            I have saved the key
          </button>
        </div>
      )}

      {canViewOwnerWorkflow && (
        <div className="owner-workflow-panel">
          <div className="owner-workflow-summary">
            <div>
              <span className="product-page-kicker">Owner workflow</span>
              <strong>{unreadOwnerCount} unread owner alerts</strong>
            </div>
            <dl>
              <dt>Role</dt><dd>{ownerPermissions?.role || '-'}</dd>
              <dt>Audit rows</dt><dd>{ownerAuditLogs.length}</dd>
              <dt>Rules</dt><dd>{ownerNotificationRules.length}</dd>
            </dl>
          </div>

          <div className="owner-workflow-grid">
            <section className="owner-workflow-section">
              <h3>Recent Notifications</h3>
              {ownerNotifications.length === 0 ? (
                <p className="text-muted">No owner notifications yet.</p>
              ) : (
                <div className="owner-workflow-list">
                  {ownerNotifications.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`owner-workflow-item ${item.is_read ? '' : 'is-unread'}`}
                      onClick={() => handleMarkOwnerNotificationRead(item.id)}
                    >
                      <span>
                        <strong>{item.title}</strong>
                        <small>{item.message}</small>
                      </span>
                      <em>{item.is_read ? 'Read' : 'New'}</em>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="owner-workflow-section">
              <h3>Audit History</h3>
              {ownerAuditLogs.length === 0 ? (
                <p className="text-muted">No audit records yet.</p>
              ) : (
                <div className="owner-workflow-list">
                  {ownerAuditLogs.map((item) => (
                    <div key={item.id} className="owner-workflow-item">
                      <span>
                        <strong>{item.event_type}</strong>
                        <small>{item.description || 'Audit event recorded'}</small>
                      </span>
                      <em>{item.created_at ? new Date(item.created_at).toLocaleDateString() : '-'}</em>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {canManageOwnerRules && (
              <section className="owner-workflow-section">
                <h3>Notification Rules</h3>
                {ownerNotificationRules.length === 0 ? (
                  <p className="text-muted">No rules available.</p>
                ) : (
                  <div className="owner-rule-list">
                    {ownerNotificationRules.map((rule) => (
                      <label key={`${rule.event_type}-${rule.channel}`} className="owner-rule-item">
                        <input
                          type="checkbox"
                          checked={Boolean(rule.is_enabled)}
                          onChange={() => handleToggleOwnerRule(rule)}
                        />
                        <span>
                          <strong>{rule.event_type}</strong>
                          <small>{rule.channel || 'in_app'}</small>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </section>
            )}

            {ownerPermissions?.permissions?.['users.view'] && (
              <section className="owner-workflow-section">
                <h3>Team Members</h3>
                {canManageOwnerUsers && (
                  <form className="owner-member-form" onSubmit={handleCreateOwnerUser}>
                    <input
                      type="email"
                      value={newMemberEmail}
                      onChange={(event) => setNewMemberEmail(event.target.value)}
                      placeholder="hr@example.com"
                      required
                    />
                    <select value={newMemberRole} onChange={(event) => setNewMemberRole(event.target.value)}>
                      {managedRoles.map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                    </select>
                    <button type="submit" className="btn-outline btn-sm">Add</button>
                  </form>
                )}
                {ownerUsers.length === 0 ? (
                  <p className="text-muted">No team members yet.</p>
                ) : (
                  <div className="owner-member-list">
                    {ownerUsers.map((member) => (
                      <div key={member.id} className="owner-member-item">
                        <span>
                          <strong>{member.email}</strong>
                          <small>{member.supabase_id?.startsWith('pending-owner-') ? 'Pending local member' : `User #${member.id}`}</small>
                        </span>
                        {canManageOwnerUsers ? (
                          <select
                            value={member.role || 'limited'}
                            onChange={(event) => handleUpdateOwnerUserRole(member.id, event.target.value)}
                          >
                            {managedRoles.map((role) => (
                              <option key={role} value={role}>{role}</option>
                            ))}
                          </select>
                        ) : (
                          <em>{member.role}</em>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {canViewCandidateActions && (
              <section className="owner-workflow-section owner-candidate-section">
                <div className="owner-section-header">
                  <h3>Candidate Controls</h3>
                  <label className="owner-inline-toggle">
                    <input
                      type="checkbox"
                      checked={showDeletedCandidates}
                      onChange={(event) => setShowDeletedCandidates(event.target.checked)}
                    />
                    Show deleted
                  </label>
                </div>
                {ownerCandidateActions.length === 0 ? (
                  <p className="text-muted">No candidate actions yet.</p>
                ) : (
                  <div className="owner-candidate-list">
                    {ownerCandidateActions.map((action) => {
                      const draft = candidateScoreDrafts[action.id] || {}
                      const assignee = assignableUsers.find((member) => member.id === action.assigned_user_id)
                      return (
                        <div key={action.id} className={`owner-candidate-item ${action.deleted_at ? 'is-muted' : ''}`}>
                          <div className="owner-candidate-main">
                            <span>
                              <strong>{action.candidate_name || `Candidate #${action.id}`}</strong>
                              <small>{action.candidate_email || 'No email'} - Job #{action.job_id}</small>
                            </span>
                            <em>{action.deleted_at ? 'Deleted' : action.anonymized_at ? 'Anonymized' : action.action || 'Active'}</em>
                          </div>

                          <div className="owner-candidate-fields">
                            <label>
                              Final
                              <input
                                type="number"
                                min="0"
                                max="100"
                                step="0.1"
                                value={draft.final_score ?? ''}
                                onChange={(event) => handleCandidateScoreDraft(action.id, 'final_score', event.target.value)}
                                disabled={!canUpdateCandidateScores || Boolean(action.deleted_at)}
                              />
                            </label>
                            <label>
                              ATS
                              <input
                                type="number"
                                min="0"
                                max="100"
                                step="0.1"
                                value={draft.ats_score ?? ''}
                                onChange={(event) => handleCandidateScoreDraft(action.id, 'ats_score', event.target.value)}
                                disabled={!canUpdateCandidateScores || Boolean(action.deleted_at)}
                              />
                            </label>
                            <label>
                              Owner
                              {canManageCandidateActions ? (
                                <select
                                  value={action.assigned_user_id || ''}
                                  onChange={(event) => handleAssignCandidateAction(action.id, event.target.value)}
                                  disabled={Boolean(action.deleted_at)}
                                >
                                  <option value="">Unassigned</option>
                                  {assignableUsers.map((member) => (
                                    <option key={member.id} value={member.id}>{member.email}</option>
                                  ))}
                                </select>
                              ) : (
                                <span className="owner-readonly-value">{assignee?.email || 'Unassigned'}</span>
                              )}
                            </label>
                          </div>

                          <div className="owner-candidate-actions">
                            {canUpdateCandidateScores && (
                              <button
                                type="button"
                                className="btn-outline btn-sm"
                                onClick={() => handleSaveCandidateScore(action)}
                                disabled={Boolean(action.deleted_at)}
                              >
                                Save score
                              </button>
                            )}
                            {canManageCandidateActions && (
                              <>
                                <button
                                  type="button"
                                  className="btn-outline btn-sm"
                                  onClick={() => handleAnonymizeCandidateAction(action.id)}
                                  disabled={Boolean(action.anonymized_at)}
                                >
                                  Anonymize
                                </button>
                                {!action.deleted_at && (
                                  <button
                                    type="button"
                                    className="btn-danger btn-sm"
                                    onClick={() => handleDeleteCandidateAction(action.id)}
                                  >
                                    Delete
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>
            )}

            {canManageRolePermissions && (
              <section className="owner-workflow-section">
                <h3>Permission Overrides</h3>
                <form className="owner-permission-form" onSubmit={handleRolePermissionSubmit}>
                  <select value={permissionRole} onChange={(event) => setPermissionRole(event.target.value)}>
                    {managedRoles.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                  <select value={permissionKey} onChange={(event) => setPermissionKey(event.target.value)}>
                    {permissionOptions.map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                  <label>
                    <input
                      type="checkbox"
                      checked={permissionAllowed}
                      onChange={(event) => setPermissionAllowed(event.target.checked)}
                    />
                    Allow
                  </label>
                  <button type="submit" className="btn-outline btn-sm">Save</button>
                </form>
                {permissionOverrides.length === 0 ? (
                  <p className="text-muted">No permission overrides yet.</p>
                ) : (
                  <div className="owner-workflow-list">
                    {permissionOverrides.slice(0, 6).map((item) => (
                      <div key={item.id} className="owner-workflow-item">
                        <span>
                          <strong>{item.role}</strong>
                          <small>{item.permission_key}</small>
                        </span>
                        <em>{item.is_allowed ? 'Allow' : 'Deny'}</em>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>
      )}

      <div className="worker-panel-grid">
        <form onSubmit={handleCreateKey} className="worker-form">
          <h3>Create New Key</h3>
          <div className="settings-field">
            <label>Key name / device</label>
            <input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Office laptop worker" required />
          </div>
          <div className="settings-field">
            <label>Restricted job</label>
            <select value={newKeyJobId} onChange={(e) => setNewKeyJobId(e.target.value)}>
              <option value="">All active jobs</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>{job.title}</option>
              ))}
            </select>
          </div>
          <div className="settings-field">
            <label>CV quota limit</label>
            <input
              type="number"
              value={newKeyQuota}
              min="1"
              max={quotaRemaining || monthlyLimit}
              onChange={(e) => setNewKeyQuota(e.target.value)}
              required
            />
            <small className={isQuotaBlocked ? 'text-danger' : 'text-muted'}>
              {isQuotaBlocked
                ? 'Monthly Local Worker quota is full. Revoke unused keys or wait for renewal.'
                : `${quotaRemaining} CV allocation remaining this month.`}
            </small>
          </div>
          <button type="submit" className="btn-primary" disabled={loading || isQuotaBlocked}>
            {loading ? 'Processing...' : 'Generate key'}
          </button>
        </form>

        <div className="worker-list">
          <h3>Worker Keys</h3>
          {loading && keys.length === 0 ? (
            <p className="text-muted">Loading keys...</p>
          ) : keys.length === 0 ? (
            <div className="empty-state compact">
              <h3>No worker keys yet</h3>
              <p>Create a key to connect a local worker.</p>
            </div>
          ) : (
            <div className="table-wrapper">
              <table className="data-table worker-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Usage</th>
                    <th>Job</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {keys.map((key) => {
                    const totalUsed = (key.quota_used || 0) + (key.quota_reserved || 0)
                    const percentUsed = key.quota_limit ? Math.min(100, Math.round((totalUsed / key.quota_limit) * 100)) : 0
                    return (
                      <tr key={key.id} className={key.revoked_at ? 'is-muted' : ''}>
                        <td>
                          <strong>{key.name}</strong>
                          <span className="worker-key-prefix">{key.key_prefix}</span>
                        </td>
                        <td>
                          <div className="worker-usage">
                            <span>{totalUsed}/{key.quota_limit}</span>
                            <div className="worker-usage-bar"><span style={{ width: `${percentUsed}%` }} /></div>
                          </div>
                        </td>
                        <td>{key.job_id ? (jobs.find((job) => job.id === key.job_id)?.title || `Job #${key.job_id}`) : 'All jobs'}</td>
                        <td>
                          <span className={`status-pill ${key.revoked_at ? 'status-pill-danger' : 'status-pill-success'}`}>
                            {key.revoked_at ? 'Revoked' : 'Active'}
                          </span>
                        </td>
                        <td>
                          {!key.revoked_at && (
                            <button type="button" className="btn-danger btn-sm" onClick={() => handleRevokeKey(key.id)}>
                              Revoke
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {jobs.length > 0 && (
        <div className="worker-progress-grid">
          {jobs.map((job) => {
            const progress = progressByJob[job.id]
            return (
              <div key={job.id} className="worker-progress-card">
                <div>
                  <strong>{job.title}</strong>
                  <span>#{job.id}</span>
                </div>
                {progress ? (
                  <dl>
                    <dt>Total</dt><dd>{progress.total ?? progress.total_cvs ?? 0}</dd>
                    <dt>Claimed</dt><dd>{progress.claimed ?? 0}</dd>
                    <dt>Processed</dt><dd>{progress.processed ?? 0}</dd>
                    <dt>Failed</dt><dd>{progress.failed ?? 0}</dd>
                    <dt>Accept</dt><dd>{progress.recommended_accept ?? 0}</dd>
                    <dt>Review</dt><dd>{progress.recommended_review ?? 0}</dd>
                    <dt>Reject</dt><dd>{progress.recommended_reject ?? 0}</dd>
                    <dt>Quota left</dt><dd>{progress.quota_remaining ?? 0}</dd>
                  </dl>
                ) : (
                  <p className="text-muted">Progress not available yet.</p>
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="worker-list worker-session-list">
        <h3>Connected Devices</h3>
        {sessions.length === 0 ? (
          <p className="text-muted">No worker sessions have connected yet.</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table worker-table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Version</th>
                  <th>Key</th>
                  <th>Last seen</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id} className={session.revoked_at ? 'is-muted' : ''}>
                    <td>{session.device_name || 'Unknown device'}</td>
                    <td>{session.worker_version || '-'}</td>
                    <td>{session.key_name || `Key #${session.worker_key_id}`}</td>
                    <td>{session.last_seen_at ? new Date(session.last_seen_at).toLocaleString() : '-'}</td>
                    <td>
                      <span className={`status-pill ${session.revoked_at || session.is_expired ? 'status-pill-danger' : 'status-pill-success'}`}>
                        {session.revoked_at ? 'Revoked' : session.is_expired ? 'Expired' : 'Active'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
