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
          <a href="#">{t('landing.footer_about')}</a>
          <a href="#">{t('landing.footer_contact')}</a>
          <a href="#">{t('landing.footer_blog')}</a>
        </div>

        <div className="footer-col">
          <h4>{t('landing.footer_legal')}</h4>
          <a href="#">{t('landing.footer_privacy')}</a>
          <a href="#">{t('landing.footer_terms')}</a>
        </div>
      </div>

      <div className="footer-bottom">
        <p>© {year} CV Analyzer. {t('landing.footer_rights')}</p>
      </div>
    </footer>
  )
}
