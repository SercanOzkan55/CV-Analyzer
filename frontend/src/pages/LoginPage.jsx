import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, FileCheck2, LockKeyhole, ShieldCheck, Sparkles, Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'

export default function LoginPage() {
  const { signIn, signInWithGoogle } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const shouldReduceMotion = useReducedMotion()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    document.title = `${t('auth.login_title')} — CV Analyzer`
  }, [t])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    try {
      setLoading(true)
      await signIn(email, password)
      addToast(t('toast.login_success'), 'success')
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogle() {
    try {
      setLoading(true)
      await signInWithGoogle()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-layout auth-layout-kinetic">
      <Navbar />
      <main className="auth-page auth-page-kinetic" id="main-content">
        <div className="auth-depth-field" aria-hidden="true">
          <span className="auth-depth-line auth-depth-line-a" />
          <span className="auth-depth-line auth-depth-line-b" />
          <span className="auth-depth-line auth-depth-line-c" />
        </div>

        <motion.section
          className="auth-experience-panel"
          aria-hidden="true"
          initial={{ opacity: 0, x: shouldReduceMotion ? 0 : -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: shouldReduceMotion ? 0 : 0.55, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="auth-panel-badge">
            <ShieldCheck size={15} />
            Secure workspace
          </div>
          <h2>CV Analyzer</h2>
          <p>Resume intelligence, match signals, and recruiter workflows in one polished cockpit.</p>

          <div className="auth-signal-stage">
            <motion.div
              className="auth-signal-card auth-signal-card-main"
              animate={shouldReduceMotion ? undefined : { y: [0, -8, 0], rotateX: [0, 2, 0] }}
              transition={{ duration: 4.8, repeat: Infinity, ease: 'easeInOut' }}
            >
              <div className="auth-signal-head">
                <span><FileCheck2 size={14} /> ATS Scan</span>
                <strong>94%</strong>
              </div>
              <div className="auth-signal-bars">
                <span style={{ width: '88%' }} />
                <span style={{ width: '62%' }} />
                <span style={{ width: '74%' }} />
              </div>
            </motion.div>

            <motion.div
              className="auth-signal-chip auth-signal-chip-left"
              animate={shouldReduceMotion ? undefined : { y: [0, 10, 0] }}
              transition={{ duration: 5.2, repeat: Infinity, ease: 'easeInOut', delay: 0.3 }}
            >
              <Sparkles size={14} />
              12 signals
            </motion.div>

            <motion.div
              className="auth-signal-chip auth-signal-chip-right"
              animate={shouldReduceMotion ? undefined : { y: [0, -10, 0] }}
              transition={{ duration: 4.6, repeat: Infinity, ease: 'easeInOut', delay: 0.7 }}
            >
              <Zap size={14} />
              Ready
            </motion.div>
          </div>
        </motion.section>

        <motion.div
          className="auth-card auth-card-kinetic"
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 22, rotateX: shouldReduceMotion ? 0 : 3 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ duration: shouldReduceMotion ? 0 : 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
        >
          <div className="auth-card-mark" aria-hidden="true">
            <LockKeyhole size={18} />
          </div>
          <h1>{t('auth.login_title')}</h1>
          <p className="auth-subtitle">{t('auth.login_subtitle')}</p>

          <button type="button" className="btn-google" onClick={handleGoogle}>
            <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
            {t('auth.sign_in_google')}
          </button>

          <div className="auth-divider"><span>{t('auth.or_divider')}</span></div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label>{t('auth.email')}</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
            </div>
            <div className="form-group">
              <label>{t('auth.password')}</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="current-password" />
            </div>

            <div className="form-row">
              <span />
              <Link to="/forgot-password" className="link-btn">{t('auth.forgot_password')}</Link>
            </div>

            {error && <p className="error">{error}</p>}

            <button type="submit" className="btn-primary btn-full" disabled={loading}>
              {loading ? t('common.loading') : (
                <>
                  {t('auth.sign_in')}
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          <p className="auth-switch">
            {!(import.meta.env.VITE_PRIVATE_MODE === 'true' || import.meta.env.VITE_REGISTRATION_DISABLED === 'true') && (
              <>{t('auth.no_account')} <Link to="/register" className="link-btn">{t('nav.register')}</Link></>
            )}
          </p>
        </motion.div>
      </main>
    </div>
  )
}
