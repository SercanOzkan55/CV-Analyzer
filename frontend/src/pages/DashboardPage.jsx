import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import { useToast } from '../components/Toast'
import { createBillingPortalSession } from '../api'
import { getHistory } from '../utils/historyStorage'

export default function DashboardPage() {
  const { user, token, plan, planLoading, usageToday, dailyLimit, usageSource, canAnalyze } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const history = getHistory(user)
  const name = user?.email?.split('@')[0] || ''
  const usagePercent = dailyLimit === Infinity ? 0 : (usageToday / dailyLimit) * 100
  const showUsageSource = import.meta.env.DEV || import.meta.env.VITE_SHOW_USAGE_SOURCE === '1'

  useEffect(() => {
    document.title = `${t('nav.dashboard')} — CV Analyzer`
  }, [t])

  async function onManageBilling() {
    if (!token) return
    try {
      const session = await createBillingPortalSession(token, {
        return_url: `${window.location.origin}/dashboard`,
      })
      if (session?.mode === 'mock') {
        return
      }
      if (session?.url) {
        window.location.assign(session.url)
        return
      }
      addToast(t('toast.billing_unavailable'), 'error')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    }
  }

  function getScoreColor(score) {
    if (score >= 75) return '#22c55e'
    if (score >= 50) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        {/* Welcome Section */}
        <div className="dashboard-welcome">
          <div className="welcome-content">
            <div className="welcome-greeting">
              <span className="welcome-wave">👋</span>
              <h1>{t('dashboard.welcome')}, <span className="gradient-text">{name}</span></h1>
            </div>
            <p className="text-muted">{t('dashboard.welcome_subtitle')}</p>
          </div>
          <Link to="/analyze" className="btn-primary btn-lg">
            <span>✦</span> {t('dashboard.quick_analyze')}
          </Link>
        </div>

        {/* Stats Cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-info">
              <span className="stat-value">{history.length}</span>
              <span className="stat-label">{t('dashboard.recent_analyses')}</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">📅</div>
            <div className="stat-info">
              <span className="stat-value">{usageToday} {t('dashboard.of')} {dailyLimit === Infinity ? '∞' : dailyLimit}</span>
              <span className="stat-label">{t('dashboard.usage_today')}</span>
              {showUsageSource && <span className="stat-label">source: {usageSource}</span>}
            </div>
            <div className="stat-bar">
              <div className="stat-bar-fill" style={{ width: `${Math.min(usagePercent, 100)}%` }} />
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">⭐</div>
            <div className="stat-info">
              <span className="stat-value">{planLoading ? '...' : plan === 'admin' ? 'Admin' : plan === 'free' ? t('dashboard.free_plan') : t('dashboard.pro_plan')}</span>
              <span className="stat-label">{t('dashboard.plan')}</span>
            </div>
            {!planLoading && plan === 'free' && <Link to="/pricing" className="stat-link">{t('nav.upgrade')}</Link>}
            {!planLoading && plan !== 'free' && plan !== 'admin' && (
              <button type="button" className="btn-outline btn-sm" onClick={onManageBilling}>
                {t('pricing.manage_billing')}
              </button>
            )}
          </div>
        </div>

        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>{t('dashboard.premium_hub_title')}</h2>
            <Link to="/premium" className="link-btn">{t('dashboard.open_premium_hub')}</Link>
          </div>
          <p className="text-muted">
            {planLoading ? '...' : plan === 'free' ? t('dashboard.premium_hub_locked') : t('dashboard.premium_hub_ready')}
          </p>
        </div>

        {/* Daily Limit Warning */}
        {!planLoading && !canAnalyze() && (
          <div className="alert alert-warning">
            <span className="alert-icon">⚠️</span>
            <div>
              <strong>{t('dashboard.daily_limit_reached')}</strong>
              <p>{t('dashboard.daily_limit_desc')}</p>
            </div>
            <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade')}</Link>
          </div>
        )}

        {/* Recent Analyses */}
        <div className="card">
          <div className="card-header">
            <h2>{t('dashboard.recent_analyses')}</h2>
            {history.length > 0 && <Link to="/history" className="link-btn">{t('dashboard.view_all')}</Link>}
          </div>

          {history.length > 0 ? (
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t('history.job_title')}</th>
                    <th>{t('dashboard.score')}</th>
                    <th>{t('dashboard.date')}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item, i) => (
                    <tr key={i}>
                      <td className="td-job">{item.jobTitle || item.fileName || '-'}</td>
                      <td>
                        <span className="score-badge" style={{ color: getScoreColor(item.score) }}>
                          {Math.round(item.score)}%
                        </span>
                      </td>
                      <td className="text-muted">{new Date(item.date).toLocaleDateString()}</td>
                      <td>
                        <Link to={`/history`} className="btn-outline btn-sm">{t('dashboard.view_details')}</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📄</div>
              <h3>{t('dashboard.no_analyses')}</h3>
              <p>{t('dashboard.no_analyses_desc')}</p>
              <Link to="/analyze" className="btn-primary">{t('dashboard.start_first')}</Link>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
