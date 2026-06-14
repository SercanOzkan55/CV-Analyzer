import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart2, Calendar, Crown, TrendingUp, Zap, ArrowRight,
  Clock, FileText, Briefcase, Activity, ChevronRight,
  Award, History, Rocket, Star, Lightbulb,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import { useToast } from '../components/Toast'
import { createBillingPortalSession, fetchAnalysisTrends } from '../api'
import { getHistory } from '../utils/historyStorage'
import useAnimatedCounter from '../hooks/useAnimatedCounter'
import { getScoreColor } from '../utils/scoreColors'
import OnboardingModal from '../components/OnboardingModal'
import QuotaWarningBanner from '../components/QuotaWarningBanner'
import UsageChart from '../components/UsageChart'
import FavoritesList from '../components/FavoritesList'
import StreakBadge from '../components/StreakBadge'
import InsightsPanel from '../components/InsightsPanel'

// ─── Animation Variants ─────────────────────────────────────────
const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.42, ease: [0.4, 0, 0.2, 1] } },
}

const scaleVariants = {
  hidden: { opacity: 0, scale: 0.93 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.38, ease: [0.34, 1.56, 0.64, 1] } },
}

// ─── Stat Card ──────────────────────────────────────────────────
function DBStatCard({ icon: Icon, iconColor, value, label, progress, children }) {
  const animatedValue = useAnimatedCounter(typeof value === 'number' ? value : 0, 1000)
  const displayValue = typeof value === 'number' ? animatedValue : value

  return (
    <motion.div
      className="db-stat-card"
      variants={itemVariants}
      whileHover={{ y: -5, rotateX: -2, rotateY: 1.5, transition: { duration: 0.18, ease: 'easeOut' } }}
    >
      <div className="db-stat-icon-wrap" style={{ '--icon-color': iconColor }}>
        <Icon size={20} strokeWidth={1.8} style={{ color: iconColor }} />
      </div>
      <div className="db-stat-body">
        <span className="db-stat-value" style={{ color: iconColor }}>
          {displayValue}
        </span>
        <span className="db-stat-label">{label}</span>
      </div>
      {progress !== undefined && (
        <div className="db-stat-progress-bar">
          <motion.div
            className="db-stat-progress-fill"
            style={{ background: iconColor }}
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(progress, 100)}%` }}
            transition={{ duration: 1.3, delay: 0.4, ease: [0.25, 0.8, 0.25, 1] }}
          />
        </div>
      )}
      {children}
    </motion.div>
  )
}

// ─── Analysis Card ──────────────────────────────────────────────
function AnalysisCard({ item }) {
  const scoreColor = getScoreColor(item.score)

  return (
    <motion.div
      className="db-analysis-card"
      variants={itemVariants}
      whileHover={{ x: 4, transition: { duration: 0.2 } }}
    >
      <div className="db-analysis-score">
        <ScoreCircle score={Math.round(item.score)} size={50} />
      </div>
      <div className="db-analysis-info">
        <span className="db-analysis-title">
          {item.jobTitle || item.fileName || 'İsimsiz Analiz'}
        </span>
        <span className="db-analysis-date">
          <Clock size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
          {new Date(item.date).toLocaleDateString()}
        </span>
      </div>
      <div className="db-analysis-right">
        <span
          className="db-analysis-badge"
          style={{
            color: scoreColor,
            borderColor: `${scoreColor}35`,
            background: `${scoreColor}12`,
          }}
        >
          {Math.round(item.score)}%
        </span>
        <Link to="/history" className="db-analysis-link">
          <ChevronRight size={14} />
        </Link>
      </div>
    </motion.div>
  )
}

// ─── Quick Action Card ──────────────────────────────────────────
function QuickActionCard({ icon: Icon, iconColor, title, desc, to }) {
  return (
    <motion.div variants={scaleVariants} whileHover={{ scale: 1.02, rotateY: 1.8, transition: { duration: 0.2 } }}>
      <Link to={to} className="db-action-card" style={{ '--action-color': iconColor }}>
        <div className="db-action-icon">
          <Icon size={18} strokeWidth={1.8} style={{ color: iconColor }} />
        </div>
        <div className="db-action-text">
          <span className="db-action-title">{title}</span>
          <span className="db-action-desc">{desc}</span>
        </div>
        <ArrowRight size={14} className="db-action-arrow" />
      </Link>
    </motion.div>
  )
}

// ─── Score Trend Chart (SVG) ────────────────────────────────
function ScoreTrendChart({ history }) {
  const data = [...history].reverse().slice(-10)
  const W = 500, H = 260, PX = 44, PY = 28, PB = 40

  // Dynamic Y-axis range based on actual scores
  const scores = data.map(item => item.score || 0)
  const rawMin = Math.min(...scores)
  const rawMax = Math.max(...scores)
  const padding = Math.max((rawMax - rawMin) * 0.2, 8)
  const minS = Math.max(0, Math.floor((rawMin - padding) / 5) * 5)
  const maxS = Math.min(100, Math.ceil((rawMax + padding) / 5) * 5)
  const rangeY = maxS - minS || 1

  // Generate nice Y-axis ticks
  const step = rangeY <= 20 ? 5 : rangeY <= 50 ? 10 : 25
  const yTicks = []
  for (let v = minS; v <= maxS; v += step) yTicks.push(v)
  if (yTicks[yTicks.length - 1] < maxS) yTicks.push(maxS)

  const chartH = H - PY - PB

  const points = data.map((item, i) => {
    const x = PX + (i / Math.max(data.length - 1, 1)) * (W - PX * 2)
    const y = PY + (1 - ((item.score || 0) - minS) / rangeY) * chartH
    return { x, y, score: Math.round(item.score || 0), date: new Date(item.date).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' }) }
  })

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  const areaPath = linePath + ` L${points[points.length - 1].x},${PY + chartH} L${points[0].x},${PY + chartH} Z`

  // Smooth curve (catmull-rom)
  function catmullRom(pts) {
    if (pts.length < 2) return ''
    if (pts.length === 2) return `M${pts[0].x},${pts[0].y} L${pts[1].x},${pts[1].y}`
    let d = `M${pts[0].x},${pts[0].y}`
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)]
      const p1 = pts[i]
      const p2 = pts[Math.min(pts.length - 1, i + 1)]
      const p3 = pts[Math.min(pts.length - 1, i + 2)]
      const cp1x = p1.x + (p2.x - p0.x) / 6
      const cp1y = p1.y + (p2.y - p0.y) / 6
      const cp2x = p2.x - (p3.x - p1.x) / 6
      const cp2y = p2.y - (p3.y - p1.y) / 6
      d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`
    }
    return d
  }

  const curvePath = catmullRom(points)
  const curveAreaPath = curvePath + ` L${points[points.length - 1].x},${PY + chartH} L${points[0].x},${PY + chartH} Z`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="db-trend-svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.02" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {yTicks.map((v) => {
        const y = PY + (1 - (v - minS) / rangeY) * chartH
        return (
          <g key={v}>
            <line x1={PX} y1={y} x2={W - PX} y2={y} stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray={v === minS || v === maxS ? 'none' : '3,3'} />
            <text x={PX - 8} y={y + 3} textAnchor="end" fontSize="9" fill="var(--color-text-muted)">{v}</text>
          </g>
        )
      })}
      <path d={curveAreaPath} fill="url(#trendGrad)" />
      <path d={curvePath} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" filter="url(#glow)" />
      {points.map((p, i) => (
        <g key={i} className="db-trend-point">
          <circle cx={p.x} cy={p.y} r="5" fill="var(--color-accent)" stroke="var(--color-card)" strokeWidth="2.5" />
          <text x={p.x} y={p.y - 10} textAnchor="middle" fontSize="8.5" fontWeight="600" fill="var(--color-accent)">{p.score}</text>
          <title>{p.date}: {p.score}%</title>
        </g>
      ))}
      {/* X-axis date labels */}
      {points.map((p, i) => (
        (data.length <= 6 || i % Math.ceil(data.length / 6) === 0 || i === data.length - 1) && (
          <text key={`d${i}`} x={p.x} y={H - 8} textAnchor="middle" fontSize="8" fill="var(--color-text-muted)">{p.date}</text>
        )
      ))}
    </svg>
  )
}

// ─── Main Dashboard ─────────────────────────────────────────────
export default function DashboardPage() {
  const { user, token, plan, planLoading, usageToday, dailyLimit, usageSource, canAnalyze } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const history = getHistory(user)
  const [remoteTrends, setRemoteTrends] = useState([])
  const [trendLoading, setTrendLoading] = useState(false)
  const name = user?.email?.split('@')[0] || ''
  const usagePercent = dailyLimit === Infinity ? 0 : (usageToday / dailyLimit) * 100
  const showUsageSource = import.meta.env.DEV || import.meta.env.VITE_SHOW_USAGE_SOURCE === '1'

  const bestScore = useMemo(
    () => (history.length ? Math.max(...history.map((h) => h.score || 0)) : 0),
    [history]
  )

  useEffect(() => {
    document.title = `${t('nav.dashboard')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    let cancelled = false
    if (!token) {
      setRemoteTrends([])
      return undefined
    }

    setTrendLoading(true)
    fetchAnalysisTrends(token, 90)
      .then((data) => {
        if (cancelled) return
        const rows = Array.isArray(data?.days) ? data.days : []
        setRemoteTrends(rows.map((row) => ({
          date: row.date,
          score: Number(row.average_score || 0),
          bestScore: Number(row.best_score || 0),
          count: Number(row.count || 0),
        })))
      })
      .catch(() => {
        if (!cancelled) setRemoteTrends([])
      })
      .finally(() => {
        if (!cancelled) setTrendLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [token])

  const trendHistory = remoteTrends.length >= 2 ? remoteTrends : history

  async function onManageBilling() {
    if (!token) return
    try {
      const session = await createBillingPortalSession(token, {
        return_url: `${window.location.origin}/dashboard`,
      })
      if (session?.mode === 'mock') return
      if (session?.url) { window.location.assign(session.url); return }
      addToast(t('toast.billing_unavailable'), 'error')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    }
  }

  const planLabel = planLoading
    ? '...'
    : plan === 'admin' ? 'Admin'
    : plan === 'free' ? t('dashboard.free_plan')
    : t('dashboard.pro_plan')

  const quickActions = [
    {
      icon: Zap,
      iconColor: 'var(--color-accent)',
      title: t('dashboard.quick_analyze'),
      desc: "CV'nizi hemen analiz edin",
      to: '/analyze',
    },
    {
      icon: History,
      iconColor: 'var(--status-accent)',
      title: t('nav.history'),
      desc: 'Geçmiş analizleri görün',
      to: '/history',
    },
    {
      icon: Briefcase,
      iconColor: 'var(--status-success)',
      title: 'Career Studio',
      desc: 'Kariyer hedeflerinizi planlayın',
      to: '/career-studio',
    },
    {
      icon: FileText,
      iconColor: 'var(--color-accent-pink)',
      title: 'CV Oluştur',
      desc: 'Profesyonel CV hazırlayın',
      to: '/cv-builder',
    },
  ]

  return (
    <div className="app-layout">
      <Navbar />
      <OnboardingModal />
      <main className="main-content" id="main-content">

        {/* ── Hero Welcome ──────────────────────────────── */}
        <motion.div
          className="db-hero"
          initial={{ opacity: 0, y: -18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="db-hero-orb db-hero-orb-1" />
          <div className="db-hero-orb db-hero-orb-2" />
          <div className="db-hero-orb db-hero-orb-3" />
          <div className="db-hero-inner">
            <div className="db-hero-left">
              <motion.div
                className="db-hero-badges"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2, duration: 0.4 }}
              >
                <span className={`glow-badge ${plan === 'free' ? 'glow-badge-accent' : 'glow-badge-gold'}`}>
                  {plan === 'free' ? '🆓 ' : '⭐ '}{planLabel}
                </span>
                {history.length > 0 && (
                  <span className="glow-badge glow-badge-success">
                    🎯 {history.length} {t('dashboard.recent_analyses')}
                  </span>
                )}
              </motion.div>

              <div className="db-hero-greeting">
                <span className="welcome-wave">👋</span>
                <h1>
                  {t('dashboard.welcome')},&nbsp;
                  <span className="gradient-text">{name}</span>!
                </h1>
              </div>
              <p className="db-hero-subtitle">{t('dashboard.welcome_subtitle')}</p>

              <div className="db-hero-ctas">
                <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                  <Link to="/analyze" className="btn-primary btn-lg">
                    <Zap size={16} />
                    {t('dashboard.quick_analyze')}
                  </Link>
                </motion.div>
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                  <Link to="/history" className="btn-outline btn-lg">
                    <Activity size={16} />
                    {t('nav.history')}
                  </Link>
                </motion.div>
              </div>
            </div>

            {history.length > 0 && bestScore > 0 && (
              <motion.div
                className="db-hero-score"
                initial={{ opacity: 0, scale: 0.75 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.35, duration: 0.55, ease: [0.34, 1.56, 0.64, 1] }}
              >
                <ScoreCircle score={bestScore} size={120} label="Best" />
                <span className="db-hero-score-label">En İyi Skor</span>
              </motion.div>
            )}
          </div>
        </motion.div>

        {/* ── Quota Warning ───────────────────────────── */}
        <QuotaWarningBanner />

        {/* ── Stats Grid ────────────────────────────────── */}
        <motion.div
          className="db-stats-grid"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          <DBStatCard
            icon={BarChart2}
            iconColor="var(--color-accent)"
            value={history.length}
            label={t('dashboard.recent_analyses')}
            progress={Math.min(history.length * 10, 100)}
          />

          <DBStatCard
            icon={Calendar}
            iconColor="var(--color-warning)"
            value={`${usageToday}/${dailyLimit === Infinity ? '∞' : dailyLimit}`}
            label={t('dashboard.usage_today')}
            progress={usagePercent}
          >
            {showUsageSource && (
              <span className="db-stat-label" style={{ fontSize: '0.7rem' }}>
                src: {usageSource}
              </span>
            )}
          </DBStatCard>

          <DBStatCard
            icon={Crown}
            iconColor={plan === 'free' ? 'var(--color-text-muted)' : 'var(--status-warning)'}
            value={planLabel}
            label={t('dashboard.plan')}
          >
            {!planLoading && plan === 'free' && (
              <Link to="/pricing" className="db-stat-cta">
                {t('nav.upgrade')} <ArrowRight size={11} style={{ display: 'inline', verticalAlign: 'middle' }} />
              </Link>
            )}
            {!planLoading && plan !== 'free' && plan !== 'admin' && (
              <button type="button" className="db-stat-cta" onClick={onManageBilling}>
                {t('pricing.manage_billing')}
              </button>
            )}
          </DBStatCard>

          <DBStatCard
            icon={Award}
            iconColor="var(--status-accent)"
            value={history.length > 0 ? `${Math.round(bestScore)}%` : '--'}
            label="En İyi Skor"
            progress={bestScore}
          />
        </motion.div>

        {/* ── Daily Limit Warning ───────────────────────── */}
        <AnimatePresence>
          {!planLoading && !canAnalyze() && (
            <motion.div
              className="alert alert-warning"
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: 'auto', marginBottom: 20 }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.35 }}
            >
              <span className="alert-icon" style={{ color: 'var(--color-warning)' }}>⚠️</span>
              <div>
                <strong>{t('dashboard.daily_limit_reached')}</strong>
                <p>{t('dashboard.daily_limit_desc')}</p>
              </div>
              <Link to="/pricing" className="btn-primary btn-sm">{t('nav.upgrade')}</Link>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Streak & Insights ─────────────────────── */}
        <div className="db-streak-insights-row">
          <StreakBadge />
        </div>

        {/* ── Score Trend Chart ──────────────────────── */}
        {trendHistory.length >= 2 && (
          <motion.div
            className="card db-trend-card"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.1 }}
          >
            <div className="db-section-header">
              <div className="db-section-title">
                <TrendingUp size={15} style={{ color: 'var(--color-accent)' }} />
                {t('dashboard.score_trend')}
              </div>
              {remoteTrends.length >= 2 && (
                <span className="text-muted text-xs">
                  {trendLoading ? 'Syncing...' : 'Database trend'}
                </span>
              )}
            </div>
            <ScoreTrendChart history={trendHistory} />
          </motion.div>
        )}

        {/* ── Usage Activity Chart ─────────────────────── */}
        <motion.div
          className="card db-chart-card"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.45, delay: 0.08 }}
        >
          <div className="db-section-header">
            <div className="db-section-title">
              <Activity size={15} style={{ color: 'var(--color-accent)' }} />
              Kullanım Aktivitesi
            </div>
          </div>
          <UsageChart />
        </motion.div>

        {/* ── Main Grid ─────────────────────────────────── */}
        <div className="db-main-grid">

          {/* Recent Analyses */}
          <motion.div
            className="card db-analyses-card"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.05 }}
          >
            <div className="db-section-header">
              <div className="db-section-title">
                <Clock size={15} style={{ color: 'var(--color-text-muted)' }} />
                {t('dashboard.recent_analyses')}
              </div>
              {history.length > 0 && (
                <Link to="/history" className="link-btn">{t('dashboard.view_all')} →</Link>
              )}
            </div>

            {history.length > 0 ? (
              <motion.div
                className="db-analyses-list"
                variants={containerVariants}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true }}
              >
                {history.slice(0, 6).map((item, i) => (
                  <AnalysisCard key={i} item={item} index={i} />
                ))}
              </motion.div>
            ) : (
              <div className="db-empty-state">
                <motion.span
                  className="db-empty-icon"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
                >
                  📄
                </motion.span>
                <h3>{t('dashboard.no_analyses')}</h3>
                <p>{t('dashboard.no_analyses_desc')}</p>
                <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                  <Link to="/analyze" className="btn-primary">{t('dashboard.start_first')}</Link>
                </motion.div>
              </div>
            )}
          </motion.div>

          {/* Sidebar */}
          <div className="db-sidebar">

            {/* Quick Actions */}
            <motion.div
              className="card"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.15 }}
            >
              <div className="db-section-header">
                <div className="db-section-title">
                  <Rocket size={15} style={{ color: 'var(--color-accent)' }} />
                  Hızlı İşlemler
                </div>
              </div>
              <motion.div
                className="db-actions-list"
                variants={containerVariants}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true }}
              >
                {quickActions.map((action, i) => (
                  <QuickActionCard key={i} {...action} />
                ))}
              </motion.div>
            </motion.div>

            {/* Favorites */}
            <motion.div
              className="card"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.2 }}
            >
              <div className="db-section-header">
                <div className="db-section-title">
                  <Star size={15} style={{ color: 'var(--status-warning)' }} />
                  Favoriler
                </div>
                <Link to="/history" className="link-btn">Tümü →</Link>
              </div>
              <FavoritesList />
            </motion.div>

            {/* Insights */}
            <motion.div
              className="card"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.22 }}
            >
              <div className="db-section-header">
                <div className="db-section-title">
                  <Lightbulb size={15} style={{ color: 'var(--status-warning)' }} />
                  Öneriler
                </div>
              </div>
              <InsightsPanel />
            </motion.div>

            {/* Premium Hub */}
            <motion.div
              className="card db-premium-card"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.25 }}
              whileHover={{ y: -5, rotateX: -2, rotateY: 1.5, transition: { duration: 0.2 } }}
            >
              <div className="db-premium-inner">
                <motion.span
                  className="db-premium-icon"
                  animate={{ rotate: [0, 10, -10, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                >
                  ✨
                </motion.span>
                <div style={{ flex: 1 }}>
                  <div className="db-section-title" style={{ marginBottom: 6 }}>
                    <TrendingUp size={14} style={{ color: 'var(--color-accent)' }} />
                    {t('dashboard.premium_hub_title')}
                  </div>
                  <p className="text-muted" style={{ fontSize: '0.82rem', marginBottom: 14, lineHeight: 1.55 }}>
                    {planLoading
                      ? '...'
                      : plan === 'free'
                      ? t('dashboard.premium_hub_locked')
                      : t('dashboard.premium_hub_ready')}
                  </p>
                  <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                    <Link to="/premium" className="btn-primary btn-sm" style={{ display: 'inline-flex', gap: 6 }}>
                      {t('dashboard.open_premium_hub')}
                      <ArrowRight size={13} />
                    </Link>
                  </motion.div>
                </div>
              </div>
            </motion.div>

          </div>
        </div>

      </main>
    </div>
  )
}
