import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { findSeoPage } from '../content/seoPages'
import { findEnSeoPage, EN_EQUIVALENT_BY_TR_PATH } from '../content/enSeoPages'
import { getGuideUi, getLocalizedSeoPage } from '../content/guideI18n'
import { useLanguage } from '../i18n/LanguageContext'

const SITE_URL = 'https://cvanalyzer.dev'

const PUBLIC_META = {
  '/': {
    title: 'Ücretsiz CV Analiz ve ATS Kontrolü | CV Analyzer',
    description: 'CV’nizi ücretsiz analiz edin; ATS uyumunu, iş ilanı eşleşmesini, beceri boşluklarını ve geliştirme önerilerini tek ekranda görün.',
  },
  '/pricing': {
    title: 'CV Analyzer Planları ve Özellikleri',
    description: 'CV analizi, ATS kontrolü, iş eşleşmesi ve CV geliştirme özelliklerini karşılaştırın.',
  },
  '/about': {
    title: 'CV Analyzer Hakkında',
    description: 'CV Analyzer’ın özgeçmiş değerlendirmesini daha açık, erişilebilir ve uygulanabilir hale getirme yaklaşımını öğrenin.',
  },
  '/rehber': {
    title: 'CV Hazırlama ve ATS Rehberleri | CV Analyzer',
    description: 'CV hazırlama, ATS okunabilirliği, mülakat, ön yazı ve role özel CV örnekleri için özgün ve uygulanabilir rehberleri inceleyin.',
  },
  '/privacy': {
    title: 'Gizlilik Politikası | CV Analyzer',
    description: 'CV Analyzer’ın CV dosyalarını, analiz sonuçlarını ve hesap verilerini nasıl işlediğini inceleyin.',
  },
  '/terms': {
    title: 'Kullanım Koşulları | CV Analyzer',
    description: 'CV Analyzer hizmetlerinin kullanım koşullarını ve kullanıcı sorumluluklarını inceleyin.',
  },
}

function upsertMeta(selector, attributes) {
  let node = document.head.querySelector(selector)
  if (!node) {
    node = document.createElement('meta')
    document.head.appendChild(node)
  }
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value))
}

function upsertCanonical(href) {
  let node = document.head.querySelector('link[rel="canonical"]')
  if (!node) {
    node = document.createElement('link')
    node.setAttribute('rel', 'canonical')
    document.head.appendChild(node)
  }
  node.setAttribute('href', href)
}

function upsertHreflangLinks(links) {
  document.head.querySelectorAll('link[data-hreflang-managed="true"]').forEach((node) => node.remove())
  links.forEach(({ hreflang, href }) => {
    const node = document.createElement('link')
    node.setAttribute('rel', 'alternate')
    node.setAttribute('hreflang', hreflang)
    node.setAttribute('href', href)
    node.setAttribute('data-hreflang-managed', 'true')
    document.head.appendChild(node)
  })
}

function setStructuredData(data) {
  const existing = document.getElementById('route-structured-data')
  if (!data) {
    existing?.remove()
    return
  }
  const node = existing || document.createElement('script')
  node.id = 'route-structured-data'
  node.type = 'application/ld+json'
  node.textContent = JSON.stringify(data)
  if (!existing) document.head.appendChild(node)
}

function buildPageSchema(page) {
  const canonical = `${SITE_URL}${page.path}`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article',
        headline: page.title,
        description: page.description,
        dateModified: page.updatedAt,
        datePublished: page.updatedAt,
        inLanguage: page.contentLanguage === 'tr' ? 'tr-TR' : 'en-US',
        mainEntityOfPage: canonical,
        author: { '@type': 'Organization', name: 'CV Analyzer', url: SITE_URL },
        publisher: { '@type': 'Organization', name: 'CV Analyzer', url: SITE_URL },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'CV Analyzer', item: `${SITE_URL}/` },
          { '@type': 'ListItem', position: 2, name: page.title, item: canonical },
        ],
      },
      {
        '@type': 'FAQPage',
        mainEntity: page.faq.map((item) => ({
          '@type': 'Question',
          name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
    ],
  }
}

function buildEnPageSchema(page) {
  const canonical = `${SITE_URL}${page.path}`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article',
        headline: page.title,
        description: page.description,
        dateModified: page.updatedAt,
        datePublished: page.updatedAt,
        inLanguage: 'en-US',
        mainEntityOfPage: canonical,
        author: { '@type': 'Organization', name: 'CV Analyzer', url: SITE_URL },
        publisher: { '@type': 'Organization', name: 'CV Analyzer', url: SITE_URL },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'CV Analyzer', item: `${SITE_URL}/` },
          { '@type': 'ListItem', position: 2, name: page.title, item: canonical },
        ],
      },
      {
        '@type': 'FAQPage',
        mainEntity: page.faq.map((item) => ({
          '@type': 'Question',
          name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
    ],
  }
}

export default function SEOManager() {
  const { pathname } = useLocation()
  const { lang, setRouteLangOverride } = useLanguage()

  useEffect(() => {
    const enPage = findEnSeoPage(pathname)

    if (enPage) {
      setRouteLangOverride('en')
      const canonical = `${SITE_URL}${enPage.path}`

      document.title = enPage.seoTitle
      upsertMeta('meta[name="description"]', { name: 'description', content: enPage.description })
      upsertMeta('meta[name="robots"]', { name: 'robots', content: 'index, follow, max-image-preview:large' })
      upsertMeta('meta[property="og:title"]', { property: 'og:title', content: enPage.seoTitle })
      upsertMeta('meta[property="og:description"]', { property: 'og:description', content: enPage.description })
      upsertMeta('meta[property="og:url"]', { property: 'og:url', content: canonical })
      upsertMeta('meta[property="og:locale"]', { property: 'og:locale', content: 'en_US' })
      upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: enPage.seoTitle })
      upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: enPage.description })
      upsertCanonical(canonical)
      upsertHreflangLinks([
        { hreflang: 'en', href: canonical },
        ...(enPage.trPath ? [{ hreflang: 'tr', href: `${SITE_URL}${enPage.trPath}` }] : []),
        { hreflang: 'x-default', href: canonical },
      ])
      setStructuredData(buildEnPageSchema(enPage))
      return
    }

    setRouteLangOverride(null)

    const sourcePage = findSeoPage(pathname)
    const page = sourcePage ? getLocalizedSeoPage(sourcePage, lang) : null
    const guideUi = getGuideUi(lang)
    const normalizedPath = pathname !== '/' ? pathname.replace(/\/$/, '') : '/'
    const publicMeta = normalizedPath === '/rehber'
      ? {
          title: `${guideUi.hubTitle} | CV Analyzer`,
          description: guideUi.hubDescription,
        }
      : PUBLIC_META[normalizedPath]
    const indexable = Boolean(page || publicMeta)
    const title = page?.seoTitle || publicMeta?.title || 'CV Analyzer'
    const description = page?.description || publicMeta?.description || 'CV Analyzer kullanıcı alanı.'
    const canonicalPath = page?.path || (normalizedPath === '/' ? '/' : `${normalizedPath}/`)
    const canonical = `${SITE_URL}${canonicalPath === '/' ? '/' : canonicalPath}`

    document.title = title
    upsertMeta('meta[name="description"]', { name: 'description', content: description })
    upsertMeta('meta[name="robots"]', {
      name: 'robots',
      content: indexable ? 'index, follow, max-image-preview:large' : 'noindex, nofollow',
    })
    upsertMeta('meta[property="og:title"]', { property: 'og:title', content: title })
    upsertMeta('meta[property="og:description"]', { property: 'og:description', content: description })
    upsertMeta('meta[property="og:url"]', { property: 'og:url', content: canonical })
    upsertMeta('meta[property="og:locale"]', {
      property: 'og:locale',
      content: guideUi.locale.replace('-', '_'),
    })
    upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: title })
    upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: description })
    upsertCanonical(canonical)

    const enEquivalentPath = EN_EQUIVALENT_BY_TR_PATH[canonicalPath]
    upsertHreflangLinks(
      enEquivalentPath
        ? [
            { hreflang: 'tr', href: canonical },
            { hreflang: 'en', href: `${SITE_URL}${enEquivalentPath}` },
            { hreflang: 'x-default', href: `${SITE_URL}${enEquivalentPath}` },
          ]
        : [],
    )
    setStructuredData(page ? buildPageSchema(page) : null)
  }, [lang, pathname, setRouteLangOverride])

  return null
}
