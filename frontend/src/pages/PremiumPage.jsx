import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { activatePremiumTrial } from '../api'
import { getHistory } from '../utils/historyStorage'

function aggregateMissingSkills(history) {
  const counts = {}
  for (const item of history) {
    const skills = item?.result?.missing_skills || []
    for (const s of skills) {
      const key = String(s || '').trim()
      if (!key) continue
      counts[key] = (counts[key] || 0) + 1
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
}

export default function PremiumPage() {
  const { user, token, plan, planLoading, refreshUsage } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const history = getHistory(user)
  const premium = !planLoading && (plan === 'pro' || plan === 'enterprise' || plan === 'admin')

  useEffect(() => {
    document.title = `${t('nav.premium')} — CV Analyzer`
  }, [t])

  async function onActivateTrial() {
    if (!token) return
    try {
      await activatePremiumTrial(token, { plan_type: 'pro' })
      await refreshUsage()
      addToast(t('toast.premium_trial_activated'), 'success')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    }
  }

  const scored = history
    .map((x) => x?.result?.benchmark?.ahead_percent)
    .filter((x) => Number.isFinite(x))
  const avgAhead = scored.length ? (scored.reduce((a, b) => a + b, 0) / scored.length) : 0

  const atsScores = history
    .map((x) => x?.result?.ats_score)
    .filter((x) => Number.isFinite(x))
  const avgAts = atsScores.length ? (atsScores.reduce((a, b) => a + b, 0) / atsScores.length) : 0

  const topMissing = aggregateMissingSkills(history)

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <div className="dashboard-header">
          <div>
            <h1>{t('premium.title')}</h1>
            <p className="text-muted">{t('premium.subtitle')}</p>
          </div>
          {!planLoading && !premium && <Link to="/pricing" className="btn-primary btn-lg">{t('nav.upgrade')}</Link>}
        </div>

        {!planLoading && !premium && (
          <div className="alert alert-warning">
            <span className="alert-icon">🔒</span>
            <div>
              <strong>{t('premium.locked_title')}</strong>
              <p>{t('premium.locked_desc')}</p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="btn-primary btn-sm" onClick={onActivateTrial}>
                {t('premium.activate_trial')}
              </button>
              <Link to="/pricing" className="btn-outline btn-sm">{t('nav.upgrade')}</Link>
            </div>
          </div>
        )}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-info">
              <span className="stat-value">{premium ? `%${avgAhead.toFixed(1)}` : '---'}</span>
              <span className="stat-label">{t('premium.avg_ahead')}</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">🎯</div>
            <div className="stat-info">
              <span className="stat-value">{premium ? avgAts.toFixed(1) : '---'}</span>
              <span className="stat-label">{t('premium.avg_ats')}</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">🧠</div>
            <div className="stat-info">
              <span className="stat-value">{premium ? topMissing.length : '---'}</span>
              <span className="stat-label">{t('premium.active_gaps')}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>{t('premium.skill_gap_title')}</h2>
          </div>
          {premium ? (
            topMissing.length > 0 ? (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t('premium.skill')}</th>
                      <th>{t('premium.frequency')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topMissing.map(([skill, count]) => (
                      <tr key={skill}>
                        <td>{skill}</td>
                        <td>{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-muted">{t('premium.not_enough_history')}</p>
            )
          ) : (
            <p className="text-muted">{t('premium.locked_table')}</p>
          )}
        </div>
      </main>
    </div>
  )
}
