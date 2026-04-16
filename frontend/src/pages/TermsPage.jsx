import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function TermsPage() {
  const { t } = useLanguage()

  return (
    <div className="page-wrapper">
      <Navbar />
      <main className="legal-page" id="main-content">
        <div className="legal-container">
          <h1>{t('terms.title')}</h1>
          <p className="legal-updated">{t('terms.last_updated')}: 2026-03-01</p>

          <section>
            <h2>{t('terms.section1_title')}</h2>
            <p>{t('terms.section1_text')}</p>
          </section>

          <section>
            <h2>{t('terms.section2_title')}</h2>
            <p>{t('terms.section2_text')}</p>
          </section>

          <section>
            <h2>{t('terms.section3_title')}</h2>
            <p>{t('terms.section3_text')}</p>
          </section>

          <section>
            <h2>{t('terms.section4_title')}</h2>
            <p>{t('terms.section4_text')}</p>
          </section>

          <section>
            <h2>{t('terms.section5_title')}</h2>
            <p>{t('terms.section5_text')}</p>
          </section>

          <section>
            <h2>{t('terms.section6_title')}</h2>
            <p>{t('terms.section6_text')}</p>
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
