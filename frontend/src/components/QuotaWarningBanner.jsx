import React from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Zap, ArrowRight } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'

/**
 * Progressive quota warning banner.
 * Shows at 60%, 80%, 100% usage thresholds for free-plan users.
 */
export default function QuotaWarningBanner() {
  const { plan, planLoading, usageToday, dailyLimit, role } = useAuth()
  const { t } = useLanguage()

  // Don't show for pro/enterprise/admin users or while loading
  if (planLoading || plan !== 'free' || role === 'admin') return null
  if (dailyLimit === Infinity || dailyLimit === 0) return null

  const pct = (usageToday / dailyLimit) * 100
  const remaining = Math.max(0, dailyLimit - usageToday)

  // Determine warning tier
  let tier = null
  if (pct >= 100) tier = 'critical'
  else if (pct >= 80) tier = 'warning'
  else if (pct >= 60) tier = 'info'

  if (!tier) return null

  const config = {
    info: {
      icon: <Zap size={16} />,
      className: 'quota-banner quota-banner-info',
      title: `${remaining} analiz hakkınız kaldı`,
      desc: `Günlük ${dailyLimit} limitinizin %${Math.round(pct)}'ini kullandınız.`,
    },
    warning: {
      icon: <AlertTriangle size={16} />,
      className: 'quota-banner quota-banner-warning',
      title: `Son ${remaining} analiz hakkınız!`,
      desc: 'Limitiniz dolmak üzere. Pro plana geçerek sınırsız analiz yapın.',
    },
    critical: {
      icon: <AlertTriangle size={16} />,
      className: 'quota-banner quota-banner-critical',
      title: t('dashboard.daily_limit_reached') || 'Günlük limit doldu',
      desc: t('dashboard.daily_limit_desc') || 'Pro plana yükselterek sınırsız analiz yapabilirsiniz.',
    },
  }

  const c = config[tier]

  return (
    <AnimatePresence>
      <motion.div
        className={c.className}
        initial={{ opacity: 0, y: -8, height: 0 }}
        animate={{ opacity: 1, y: 0, height: 'auto' }}
        exit={{ opacity: 0, y: -8, height: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="quota-banner-icon">{c.icon}</div>
        <div className="quota-banner-text">
          <strong>{c.title}</strong>
          <span>{c.desc}</span>
        </div>
        <div className="quota-banner-bar">
          <div className="quota-banner-bar-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
        <Link to="/pricing" className="quota-banner-cta">
          Upgrade <ArrowRight size={13} />
        </Link>
      </motion.div>
    </AnimatePresence>
  )
}
