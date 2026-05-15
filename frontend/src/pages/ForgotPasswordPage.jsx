import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'

export default function ForgotPasswordPage() {
  const { resetPassword } = useAuth()
  const { t } = useLanguage()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    document.title = `${t('auth.forgot_title')} — CV Analyzer`
  }, [t])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    try {
      setLoading(true)
      await resetPassword(email)
      setSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-layout">
      <Navbar />
      <main className="auth-page" id="main-content">
        <div className="auth-card">
          <h1>{t('auth.forgot_title')}</h1>
          <p className="auth-subtitle">{t('auth.forgot_subtitle')}</p>

          {sent ? (
            <div className="success-box">
              <div className="success-icon">✓</div>
              <p>{t('auth.reset_sent')}</p>
              <Link to="/login" className="btn-primary btn-full">{t('auth.back_to_login')}</Link>
            </div>
          ) : (
            <form className="auth-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label>{t('auth.email')}</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
              </div>

              {error && <p className="error">{error}</p>}

              <button type="submit" className="btn-primary btn-full" disabled={loading}>
                {loading ? t('common.loading') : t('auth.send_reset')}
              </button>
            </form>
          )}

          <p className="auth-switch">
            <Link to="/login" className="link-btn">{t('auth.back_to_login')}</Link>
          </p>
        </div>
      </main>
    </div>
  )
}
