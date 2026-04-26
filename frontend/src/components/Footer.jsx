import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'

export default function Footer() {
  const { t } = useLanguage()
  const year = new Date().getFullYear()

  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <span className="footer-logo">◆ CV Analyzer</span>
          <p className="footer-desc">{t('landing.footer_description')}</p>
        </div>

        <div className="footer-col">
          <h4>{t('landing.footer_product')}</h4>
          <Link to="/#features">{t('nav.features')}</Link>
          <Link to="/pricing">{t('nav.pricing')}</Link>
          <Link to="/#faq">{t('nav.faq')}</Link>
        </div>
        
        <div className="footer-col">
          <h4>{t('landing.footer_company')}</h4>
          <Link to="/about">{t('about.title')}</Link>
          <Link to="/blog">{t('nav.blog') || 'Blog'}</Link>
          <a href="mailto:support@cvanalyzer.app">{t('landing.footer_contact')}</a>
        </div>

        <div className="footer-col">
          <h4>{t('landing.footer_legal')}</h4>
          <Link to="/privacy">{t('landing.footer_privacy')}</Link>
          <Link to="/terms">{t('landing.footer_terms')}</Link>
        </div>
      </div>

      <div className="footer-bottom">
        <p>© {year} CV Analyzer. {t('landing.footer_rights')}</p>
      </div>
    </footer>
  )
}
