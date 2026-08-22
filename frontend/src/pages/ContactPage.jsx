import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { useLanguage } from '../i18n/LanguageContext'
import { CONTACT_EMAIL, CONTACT_EN, CONTACT_TR, CONTACT_UPDATED_AT } from '../content/contactInfo'

export default function ContactPage({ locale }) {
  const { lang } = useLanguage()
  const isEnglish = locale === 'en' || (!locale && lang === 'en')
  const page = isEnglish ? CONTACT_EN : CONTACT_TR
  const other = isEnglish ? CONTACT_TR : CONTACT_EN

  return (
    <div className="page-wrapper">
      <Navbar />
      <main className="legal-page" id="main-content">
        <div className="legal-container">
          <h1>{page.title}</h1>
          <p className="legal-updated">
            {isEnglish ? 'Last updated' : 'Son güncelleme'}: {CONTACT_UPDATED_AT}
          </p>
          <p>{page.intro}</p>

          <p>
            <a className="contact-email" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
          </p>

          {page.sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
              {section.bullets && (
                <ul>
                  {section.bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          <div className="legal-back">
            <Link to={other.path}>
              {isEnglish ? 'Türkçe iletişim sayfası' : 'Contact page in English'}
            </Link>
            {' · '}
            <Link to={isEnglish ? '/en/' : '/'}>
              ← {isEnglish ? 'Back to guides' : 'Ana sayfaya dön'}
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
