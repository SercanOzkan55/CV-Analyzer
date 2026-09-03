import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { findSeoPage } from '../content/seoPages'
import { findEnSeoPage, EN_EQUIVALENT_BY_TR_PATH } from '../content/enSeoPages'
import { getGuideUi, getLocalizedSeoPage } from '../content/guideI18n'
import { EDITORIAL_POLICY } from '../content/editorialPolicy'
import { EDITORIAL_POLICY_EN } from '../content/editorialPolicyEn'
import { CONTACT_EN, CONTACT_TR } from '../content/contactInfo'
import { PRIVACY_EN, PRIVACY_TR, TERMS_EN, TERMS_TR } from '../content/legalPolicies'
import { useLanguage } from '../i18n/LanguageContext'

const SITE_URL = 'https://cvanalyzer.dev'
const ATS_TEXT_CHECK_PATH = '/araclar/ats-metin-kontrolu'

const PUBLIC_META = {
  '/': {
    title: 'CV Analyzer — Ücretsiz CV Analizi ve ATS Uyum Kontrolü',
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
  '/editoryal-politika': {
    title: EDITORIAL_POLICY.seoTitle,
    description: EDITORIAL_POLICY.description,
  },
  '/rehber': {
    title: 'CV Hazırlama ve ATS Rehberleri | CV Analyzer',
    description: 'CV hazırlama, ATS okunabilirliği, mülakat, ön yazı ve role özel CV örnekleri için özgün ve uygulanabilir rehberleri inceleyin.',
  },
  '/privacy': {
    title: PRIVACY_TR.seoTitle,
    description: PRIVACY_TR.description,
  },
  '/terms': {
    title: TERMS_TR.seoTitle,
    description: TERMS_TR.description,
  },
  '/iletisim': {
    title: CONTACT_TR.seoTitle,
    description: CONTACT_TR.description,
  },
  [ATS_TEXT_CHECK_PATH]: {
    title: 'Ücretsiz ATS Metin Ön Kontrolü | CV Analyzer',
    description: 'CV metninizi bölüm başlıkları, iletişim bilgileri, okuma düzeni ve kanıta dayalı deneyim anlatımı açısından tarayıcınızda ücretsiz kontrol edin.',
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

const EN_PUBLIC_META = {
  '/en': {
    title: 'English CV, ATS and Application Guides | CV Analyzer',
    description: 'Practical English guidance for reviewing CVs, checking ATS readability, preparing applications and practising interviews across varied European markets.',
    trPath: '/rehber/',
  },
  '/en/about': {
    title: 'About CV Analyzer',
    description: 'Learn how CV Analyzer provides explainable document checks and practical guidance without promising a hiring outcome.',
    trPath: '/about/',
  },
  '/en/privacy': {
    title: PRIVACY_EN.seoTitle,
    description: PRIVACY_EN.description,
    trPath: '/privacy/',
  },
  '/en/terms': {
    title: TERMS_EN.seoTitle,
    description: TERMS_EN.description,
    trPath: '/terms/',
  },
  '/en/pricing': {
    title: 'CV Analyzer Plans and Features',
    description: 'Compare CV analysis, ATS checking and career-tool plans available from CV Analyzer.',
    trPath: '/pricing/',
  },
  '/en/editorial-policy': {
    title: EDITORIAL_POLICY_EN.seoTitle,
    description: EDITORIAL_POLICY_EN.description,
    trPath: '/editoryal-politika/',
  },
  '/en/contact': {
    title: CONTACT_EN.seoTitle,
    description: CONTACT_EN.description,
    trPath: '/iletisim/',
  },
}

const EN_PUBLIC_BY_TR_PATH = Object.fromEntries(
  Object.entries(EN_PUBLIC_META).map(([path, meta]) => [meta.trPath, `${path}/`]),
)

function setSiteStructuredDataEnabled(enabled) {
  const node = document.getElementById('site-structured-data')
  if (node) node.type = enabled ? 'application/ld+json' : 'application/json'
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
        author: { '@type': 'Person', name: 'Sercan Özkan', jobTitle: 'Kurucu geliştirici ve içerik sorumlusu', url: `${SITE_URL}/about/` },
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
        inLanguage: 'en',
        mainEntityOfPage: canonical,
        author: { '@type': 'Person', name: 'Sercan Özkan', jobTitle: 'Founder-developer and publishing lead', url: `${SITE_URL}/about/` },
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

function buildAtsTextCheckSchema() {
  const canonical = `${SITE_URL}${ATS_TEXT_CHECK_PATH}/`
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'ATS Metin Ön Kontrolü',
    description: PUBLIC_META[ATS_TEXT_CHECK_PATH].description,
    url: canonical,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Any',
    browserRequirements: 'Requires JavaScript',
    inLanguage: 'tr-TR',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'TRY',
    },
    featureList: [
      'Standart CV bölüm başlıklarını kontrol etme',
      'Düz metin okuma düzenini kontrol etme',
      'İletişim bilgisi bulunabilirliğini kontrol etme',
      'Eylem ve ölçülebilir kanıt ifadelerini açıklama',
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
      setSiteStructuredDataEnabled(false)

      document.title = enPage.seoTitle
      upsertMeta('meta[name="description"]', { name: 'description', content: enPage.description })
      upsertMeta('meta[name="robots"]', {
        name: 'robots',
        content: enPage.indexable === false ? 'noindex, follow' : 'index, follow, max-image-preview:large',
      })
      upsertMeta('meta[property="og:title"]', { property: 'og:title', content: enPage.seoTitle })
      upsertMeta('meta[property="og:description"]', { property: 'og:description', content: enPage.description })
      upsertMeta('meta[property="og:url"]', { property: 'og:url', content: canonical })
      upsertMeta('meta[property="og:locale"]', { property: 'og:locale', content: 'en_GB' })
      upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: enPage.seoTitle })
      upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: enPage.description })
      upsertCanonical(canonical)
      upsertHreflangLinks(enPage.indexable === false ? [] : [
        { hreflang: 'en', href: canonical },
        ...(enPage.trPath ? [{ hreflang: 'tr', href: `${SITE_URL}${enPage.trPath}` }] : []),
        { hreflang: 'x-default', href: `${SITE_URL}/en/` },
      ])
      setStructuredData(enPage.indexable === false ? null : buildEnPageSchema(enPage))
      return
    }

    const normalizedPath = pathname !== '/' ? pathname.replace(/\/$/, '') : '/'
    const enPublicMeta = EN_PUBLIC_META[normalizedPath]
    if (enPublicMeta) {
      setRouteLangOverride('en')
      setSiteStructuredDataEnabled(false)
      const canonical = `${SITE_URL}${normalizedPath}/`
      document.title = enPublicMeta.title
      upsertMeta('meta[name="description"]', { name: 'description', content: enPublicMeta.description })
      upsertMeta('meta[name="robots"]', { name: 'robots', content: 'index, follow, max-image-preview:large' })
      upsertMeta('meta[property="og:title"]', { property: 'og:title', content: enPublicMeta.title })
      upsertMeta('meta[property="og:description"]', { property: 'og:description', content: enPublicMeta.description })
      upsertMeta('meta[property="og:url"]', { property: 'og:url', content: canonical })
      upsertMeta('meta[property="og:locale"]', { property: 'og:locale', content: 'en_GB' })
      upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: enPublicMeta.title })
      upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: enPublicMeta.description })
      upsertCanonical(canonical)
      upsertHreflangLinks([
        { hreflang: 'en', href: canonical },
        { hreflang: 'tr', href: `${SITE_URL}${enPublicMeta.trPath}` },
        { hreflang: 'x-default', href: `${SITE_URL}/en/` },
      ])
      setStructuredData({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: enPublicMeta.title,
        description: enPublicMeta.description,
        url: canonical,
        inLanguage: 'en',
      })
      return
    }

    setRouteLangOverride(null)
    setSiteStructuredDataEnabled(true)

    const sourcePage = findSeoPage(pathname)
    const page = sourcePage ? getLocalizedSeoPage(sourcePage, lang) : null
    const guideUi = getGuideUi(lang)
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

    const enEquivalentPath = EN_EQUIVALENT_BY_TR_PATH[canonicalPath] || EN_PUBLIC_BY_TR_PATH[canonicalPath]
    upsertHreflangLinks(
      enEquivalentPath
        ? [
            { hreflang: 'tr', href: canonical },
            { hreflang: 'en', href: `${SITE_URL}${enEquivalentPath}` },
            { hreflang: 'x-default', href: `${SITE_URL}${enEquivalentPath}` },
          ]
        : [],
    )
    setStructuredData(
      page
        ? buildPageSchema(page)
        : normalizedPath === ATS_TEXT_CHECK_PATH
          ? buildAtsTextCheckSchema()
          : null,
    )
  }, [lang, pathname, setRouteLangOverride])

  return null
}
