import React, { useEffect, useMemo, useState } from 'react'
import { Activity, Database, DollarSign, Mail, PlayCircle, RefreshCw, Shield, TerminalSquare } from 'lucide-react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import {
  adminOpsCost,
  adminOpsEmailTest,
  adminOpsHealth,
  adminOpsSecurity,
  adminParserRegression,
  billingAdminMe,
} from '../api'

const ADMIN_TOKEN_STORAGE_KEY = 'billing_admin_token'

function Stat({ label, value, tone = 'default' }) {
  return (
    <div className={`ops-stat ops-stat-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function EventList({ items = [], empty = 'No events yet' }) {
  if (!items.length) return <p className="text-muted">{empty}</p>
  return (
    <div className="ops-event-list">
      {items.slice(0, 10).map((item, index) => (
        <div className="ops-event-row" key={`${item.timestamp || index}-${index}`}>
          <span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : '-'}</span>
          <strong>{item.kind || item.endpoint || 'event'}</strong>
          <code>{item.status || item.severity || item.estimated_tokens || ''}</code>
        </div>
      ))}
    </div>
  )
}

export default function OpsCenterPage() {
  const { token, user } = useAuth()
  const { addToast } = useToast()

  const [adminToken, setAdminToken] = useState('')
  const [verified, setVerified] = useState(false)
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState(null)
  const [cost, setCost] = useState(null)
  const [security, setSecurity] = useState(null)
  const [parser, setParser] = useState(null)
  const [emailTo, setEmailTo] = useState(user?.email || '')
  const [emailResult, setEmailResult] = useState(null)

  useEffect(() => {
    document.title = 'Operations Center - CV Analyzer'
    try {
      localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
      const stored = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || ''
      if (stored) setAdminToken(stored)
    } catch {
      // noop
    }
  }, [])

  const canQuery = useMemo(() => !!token && !!adminToken.trim() && verified, [token, adminToken, verified])

  async function verifyAccess() {
    if (!token || !adminToken.trim()) {
      addToast('Admin token gerekli', 'error')
      return
    }
    setLoading(true)
    try {
      await billingAdminMe(token, adminToken.trim())
      setVerified(true)
      try {
        localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
        sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken.trim())
      } catch {
        // noop
      }
      addToast('Admin erisimi dogrulandi', 'success')
      await refreshAll(true)
    } catch (err) {
      setVerified(false)
      addToast(err.message || 'Admin dogrulama basarisiz', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function refreshAll(force = false) {
    if (!force && !canQuery) return
    setLoading(true)
    try {
      const [healthData, costData, securityData] = await Promise.all([
        adminOpsHealth(token, adminToken.trim()),
        adminOpsCost(token, adminToken.trim()),
        adminOpsSecurity(token, adminToken.trim()),
      ])
      setHealth(healthData)
      setCost(costData)
      setSecurity(securityData)
    } catch (err) {
      addToast(err.message || 'Operasyon verisi alinamadi', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function runParserRegression() {
    if (!canQuery) return
    setLoading(true)
    try {
      const data = await adminParserRegression(token, adminToken.trim(), {})
      setParser(data)
      addToast(data.passed ? 'Parser regression basarili' : 'Parser regression sorun buldu', data.passed ? 'success' : 'warning')
    } catch (err) {
      addToast(err.message || 'Parser testi calismadi', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function sendEmailTest(e) {
    e.preventDefault()
    if (!canQuery) return
    setLoading(true)
    try {
      const data = await adminOpsEmailTest(token, adminToken.trim(), {
        to_email: emailTo,
        subject: 'CV Analyzer delivery test',
        body: 'This is an automatic delivery test from CV Analyzer Operations Center.',
      })
      setEmailResult(data)
      addToast(data.sent ? 'Test maili gonderildi' : 'Email backend maili gonderemedi', data.sent ? 'success' : 'warning')
    } catch (err) {
      addToast(err.message || 'Mail testi basarisiz', 'error')
    } finally {
      setLoading(false)
    }
  }

  const statusTone = health?.status === 'ok' ? 'success' : 'warning'

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content ops-center-page" id="main-content">
        <div className="ops-header">
          <div>
            <span className="ops-kicker">Admin Operations</span>
            <h1>Operations Center</h1>
            <p className="text-muted">Health, AI cost, security signals, parser tests and email delivery checks.</p>
          </div>
          <button className="btn-outline" onClick={() => refreshAll()} disabled={!canQuery || loading}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        <section className="admin-card">
          <div className="admin-card-header">
            <Shield size={18} className="admin-card-icon" />
            <h2>Admin Verification</h2>
          </div>
          <div className="ops-inline-form">
            <input
              type="password"
              value={adminToken}
              onChange={(e) => {
                setAdminToken(e.target.value)
                setVerified(false)
              }}
              placeholder="Billing admin token"
            />
            <button className="btn-primary" onClick={verifyAccess} disabled={loading}>
              {loading ? <RefreshCw size={16} /> : <Shield size={16} />} Verify
            </button>
          </div>
        </section>

        {verified && (
          <>
            <section className="ops-grid">
              <div className="admin-card">
                <div className="admin-card-header">
                  <Activity size={18} className="admin-card-icon" />
                  <h2>Product Health</h2>
                </div>
                <div className="ops-stat-grid">
                  <Stat label="Status" value={health?.status || '-'} tone={statusTone} />
                  <Stat label="Ready" value={health?.ready ? 'yes' : 'no'} />
                  <Stat label="Disk" value={health?.disk_usage_percent != null ? `${health.disk_usage_percent}%` : '-'} />
                  <Stat label="Panic" value={health?.panic_mode ? 'on' : 'off'} tone={health?.panic_mode ? 'danger' : 'success'} />
                </div>
              </div>

              <div className="admin-card">
                <div className="admin-card-header">
                  <DollarSign size={18} className="admin-card-icon" />
                  <h2>AI Cost</h2>
                </div>
                <div className="ops-stat-grid">
                  <Stat label="Calls today" value={cost?.today?.calls ?? 0} />
                  <Stat label="Tokens" value={cost?.today?.estimated_tokens ?? 0} />
                  <Stat label="USD est." value={`$${cost?.today?.estimated_cost_usd ?? 0}`} tone="success" />
                  <Stat label="Optimize cap" value={cost?.pricing?.optimize_daily_cap ?? '-'} />
                </div>
              </div>

              <div className="admin-card">
                <div className="admin-card-header">
                  <Database size={18} className="admin-card-icon" />
                  <h2>Storage</h2>
                </div>
                <div className="ops-key-list">
                  {Object.entries(health?.storage || {}).map(([key, value]) => (
                    <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>
                  ))}
                </div>
              </div>

              <div className="admin-card">
                <div className="admin-card-header">
                  <Shield size={18} className="admin-card-icon" />
                  <h2>Security</h2>
                </div>
                <div className="ops-key-list">
                  {Object.entries(security?.config || {}).map(([key, value]) => (
                    <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>
                  ))}
                </div>
              </div>
            </section>

            <section className="ops-grid ops-grid-wide">
              <div className="admin-card">
                <div className="admin-card-header">
                  <TerminalSquare size={18} className="admin-card-icon" />
                  <h2>Parser Regression</h2>
                  <button className="btn-outline btn-sm" onClick={runParserRegression} disabled={loading}>
                    <PlayCircle size={14} /> Run
                  </button>
                </div>
                {parser ? (
                  <div>
                    <div className="ops-stat-grid">
                      <Stat label="Passed" value={`${parser.passed_count}/${parser.total}`} tone={parser.passed ? 'success' : 'warning'} />
                    </div>
                    <div className="ops-event-list">
                      {(parser.results || []).map((item) => (
                        <div className="ops-event-row" key={item.name}>
                          <span>{item.name}</span>
                          <strong>{item.passed ? 'passed' : 'failed'}</strong>
                          <code>{item.detected_language || '-'}</code>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : <p className="text-muted">Run the built-in parser regression pack.</p>}
              </div>

              <div className="admin-card">
                <div className="admin-card-header">
                  <Mail size={18} className="admin-card-icon" />
                  <h2>Email Delivery</h2>
                </div>
                <form className="ops-inline-form" onSubmit={sendEmailTest}>
                  <input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="test@example.com" required />
                  <button className="btn-primary" disabled={loading}><Mail size={16} /> Send Test</button>
                </form>
                {emailResult && <p className="text-muted">Backend status: {emailResult.sent ? 'sent' : 'not sent'}</p>}
              </div>
            </section>

            <section className="ops-grid ops-grid-wide">
              <div className="admin-card">
                <div className="admin-card-header">
                  <Activity size={18} className="admin-card-icon" />
                  <h2>Recent Ops Events</h2>
                </div>
                <EventList items={health?.recent_events || []} />
              </div>
              <div className="admin-card">
                <div className="admin-card-header">
                  <Shield size={18} className="admin-card-icon" />
                  <h2>Recent Security Events</h2>
                </div>
                <EventList items={security?.recent_events || []} empty="No security events recorded" />
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
