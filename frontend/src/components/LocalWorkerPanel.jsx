import React, { useEffect, useState } from 'react'
import { createWorkerKey, fetchWorkerProgress, listWorkerKeys, recruiterListJobs, revokeWorkerKey } from '../api'
import { useAuth } from '../context/AuthContext'

export default function LocalWorkerPanel({ organizationId }) {
  const { token } = useAuth()
  const [keys, setKeys] = useState([])
  const [jobs, setJobs] = useState([])
  const [progressByJob, setProgressByJob] = useState({})
  const [loading, setLoading] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyJobId, setNewKeyJobId] = useState('')
  const [newKeyQuota, setNewKeyQuota] = useState(1000)
  const [createdKeyData, setCreatedKeyData] = useState(null)

  useEffect(() => {
    if (!token) return
    fetchKeys()
    fetchJobs()
  }, [token])

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
      await fetchKeys()
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
    } catch (error) {
      console.error('Error revoking worker key:', error)
      window.alert(error.message || 'Failed to revoke worker key')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card product-card worker-panel">
      <div className="worker-panel-header">
        <div>
          <span className="product-page-kicker">Local Worker</span>
          <h2>Local Worker Management</h2>
          <p className="text-muted">Generate scoped worker keys for secure local CV processing.</p>
        </div>
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
            <input type="number" value={newKeyQuota} min="1" onChange={(e) => setNewKeyQuota(e.target.value)} required />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
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
    </div>
  )
}
