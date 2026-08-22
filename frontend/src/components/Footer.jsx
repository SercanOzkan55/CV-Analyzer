import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import { BLOG_ENABLED } from '../config/features'

export default function Footer() {
  const { t, lang } = useLanguage()
  const year = new Date().getFullYear()
  const isEnglish = lang === 'en'

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
          <Link to={isEnglish ? '/en/pricing/' : '/pricing'}>{t('nav.pricing')}</Link>
          <Link to="/#faq">{t('nav.faq')}</Link>
        </div>
        
        <div className="footer-col">
          <h4>{t('landing.footer_company')}</h4>
          <Link to={isEnglish ? '/en/about/' : '/about'}>{t('about.title')}</Link>
          {BLOG_ENABLED && <Link to="/blog">{t('nav.blog') || 'Blog'}</Link>}
          <Link to={isEnglish ? '/en/contact/' : '/iletisim/'}>{t('landing.footer_contact')}</Link>
        </div>

        <div className="footer-col">
          <h4>{isEnglish ? 'English guides' : 'CV Rehberleri'}</h4>
          <Link to={isEnglish ? '/en/' : '/rehber/'}>{isEnglish ? 'All English guides' : 'Tüm rehberler'}</Link>
          <Link to={isEnglish ? '/en/ai-cv-analyzer/' : '/cv-analiz/'}>{isEnglish ? 'AI CV analysis' : 'CV analiz'}</Link>
          <Link to={isEnglish ? '/en/ats-resume-checker/' : '/ats-cv-kontrol/'}>{isEnglish ? 'ATS resume check' : 'ATS CV kontrolü'}</Link>
        </div>

        <div className="footer-col">
          <h4>{isEnglish ? 'Career preparation' : 'English edition'}</h4>
          <Link to="/en/ai-interview-simulator/">Interview preparation</Link>
          <Link to="/en/resume-builder/">Resume builder guide</Link>
          {!isEnglish && <Link to="/en/">English guide centre</Link>}
        </div>

        <div className="footer-col">
          <h4>{t('landing.footer_legal')}</h4>
          <Link to={isEnglish ? '/en/privacy/' : '/privacy'}>{t('landing.footer_privacy')}</Link>
          <Link to={isEnglish ? '/en/terms/' : '/terms'}>{t('landing.footer_terms')}</Link>
          <Link to={isEnglish ? '/en/editorial-policy/' : '/editoryal-politika/'}>{isEnglish ? 'Editorial policy' : 'İçerik ilkeleri'}</Link>
        </div>
      </div>

      <div className="footer-bottom">
        <p>© {year} CV Analyzer. {t('landing.footer_rights')}</p>
      </div>
    </footer>
  )
}
