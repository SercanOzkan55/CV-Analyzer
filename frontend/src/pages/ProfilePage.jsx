import React, { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Shield, BarChart2, Calendar, Crown, FileText, TrendingUp } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import { getHistory } from '../utils/historyStorage'

const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
}

export default function ProfilePage() {
  const { user, plan, planLoading, usageToday, dailyLimit, role } = useAuth()
  const { t } = useLanguage()
  const history = getHistory(user)
  const name = user?.user_metadata?.full_name || user?.email?.split('@')[0] || ''
  const memberSince = user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'

  const bestScore = useMemo(
    () => (history.length ? Math.max(...history.map((h) => h.score || 0)) : 0),
    [history]
  )
  const avgScore = useMemo(
    () => history.length ? Math.round(history.reduce((s, h) => s + (h.score || 0), 0) / history.length) : 0,
    [history]
  )

  useEffect(() => {
    document.title = `${t('profile.title')} — CV Analyzer`
  }, [t])

  const planLabel = planLoading ? '...'
    : plan === 'admin' ? 'Admin'
    : plan === 'free' ? t('dashboard.free_plan')
    : t('dashboard.pro_plan')

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div
          className="profile-hero"
          initial={{ opacity: 0, y: -18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="profile-avatar">
            <User size={40} strokeWidth={1.5} />
          </div>
          <h1 className="gradient-text">{name}</h1>
          <p className="text-muted">{user?.email}</p>
          <div className="profile-badges">
            <span className={`glow-badge ${plan === 'free' ? 'glow-badge-accent' : 'glow-badge-gold'}`}>
              {planLabel}
            </span>
            {role !== 'individual' && (
              <span className="glow-badge glow-badge-success">{role}</span>
            )}
          </div>
        </motion.div>

        <motion.div
          className="profile-stats-grid"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.08 } } }}
        >
          <motion.div className="profile-stat-card" variants={itemVariants}>
            <BarChart2 size={20} style={{ color: 'var(--color-accent)' }} />
            <div className="profile-stat-body">
              <span className="profile-stat-value">{history.length}</span>
              <span className="profile-stat-label">{t('profile.total_analyses')}</span>
            </div>
          </motion.div>

          <motion.div className="profile-stat-card" variants={itemVariants}>
            <TrendingUp size={20} style={{ color: 'var(--status-accent)' }} />
            <div className="profile-stat-body">
              <span className="profile-stat-value">{bestScore > 0 ? `${Math.round(bestScore)}%` : '—'}</span>
              <span className="profile-stat-label">{t('profile.best_score')}</span>
            </div>
          </motion.div>

          <motion.div className="profile-stat-card" variants={itemVariants}>
            <FileText size={20} style={{ color: 'var(--status-success)' }} />
            <div className="profile-stat-body">
              <span className="profile-stat-value">{avgScore > 0 ? `${avgScore}%` : '—'}</span>
              <span className="profile-stat-label">{t('profile.avg_score')}</span>
            </div>
          </motion.div>

          <motion.div className="profile-stat-card" variants={itemVariants}>
            <Calendar size={20} style={{ color: 'var(--color-accent-pink)' }} />
            <div className="profile-stat-body">
              <span className="profile-stat-value">{memberSince}</span>
              <span className="profile-stat-label">{t('profile.member_since')}</span>
            </div>
          </motion.div>
        </motion.div>

        <div className="profile-details-grid">
          <motion.div
            className="card product-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <h2>{t('profile.account_info')}</h2>
            <div className="profile-info-row">
              <Mail size={16} />
              <span className="profile-info-label">{t('settings.email')}</span>
              <span className="profile-info-value">{user?.email || '—'}</span>
            </div>
            <div className="profile-info-row">
              <Crown size={16} />
              <span className="profile-info-label">{t('dashboard.plan')}</span>
              <span className="profile-info-value">{planLabel}</span>
            </div>
            <div className="profile-info-row">
              <Shield size={16} />
              <span className="profile-info-label">{t('profile.role')}</span>
              <span className="profile-info-value" style={{ textTransform: 'capitalize' }}>{role}</span>
            </div>
            <div className="profile-info-row">
              <BarChart2 size={16} />
              <span className="profile-info-label">{t('dashboard.usage_today')}</span>
              <span className="profile-info-value">{usageToday} / {dailyLimit === Infinity ? '∞' : dailyLimit}</span>
            </div>
          </motion.div>

          <motion.div
            className="card product-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            <h2>{t('profile.quick_actions')}</h2>
            <div className="profile-actions">
              <Link to="/settings" className="btn-outline">{t('nav.settings')}</Link>
              <Link to="/analyze" className="btn-primary">{t('dashboard.quick_analyze')}</Link>
              {plan === 'free' && <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade')}</Link>}
            </div>
            {bestScore > 0 && (
              <div className="profile-best-score">
                <ScoreCircle score={Math.round(bestScore)} size={80} label="Best" />
              </div>
            )}
          </motion.div>
        </div>
      </main>
    </div>
  )
}
