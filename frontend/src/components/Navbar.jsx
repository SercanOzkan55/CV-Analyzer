import React, { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ChevronDown,
  FileSearch,
  LogOut,
  Moon,
  Settings,
  Sun,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useTheme } from '../context/ThemeContext'
import { BLOG_ENABLED } from '../config/features'
import NotificationCenter from './NotificationCenter'

const langLabels = { en: 'EN', tr: 'TR' }

export default function Navbar() {
  const { user, signOut, plan, planLoading } = useAuth()
  const { t, lang, setLang, availableLanguages } = useLanguage()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  const isLanding = !user
  const billingAdminEmails = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  const isBillingAdmin = !!user?.email && billingAdminEmails.includes(String(user.email).toLowerCase())

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 40)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  async function handleLogout() {
    await signOut()
  }

  return (
    <motion.nav
      className={`navbar${scrolled ? ' navbar-scrolled' : ''}`}
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo" aria-label="CV Analyzer home">
          <motion.span
            className="logo-icon"
            animate={{ opacity: [0.82, 1, 0.82] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            aria-hidden="true"
          >
            <FileSearch size={20} strokeWidth={1.8} />
          </motion.span>
          <span className="logo-wordmark">CV Analyzer</span>
        </Link>

        <button
          className="mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={mobileOpen}
        >
          <motion.span aria-hidden="true" animate={{ rotate: mobileOpen ? 45 : 0, y: mobileOpen ? 6 : 0 }} transition={{ duration: 0.2 }} />
          <motion.span aria-hidden="true" animate={{ opacity: mobileOpen ? 0 : 1, scaleX: mobileOpen ? 0 : 1 }} transition={{ duration: 0.2 }} />
          <motion.span aria-hidden="true" animate={{ rotate: mobileOpen ? -45 : 0, y: mobileOpen ? -6 : 0 }} transition={{ duration: 0.2 }} />
        </button>

        <div className={`navbar-links ${mobileOpen ? 'open' : ''}`}>
          {isLanding ? (
            <>
              <a href="/#features" className="nav-link">{t('nav.features')}</a>
              <a href="/#pricing" className="nav-link">{t('nav.pricing')}</a>
              <a href="/#faq" className="nav-link">{t('nav.faq')}</a>
              <NavLink to="/cv-analiz/" active={location.pathname === '/cv-analiz/'}>CV Rehberi</NavLink>
              {BLOG_ENABLED && <NavLink to="/blog" active={location.pathname === '/blog'}>Blog</NavLink>}
            </>
          ) : (
            <>
              <NavLink to="/dashboard" active={location.pathname === '/dashboard'}>{t('nav.dashboard')}</NavLink>
              <NavLink to="/analyze" active={location.pathname === '/analyze'}>{t('nav.analyze')}</NavLink>

              <div className="nav-dropdown">
                <button
                  type="button"
                  className="nav-dropdown-trigger"
                  aria-haspopup="true"
                  aria-label="Open tools navigation"
                >
                  {t('nav.tools') || 'Tools'} <ChevronDown size={14} />
                </button>
                <div className="nav-dropdown-menu">
                  <NavLink to="/career-studio" active={location.pathname === '/career-studio'}>Career Studio</NavLink>
                  <NavLink to="/agents" active={location.pathname === '/agents'}>AI Agent Hub</NavLink>
                  <NavLink to="/cv-builder" active={location.pathname === '/cv-builder'}>{t('nav.cv_builder')}</NavLink>

                  <NavLink to="/template-marketplace" active={location.pathname === '/template-marketplace'}>Templates</NavLink>
                  <NavLink to="/cover-letter" active={location.pathname === '/cover-letter'}>{t('nav.cover_letter')}</NavLink>
                  <NavLink to="/interview-simulator" active={location.pathname === '/interview-simulator'}>{t('nav.interview')}</NavLink>
                  <NavLink to="/job-tracker" active={location.pathname === '/job-tracker'}>{t('nav.job_tracker')}</NavLink>
                  <NavLink to="/data-center" active={location.pathname === '/data-center'}>Data Center</NavLink>
                </div>
              </div>

              <NavLink to="/history" active={location.pathname === '/history'}>{t('nav.history')}</NavLink>
              {isBillingAdmin && (
                <div className="nav-dropdown">
                  <button
                    type="button"
                    className="nav-dropdown-trigger"
                    aria-haspopup="true"
                    aria-label="Open admin navigation"
                  >
                    Admin <ChevronDown size={14} />
                  </button>
                  <div className="nav-dropdown-menu">
                    <NavLink to="/admin/billing" active={location.pathname === '/admin/billing'}>Billing</NavLink>
                    <NavLink to="/admin/ops" active={location.pathname === '/admin/ops'}>Ops Center</NavLink>
                  </div>
                </div>
              )}
              <NavLink to="/premium" active={location.pathname === '/premium'}>
                {planLoading ? '...' : plan === 'free' ? t('nav.premium_preview') : t('nav.premium')}
              </NavLink>
              <NavLink to="/recruiter" active={location.pathname === '/recruiter'}>{t('nav.recruiter')}</NavLink>
              {BLOG_ENABLED && <NavLink to="/blog" active={location.pathname === '/blog'}>Blog</NavLink>}
            </>
          )}
        </div>

        <div className="navbar-actions">
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

          <motion.button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.96, rotate: 12 }}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={theme}
                initial={{ opacity: 0, rotate: -20, scale: 0.8 }}
                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                exit={{ opacity: 0, rotate: 20, scale: 0.8 }}
                transition={{ duration: 0.18 }}
                className="theme-toggle-icon"
              >
                {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
              </motion.span>
            </AnimatePresence>
          </motion.button>

          {isLanding ? (
            <>
              <Link to="/login" className="nav-link nav-auth-link">{t('nav.login')}</Link>
              <motion.div className="nav-register-wrap" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Link to="/register" className="btn-primary btn-sm">{t('nav.register')}</Link>
              </motion.div>
            </>
          ) : (
            <>
              <NotificationCenter />
              <Link to="/profile" className="nav-link nav-icon" title={t('profile.title')} aria-label={t('profile.title')}>
                <UserRound size={16} />
              </Link>
              <Link to="/settings" className="nav-link nav-icon" title={t('nav.settings')} aria-label={t('nav.settings')}>
                <Settings size={16} />
              </Link>
              <span className="user-email">{user?.email?.split('@')[0]}</span>
              <motion.button
                className="btn-outline btn-sm"
                onClick={handleLogout}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <LogOut size={14} />
                {t('nav.logout')}
              </motion.button>
            </>
          )}
        </div>
      </div>
    </motion.nav>
  )
}

function NavLink({ to, active, children }) {
  return (
    <Link to={to} className={`nav-link ${active ? 'active' : ''}`} style={{ position: 'relative' }}>
      {children}
      {active && (
        <motion.span
          className="nav-link-indicator"
          layoutId="nav-indicator"
          transition={{ type: 'spring', stiffness: 350, damping: 30 }}
        />
      )}
    </Link>
  )
}
