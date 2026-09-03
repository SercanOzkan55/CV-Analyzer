import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SEO_PAGES } from '../src/content/seoPages.js'
import { EN_SEO_PAGES, EN_EQUIVALENT_BY_TR_PATH } from '../src/content/enSeoPages.js'
import { EDITORIAL_POLICY } from '../src/content/editorialPolicy.js'
import { EDITORIAL_POLICY_EN } from '../src/content/editorialPolicyEn.js'
import { CONTACT_EN, CONTACT_TR, CONTACT_EMAIL, CONTACT_UPDATED_AT } from '../src/content/contactInfo.js'
import { POLICY_UPDATED_AT, PRIVACY_EN, PRIVACY_TR, TERMS_EN, TERMS_TR } from '../src/content/legalPolicies.js'

const SITE_URL = 'https://cvanalyzer.dev'
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distDir = path.join(rootDir, 'dist')
const baseHtml = await readFile(path.join(distDir, 'index.html'), 'utf8')

const PUBLIC_ROUTES = [
  { path: '/', enPath: '/en/', title: 'CV Analyzer — Ücretsiz CV Analizi ve ATS Uyum Kontrolü', description: 'CV’nizi ücretsiz analiz edin; ATS uyumunu, iş ilanı eşleşmesini, beceri boşluklarını ve geliştirme önerilerini tek ekranda görün.' },
  { path: '/rehber/', enPath: '/en/', title: 'CV Hazırlama ve ATS Rehberleri | CV Analyzer', description: 'CV hazırlama, ATS okunabilirliği, mülakat, ön yazı ve role özel CV örnekleri için özgün ve uygulanabilir rehberleri inceleyin.' },
  { path: '/pricing/', enPath: '/en/pricing/', title: 'CV Analyzer Planları ve Özellikleri', description: 'CV analizi, ATS kontrolü, iş eşleşmesi ve CV geliştirme özelliklerini karşılaştırın.' },
  { path: '/about/', enPath: '/en/about/', title: 'CV Analyzer Hakkında', description: 'CV Analyzer’ın özgeçmiş değerlendirmesini daha açık, erişilebilir ve uygulanabilir hale getirme yaklaşımını öğrenin.' },
  { path: '/araclar/ats-metin-kontrolu/', title: 'Ücretsiz ATS Metin Ön Kontrolü | CV Analyzer', description: 'CV metninizi bölüm başlıkları, iletişim bilgileri, okuma düzeni ve kanıta dayalı deneyim anlatımı açısından tarayıcınızda ücretsiz kontrol edin.' },
  { path: EDITORIAL_POLICY.path, enPath: EDITORIAL_POLICY_EN.path, title: EDITORIAL_POLICY.seoTitle, description: EDITORIAL_POLICY.description },
  { path: PRIVACY_TR.path, enPath: PRIVACY_EN.path, title: PRIVACY_TR.seoTitle, description: PRIVACY_TR.description },
  { path: TERMS_TR.path, enPath: TERMS_EN.path, title: TERMS_TR.seoTitle, description: TERMS_TR.description },
  { path: CONTACT_TR.path, enPath: CONTACT_EN.path, title: CONTACT_TR.seoTitle, description: CONTACT_TR.description },
]

const EN_PUBLIC_ROUTES = [
  { path: '/en/', trPath: '/rehber/', title: 'English CV, ATS and Application Guides | CV Analyzer', description: 'Practical English guidance for reviewing CVs, checking ATS readability, preparing applications and practising interviews across varied European markets.' },
  { path: '/en/about/', trPath: '/about/', title: 'About CV Analyzer', description: 'Learn how CV Analyzer provides explainable document checks and practical guidance without promising a hiring outcome.' },
  { path: PRIVACY_EN.path, trPath: PRIVACY_TR.path, title: PRIVACY_EN.seoTitle, description: PRIVACY_EN.description },
  { path: TERMS_EN.path, trPath: TERMS_TR.path, title: TERMS_EN.seoTitle, description: TERMS_EN.description },
  { path: '/en/pricing/', trPath: '/pricing/', title: 'CV Analyzer Plans and Features', description: 'Compare CV analysis, ATS checking and career-tool plans available from CV Analyzer.' },
  { path: EDITORIAL_POLICY_EN.path, trPath: EDITORIAL_POLICY.path, title: EDITORIAL_POLICY_EN.seoTitle, description: EDITORIAL_POLICY_EN.description },
  { path: CONTACT_EN.path, trPath: CONTACT_TR.path, title: CONTACT_EN.seoTitle, description: CONTACT_EN.description },
]

const NOINDEX_ROUTES = [
  '/login', '/register', '/forgot-password', '/dashboard', '/analyze', '/career-studio',
  '/feedback', '/history', '/settings', '/profile', '/compare', '/my-cvs', '/recruiter',
  '/premium', '/cv-builder', '/cover-letter', '/interview-simulator', '/job-tracker',
  '/agents', '/data-center', '/template-marketplace', '/admin/billing', '/admin/ops',
  '/recruiter-hub',
]

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function replaceTag(html, pattern, replacement) {
  return pattern.test(html) ? html.replace(pattern, replacement) : html.replace('</head>', `${replacement}\n</head>`)
}

function applyMeta(html, { title, description, canonical, robots = 'index, follow, max-image-preview:large', schema, htmlLang = 'tr', ogLocale, alternates = [] }) {
  let output = html.replace(/<html\s+lang="[^"]*"/, `<html lang="${htmlLang}"`)
  output = output.replace(/<title>.*?<\/title>/s, `<title>${escapeHtml(title)}</title>`)
  output = replaceTag(output, /<meta\s+name="description"[^>]*>/i, `<meta name="description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+name="robots"[^>]*>/i, `<meta name="robots" content="${escapeHtml(robots)}" />`)
  output = replaceTag(output, /<link\s+rel="canonical"[^>]*>/i, `<link rel="canonical" href="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+property="og:title"[^>]*>/i, `<meta property="og:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+property="og:description"[^>]*>/i, `<meta property="og:description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+property="og:url"[^>]*>/i, `<meta property="og:url" content="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+property="og:locale"[^>]*>/i, `<meta property="og:locale" content="${escapeHtml(ogLocale || (htmlLang === 'en' ? 'en_GB' : 'tr_TR'))}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(description)}" />`)
  if (alternates.length) {
    const links = alternates.map(({ hreflang, href }) => `<link rel="alternate" hreflang="${escapeHtml(hreflang)}" href="${escapeHtml(href)}" data-hreflang-managed="true" />`).join('')
    output = output.replace('</head>', `${links}\n</head>`)
  }
  if (schema) {
    output = output.replace('</head>', `<script id="route-structured-data" type="application/ld+json">${JSON.stringify(schema).replaceAll('<', '\\u003c')}</script>\n</head>`)
  }
  return output
}

function removeSiteStructuredData(html) {
  return html.replace(/\s*<script\s+id="site-structured-data"[^>]*>[\s\S]*?<\/script>/i, '')
}

// Contact and legal documents carry multi-paragraph sections and bullet lists,
// so they share this renderer instead of the single-paragraph `pages` table
// further down. Bare URLs become links, which matters for the advertising
// opt-out routes in the privacy policy.
const URL_PATTERN = /(https?:\/\/[^\s]+)/g

// Cloudflare's Email Address Obfuscation rewrites mailto links and bare
// addresses into /cdn-cgi/l/email-protection stubs that need a decoder script.
// That script is injected after our nginx sub_filter has stamped nonces, so
// 'strict-dynamic' blocks it and the address renders broken. These comment
// markers are Cloudflare's documented opt-out and need no dashboard change.
// https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/
function emailOff(html) {
  return `<!--email_off-->${html}<!--/email_off-->`
}

const EMAIL_PATTERN = /([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g

function protectEmails(value = '') {
  return String(value).split(EMAIL_PATTERN)
    .map((part, index) => (index % 2 === 0 ? part : emailOff(part)))
    .join('')
}

function escapeHtmlWithLinks(value = '') {
  return String(value)
    .split(URL_PATTERN)
    .map((part, index) => (index % 2 === 0
      ? protectEmails(escapeHtml(part))
      : `<a href="${escapeHtml(part)}" target="_blank" rel="noopener noreferrer">${escapeHtml(part)}</a>`))
    .join('')
}

function staticDocContent(page, { isEnglish, updatedAt, email }) {
  const sections = page.sections.map((section) => `
    <section>
      <h2>${escapeHtml(section.heading)}</h2>
      ${section.paragraphs.map((paragraph) => `<p>${escapeHtmlWithLinks(paragraph)}</p>`).join('')}
      ${section.bullets ? `<ul>${section.bullets.map((item) => `<li>${escapeHtmlWithLinks(item)}</li>`).join('')}</ul>` : ''}
    </section>`).join('')
  const updatedLabel = isEnglish ? 'Last updated' : 'Son güncelleme'
  const emailLine = email ? `<p>${emailOff(`<a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>`)}</p>` : ''
  return `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>${escapeHtml(page.title)}</h1><p><time datetime="${escapeHtml(updatedAt)}">${updatedLabel}: ${escapeHtml(updatedAt)}</time></p><p>${escapeHtmlWithLinks(page.intro)}</p>${emailLine}${sections}</article></main>`
}

function contactSchema(page, { isEnglish }) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ContactPage',
    name: page.title,
    description: page.description,
    url: `${SITE_URL}${page.path}`,
    inLanguage: isEnglish ? 'en' : 'tr-TR',
    mainEntity: {
      '@type': 'Organization',
      name: 'CV Analyzer',
      url: SITE_URL,
      email: CONTACT_EMAIL,
      contactPoint: [{
        '@type': 'ContactPoint',
        contactType: 'customer support',
        email: CONTACT_EMAIL,
        availableLanguage: ['tr', 'en'],
      }],
    },
  }
}

function pageSchema(page) {
  const canonical = `${SITE_URL}${page.path}`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article', headline: page.title, description: page.description,
        datePublished: page.updatedAt, dateModified: page.updatedAt, inLanguage: 'tr-TR',
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
          '@type': 'Question', name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
    ],
  }
}

function enPageSchema(page) {
  const canonical = `${SITE_URL}${page.path}`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article', headline: page.title, description: page.description,
        datePublished: page.updatedAt, dateModified: page.updatedAt, inLanguage: 'en',
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
          '@type': 'Question', name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
    ],
  }
}

function staticEnPageContent(page) {
  const highlights = `<ul>${page.highlights.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
  const sections = page.sections.map((section) => `
    <section>
      <h2>${escapeHtml(section.heading)}</h2>
      ${section.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
      ${section.bullets ? `<ul>${section.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
    </section>`).join('')
  const faq = page.faq.map((item) => `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`).join('')
  return `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><header><p class="seo-eyebrow">${escapeHtml(page.eyebrow)}</p><h1>${escapeHtml(page.title)}</h1><p>${escapeHtml(page.intro)}</p></header><section><h2>Why use it</h2>${highlights}</section>${sections}<section class="seo-faq"><h2>Frequently asked questions</h2>${faq}</section><p><a href="${escapeHtml(page.ctaHref)}">${escapeHtml(page.ctaLabel)}</a></p></article></main>`
}

function staticEnPublicChrome(content) {
  return `
    <header data-prerendered="true">
      <nav aria-label="Main navigation">
        <a href="/">CV Analyzer</a>
        <a href="/en/">English guides</a>
        <a href="/en/pricing/">Pricing</a>
        <a href="/en/about/">About</a>
        <a href="/en/contact/">Contact</a>
      </nav>
    </header>
    ${content}
    <footer data-prerendered="true">
      <nav aria-label="Footer">
        <a href="/en/privacy/">Privacy Policy</a>
        <a href="/en/terms/">Terms of Use</a>
        <a href="/en/editorial-policy/">Editorial Policy</a>
        <a href="/en/contact/">Contact</a>
      </nav>
      <p>© 2026 CV Analyzer</p>
    </footer>`
}

function staticEnglishPublicPage(routePath) {
  if (routePath === '/en/') {
    const guides = EN_SEO_PAGES.filter((page) => page.indexable !== false).map(
      (page) => `<article><h2><a href="${escapeHtml(page.path)}">${escapeHtml(page.title)}</a></h2><p>${escapeHtml(page.description)}</p></article>`,
    ).join('')
    return staticEnPublicChrome(`<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>English CV, ATS and application guides</h1><p>Practical, country-neutral guidance for reviewing a CV, checking document readability, preparing for interviews and building truthful applications. CV conventions differ across Europe, so the specific vacancy and local requirements come first.</p><section><h2>Who these guides are for</h2><p>These pages are written for people applying in English, whether that means an international role, a multinational employer in their own country, or a move abroad. They assume no prior knowledge of applicant tracking systems and avoid advice that only works in one job market.</p><p>Where practice genuinely differs between countries — photographs, date of birth, references, CV length — we say so rather than presenting one national convention as a universal rule. A CV that is standard in Germany can look wrong in the United Kingdom, and neither is objectively correct.</p></section><section><h2>How we approach advice</h2><p>Every recommendation here is meant to be checkable against your own document. We do not promise interview rates, and we never suggest adding experience, results or skills you do not actually have. The aim is to help you present what is genuinely yours in a clearer, more relevant way.</p><p>Guides are reviewed before publication and revised when they fall out of date. Our editorial policy page explains that process and how to report an error.</p></section><section><h2>Where to start</h2><p>If you are unsure which guide you need: start with the ATS resume checker page when your applications get no response at all, and with the CV analyzer page when you want a section-by-section review of the document itself. If you already have interviews lined up, the interview preparation guide is the more useful entry point.</p></section>${guides}</article></main>`)
  }

  if (routePath === EDITORIAL_POLICY_EN.path) {
    const sections = EDITORIAL_POLICY_EN.sections.map((section) => `<section><h2>${escapeHtml(section.heading)}</h2>${section.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}</section>`).join('')
    return staticEnPublicChrome(`<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>${escapeHtml(EDITORIAL_POLICY_EN.title)}</h1><p><time datetime="${escapeHtml(EDITORIAL_POLICY_EN.updatedAt)}">Last updated: 3 September 2026</time></p><p>${escapeHtml(EDITORIAL_POLICY_EN.intro)}</p>${sections}</article></main>`)
  }

  if (routePath === CONTACT_EN.path) {
    return staticEnPublicChrome(staticDocContent(CONTACT_EN, { isEnglish: true, updatedAt: CONTACT_UPDATED_AT, email: CONTACT_EMAIL }))
  }

  if (routePath === PRIVACY_EN.path) {
    return staticEnPublicChrome(staticDocContent(PRIVACY_EN, { isEnglish: true, updatedAt: POLICY_UPDATED_AT }))
  }

  if (routePath === TERMS_EN.path) {
    return staticEnPublicChrome(staticDocContent(TERMS_EN, { isEnglish: true, updatedAt: POLICY_UPDATED_AT }))
  }

  const pages = {
    '/en/about/': ['About CV Analyzer', 'CV Analyzer is an independent product designed to turn CV review into understandable findings and practical next steps rather than a single opaque score.', [
      ['Why we built it', 'Feedback on a job application is usually either absent or reduced to a single line such as "your CV was not a match". CV Analyzer exists to make that feedback concrete and explainable: which section looks weak, why it looks weak, and what could be changed.'],
      ['Our approach', 'We review document structure, text readability, experience and skills evidence, and relevance to a target vacancy as separate signals. Results support the user’s own review and do not guarantee employment.'],
      ['Transparency and control', 'Suggestions are grounded in what the CV actually contains; we do not invent experience or skills. Users can manage and delete their saved analyses and CV versions from their account at any time.'],
      ['Who writes the guides', 'Founder-developer Sercan Özkan is accountable for publishing the guides and methodology pages. This does not claim recruiter credentials. Content is checked against product behaviour and revised when it falls out of date; the editorial policy explains the process.'],
      ['Independence', 'CV Analyzer is operated independently by founder-developer Sercan Özkan. We have no commercial relationship with any employer, job board or ATS vendor, so our assessments are not shaped by third-party interests.'],
      ['How the product is funded', 'The product is funded by paid subscriptions and by advertising shown on public content pages. Advertising revenue has no influence on analysis results; ads appear only alongside guide content and never inside analysis screens.'],
      ['Who the product is designed for', 'The product provides separate workflows for people preparing a first CV, changing role or sector, applying abroad, and authorised teams manually reviewing a candidate pool. This describes intended use, not measured user demographics. The tools do not make automated hiring decisions.'],
      ['We are explicit about our limits', 'There is a limit to what any CV analysis tool can do, and we do not hide it. We cannot reproduce the exact behaviour of every applicant tracking system on the market, we cannot anticipate an employer’s subjective judgement, and we do not produce hiring-probability predictions. Our methodology page sets out what we measure and what we deliberately do not.'],
      ['Contact', 'Questions about the product, privacy or our content can be sent through the contact page or to support@cvanalyzer.dev. General questions are answered within 1-2 working days; privacy and deletion requests within 30 days at the latest.'],
    ]],
    '/en/pricing/': ['CV Analyzer plans', 'Compare the options available for CV analysis, ATS readability checks and career tools. Current limits are always shown on the pricing screen inside the product.', [
      ['Start for free', 'The free plan covers core CV analysis, ATS readability checks and explainable improvement suggestions without a card. Daily analysis and AI tool usage are capped on this plan.'],
      ['What every plan includes', 'All plans include section structure review, text extraction quality checks, skills and experience analysis, and vacancy matching. Higher tiers add larger daily limits, retained history and additional career tools.'],
      ['Individual and team use', 'Different options support individual applicants and authorised recruitment teams. Recruiter tools assist manual review and do not make an automated hiring decision.'],
      ['Is the free plan enough?', 'For most people working on a single CV and preparing a handful of applications, the free plan is enough. The daily allowance covers editing a CV and re-checking it. If you are applying to many roles at once, tailoring the document for each vacancy, or making heavy use of the AI tools, a higher tier will suit you better.'],
      ['Choosing a plan', 'Recent graduates and candidates focused on one target role usually start on the free plan. Professionals in an active search, preparing several applications a week, tend to upgrade once the daily allowance stops being sufficient. Recruitment teams reviewing a candidate pool need the batch analysis and comparison features instead.'],
      ['Billing and cancellation', 'Paid plans are subscriptions and can be cancelled at any time from the settings screen in the application. After cancelling you keep access until the end of the current period, with no mid-term charge. Price or limit changes never take effect to your disadvantage before the current period ends.'],
      ['Your data is treated the same on every plan', 'Our data handling is identical regardless of which plan you use. Your CV content is never used for ad targeting and is never shared with third-party advertising networks. You can delete your records from the Data Centre screen or close your account entirely.'],
      ['Before you buy', 'Plan scope and limits can change over time. Confirm the current details on the pricing screen before purchasing, and contact us if anything is unclear.'],
    ]],
  }
  const [title, intro, sections = []] = pages[routePath] || []
  if (!title) return ''
  return staticEnPublicChrome(`<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>${escapeHtml(title)}</h1><p>${escapeHtml(intro)}</p>${sections.map(([heading, body]) => `<section><h2>${escapeHtml(heading)}</h2><p>${escapeHtmlWithLinks(body)}</p></section>`).join('')}</article></main>`)
}

function staticPageContent(page) {
  const sections = page.sections.map((section) => `
    <section>
      <h2>${escapeHtml(section.heading)}</h2>
      ${section.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
      ${section.bullets ? `<ul>${section.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
    </section>`).join('')
  const faq = page.faq.map((item) => `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`).join('')
  return `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><header><p class="seo-eyebrow">${escapeHtml(page.eyebrow)}</p><h1>${escapeHtml(page.title)}</h1><p>${escapeHtml(page.intro)}</p><p class="seo-trust-note"><strong>Sercan Özkan</strong> — kurucu geliştirici ve içerik sorumlusu · <a href="/about/">Yayın sorumlusu hakkında</a> · <a href="/editoryal-politika/">Editoryal yaklaşımımız</a></p></header>${sections}<section class="seo-faq"><h2>Sık sorulan sorular</h2>${faq}</section><p><a href="/register">CV’nizi ücretsiz analiz edin</a></p></article></main>`
}

function staticPublicChrome(content) {
  return `
    <header data-prerendered="true">
      <nav aria-label="Ana navigasyon">
        <a href="/">CV Analyzer</a>
        <a href="/rehber/">CV rehberleri</a>
        <a href="/araclar/ats-metin-kontrolu/">ATS metin kontrolü</a>
        <a href="/pricing/">Fiyatlandırma</a>
        <a href="/about/">Hakkımızda</a>
        <a href="/editoryal-politika/">Editoryal politika</a>
        <a href="/iletisim/">İletişim</a>
      </nav>
    </header>
    ${content}
    <footer data-prerendered="true">
      <nav aria-label="Alt bilgi">
        <a href="/privacy/">Gizlilik Politikası</a>
        <a href="/terms/">Kullanım Koşulları</a>
        <a href="/editoryal-politika/">İçerik ilkeleri</a>
        <a href="/iletisim/">İletişim</a>
      </nav>
      <p>© 2026 CV Analyzer</p>
    </footer>`
}

function staticPublicPage(routePath) {
  if (routePath === '/araclar/ats-metin-kontrolu/') {
    return staticPublicChrome(`<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><p class="seo-eyebrow">Herkese açık ve ücretsiz araç</p><h1>ATS Metin Ön Kontrolü</h1><p>CV’nizden kopyaladığınız düz metni standart bölüm başlıkları, iletişim bilgileri, okuma düzeni ve kanıta dayalı deneyim anlatımı açısından tarayıcınızda kontrol edin. Metin sunucuya gönderilmez ve kaydedilmez.</p><section><h2>Kontrol formülü</h2><p>Toplam puan beş görünür bileşenden oluşur: bölüm yapısı 30, iletişim 15, metin kapsamı 15, düz metin okuma düzeni 20 ve eylem ile ölçülebilir kanıt 20 puan. Sonuç bir işverenin özel ATS sıralamasını taklit etmez.</p></section><section><h2>Neleri kontrol eder?</h2><ul><li>Deneyim, eğitim, beceriler, özet ve proje gibi standart başlıkları</li><li>Seçilebilir e-posta ve telefon metnini</li><li>Birleşmiş sütunlara işaret edebilen çok uzun satırları ve tablo ayırıcılarını</li><li>Eylem fiilleriyle desteklenen ölçülebilir kapsam ifadelerini</li></ul></section><section><h2>Kurgusal önce ve sonra örneği</h2><p><strong>Önce:</strong> Raporlardan ve müşterilerle iletişimden sorumluydum.</p><p><strong>Sonra:</strong> CRM kayıtlarından haftalık destek raporu oluşturdu; tekrar eden 6 sorun türünü ürün ekibine aktararak takip süresini kısalttı.</p><p>Bu örnek gerçek bir adaya ait değildir. Sayı yalnızca cümlenin kapsamını görünür kılmak için kullanılan temsili veridir.</p></section><section><h2>Sınırlar</h2><p>Araç dosyayı ayrıştırmaz, gerçekleri doğrulamaz, işe alınma ihtimali üretmez ve belirli bir ATS ürününü taklit etmez. PDF veya DOCX’in görsel yapısını ayrıca kontrol etmeniz gerekir.</p></section><p><a href="/metodoloji/cv-analizi/">Ürün metodolojisini inceleyin</a> · <a href="/editoryal-politika/">Editoryal yaklaşımımız</a> · <a href="/rehber/">CV rehberleri</a></p></article></main>`)
  }

  if (routePath === '/rehber/') {
    const guides = SEO_PAGES.map(
      (page) => `<article><h2><a href="${escapeHtml(page.path)}">${escapeHtml(page.title)}</a></h2><p>${escapeHtml(page.description)}</p></article>`,
    ).join('')
    return staticPublicChrome(
      `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>CV hazırlama ve ATS rehberleri</h1><p>CV’nizi ilk kez hazırlamadan hedef ilana uyarlamaya, mülakat planından ön yazıya kadar ihtiyaç duyacağınız kaynakları tek yerde inceleyin.</p><section><h2>Nereden başlamalısınız?</h2><p>Hangi rehbere ihtiyacınız olduğundan emin değilseniz, sorunun nerede olduğuna göre seçim yapmak en hızlı yoldur. Başvurularınıza hiç geri dönüş gelmiyorsa önce ATS okunabilirliğini kontrol edin: sorun çoğu zaman içerikte değil, belgenin doğru okunamamasındadır.</p><p>CV’nizi baştan hazırlıyorsanız adım adım rehberle başlayın. Belge hazır ama hedef role uygun görünmediğini düşünüyorsanız, role özel örnekleri inceleyin. Görüşme aşamasına geçtiyseniz mülakat hazırlığı rehberi daha faydalı olacaktır.</p></section><section><h2>Bu rehberleri nasıl hazırlıyoruz?</h2><p>Rehberlerimiz CV Analyzer editoryal ekibi tarafından yazılır, yayımlanmadan önce gözden geçirilir ve güncelliğini yitirdiğinde revize edilir. Her tavsiyeyi kendi belgeniz üzerinde doğrulayabileceğiniz biçimde yazmayı hedefliyoruz.</p><p>Garanti edemeyeceğimiz sonuçları vaat etmiyoruz: belirli bir geri dönüş oranı, kesin bir ATS puanı veya işe alınma sözü vermiyoruz. Sahip olmadığınız deneyim ve becerileri CV’nize eklemenizi de hiçbir rehberde önermiyoruz.</p><p>İçeriklerde hata veya eksik gördüğünüzde iletişim sayfamızdan bildirebilirsiniz; editoryal ilkelerimizin tamamını ayrı bir sayfada yayımlıyoruz.</p></section><section><h2>Ülkeye göre değişen kurallar</h2><p>CV beklentileri ülkeden ülkeye değişir. Fotoğraf, doğum tarihi, medeni durum ve referans bilgisi Türkiye’de yaygınken birçok Avrupa ülkesinde önerilmez veya doğrudan sakıncalı görülür. Belge uzunluğu konusunda da tek bir kural yoktur.</p><p>Bu nedenle rehberlerimizde farklılık olan konuları tek bir doğru gibi sunmuyoruz. Yurt dışı başvurusu hazırlıyorsanız hedef ülkenin yerel beklentilerini ayrıca kontrol etmenizi öneririz.</p></section>${guides}</article></main>`,
    )
  }

  if (routePath === EDITORIAL_POLICY.path) {
    const sections = EDITORIAL_POLICY.sections.map((section) => `
      <section>
        <h2>${escapeHtml(section.heading)}</h2>
        ${section.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
      </section>`).join('')
    return staticPublicChrome(
      `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>${escapeHtml(EDITORIAL_POLICY.title)}</h1><p><time datetime="${escapeHtml(EDITORIAL_POLICY.updatedAt)}">Son güncelleme: 3 Eylül 2026</time></p><p>${escapeHtml(EDITORIAL_POLICY.intro)}</p>${sections}</article></main>`,
    )
  }

  if (routePath === CONTACT_TR.path) {
    return staticPublicChrome(staticDocContent(CONTACT_TR, { isEnglish: false, updatedAt: CONTACT_UPDATED_AT, email: CONTACT_EMAIL }))
  }

  if (routePath === PRIVACY_TR.path) {
    return staticPublicChrome(staticDocContent(PRIVACY_TR, { isEnglish: false, updatedAt: POLICY_UPDATED_AT }))
  }

  if (routePath === TERMS_TR.path) {
    return staticPublicChrome(staticDocContent(TERMS_TR, { isEnglish: false, updatedAt: POLICY_UPDATED_AT }))
  }

  const pages = {
    '/': {
      title: 'CV’nizi ATS ve hedef iş ilanına göre değerlendirin',
      intro: 'CV Analyzer; özgeçmişinizin okunabilirliğini, bölüm yapısını, deneyim ve beceri anlatımını ve hedef rolle ilişkisini ayrı başlıklarda incelemenize yardımcı olur. Tek bir puan vermek yerine, hangi bölümün neden geliştirilmesi gerektiğini açıklarız.',
      sections: [
        ['Tek puandan daha açıklayıcı sonuçlar', 'Analiz; iletişim bilgileri, standart bölüm başlıkları, metin çıkarma kalitesi, deneyim anlatımı, beceriler ve iş ilanı eşleşmesi gibi sinyalleri ayrı ayrı gösterir. Böylece hangi değişikliğin neden gerekli olduğunu görebilir, önerileri körü körüne uygulamak yerine kendi kararınızı verebilirsiniz.'],
        ['ATS okunabilirliği neden önemli?', 'Birçok işveren başvuruları önce aday takip sistemleri (ATS) üzerinden değerlendirir. Çok sütunlu yerleşimler, metin kutuları, tablolar, görsel içine gömülü yazılar ve alışılmadık bölüm başlıkları metnin hatalı çıkarılmasına yol açabilir. Analiz, CV’nizin bu sistemlerde nasıl bir metne dönüştüğünü görmenizi sağlar.'],
        ['İş ilanıyla eşleşme', 'Hedeflediğiniz ilanın metnini eklediğinizde, ilandaki sorumluluk ve nitelik ifadeleriyle CV’nizdeki kanıtları karşılaştırırız. Eksik kalan başlıkları ve halihazırda güçlü olduğunuz alanları ayrı ayrı listeleriz.'],
        ['Gerçekleri koruyan öneriler', 'CV’nizde bulunmayan deneyim, sonuç veya becerileri eklemenizi önermeyiz. Amaç, sahip olduğunuz bilgileri daha açık, ölçülebilir ve hedef rolle ilişkili biçimde sunmanıza yardımcı olmaktır. Nihai karar ve sorumluluk her zaman sizindir.'],
        ['Verileriniz üzerinde kontrol', 'Yüklediğiniz dosyalar hesabınıza bağlı olarak saklanır ve Veri Merkezi ekranından dilediğiniz zaman silinebilir. CV içeriğiniz reklam hedeflemesi için kullanılmaz ve reklam ağlarıyla paylaşılmaz.'],
        ['Ücretsiz başlayın', 'Hesap oluşturarak CV dosyanızı analiz edebilir, ATS görünümünü inceleyebilir ve geliştirme adımlarını kendi belgeniz üzerinde uygulayabilirsiniz. Ücretsiz plan günlük kullanım sınırlarıyla sunulur.'],
        ['Analiz nasıl çalışır?', 'CV dosyanızı yükledikten sonra belge önce metne çevrilir. Bu aşama kritiktir: çok sütunlu yerleşimler, tablolar veya görsel içine gömülmüş yazılar doğru okunamazsa sonraki tüm değerlendirmeler eksik veriyle yapılır. Bu nedenle metin çıkarma kalitesini ayrı bir başlık olarak gösteririz. Ardından bölümler sınıflandırılır, içerik sinyalleri değerlendirilir ve varsa iş ilanıyla karşılaştırma yapılır.'],
        ['Hedef ilanla karşılaştırma', 'Başvurmayı düşündüğünüz ilanın metnini eklediğinizde, ilandaki sorumluluk ve nitelik ifadeleriyle CV’nizdeki kanıtlar karşılaştırılır. Eksik kalan başlıkları ve halihazırda güçlü olduğunuz alanları ayrı ayrı görürsünüz. Bu karşılaştırma birebir kelime eşleşmesinden ibaret değildir; yakın anlamlı ifadeler ve yaygın kısaltmalar da dikkate alınır.'],
        ['Neyi vaat etmiyoruz?', 'Analiz sonucu bir işe alınma tahmini değildir. Piyasadaki her aday takip sisteminin davranışını birebir taklit edemeyiz ve işverenin öznel değerlendirmesini öngöremeyiz. Neyi ölçtüğümüzü ve bilinçli olarak neyi ölçmediğimizi metodoloji sayfamızda ayrıntılı biçimde açıklıyoruz.'],
        ['Kariyer rehberleri', 'CV hazırlama, ATS okunabilirliği, ön yazı, mülakat hazırlığı ve role özel CV örnekleri için herkese açık rehber merkezimizi ziyaret edebilirsiniz. Rehberler editoryal politikamıza göre hazırlanır, yayımlanmadan önce gözden geçirilir ve güncelliğini yitirdiğinde revize edilir.'],
      ],
    },
    '/pricing/': {
      title: 'CV Analyzer planları',
      intro: 'CV analizi, ATS okunabilirlik kontrolü ve iş ilanı karşılaştırması için sunulan planları karşılaştırın. Güncel limitler her zaman uygulama içindeki fiyatlandırma ekranında gösterilir.',
      sections: [
        ['Ücretsiz başlangıç', 'Temel CV analizi, ATS okunabilirlik kontrolü ve açıklanabilir geliştirme önerileriyle ürünü kredi kartı gerekmeden deneyebilirsiniz. Ücretsiz planda günlük analiz ve yapay zekâ aracı kullanımı belirli bir sayıyla sınırlıdır.'],
        ['Neler dahil?', 'Tüm planlarda bölüm yapısı incelemesi, metin çıkarma kalitesi kontrolü, beceri ve deneyim analizi ile iş ilanı eşleşmesi yer alır. Üst planlar daha yüksek günlük limit, geçmiş kayıtlarının saklanması ve ek kariyer araçları sunar.'],
        ['Bireysel ve ekip kullanımı', 'Daha yüksek analiz ihtiyacı olan kullanıcılar ile aday havuzu yöneten ekipler için farklı kullanım seçenekleri bulunur. İşe alım araçları manuel değerlendirmeyi destekler; otomatik olarak işe alım kararı vermez.'],
        ['Ücretsiz plan gerçekten yeterli mi?', 'Tek bir CV üzerinde çalışan ve birkaç başvuru hazırlayan çoğu kullanıcı için ücretsiz plan yeterlidir. Günlük analiz hakkı, bir CV’yi düzenleyip tekrar kontrol etmeye imkân verir. Aynı anda çok sayıda role başvuruyor, her ilan için ayrı uyarlama yapıyor veya yapay zekâ araçlarını yoğun kullanıyorsanız üst planlar daha uygun olur.'],
        ['Hangi plan size uygun?', 'Yeni mezunlar ve tek hedefe odaklanan adaylar genellikle ücretsiz planla başlar. Aktif iş arayışında olan, haftada birden fazla başvuru hazırlayan profesyoneller günlük limitin yeterli gelmediği noktada plan yükseltir. Aday havuzu değerlendiren işe alım ekipleri ise toplu analiz ve karşılaştırma özelliklerine ihtiyaç duyar.'],
        ['Ödeme ve iptal koşulları', 'Ücretli planlar abonelik biçiminde sunulur ve uygulama içindeki ayarlar ekranından dilediğiniz zaman iptal edilebilir. İptal ettiğinizde erişiminiz mevcut dönemin sonuna kadar devam eder; ara dönemde ek ücret alınmaz. Fiyat veya limit değişiklikleri, yürürlükteki abonelik dönemi bitmeden aleyhinize uygulanmaz.'],
        ['Verileriniz plandan bağımsız korunur', 'Hangi planı kullanırsanız kullanın veri işleme ilkelerimiz aynıdır. CV içeriğiniz reklam hedeflemesi için kullanılmaz ve üçüncü taraf reklam ağlarıyla paylaşılmaz. Kayıtlarınızı Veri Merkezi ekranından silebilir, hesabınızı tamamen kapatabilirsiniz.'],
        ['Satın almadan önce', 'Plan kapsamı ve limitleri zaman zaman güncellenebilir. Satın alma öncesinde fiyatlandırma ekranındaki güncel bilgileri doğrulamanızı, sorularınız için iletişim sayfamızdan bize ulaşmanızı öneririz.'],
      ],
    },
    '/about/': {
      title: 'CV Analyzer hakkında',
      intro: 'CV Analyzer, özgeçmiş değerlendirmesini tek bir puan yerine anlaşılır bulgulara ve uygulanabilir adımlara dönüştürmek amacıyla geliştirilen bağımsız bir üründür.',
      sections: [
        ['Neden kurduk?', 'İş arayanların aldığı geri bildirim çoğu zaman ya hiç gelmiyor ya da “CV’niz uygun değil” gibi tek cümlelik bir sonuçtan ibaret kalıyor. CV Analyzer’ı, bu geri bildirimi somut ve gerekçeli hale getirmek için geliştirdik: hangi bölümün neden zayıf göründüğünü ve nasıl düzeltilebileceğini açıkça göstermek istiyoruz.'],
        ['Yaklaşımımız', 'CV’nin bölüm yapısını, metin okunabilirliğini, deneyim ve beceri anlatımını ve hedef iş ilanıyla ilişkisini ayrı sinyaller olarak değerlendiririz. Sonuçlar işe alınma garantisi değil, adayın kendi belgesini gözden geçirmesine yardımcı olan rehberliktir.'],
        ['Şeffaflık ve kontrol', 'Önerilerin gerçekte CV’de bulunan bilgilere dayanmasını, uydurma deneyim veya beceri eklememesini hedefleriz. Kullanıcılar kayıtlı analizlerini ve CV sürümlerini hesaplarından yönetebilir ve silebilir.'],
        ['İçeriklerimizi kim hazırlıyor?', 'Rehber ve metodoloji sayfalarının yayın sorumlusu kurucu geliştirici Sercan Özkan’dır. Bu ifade işe alım uzmanlığı iddiası değildir. İçerikler yayımlanmadan önce ürün davranışı ve kesin sonuç izlenimi veren ifadeler açısından gözden geçirilir; süreç editoryal politika sayfasında açıklanır.'],
        ['Ürünü işleten', 'CV Analyzer, kurucu geliştirici Sercan Özkan tarafından bağımsız olarak işletilmektedir. Herhangi bir işveren, iş ilanı platformu veya ATS sağlayıcısıyla ticari bağımız yoktur; değerlendirmelerimiz bu nedenle üçüncü taraf çıkarlarından etkilenmez.'],
        ['Nasıl finanse ediliyoruz?', 'Ürün, ücretli abonelikler ve herkese açık içerik sayfalarında gösterilen reklamlarla finanse edilir. Reklam gelirinin analiz sonuçları üzerinde hiçbir etkisi yoktur; reklamlar yalnızca rehber içeriklerinde ve analiz ekranlarının dışında gösterilir.'],
        ['Kimler için tasarlandı?', 'Ürün; ilk CV’sini hazırlayanlar, rol veya sektör değiştirenler, yurt dışı başvurusuna hazırlananlar ve aday havuzunu manuel inceleyen yetkili ekipler için farklı çalışma alanları sunar. Bu bir kullanıcı dağılımı iddiası değildir; işe alım araçları otomatik karar vermez ve insan değerlendirmesinin yerini almaz.'],
        ['Sınırlarımızı açıkça söylüyoruz', 'Bir CV analiz aracının yapabilecekleri sınırlıdır ve bunu gizlemiyoruz. Piyasadaki her aday takip sisteminin davranışını birebir taklit edemeyiz, işverenin öznel değerlendirmesini öngöremeyiz ve işe alınma olasılığı tahmini üretmeyiz. Metodoloji sayfamızda neyi ölçtüğümüzü ve bilinçli olarak neyi ölçmediğimizi ayrıntılı biçimde açıklıyoruz.'],
        ['İletişim', 'Ürün, gizlilik veya içeriklerle ilgili sorularınızı iletişim sayfamız üzerinden veya support@cvanalyzer.dev adresine iletebilirsiniz. Genel soruları hafta içi 1-2 iş günü içinde, gizlilik ve veri silme taleplerini ise en geç 30 gün içinde yanıtlıyoruz.'],
      ],
    },
  }
  const page = pages[routePath]
  if (!page) return ''
  const sections = page.sections
    .map(([heading, body]) => `<section><h2>${escapeHtml(heading)}</h2><p>${escapeHtmlWithLinks(body)}</p></section>`)
    .join('')
  return staticPublicChrome(
    `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>${escapeHtml(page.title)}</h1><p>${escapeHtml(page.intro)}</p>${sections}</article></main>`,
  )
}

async function writeRoute(route, html) {
  const routeDir = path.join(distDir, route.replace(/^\//, '').replace(/\/$/, ''))
  await mkdir(routeDir, { recursive: true })
  await writeFile(path.join(routeDir, 'index.html'), html, 'utf8')
}

for (const page of SEO_PAGES) {
  const canonical = `${SITE_URL}${page.path}`
  const enEquivalentPath = EN_EQUIVALENT_BY_TR_PATH[page.path]
  const alternates = enEquivalentPath
    ? [
        { hreflang: 'tr', href: canonical },
        { hreflang: 'en', href: `${SITE_URL}${enEquivalentPath}` },
        { hreflang: 'x-default', href: `${SITE_URL}${enEquivalentPath}` },
      ]
    : []
  let html = applyMeta(baseHtml, {
    title: page.seoTitle,
    description: page.description,
    canonical,
    schema: pageSchema(page),
    alternates,
  })
  html = html.replace('<div id="root"></div>', `<div id="root">${staticPublicChrome(staticPageContent(page))}</div>`)
  await writeRoute(page.path, html)
}

for (const page of EN_SEO_PAGES) {
  const canonical = `${SITE_URL}${page.path}`
  const indexable = page.indexable !== false
  let html = applyMeta(baseHtml, {
    title: page.seoTitle,
    description: page.description,
    canonical,
    schema: indexable ? enPageSchema(page) : null,
    robots: indexable ? 'index, follow, max-image-preview:large' : 'noindex, follow',
    htmlLang: 'en',
    alternates: indexable ? [
      { hreflang: 'en', href: canonical },
      ...(page.trPath ? [{ hreflang: 'tr', href: `${SITE_URL}${page.trPath}` }] : []),
      { hreflang: 'x-default', href: `${SITE_URL}/en/` },
    ] : [],
  })
  html = removeSiteStructuredData(html)
  html = html.replace('<div id="root"></div>', `<div id="root">${staticEnPublicChrome(staticEnPageContent(page))}</div>`)
  await writeRoute(page.path, html)
}

for (const route of PUBLIC_ROUTES) {
  const canonical = `${SITE_URL}${route.path}`
  const alternates = route.enPath ? [
    { hreflang: 'tr', href: canonical },
    { hreflang: 'en', href: `${SITE_URL}${route.enPath}` },
    { hreflang: 'x-default', href: `${SITE_URL}/en/` },
  ] : []
  let html = applyMeta(baseHtml, {
    ...route,
    canonical,
    alternates,
    schema: route.path === CONTACT_TR.path
      ? contactSchema(CONTACT_TR, { isEnglish: false })
      : route.path === '/araclar/ats-metin-kontrolu/'
        ? {
            '@context': 'https://schema.org', '@type': 'WebApplication',
            name: 'ATS Metin Ön Kontrolü', description: route.description, url: canonical,
            applicationCategory: 'BusinessApplication', operatingSystem: 'Any', inLanguage: 'tr-TR',
            offers: { '@type': 'Offer', price: '0', priceCurrency: 'TRY' },
          }
        : null,
  })
  html = html.replace('<div id="root"></div>', `<div id="root">${staticPublicPage(route.path)}</div>`)
  await writeRoute(route.path, html)
}

for (const route of EN_PUBLIC_ROUTES) {
  const canonical = `${SITE_URL}${route.path}`
  let html = applyMeta(baseHtml, {
    ...route,
    canonical,
    htmlLang: 'en',
    schema: route.path === CONTACT_EN.path
      ? contactSchema(CONTACT_EN, { isEnglish: true })
      : { '@context': 'https://schema.org', '@type': 'WebPage', name: route.title, description: route.description, url: canonical, inLanguage: 'en' },
    alternates: [
      { hreflang: 'en', href: canonical },
      { hreflang: 'tr', href: `${SITE_URL}${route.trPath}` },
      { hreflang: 'x-default', href: `${SITE_URL}/en/` },
    ],
  })
  html = removeSiteStructuredData(html)
  html = html.replace('<div id="root"></div>', `<div id="root">${staticEnglishPublicPage(route.path)}</div>`)
  await writeRoute(route.path, html)
}

for (const route of NOINDEX_ROUTES) {
  const html = applyMeta(baseHtml, {
    title: 'CV Analyzer',
    description: 'CV Analyzer kullanıcı alanı.',
    canonical: `${SITE_URL}${route}`,
    robots: 'noindex, nofollow',
  })
  await writeRoute(route, html)
}

// nginx serves this for anything that does not resolve to a prerendered file,
// with a real 404 status. Without it every unknown URL returned 200 plus the
// indexable homepage, which let Google index unlimited duplicate copies of the
// landing page — a soft 404 and a low-value-content signal.
const notFoundHtml = applyMeta(baseHtml, {
  title: 'Sayfa bulunamadı | CV Analyzer',
  description: 'Aradığınız sayfa bulunamadı. CV rehberlerine veya ana sayfaya dönebilirsiniz.',
  canonical: `${SITE_URL}/404`,
  robots: 'noindex, nofollow',
}).replace(
  '<div id="root"></div>',
  `<div id="root">${staticPublicChrome(`<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>Sayfa bulunamadı</h1><p>Aradığınız sayfa taşınmış, adı değişmiş veya hiç var olmamış olabilir. Aşağıdaki bağlantılardan devam edebilirsiniz.</p><ul><li><a href="/">Ana sayfa</a></li><li><a href="/rehber/">CV hazırlama ve ATS rehberleri</a></li><li><a href="/cv-analiz/">Ücretsiz CV analizi</a></li><li><a href="/iletisim/">İletişim</a></li></ul></article></main>`)}</div>`,
)
await writeFile(path.join(distDir, '404.html'), notFoundHtml, 'utf8')

console.log(`Prerendered ${SEO_PAGES.length} SEO pages, ${EN_SEO_PAGES.length} English SEO pages, ${PUBLIC_ROUTES.length + EN_PUBLIC_ROUTES.length} public routes, ${NOINDEX_ROUTES.length} noindex routes and 404.html.`)
