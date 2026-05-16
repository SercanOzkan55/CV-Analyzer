import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useTheme } from '../context/ThemeContext'
import NotificationCenter from './NotificationCenter'
import { ChevronDown } from 'lucide-react'

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

  // Close mobile menu on route change
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
        <Link to="/" className="navbar-logo">
          <motion.span
            className="logo-icon"
            animate={{ rotate: [0, 8, -4, 0] }}
            transition={{ duration: 3, repeat: Infinity, repeatDelay: 6, ease: 'easeInOut' }}
          >
            ◆
          </motion.span>
          CV Analyzer
        </Link>

        <button
          className="mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={mobileOpen}
        >
          <motion.span animate={{ rotate: mobileOpen ? 45 : 0, y: mobileOpen ? 6 : 0 }} transition={{ duration: 0.2 }} />
          <motion.span animate={{ opacity: mobileOpen ? 0 : 1, scaleX: mobileOpen ? 0 : 1 }} transition={{ duration: 0.2 }} />
          <motion.span animate={{ rotate: mobileOpen ? -45 : 0, y: mobileOpen ? -6 : 0 }} transition={{ duration: 0.2 }} />
        </button>

        <div className={`navbar-links ${mobileOpen ? 'open' : ''}`}>
          {isLanding ? (
            <>
              <a href="#features" className="nav-link">{t('nav.features')}</a>
              <a href="#pricing" className="nav-link">{t('nav.pricing')}</a>
              <a href="#faq" className="nav-link">{t('nav.faq')}</a>
              <NavLink to="/blog" active={location.pathname === '/blog'}>Blog</NavLink>
            </>
          ) : (
            <>
              <NavLink to="/dashboard" active={location.pathname === '/dashboard'}>{t('nav.dashboard')}</NavLink>
              <NavLink to="/analyze" active={location.pathname === '/analyze'}>{t('nav.analyze')}</NavLink>
              
              <div className="nav-dropdown">
                <div className="nav-dropdown-trigger">
                  {t('nav.tools') || 'Tools'} <ChevronDown size={14} />
                </div>
                <div className="nav-dropdown-menu">
                  <NavLink to="/career-studio" active={location.pathname === '/career-studio'}>Career Studio</NavLink>
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
                  <div className="nav-dropdown-trigger">
                    Admin <ChevronDown size={14} />
                  </div>
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
              <NavLink to="/blog" active={location.pathname === '/blog'}>Blog</NavLink>
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
          <motion.button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9, rotate: 20 }}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={theme}
                initial={{ opacity: 0, rotate: -30, scale: 0.7 }}
                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                exit={{ opacity: 0, rotate: 30, scale: 0.7 }}
                transition={{ duration: 0.2 }}
                style={{ display: 'inline-block' }}
              >
                {theme === 'dark' ? '☀️' : '🌙'}
              </motion.span>
            </AnimatePresence>
          </motion.button>

          {isLanding ? (
            <>
              <Link to="/login" className="nav-link">{t('nav.login')}</Link>
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Link to="/register" className="btn-primary btn-sm">{t('nav.register')}</Link>
              </motion.div>
            </>
          ) : (
            <>
              <NotificationCenter />
              <Link to="/profile" className="nav-link nav-icon" title={t('profile.title')}>👤</Link>
              <Link to="/settings" className="nav-link nav-icon" title={t('nav.settings')}>⚙</Link>
              <span className="user-email">{user?.email?.split('@')[0]}</span>
              <motion.button
                className="btn-outline btn-sm"
                onClick={handleLogout}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
              >
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
