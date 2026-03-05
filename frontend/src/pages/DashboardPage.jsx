import React from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem('cv-analyzer-history') || '[]')
  } catch { return [] }
}

export default function DashboardPage() {
  const { user, plan, usageToday, dailyLimit, canAnalyze } = useAuth()
  const { t } = useLanguage()
  const history = getHistory().slice(0, 5)
  const name = user?.email?.split('@')[0] || ''
  const usagePercent = dailyLimit === Infinity ? 0 : (usageToday / dailyLimit) * 100

  function getScoreColor(score) {
    if (score >= 75) return '#22c55e'
    if (score >= 50) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content">
        {/* Welcome Section */}
        <div className="dashboard-header">
          <div>
            <h1>{t('dashboard.welcome')}, <span className="text-accent">{name}</span></h1>
            <p className="text-muted">{t('dashboard.welcome_subtitle')}</p>
          </div>
          <Link to="/analyze" className="btn-primary btn-lg">{t('dashboard.quick_analyze')}</Link>
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
            </div>
            <div className="stat-bar">
              <div className="stat-bar-fill" style={{ width: `${Math.min(usagePercent, 100)}%` }} />
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">⭐</div>
            <div className="stat-info">
              <span className="stat-value">{plan === 'free' ? t('dashboard.free_plan') : t('dashboard.pro_plan')}</span>
              <span className="stat-label">{t('dashboard.plan')}</span>
            </div>
            {plan === 'free' && <Link to="/pricing" className="stat-link">{t('nav.upgrade')}</Link>}
          </div>
        </div>

        {/* Daily Limit Warning */}
        {!canAnalyze() && (
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
