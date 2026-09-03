import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { EDITORIAL_POLICY } from '../content/editorialPolicy'

export default function EditorialPolicyPage() {
  return (
    <div className="page-wrapper">
      <Navbar />
      <main className="legal-page" id="main-content">
        <article className="legal-container">
          <h1>{EDITORIAL_POLICY.title}</h1>
          <p className="legal-updated">
            Son güncelleme:{' '}
            <time dateTime={EDITORIAL_POLICY.updatedAt}>3 Eylül 2026</time>
          </p>
          <p>{EDITORIAL_POLICY.intro}</p>

          {EDITORIAL_POLICY.sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>
                  {paragraph.includes('support@cvanalyzer.dev')
                    ? renderContactLink(paragraph)
                    : paragraph}
                </p>
              ))}
            </section>
          ))}

          <div className="legal-back">
            <Link to="/rehber/">← CV rehberlerine dön</Link>
          </div>
        </article>
      </main>
      <Footer />
    </div>
  )
}

function renderContactLink(paragraph) {
  const [before, after = ''] = paragraph.split('support@cvanalyzer.dev')
  return (
    <>
      {before}
      <a href="mailto:support@cvanalyzer.dev">support@cvanalyzer.dev</a>
      {after}
    </>
  )
}
