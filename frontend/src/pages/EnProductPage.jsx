import React from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { EN_SEO_PAGES } from '../content/enSeoPages'

function sectionId(pageSlug, index) {
  return `${pageSlug}-section-${index + 1}`
}

function formatUpdatedAt(value) {
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

export default function EnProductPage({ page }) {
  const reduceMotion = useReducedMotion()
  const canObserve = typeof window !== 'undefined' && 'IntersectionObserver' in window
  const pageTerms = new Set(`${page.title} ${page.highlights.join(' ')}`.toLowerCase().match(/[a-z]{4,}/g) || [])
  const relatedPages = EN_SEO_PAGES
    .filter((candidate) => candidate.path !== page.path && candidate.indexable !== false)
    .map((candidate, order) => ({
      candidate,
      order,
      score: (`${candidate.title} ${candidate.highlights.join(' ')}`.toLowerCase().match(/[a-z]{4,}/g) || [])
        .filter((term) => pageTerms.has(term)).length,
    }))
    .sort((a, b) => b.score - a.score || a.order - b.order)
    .slice(0, 4)
    .map(({ candidate }) => candidate)
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
                {page.trPath && (
                  <Link to={page.trPath} className="btn-outline">
                    View Turkish version
                  </Link>
                )}
              </div>
              <div className="seo-meta" aria-label="Article details">
                <span><Clock3 size={15} aria-hidden="true" /> {page.readingTime}</span>
                <span>Updated: <time dateTime={page.updatedAt}>{formatUpdatedAt(page.updatedAt)}</time></span>
              </div>
              <div className="seo-trust-note">
                <ShieldCheck size={18} aria-hidden="true" />
                <p>
                  <strong>Sercan Özkan</strong>
                  {' '}Founder-developer and publishing lead for this guide.
                  <Link className="seo-editorial-link" to="/about/">About the publisher</Link>
                  <Link className="seo-editorial-link" to="/en/editorial-policy/">Our editorial approach</Link>
                </p>
              </div>
            </motion.div>

            <motion.div
              className="seo-product-visual"
              aria-label="What this guide covers"
              key={`${page.slug}-sample`}
              initial={reduceMotion ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: reduceMotion ? 0 : 0.06, ease: 'easeOut' }}
            >
              <div className="seo-product-head">
                <span><CheckCircle2 size={18} aria-hidden="true" /> What this guide covers</span>
                <strong>{page.highlights.length}</strong>
              </div>
              <div className="seo-product-checks">
                {page.highlights.map((highlight) => (
                  <p key={highlight}><CheckCircle2 size={17} aria-hidden="true" /> {highlight}</p>
                ))}
              </div>
              <div className="seo-product-note">This summary lists the specific outcomes covered by this page; it is not an ATS score.</div>
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
            <Link to="/en/">View all English guides <ArrowRight size={15} aria-hidden="true" /></Link>
          </aside>
        </article>

        <section className="seo-final-cta">
          <div className="seo-container">
            <div>
              <p className="seo-eyebrow">{page.finalCtaEyebrow || 'Check your own document'}</p>
              <h2>{page.finalCtaTitle || 'See how your CV is read'}</h2>
              <p>{page.finalCtaDescription || 'Review ATS readability, job matching, and practical improvement suggestions in one analysis.'}</p>
            </div>
            <Link to={page.ctaHref} className="btn-primary">
              {page.finalCtaLabel || 'Create a free account'} <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
