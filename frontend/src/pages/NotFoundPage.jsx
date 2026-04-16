import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'

export default function NotFoundPage() {
  const { t } = useLanguage()

  useEffect(() => {
    document.title = `404 — CV Analyzer`
  }, [])

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content not-found-page" id="main-content">
        <div className="not-found-container">
          <div className="not-found-code">404</div>
          <h1 className="not-found-title">
            {t('common.page_not_found') || 'Page Not Found'}
          </h1>
          <p className="not-found-desc">
            {t('common.page_not_found_desc') || "The page you're looking for doesn't exist or has been moved."}
          </p>
          <div className="not-found-actions">
            <Link to="/" className="btn-primary">
              {t('nav.home') || 'Home'}
            </Link>
            <Link to="/dashboard" className="btn-outline">
              {t('nav.dashboard') || 'Dashboard'}
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
