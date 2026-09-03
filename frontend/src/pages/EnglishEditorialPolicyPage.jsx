import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { EDITORIAL_POLICY_EN } from '../content/editorialPolicyEn'

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

export default function EnglishEditorialPolicyPage() {
  return (
    <div className="page-wrapper" lang="en">
      <Navbar />
      <main className="legal-page" id="main-content">
        <article className="legal-container">
          <h1>{EDITORIAL_POLICY_EN.title}</h1>
          <p className="legal-updated">
            Last updated: <time dateTime={EDITORIAL_POLICY_EN.updatedAt}>3 September 2026</time>
          </p>
          <p>{EDITORIAL_POLICY_EN.intro}</p>
          {EDITORIAL_POLICY_EN.sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>
                  {paragraph.includes('support@cvanalyzer.dev') ? renderContactLink(paragraph) : paragraph}
                </p>
              ))}
            </section>
          ))}
          <div className="legal-back">
            <Link to="/en/">← Back to English guides</Link>
          </div>
        </article>
      </main>
      <Footer />
    </div>
  )
}
