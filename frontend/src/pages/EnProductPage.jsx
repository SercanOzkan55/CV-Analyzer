import React from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, CheckCircle2, Clock3, FileSearch, ShieldCheck } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { EN_SEO_PAGES } from '../content/enSeoPages'

function sectionId(pageSlug, index) {
  return `${pageSlug}-section-${index + 1}`
}

function formatUpdatedAt(value) {
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

export default function EnProductPage({ page }) {
  const reduceMotion = useReducedMotion()
  const canObserve = typeof window !== 'undefined' && 'IntersectionObserver' in window
  const relatedPages = EN_SEO_PAGES.filter((candidate) => candidate.path !== page.path)
  const reveal = reduceMotion
    ? {}
    : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }
  const inViewReveal = reduceMotion || !canObserve
    ? {}
    : {
        initial: { opacity: 0, y: 10 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, amount: 0.08 },
      }

  return (
    <div className="seo-page" lang="en">
      <Navbar />
      <main id="main-content">
        <header className="seo-hero">
          <div className="seo-container seo-hero-grid">
            <motion.div
              className="seo-hero-copy"
              key={`${page.slug}-copy`}
              {...reveal}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              <p className="seo-eyebrow">{page.eyebrow}</p>
              <h1>{page.title}</h1>
              <p className="seo-lead">{page.intro}</p>
              <div className="seo-hero-actions">
                <Link to={page.ctaHref} className="btn-primary">
                  {page.ctaLabel} <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <Link to={page.trPath} className="btn-outline">
                  View Turkish version
                </Link>
              </div>
              <div className="seo-meta" aria-label="Article details">
                <span><Clock3 size={15} aria-hidden="true" /> {page.readingTime}</span>
                <span>Updated: {formatUpdatedAt(page.updatedAt)}</span>
              </div>
              <div className="seo-trust-note">
                <ShieldCheck size={18} aria-hidden="true" />
                <p>
                  <strong>CV Analyzer Editorial Team</strong>
                  {' '}This content is reviewed for clarity, usefulness, and accuracy.
                </p>
              </div>
            </motion.div>

            <motion.div
              className="seo-product-visual"
              aria-label="Illustrative CV Analyzer evaluation summary"
              key={`${page.slug}-sample`}
              initial={reduceMotion ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: reduceMotion ? 0 : 0.06, ease: 'easeOut' }}
            >
              <div className="seo-product-head">
                <span><FileSearch size={18} aria-hidden="true" /> Sample analysis summary</span>
                <strong>84/100</strong>
              </div>
              <div className="seo-score-track" aria-hidden="true"><span /></div>
              <div className="seo-product-checks">
                <p><CheckCircle2 size={17} /> Contact details are readable</p>
                <p><CheckCircle2 size={17} /> Standard section headings</p>
                <p><ShieldCheck size={17} /> ATS-safe text output</p>
              </div>
              <div className="seo-product-note">This is an illustrative example. Actual scores and suggestions depend on your CV and target role.</div>
            </motion.div>
          </div>
        </header>

        <nav className="seo-jump-band" aria-label="Table of contents">
          <div className="seo-container">
            <p className="seo-jump-title">In this guide</p>
            <div className="seo-highlight-grid">
              {page.sections.map((section, index) => (
                <a href={`#${sectionId(page.slug, index)}`} key={section.heading}>
                  <CheckCircle2 size={16} aria-hidden="true" /> {section.heading}
                </a>
              ))}
              <a href={`#${page.slug}-faq-title`}>
                <CheckCircle2 size={16} aria-hidden="true" /> Frequently asked questions
              </a>
            </div>
          </div>
        </nav>

        <article className="seo-container seo-article">
          <div className="seo-article-main">
            <section aria-label="Key benefits">
              <h2>Why use it</h2>
              <ul>
                {page.highlights.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>

            {page.sections.map((section, index) => (
              <motion.section
                id={sectionId(page.slug, index)}
                key={section.heading}
                {...inViewReveal}
                transition={{ duration: 0.24, ease: 'easeOut' }}
              >
                <h2>{section.heading}</h2>
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                {section.bullets && (
                  <ul>
                    {section.bullets.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                )}
              </motion.section>
            ))}

            <motion.section
              className="seo-faq"
              aria-labelledby={`${page.slug}-faq-title`}
              {...inViewReveal}
              transition={{ duration: 0.24, ease: 'easeOut' }}
            >
              <p className="seo-eyebrow">Frequently asked questions</p>
              <h2 id={`${page.slug}-faq-title`}>Questions about {page.title}</h2>
              {page.faq.map((item) => (
                <details key={item.question}>
                  <summary>{item.question}</summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </motion.section>
          </div>

          <aside className="seo-related" aria-label="Related tools">
            <h2>Related tools</h2>
            <p>Explore other CV Analyzer tools that approach your job search from a different angle.</p>
            {relatedPages.map((relatedPage) => (
              <Link to={relatedPage.path} key={relatedPage.path}>
                {relatedPage.eyebrow} <ArrowRight size={15} aria-hidden="true" />
              </Link>
            ))}
          </aside>
        </article>

        <section className="seo-final-cta">
          <div className="seo-container">
            <div>
              <p className="seo-eyebrow">Check your own document</p>
              <h2>See how your CV is read</h2>
              <p>Review ATS readability, job matching, and practical improvement suggestions in one analysis.</p>
            </div>
            <Link to={page.ctaHref} className="btn-primary">
              Create a free account <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
