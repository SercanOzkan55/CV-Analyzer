import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { activatePremiumTrial, fetchGlobalBenchmark, fetchProfessionBenchmarks } from '../api'
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

  const [globalStats, setGlobalStats] = useState(null)
  const [professions, setProfessions] = useState([])

  useEffect(() => {
    document.title = `${t('nav.premium')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    fetchGlobalBenchmark().then(setGlobalStats).catch(() => {})
    fetchProfessionBenchmarks().then(d => setProfessions(d?.professions || [])).catch(() => {})
  }, [])

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

  const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }
  const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.1 } } }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div
          className="dashboard-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div>
            <h1>{t('premium.title')}</h1>
            <p className="text-muted">{t('premium.subtitle')}</p>
          </div>
          {!planLoading && !premium && (
            <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
              <Link to="/pricing" className="btn-primary btn-lg">{t('nav.upgrade')}</Link>
            </motion.div>
          )}
        </motion.div>

        <AnimatePresence>
          {!planLoading && !premium && (
            <motion.div
              className="alert alert-warning"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.35 }}
            >
              <span className="alert-icon">🔒</span>
              <div>
                <strong>{t('premium.locked_title')}</strong>
                <p>{t('premium.locked_desc')}</p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <motion.button
                  type="button"
                  className="btn-primary btn-sm"
                  onClick={onActivateTrial}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {t('premium.activate_trial')}
                </motion.button>
                <Link to="/pricing" className="btn-outline btn-sm">{t('nav.upgrade')}</Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div
          className="stats-grid"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          style={!premium ? { position: 'relative' } : undefined}
        >
          {!premium && (
            <div className="premium-blur-overlay" style={{ borderRadius: 12 }}>
              <div className="premium-blur-lock">
                <span style={{ fontSize: '2rem' }}>🔒</span>
                <p style={{ fontWeight: 600, margin: '8px 0 4px' }}>{t('premium.locked_title') || 'Premium İçerik'}</p>
                <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade') || 'Planı Yükselt'}</Link>
              </div>
            </div>
          )}
          <div style={!premium ? { filter: 'blur(6px)', pointerEvents: 'none', userSelect: 'none', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' } : { display: 'contents' }}>
          {[
            { icon: '📈', value: `%${avgAhead.toFixed(1)}`, label: t('premium.avg_ahead') },
            { icon: '🎯', value: avgAts.toFixed(1), label: t('premium.avg_ats') },
            { icon: '🧠', value: topMissing.length, label: t('premium.active_gaps') },
            { icon: '🌍', value: globalStats?.total_cvs ? globalStats.total_cvs.toLocaleString() : '0', label: t('benchmark.total_analyzed') || 'Total CVs Analyzed' },
          ].map((s, i) => (
            <motion.div
              key={i}
              className="stat-card"
              variants={fadeUp}
              whileHover={{ y: -2, transition: { duration: 0.15 } }}
            >
              <div className="stat-icon">{s.icon}</div>
              <div className="stat-info">
                <span className="stat-value">{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            </motion.div>
          ))}
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.45, delay: 0.15 }}
          style={{ position: 'relative' }}
        >
          <div className="card-header">
            <h2>{t('premium.skill_gap_title')}</h2>
          </div>
          <div style={{ position: 'relative' }}>
            {!premium && (
              <div className="premium-blur-overlay">
                <div className="premium-blur-lock">
                  <span style={{ fontSize: '2rem' }}>🔒</span>
                  <p style={{ fontWeight: 600, margin: '8px 0 4px' }}>{t('premium.locked_title') || 'Premium İçerik'}</p>
                  <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade') || 'Planı Yükselt'}</Link>
                </div>
              </div>
            )}
            <div style={!premium ? { filter: 'blur(6px)', pointerEvents: 'none', userSelect: 'none' } : undefined}>
              {topMissing.length > 0 ? (
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
              )}
            </div>
          </div>
        </motion.div>

        {/* ── Profession Benchmarks ──────────────────────── */}
        {professions.length > 0 && (
          <motion.div
            className="card"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.2 }}
            style={{ position: 'relative' }}
          >
            <div className="card-header">
              <h2>🌍 {t('benchmark.profession_title') || 'Profession Benchmarks'}</h2>
            </div>
            <div style={{ position: 'relative' }}>
              {!premium && (
                <div className="premium-blur-overlay">
                  <div className="premium-blur-lock">
                    <span style={{ fontSize: '2rem' }}>🔒</span>
                    <p style={{ fontWeight: 600, margin: '8px 0 4px' }}>{t('premium.locked_title') || 'Premium İçerik'}</p>
                    <p style={{ fontSize: '0.85rem', opacity: 0.8, marginBottom: 12 }}>{t('premium.locked_desc') || 'Bu bölümü görmek için Pro plana geçin.'}</p>
                    <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade') || 'Planı Yükselt'}</Link>
                  </div>
                </div>
              )}
              <div style={!premium ? { filter: 'blur(6px)', pointerEvents: 'none', userSelect: 'none' } : undefined}>
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t('benchmark.profession') || 'Profession'}</th>
                        <th>{t('benchmark.total') || 'CVs'}</th>
                        <th>{t('benchmark.avg_score') || 'Avg ATS'}</th>
                        <th>{t('benchmark.median') || 'Median'}</th>
                        <th>{t('benchmark.top_10') || 'Top 10%'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {professions.map((p) => (
                        <tr key={p.profession}>
                          <td style={{ fontWeight: 600 }}>{p.display_name}</td>
                          <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.total_cvs}</td>
                          <td style={{ fontFamily: "'JetBrains Mono', monospace", color: p.avg >= 70 ? '#22c55e' : p.avg >= 50 ? '#eab308' : '#ef4444' }}>
                            {p.avg.toFixed(1)}
                          </td>
                          <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.median.toFixed(1)}</td>
                          <td style={{ fontFamily: "'JetBrains Mono', monospace", color: '#a78bfa' }}>{p.top_10_percent.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {globalStats?.total_cvs > 0 && (
                  <p className="text-muted" style={{ marginTop: 12, fontSize: '0.8rem', textAlign: 'center' }}>
                    {t('benchmark.based_on') || 'Based on'} {globalStats.total_cvs.toLocaleString()} {t('benchmark.cvs_analyzed') || 'CVs analyzed globally'}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  )
}
