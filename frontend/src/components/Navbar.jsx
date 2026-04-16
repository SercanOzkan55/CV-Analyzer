import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useTheme } from '../context/ThemeContext'

const langLabels = { en: 'EN', tr: 'TR' }

export default function Navbar() {
  const { user, signOut, plan, planLoading } = useAuth()
  const { t, lang, setLang, availableLanguages } = useLanguage()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = React.useState(false)

  const isLanding = !user
  const billingAdminEmails = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  const isBillingAdmin = !!user?.email && billingAdminEmails.includes(String(user.email).toLowerCase())

  async function handleLogout() {
    await signOut()
  }

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo" onClick={() => setMobileOpen(false)}>
          <span className="logo-icon">◆</span>
          CV Analyzer
        </Link>

        <button
          className="mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={mobileOpen}
        >
          <span /><span /><span />
        </button>

        <div className={`navbar-links ${mobileOpen ? 'open' : ''}`}>
          {isLanding ? (
            <>
              <a href="#features" className="nav-link" onClick={() => setMobileOpen(false)}>{t('nav.features')}</a>
              <a href="#pricing" className="nav-link" onClick={() => setMobileOpen(false)}>{t('nav.pricing')}</a>
              <a href="#faq" className="nav-link" onClick={() => setMobileOpen(false)}>{t('nav.faq')}</a>
            </>
          ) : (
            <>
              <Link to="/dashboard" className={`nav-link ${location.pathname === '/dashboard' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>{t('nav.dashboard')}</Link>
              <Link to="/analyze" className={`nav-link ${location.pathname === '/analyze' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>{t('nav.analyze')}</Link>
              <Link to="/cv-builder" className={`nav-link ${location.pathname === '/cv-builder' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>{t('nav.cv_builder')}</Link>
              <Link to="/history" className={`nav-link ${location.pathname === '/history' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>{t('nav.history')}</Link>
              {isBillingAdmin && (
                <Link to="/admin/billing" className={`nav-link ${location.pathname === '/admin/billing' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>Admin Page</Link>
              )}
              <Link to="/premium" className={`nav-link ${location.pathname === '/premium' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>
                {planLoading ? '...' : plan === 'free' ? t('nav.premium_preview') : t('nav.premium')}
              </Link>
              <Link to="/recruiter" className={`nav-link ${location.pathname === '/recruiter' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>{t('nav.recruiter')}</Link>
              <Link to="/blog" className={`nav-link ${location.pathname === '/blog' ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>Blog</Link>
            </>
          )}
        </div>

        <div className="navbar-actions">
          {/* Language Switcher */}
          <div className="lang-switcher">
            {availableLanguages.map((l) => (
              <button
                key={l}
                className={`lang-btn ${lang === l ? 'active' : ''}`}
                onClick={() => setLang(l)}
              >
                {langLabels[l] || l.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Theme Toggle */}
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>

          {isLanding ? (
            <>
              <Link to="/login" className="nav-link">{t('nav.login')}</Link>
              <Link to="/register" className="btn-primary btn-sm">{t('nav.register')}</Link>
            </>
          ) : (
            <>
              <Link to="/settings" className="nav-link nav-icon" title={t('nav.settings')}>⚙</Link>
              <span className="user-email">{user?.email?.split('@')[0]}</span>
              <button className="btn-outline btn-sm" onClick={handleLogout}>{t('nav.logout')}</button>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
