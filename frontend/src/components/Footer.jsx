import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import { BLOG_ENABLED } from '../config/features'

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
          {BLOG_ENABLED && <Link to="/blog">{t('nav.blog') || 'Blog'}</Link>}
          <a href="mailto:support@cvanalyzer.dev">{t('landing.footer_contact')}</a>
        </div>

        <div className="footer-col">
          <h4>CV Rehberleri</h4>
          <Link to="/cv-analiz/">CV analiz</Link>
          <Link to="/ats-cv-kontrol/">ATS CV kontrolü</Link>
          <Link to="/ats-uyumlu-cv/">ATS uyumlu CV</Link>
          <Link to="/rehber/cv-nasil-hazirlanir/">CV nasıl hazırlanır?</Link>
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
