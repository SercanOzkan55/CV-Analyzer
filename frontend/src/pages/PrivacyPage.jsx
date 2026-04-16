import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function PrivacyPage() {
  const { t } = useLanguage()

  return (
    <div className="page-wrapper">
      <Navbar />
      <main className="legal-page" id="main-content">
        <div className="legal-container">
          <h1>{t('privacy.title')}</h1>
          <p className="legal-updated">{t('privacy.last_updated')}: 2026-03-01</p>

          <section>
            <h2>{t('privacy.section1_title')}</h2>
            <p>{t('privacy.section1_text')}</p>
          </section>

          <section>
            <h2>{t('privacy.section2_title')}</h2>
            <p>{t('privacy.section2_text')}</p>
          </section>

          <section>
            <h2>{t('privacy.section3_title')}</h2>
            <p>{t('privacy.section3_text')}</p>
          </section>

          <section>
            <h2>{t('privacy.section4_title')}</h2>
            <p>{t('privacy.section4_text')}</p>
          </section>

          <section>
            <h2>{t('privacy.section5_title')}</h2>
            <p>{t('privacy.section5_text')}</p>
          </section>

          <section>
            <h2>{t('privacy.section6_title')}</h2>
            <p>{t('privacy.section6_text')}</p>
          </section>

          <div className="legal-back">
            <Link to="/">← {t('common.back')}</Link>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
