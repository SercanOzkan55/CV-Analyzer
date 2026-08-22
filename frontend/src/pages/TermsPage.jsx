import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import LegalDocument from '../components/LegalDocument'
import { POLICY_UPDATED_AT, TERMS_EN, TERMS_TR } from '../content/legalPolicies'

export default function TermsPage() {
  const { lang } = useLanguage()
  const isEnglish = lang === 'en'
  const doc = isEnglish ? TERMS_EN : TERMS_TR

  return (
    <div className="page-wrapper">
      <Navbar />
      <main className="legal-page" id="main-content">
        <LegalDocument
          document={doc}
          updatedAt={POLICY_UPDATED_AT}
          updatedLabel={isEnglish ? 'Last updated' : 'Son güncelleme'}
        />
        <div className="legal-container legal-back">
          <Link to={isEnglish ? '/en/privacy/' : '/privacy'}>
            {isEnglish ? 'Privacy Policy' : 'Gizlilik Politikası'}
          </Link>
          {' · '}
          <Link to={isEnglish ? '/en/' : '/'}>
            ← {isEnglish ? 'Back' : 'Geri dön'}
          </Link>
        </div>
      </main>
      <Footer />
    </div>
  )
}
