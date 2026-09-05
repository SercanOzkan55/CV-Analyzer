import React, { useEffect, useState } from 'react'
import { Activity, Check, Clipboard, Download, Laptop, Monitor, Terminal } from 'lucide-react'
import {
  anonymizeOwnerCandidateAction,
  assignOwnerCandidateAction,
  createOwnerCandidateComment,
  createOwnerUser,
  deleteOwnerCandidateAction,
  downloadWorkerExecutable,
  downloadWorkerLinux,
  downloadWorkerMacos,
  fetchOwnerCandidateComments,
  fetchOwnerCandidateActions,
  fetchOwnerAuditLogs,
  fetchOwnerNotificationRules,
  fetchOwnerNotifications,
  fetchOwnerPermissions,
  fetchOwnerRolePermissions,
  fetchOwnerUsers,
  fetchWorkerProgress,
  markOwnerNotificationRead,
  recruiterListJobs,
  updateOwnerCandidateScore,
  updateOwnerNotificationRule,
  updateOwnerRolePermission,
  updateOwnerUserRole,
} from '../api'
import { useAuth } from '../context/AuthContext'

export default function LocalWorkerPanel() {
  const { token } = useAuth()
  const [jobs, setJobs] = useState([])
  const [progressByJob, setProgressByJob] = useState({})
  const [ownerPermissions, setOwnerPermissions] = useState(null)
  const [ownerNotifications, setOwnerNotifications] = useState([])
  const [ownerAuditLogs, setOwnerAuditLogs] = useState([])
  const [ownerNotificationRules, setOwnerNotificationRules] = useState([])
  const [ownerUsers, setOwnerUsers] = useState([])
  const [ownerRolePermissions, setOwnerRolePermissions] = useState(null)
  const [ownerCandidateActions, setOwnerCandidateActions] = useState([])
  const [candidateScoreDrafts, setCandidateScoreDrafts] = useState({})
  const [candidateCommentDrafts, setCandidateCommentDrafts] = useState({})
  const [expandedCandidateComments, setExpandedCandidateComments] = useState({})
  const [candidateCommentsByAction, setCandidateCommentsByAction] = useState({})
  const [candidateCommentsLoading, setCandidateCommentsLoading] = useState({})
  const [showDeletedCandidates, setShowDeletedCandidates] = useState(false)
  const [downloadingPlatform, setDownloadingPlatform] = useState(null)
  const [copiedPlatform, setCopiedPlatform] = useState(null)
  const [newMemberEmail, setNewMemberEmail] = useState('')
  const [newMemberRole, setNewMemberRole] = useState('hr')
  const [permissionRole, setPermissionRole] = useState('hr')
  const [permissionKey, setPermissionKey] = useState('candidates.view')
  const [permissionAllowed, setPermissionAllowed] = useState(true)

  useEffect(() => {
    if (!token) return
    fetchJobs()
    fetchOwnerWorkflow()
  }, [token, showDeletedCandidates])

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
      setCandidateCommentDrafts((current) => (
        Object.fromEntries((candidateActions.items || []).map((item) => [item.id, current[item.id] || '']))
      ))
      setExpandedCandidateComments((current) => (
        Object.fromEntries((candidateActions.items || []).map((item) => [item.id, Boolean(current[item.id])]))
      ))
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
      setCandidateCommentDrafts({})
      setExpandedCandidateComments({})
      setCandidateCommentsByAction({})
      setCandidateCommentsLoading({})
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

  async function handleCreateCandidateComment(event, actionId) {
    event.preventDefault()
    const body = String(candidateCommentDrafts[actionId] || '').trim()
    if (!body) return
    try {
      await createOwnerCandidateComment(token, actionId, { body })
      setCandidateCommentDrafts((current) => ({ ...current, [actionId]: '' }))
      if (expandedCandidateComments[actionId]) {
        await loadCandidateComments(actionId)
      }
      await fetchOwnerWorkflow()
    } catch (error) {
      console.warn('Could not add candidate comment', error)
      window.alert(error.message || 'Failed to add candidate comment')
    }
  }

  async function loadCandidateComments(actionId) {
    try {
      setCandidateCommentsLoading((current) => ({ ...current, [actionId]: true }))
      const data = await fetchOwnerCandidateComments(token, actionId, { limit: 50 })
      setCandidateCommentsByAction((current) => ({
        ...current,
        [actionId]: data.items || [],
      }))
    } catch (error) {
      console.warn('Could not load candidate comments', error)
      window.alert(error.message || 'Failed to load comments')
    } finally {
      setCandidateCommentsLoading((current) => ({ ...current, [actionId]: false }))
    }
  }

  async function handleToggleCandidateComments(actionId) {
    const willExpand = !expandedCandidateComments[actionId]
    setExpandedCandidateComments((current) => ({ ...current, [actionId]: willExpand }))
    if (willExpand && !candidateCommentsByAction[actionId]) {
      await loadCandidateComments(actionId)
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

  const WORKER_DOWNLOADS = [
    {
      platform: 'windows',
      label: 'Windows',
      detail: '.exe -- Windows 10/11 (64-bit)',
      icon: Monitor,
      fetcher: downloadWorkerExecutable,
      filename: 'CV Analyzer Local Worker.exe',
    },
    {
      platform: 'macos',
      label: 'macOS',
      detail: '.zip -- Apple Silicon & Intel',
      icon: Laptop,
      fetcher: downloadWorkerMacos,
      filename: 'CV Analyzer Local Worker-macOS.zip',
    },
    {
      platform: 'linux',
      label: 'Linux',
      detail: 'binary -- most x86_64 distros',
      icon: Terminal,
      fetcher: downloadWorkerLinux,
      filename: 'CV Analyzer Local Worker-linux',
    },
  ]

  const WORKER_RUN_GUIDE = [
    {
      platform: 'windows',
      label: 'Windows',
      icon: Monitor,
      steps: [
        'Double-click the downloaded .exe -- no installation or terminal step needed.',
        'If SmartScreen warns you, click "More info" then "Run anyway" (the app isn\'t code-signed yet).',
      ],
      command: null,
    },
    {
      platform: 'macos',
      label: 'macOS',
      icon: Laptop,
      steps: [
        'Unzip the download, then run these from Terminal in that folder -- the app is unsigned, so macOS blocks it until the quarantine flag is cleared:',
      ],
      command: 'unzip "CV Analyzer Local Worker-macOS.zip"\nxattr -cr "CV Analyzer Local Worker.app"\nopen "CV Analyzer Local Worker.app"',
    },
    {
      platform: 'linux',
      label: 'Linux',
      icon: Terminal,
      steps: ['Make the binary executable, then run it from Terminal:'],
      command: 'chmod +x "CV Analyzer Local Worker"\n./"CV Analyzer Local Worker"',
    },
  ]

  async function handleCopyCommand(platform, command) {
    try {
      await navigator.clipboard.writeText(command)
      setCopiedPlatform(platform)
      setTimeout(() => setCopiedPlatform(null), 2000)
    } catch (error) {
      console.error('Error copying command:', error)
    }
  }

  async function handleDownloadWorker(entry) {
    try {
      setDownloadingPlatform(entry.platform)
      const blob = await entry.fetcher(token)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = entry.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Error downloading worker app:', error)
      window.alert(error.message || 'Failed to download worker app')
    } finally {
      setDownloadingPlatform(null)
    }
  }

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
  const canCreateCandidateComments = Boolean(ownerPermissions?.permissions?.['candidate_comments.create'])
  const unreadOwnerCount = ownerNotifications.filter((item) => !item.is_read).length
  const managedRoles = ownerRolePermissions?.roles || ['owner', 'recruiter', 'hr', 'limited']
  const permissionOptions = Object.entries(ownerRolePermissions?.permissions || ownerPermissions?.available_permissions || {})
  const permissionOverrides = ownerRolePermissions?.overrides || []
  const assignableUsers = ownerUsers.filter((member) => !member.deleted_at)

  return (
    <div className="worker-panel worker-workspace">
      <section className="worker-command-hero">
        <div className="worker-hero-copy">
          <img src="/local-worker-logo.png" alt="" className="worker-hero-logo" width={56} height={56} />
          <span className="product-page-kicker">Local Worker</span>
          <h2>Local Worker</h2>
          <p>
            Run CV processing on your own machine and keep sensitive files local -- no account key or quota required.
          </p>
        </div>
        <div className="worker-download-grid">
          {WORKER_DOWNLOADS.map((entry) => {
            const Icon = entry.icon
            const isDownloading = downloadingPlatform === entry.platform
            return (
              <button
                key={entry.platform}
                type="button"
                className="worker-download-card"
                onClick={() => handleDownloadWorker(entry)}
                disabled={Boolean(downloadingPlatform) || !token}
              >
                <span className="worker-download-icon">
                  <Icon size={22} />
                </span>
                <span className="worker-download-copy">
                  <strong>{entry.label}</strong>
                  <small>{isDownloading ? 'Preparing download...' : entry.detail}</small>
                </span>
                <span className="worker-download-meta">
                  <Download size={14} />
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="worker-guide-panel">
        <div className="worker-guide-intro">
          <span className="product-page-kicker">How it works</span>
          <p>
            Local Worker scores every CV against your job description across 12 criteria --
            skills, experience, education, language, ATS formatting and more -- entirely on
            your own machine. No CV ever leaves your computer. It can process a whole folder
            at once, and if you connect your own SMTP account in Settings, it can send
            accept/reject emails that you review and confirm before anything goes out.
          </p>
        </div>
        <div className="worker-guide-steps">
          {WORKER_RUN_GUIDE.map((entry) => {
            const Icon = entry.icon
            const isCopied = copiedPlatform === entry.platform
            return (
              <div key={entry.platform} className="worker-guide-step">
                <div className="worker-guide-step-header">
                  <Icon size={16} />
                  <strong>{entry.label}</strong>
                </div>
                {entry.steps.map((step, i) => (
                  <p key={i} className="worker-guide-step-text">{step}</p>
                ))}
                {entry.command && (
                  <div className="worker-code-block">
                    <pre><code>{entry.command}</code></pre>
                    <button
                      type="button"
                      className="worker-code-copy"
                      onClick={() => handleCopyCommand(entry.platform, entry.command)}
                      aria-label={`Copy ${entry.label} command`}
                    >
                      {isCopied ? <Check size={14} /> : <Clipboard size={14} />}
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

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

                          <div className="owner-candidate-comments">
                            <div className="owner-comment-summary">
                              <span>
                                <strong>{action.comment_count || 0} comments</strong>
                                {action.latest_comment ? (
                                  <small>
                                    {action.latest_comment.author_email || 'Team'}: {action.latest_comment.body}
                                  </small>
                                ) : (
                                  <small>No comments yet.</small>
                                )}
                              </span>
                              {Number(action.comment_count || 0) > 0 && (
                                <button
                                  type="button"
                                  className="btn-outline btn-sm"
                                  onClick={() => handleToggleCandidateComments(action.id)}
                                  disabled={Boolean(candidateCommentsLoading[action.id])}
                                >
                                  {expandedCandidateComments[action.id] ? 'Hide history' : 'View history'}
                                </button>
                              )}
                            </div>
                            {expandedCandidateComments[action.id] && (
                              <div className="owner-comment-history">
                                {candidateCommentsLoading[action.id] ? (
                                  <small>Loading comments...</small>
                                ) : (candidateCommentsByAction[action.id] || []).length === 0 ? (
                                  <small>No comments loaded.</small>
                                ) : (
                                  (candidateCommentsByAction[action.id] || []).map((comment) => (
                                    <article key={comment.id} className="owner-comment-row">
                                      <div>
                                        <strong>{comment.author_email || 'Team'}</strong>
                                        <time dateTime={comment.created_at || undefined}>
                                          {comment.created_at ? new Date(comment.created_at).toLocaleString() : '-'}
                                        </time>
                                      </div>
                                      <p>{comment.body}</p>
                                    </article>
                                  ))
                                )}
                              </div>
                            )}
                            {canCreateCandidateComments && !action.deleted_at && (
                              <form onSubmit={(event) => handleCreateCandidateComment(event, action.id)}>
                                <input
                                  value={candidateCommentDrafts[action.id] || ''}
                                  onChange={(event) => setCandidateCommentDrafts((current) => ({
                                    ...current,
                                    [action.id]: event.target.value,
                                  }))}
                                  maxLength={2000}
                                  placeholder="Add comment"
                                />
                                <button type="submit" className="btn-outline btn-sm">Comment</button>
                              </form>
                            )}
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

      {jobs.length > 0 && (
        <section className="worker-progress-section">
          <div className="worker-section-heading">
            <span className="worker-section-icon" aria-hidden="true"><Activity size={16} /></span>
            <span>
              <h3>Job Processing Progress</h3>
              <small>Local worker throughput by active job.</small>
            </span>
          </div>
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
                    </dl>
                  ) : (
                    <p className="text-muted">Progress not available yet.</p>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
