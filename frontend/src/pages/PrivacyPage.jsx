import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import LegalDocument from '../components/LegalDocument'
import { POLICY_UPDATED_AT, PRIVACY_EN, PRIVACY_TR } from '../content/legalPolicies'

export default function PrivacyPage() {
  const { lang } = useLanguage()
  const isEnglish = lang === 'en'
  const doc = isEnglish ? PRIVACY_EN : PRIVACY_TR

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
          <Link to={isEnglish ? '/en/contact/' : '/iletisim/'}>
            {isEnglish ? 'Contact us about your data' : 'Verilerinizle ilgili bize ulaşın'}
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
