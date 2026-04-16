import React, { useEffect, useState } from 'react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { fetchFeedback, submitFeedback } from '../api'

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
      addToast(t('feedback.submit_success'), 'success')

      const refreshed = await fetchFeedback(token, { limit: 30 })
      setItems(Array.isArray(refreshed?.items) ? refreshed.items : [])
    } catch (err) {
      addToast(err?.message || t('toast.error_generic'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <h1>{t('feedback.page_title')}</h1>
        <p className="text-muted" style={{ marginBottom: '1rem' }}>{t('feedback.page_subtitle')}</p>

        <div className="settings-grid">
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <h2>{t('feedback.form_title')}</h2>
            <form onSubmit={handleSubmit}>
              <div className="settings-field">
                <label>{t('feedback.category_label')}</label>
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="bug">{t('feedback.category_bug')}</option>
                  <option value="feature">{t('feedback.category_feature')}</option>
                  <option value="ux">{t('feedback.category_ux')}</option>
                  <option value="other">{t('feedback.category_other')}</option>
                </select>
              </div>

              <div className="settings-field">
                <label>{t('feedback.message_label')}</label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={5}
                  minLength={5}
                  maxLength={3000}
                  placeholder={t('feedback.message_placeholder')}
                  required
                />
              </div>

              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? t('common.loading') : t('feedback.submit_button')}
              </button>
            </form>
          </div>

          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <h2>{role === 'recruiter' ? t('feedback.inbox_title_recruiter') : t('feedback.inbox_title_user')}</h2>
            {loadingItems ? (
              <p className="text-muted">{t('common.loading')}</p>
            ) : items.length === 0 ? (
              <p className="text-muted">{t('feedback.no_items')}</p>
            ) : (
              <div style={{ display: 'grid', gap: '0.6rem' }}>
                {items.map((item, idx) => (
                  <div
                    key={`${item.timestamp || 'na'}-${idx}`}
                    style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: '0.75rem' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <strong style={{ textTransform: 'capitalize' }}>{item.category || 'other'}</strong>
                      <span className="text-muted" style={{ fontSize: '0.85rem' }}>{item.timestamp || '-'}</span>
                    </div>
                    {item.submitter && (
                      <div className="text-muted" style={{ fontSize: '0.85rem' }}>{item.submitter}</div>
                    )}
                    <div style={{ marginTop: '0.35rem', whiteSpace: 'pre-wrap' }}>{item.message}</div>
                    <div className="text-muted" style={{ marginTop: '0.35rem', fontSize: '0.85rem' }}>
                      {t('feedback.meta_page')}: {item.page || '-'} | {t('feedback.meta_lang')}: {item.lang || '-'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
