import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Bug, Inbox, Lightbulb, MessageSquareText, MonitorSmartphone, Send, Sparkles } from 'lucide-react'
import Navbar from '../components/Navbar'
import { addNotification } from '../components/NotificationCenter'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { fetchFeedback, submitFeedback } from '../api'

const CATEGORY_OPTIONS = [
  { value: 'bug', icon: Bug, labelKey: 'feedback.category_bug', fallback: 'Bug' },
  { value: 'feature', icon: Lightbulb, labelKey: 'feedback.category_feature', fallback: 'Feature' },
  { value: 'ux', icon: MonitorSmartphone, labelKey: 'feedback.category_ux', fallback: 'UX' },
  { value: 'other', icon: MessageSquareText, labelKey: 'feedback.category_other', fallback: 'Other' },
]

export default function FeedbackPage() {
  const { token, role } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()

  const [category, setCategory] = useState('bug')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loadingItems, setLoadingItems] = useState(false)
  const [items, setItems] = useState([])

  useEffect(() => {
    document.title = `${t('feedback.page_title')} - CV Analyzer`
  }, [t])

  useEffect(() => {
    let ignore = false

    async function loadFeedback() {
      if (!token) return
      try {
        setLoadingItems(true)
        const data = await fetchFeedback(token, { limit: 30 })
        if (!ignore) {
          setItems(Array.isArray(data?.items) ? data.items : [])
        }
      } catch {
        if (!ignore) setItems([])
      } finally {
        if (!ignore) setLoadingItems(false)
      }
    }

    loadFeedback()
    return () => {
      ignore = true
    }
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmed = String(message || '').trim()

    if (trimmed.length < 5) {
      addToast(t('feedback.too_short'), 'error')
      return
    }

    try {
      setSubmitting(true)
      await submitFeedback(token, {
        category,
        message: trimmed,
        page: '/feedback',
        lang,
      })
      setMessage('')
      addNotification({
        title: t('feedback.page_title') || 'Complaint',
        message: `${t('feedback.category_label') || 'Category'}: ${category} - ${trimmed.slice(0, 120)}`,
        type: category === 'bug' ? 'warning' : 'info',
      })
      addToast(t('feedback.submit_success'), 'success')

      const refreshed = await fetchFeedback(token, { limit: 30 })
      setItems(Array.isArray(refreshed?.items) ? refreshed.items : [])
    } catch (err) {
      addToast(err?.message || t('toast.error_generic'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const canReviewFeedback = ['admin', 'owner', 'recruiter'].includes(String(role || '').toLowerCase())
  const inboxTitle = canReviewFeedback
    ? t('feedback.inbox_title_recruiter')
    : t('feedback.inbox_title_user')

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content feedback-page" id="main-content">
        <motion.section
          className="feedback-hero"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.36 }}
        >
          <div className="feedback-hero-icon" aria-hidden="true">
            <MessageSquareText size={26} />
          </div>
          <div className="feedback-hero-copy">
            <span className="product-page-kicker">Support channel</span>
            <h1>{t('feedback.page_title')}</h1>
            <p>{t('feedback.page_subtitle')}</p>
          </div>
          <div className="feedback-hero-metrics" aria-hidden="true">
            <span><strong>24h</strong> Triage</span>
            <span><strong>{items.length}</strong> Open notes</span>
            <span><strong>AI</strong> Routed</span>
          </div>
        </motion.section>

        <div className="feedback-layout">
          <motion.section
            className="card feedback-form-card"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, duration: 0.36 }}
          >
            <div className="feedback-card-header">
              <div>
                <span className="product-page-kicker">Ticket details</span>
                <h2>{t('feedback.form_title')}</h2>
              </div>
              <Sparkles size={20} aria-hidden="true" />
            </div>

            <form onSubmit={handleSubmit} className="feedback-form">
              <fieldset className="feedback-category-field">
                <legend>{t('feedback.category_label')}</legend>
                <div className="feedback-category-grid">
                  {CATEGORY_OPTIONS.map((option) => {
                    const Icon = option.icon
                    const active = category === option.value
                    return (
                      <button
                        key={option.value}
                        type="button"
                        className={`feedback-category-option ${active ? 'is-active' : ''}`}
                        onClick={() => setCategory(option.value)}
                      >
                        <Icon size={17} />
                        <span>{t(option.labelKey) || option.fallback}</span>
                      </button>
                    )
                  })}
                </div>
              </fieldset>

              <div className="settings-field feedback-message-field">
                <label htmlFor="feedback-message">{t('feedback.message_label')}</label>
                <textarea
                  id="feedback-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={7}
                  minLength={5}
                  maxLength={3000}
                  placeholder={t('feedback.message_placeholder')}
                  required
                />
              </div>

              <div className="feedback-form-footer">
                <span>{message.length}/3000</span>
                <motion.button
                  type="submit"
                  className="btn-primary"
                  disabled={submitting}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Send size={16} />
                  {submitting ? t('common.loading') : t('feedback.submit_button')}
                </motion.button>
              </div>
            </form>
          </motion.section>

          <motion.aside
            className="card feedback-inbox-card"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14, duration: 0.36 }}
          >
            <div className="feedback-card-header">
              <div>
                <span className="product-page-kicker">History</span>
                <h2>{inboxTitle}</h2>
              </div>
              <Inbox size={20} aria-hidden="true" />
            </div>

            {loadingItems ? (
              <p className="text-muted">{t('common.loading')}</p>
            ) : items.length === 0 ? (
              <div className="feedback-empty-state">
                <Sparkles size={24} />
                <strong>{t('feedback.no_items')}</strong>
                <span>Send a note and your latest tickets will appear here.</span>
              </div>
            ) : (
              <div className="feedback-item-list">
                {items.map((item, idx) => (
                  <article key={`${item.timestamp || 'na'}-${idx}`} className="feedback-item">
                    <div className="feedback-item-topline">
                      <strong>{item.category || 'other'}</strong>
                      <time dateTime={item.timestamp || undefined}>{item.timestamp || '-'}</time>
                    </div>
                    {item.submitter && (
                      <span className="feedback-item-submitter">{item.submitter}</span>
                    )}
                    <p>{item.message}</p>
                    <small>
                      {t('feedback.meta_page')}: {item.page || '-'} | {t('feedback.meta_lang')}: {item.lang || '-'}
                    </small>
                  </article>
                ))}
              </div>
            )}
          </motion.aside>
        </div>
      </main>
    </div>
  )
}
