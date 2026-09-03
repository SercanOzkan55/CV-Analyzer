import React from 'react'
import { motion } from 'framer-motion'
import { LifeBuoy, MessageCircle, Sparkles } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'

export default function FeedbackButton() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { t } = useLanguage()
  const label = t('feedback.button_text') || 'Support'
  const isPublicContent = pathname === '/'
    || /^\/(?:araclar|rehber|cv-|ats-|metodoloji|mulakat|on-yazi|en(?:\/|$))/.test(pathname)
    || ['/about', '/editoryal-politika', '/privacy', '/terms', '/iletisim', '/pricing'].includes(pathname)

  return (
    <motion.button
      type="button"
      className={`feedback-floating-btn${isPublicContent ? ' feedback-floating-btn--compact' : ''}`}
      aria-label={label}
      title={t('feedback.button_title') || label}
      onClick={() => navigate('/feedback')}
      whileHover={{ y: -3, scale: 1.03 }}
      whileTap={{ scale: 0.96 }}
    >
      <span className="feedback-btn-aura" />
      <span className="feedback-btn-icon" aria-hidden="true">
        <MessageCircle size={18} />
        <Sparkles size={10} className="feedback-btn-spark" />
      </span>
      <span className="feedback-btn-label">{label}</span>
      <LifeBuoy size={16} className="feedback-btn-support-icon" aria-hidden="true" />
    </motion.button>
  )
}
