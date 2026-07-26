import React from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, BookOpen, Clock3, Languages } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { SEO_PAGES } from '../content/seoPages'
import { getGuideUi, getLocalizedSeoPages } from '../content/guideI18n'
import { useLanguage } from '../i18n/LanguageContext'

const CATEGORY_MATCHERS = [
  (page) => ['/cv-analiz/', '/ats-cv-kontrol/', '/ats-uyumlu-cv/'].includes(page.path),
  (page) => page.path.startsWith('/rehber/'),
  (page) => page.path.startsWith('/cv-ornekleri/'),
  (page) => page.path.startsWith('/metodoloji/'),
]

export default function GuideHubPage() {
  const { lang } = useLanguage()
  const reduceMotion = useReducedMotion()
  const ui = getGuideUi(lang)
  const pages = getLocalizedSeoPages(SEO_PAGES, lang)
  const canObserve = typeof window !== 'undefined' && 'IntersectionObserver' in window
  const reveal = reduceMotion
    ? {}
    : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }
  const inViewReveal = reduceMotion || !canObserve
    ? {}
    : {
        initial: { opacity: 0, y: 10 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, amount: 0.12 },
      }

  return (
    <div className="seo-page">
      <Navbar />
      <main id="main-content">
        <header className="seo-hub-hero">
          <motion.div
            className="seo-container"
            key={lang}
            {...reveal}
            transition={{ duration: 0.28, ease: 'easeOut' }}
          >
            <p className="seo-eyebrow">{ui.hubEyebrow}</p>
            <h1>{ui.hubTitle}</h1>
            <p className="seo-lead">{ui.hubDescription}</p>
            <div className="seo-hub-summary" aria-label={ui.hubTitle}>
              <span><BookOpen size={17} aria-hidden="true" /> {ui.guideCount(pages.length)}</span>
              <span><Clock3 size={17} aria-hidden="true" /> {ui.shortFormat}</span>
            </div>
            {ui.fallbackNotice && (
              <p className="seo-language-note" role="note">
                <Languages size={17} aria-hidden="true" /> {ui.fallbackNotice}
              </p>
            )}
          </motion.div>
        </header>

        <div className="seo-container seo-hub-content">
          {CATEGORY_MATCHERS.map((matches, categoryIndex) => {
            const categoryPages = pages.filter(matches)
            const [title, description] = ui.categories[categoryIndex]
            if (!categoryPages.length) return null

            return (
              <motion.section
                className="seo-hub-section"
                key={`${lang}-${title}`}
                {...inViewReveal}
                transition={{ duration: 0.26, ease: 'easeOut' }}
              >
                <div className="seo-hub-section-heading">
                  <h2>{title}</h2>
                  <p>{description}</p>
                </div>
                <div className="seo-guide-grid">
                  {categoryPages.map((page, pageIndex) => (
                    <motion.article
                      className="seo-guide-card"
                      key={page.path}
                      {...inViewReveal}
                      transition={{ duration: 0.22, delay: reduceMotion ? 0 : pageIndex * 0.04 }}
                    >
                      <p
                        className="seo-eyebrow"
                        lang={page.contentLanguage}
                        dir={lang === 'ar' && page.contentLanguage === 'en' ? 'ltr' : undefined}
                      >
                        {page.eyebrow}
                      </p>
                      <h3
                        lang={page.contentLanguage}
                        dir={lang === 'ar' && page.contentLanguage === 'en' ? 'ltr' : undefined}
                      >
                        <Link to={page.path}>{page.title}</Link>
                      </h3>
                      <p
                        lang={page.contentLanguage}
                        dir={lang === 'ar' && page.contentLanguage === 'en' ? 'ltr' : undefined}
                      >
                        {page.description}
                      </p>
                      <div className="seo-guide-card-footer">
                        <span><Clock3 size={15} aria-hidden="true" /> {page.readingTime}</span>
                        <Link to={page.path} aria-label={ui.readGuideLabel(page.title)}>
                          {ui.readGuide} <ArrowRight size={16} aria-hidden="true" />
                        </Link>
                      </div>
                    </motion.article>
                  ))}
                </div>
              </motion.section>
            )
          })}
        </div>
      </main>
      <Footer />
    </div>
  )
}
