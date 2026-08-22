import React from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, CheckCircle2, Clock3, FileSearch, Languages, ShieldCheck } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import AdSlot from '../components/AdSlot'
import { SEO_PAGES } from '../content/seoPages'
import { EN_EQUIVALENT_BY_TR_PATH } from '../content/enSeoPages'
import { getGuideUi, getLocalizedSeoPage, getLocalizedSeoPages } from '../content/guideI18n'
import { useLanguage } from '../i18n/LanguageContext'

function sectionId(pageSlug, index) {
  return `${pageSlug}-section-${index + 1}`
}

function formatUpdatedAt(value, locale) {
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

export default function SEOContentPage({ page: sourcePage }) {
  const { lang } = useLanguage()
  const reduceMotion = useReducedMotion()
  const ui = getGuideUi(lang)
  const page = getLocalizedSeoPage(sourcePage, lang)
  const enEquivalentPath = EN_EQUIVALENT_BY_TR_PATH[sourcePage.path]
  const canObserve = typeof window !== 'undefined' && 'IntersectionObserver' in window
  const relatedPages = getLocalizedSeoPages(
    SEO_PAGES.filter((candidate) => candidate.path !== sourcePage.path).slice(0, 4),
    lang,
  )
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
    <div className="seo-page">
      <Navbar />
      <main id="main-content">
        <header className="seo-hero">
          <div className="seo-container seo-hero-grid">
            <motion.div
              className="seo-hero-copy"
              key={`${lang}-${page.slug}-copy`}
              {...reveal}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              <div
                className="seo-guide-localized-copy"
                lang={page.contentLanguage}
                dir={lang === 'ar' && page.contentLanguage === 'en' ? 'ltr' : undefined}
              >
                <p className="seo-eyebrow">{page.eyebrow}</p>
                <h1>{page.title}</h1>
                <p className="seo-lead">{page.intro}</p>
              </div>
              {page.isFallback && (
                <p className="seo-language-note" role="note">
                  <Languages size={17} aria-hidden="true" /> {ui.fallbackNotice}
                </p>
              )}
              <div className="seo-hero-actions">
                <Link to="/register" className="btn-primary">
                  {ui.analyzeCta} <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <Link to="/ats-cv-kontrol/" className="btn-outline">
                  {ui.atsCta}
                </Link>
              </div>
              <div className="seo-meta" aria-label={ui.contentInfo}>
                <span><Clock3 size={15} aria-hidden="true" /> {page.readingTime}</span>
                <span>{ui.updated}: {formatUpdatedAt(page.updatedAt, ui.locale)}</span>
              </div>
              <div className="seo-trust-note">
                <ShieldCheck size={18} aria-hidden="true" />
                <p>
                  <strong>{ui.editorialTeam}</strong>
                  {ui.editorialNote}
                  <Link className="seo-editorial-link" to="/editoryal-politika/">
                    {ui.editorialPolicyLink || 'Editoryal yaklaşımımız'}
                  </Link>
                </p>
              </div>
            </motion.div>

            <motion.div
              className="seo-product-visual"
              aria-label={ui.sampleAria}
              key={`${lang}-${page.slug}-sample`}
              initial={reduceMotion ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: reduceMotion ? 0 : 0.06, ease: 'easeOut' }}
            >
              <div className="seo-product-head">
                <span><FileSearch size={18} aria-hidden="true" /> {ui.sampleSummary}</span>
                <strong>84/100</strong>
              </div>
              <div className="seo-score-track" aria-hidden="true"><span /></div>
              <div className="seo-product-checks">
                <p><CheckCircle2 size={17} /> {ui.sampleChecks[0]}</p>
                <p><CheckCircle2 size={17} /> {ui.sampleChecks[1]}</p>
                <p><ShieldCheck size={17} /> {ui.sampleChecks[2]}</p>
              </div>
              <div className="seo-product-note">{ui.sampleNote}</div>
            </motion.div>
          </div>
        </header>

        <nav className="seo-jump-band" aria-label={ui.contents}>
          <div className="seo-container">
            <p className="seo-jump-title">{ui.inThisGuide}</p>
            <div className="seo-highlight-grid">
              {page.sections.map((section, index) => (
                <a href={`#${sectionId(page.slug, index)}`} key={section.heading}>
                  <CheckCircle2 size={16} aria-hidden="true" /> {section.heading}
                </a>
              ))}
              <a href={`#${page.slug}-faq-title`}>
                <CheckCircle2 size={16} aria-hidden="true" /> {ui.faq}
              </a>
            </div>
          </div>
        </nav>

        <article className="seo-container seo-article">
          <div
            className="seo-article-main"
            lang={page.contentLanguage}
            dir={lang === 'ar' && page.contentLanguage === 'en' ? 'ltr' : undefined}
          >
            {page.sections.map((section, index) => (
              <React.Fragment key={section.heading}>
                <motion.section
                  id={sectionId(page.slug, index)}
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
                {index === 1 && <AdSlot placement="article_mid" />}
              </React.Fragment>
            ))}

            <motion.section
              className="seo-faq"
              aria-labelledby={`${page.slug}-faq-title`}
              {...inViewReveal}
              transition={{ duration: 0.24, ease: 'easeOut' }}
            >
              <p className="seo-eyebrow">{ui.faq}</p>
              <h2 id={`${page.slug}-faq-title`}>{ui.questionsAbout(page.title)}</h2>
              {page.faq.map((item) => (
                <details key={item.question}>
                  <summary>{item.question}</summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </motion.section>

            <AdSlot placement="article_end" />
          </div>

          <aside className="seo-related" aria-label={ui.relatedGuides}>
            <h2>{ui.relatedGuides}</h2>
            <p>{ui.relatedDescription}</p>
            {enEquivalentPath && (
              <Link to={enEquivalentPath} className="seo-related-en">
                <Languages size={15} aria-hidden="true" />{' '}
                {lang === 'tr' ? 'İngilizce ürün sayfasını görüntüle' : 'View the English product page'}
                {' '}<ArrowRight size={15} aria-hidden="true" />
              </Link>
            )}
            {relatedPages.map((relatedPage) => (
              <Link to={relatedPage.path} key={relatedPage.path}>
                {relatedPage.eyebrow} <ArrowRight size={15} aria-hidden="true" />
              </Link>
            ))}
            <Link to="/rehber/" className="seo-related-all">
              {ui.allGuides} <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </aside>
        </article>

        <section className="seo-final-cta">
          <div className="seo-container">
            <div>
              <p className="seo-eyebrow">{ui.finalEyebrow}</p>
              <h2>{ui.finalTitle}</h2>
              <p>{ui.finalDescription}</p>
            </div>
            <Link to="/register" className="btn-primary">
              {ui.createAccount} <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
