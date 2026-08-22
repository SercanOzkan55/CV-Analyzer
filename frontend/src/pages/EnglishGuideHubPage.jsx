import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BookOpenCheck, CheckCircle2 } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { EN_SEO_PAGES } from '../content/enSeoPages'

export default function EnglishGuideHubPage() {
  const pages = EN_SEO_PAGES.filter((page) => page.indexable !== false)

  return (
    <div className="seo-page" lang="en">
      <Navbar />
      <main id="main-content">
        <header className="seo-hero">
          <div className="seo-container seo-hero-grid">
            <div className="seo-hero-copy">
              <p className="seo-eyebrow">CV Analyzer knowledge centre</p>
              <h1>English CV, ATS and application guides</h1>
              <p className="seo-lead">
                Practical guidance for reviewing a CV, checking document readability, preparing for interviews and building a truthful application. Country and employer conventions vary across Europe, so every guide states what a tool can and cannot conclude.
              </p>
              <div className="seo-trust-note">
                <BookOpenCheck size={18} aria-hidden="true" />
                <p>
                  <strong>Published by CV Analyzer</strong>
                  Read our <Link className="seo-editorial-link" to="/en/editorial-policy/">editorial approach</Link> and limitations.
                </p>
              </div>
            </div>
            <div className="seo-product-visual" aria-label="What these guides cover">
              <div className="seo-product-head"><span>Reader checklist</span></div>
              <div className="seo-product-checks">
                <p><CheckCircle2 size={17} /> Evidence before keywords</p>
                <p><CheckCircle2 size={17} /> Readability before decoration</p>
                <p><CheckCircle2 size={17} /> Local vacancy instructions first</p>
              </div>
              <div className="seo-product-note">No guide can guarantee an ATS result, interview or hiring decision.</div>
            </div>
          </div>
        </header>

        <section className="seo-container seo-article" aria-labelledby="english-guides-title">
          <div className="seo-article-main">
            <h2 id="english-guides-title">Reviewed English guides</h2>
            {pages.map((page) => (
              <article key={page.path}>
                <p className="seo-eyebrow">{page.eyebrow}</p>
                <h3><Link to={page.path}>{page.title}</Link></h3>
                <p>{page.description}</p>
                <Link className="seo-editorial-link" to={page.path}>Read guide <ArrowRight size={15} aria-hidden="true" /></Link>
              </article>
            ))}
          </div>
          <aside className="seo-related" aria-label="English reader information">
            <h2>Reader information</h2>
            <Link to="/en/editorial-policy/">Editorial policy</Link>
            <Link to="/en/privacy/">Privacy policy</Link>
            <Link to="/en/terms/">Terms of use</Link>
            <Link to="/en/about/">About CV Analyzer</Link>
          </aside>
        </section>
      </main>
      <Footer />
    </div>
  )
}
