import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SEO_PAGES } from '../src/content/seoPages.js'

const SITE_URL = 'https://cvanalyzer.dev'
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distDir = path.join(rootDir, 'dist')
const baseHtml = await readFile(path.join(distDir, 'index.html'), 'utf8')

const PUBLIC_ROUTES = [
  { path: '/pricing/', title: 'CV Analyzer Planları ve Özellikleri', description: 'CV analizi, ATS kontrolü, iş eşleşmesi ve CV geliştirme özelliklerini karşılaştırın.' },
  { path: '/about/', title: 'CV Analyzer Hakkında', description: 'CV Analyzer’ın özgeçmiş değerlendirmesini daha açık, erişilebilir ve uygulanabilir hale getirme yaklaşımını öğrenin.' },
  { path: '/privacy/', title: 'Gizlilik Politikası | CV Analyzer', description: 'CV Analyzer’ın CV dosyalarını, analiz sonuçlarını ve hesap verilerini nasıl işlediğini inceleyin.' },
  { path: '/terms/', title: 'Kullanım Koşulları | CV Analyzer', description: 'CV Analyzer hizmetlerinin kullanım koşullarını ve kullanıcı sorumluluklarını inceleyin.' },
]

const NOINDEX_ROUTES = [
  '/login', '/register', '/forgot-password', '/dashboard', '/analyze', '/career-studio',
  '/feedback', '/history', '/settings', '/profile', '/compare', '/my-cvs', '/recruiter',
  '/premium', '/cv-builder', '/cover-letter', '/interview-simulator', '/job-tracker',
  '/agents', '/data-center', '/template-marketplace', '/admin/billing', '/admin/ops',
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

function applyMeta(html, { title, description, canonical, robots = 'index, follow, max-image-preview:large', schema }) {
  let output = html.replace(/<html\s+lang="[^"]*"/, '<html lang="tr"')
  output = output.replace(/<title>.*?<\/title>/s, `<title>${escapeHtml(title)}</title>`)
  output = replaceTag(output, /<meta\s+name="description"[^>]*>/i, `<meta name="description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+name="robots"[^>]*>/i, `<meta name="robots" content="${escapeHtml(robots)}" />`)
  output = replaceTag(output, /<link\s+rel="canonical"[^>]*>/i, `<link rel="canonical" href="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+property="og:title"[^>]*>/i, `<meta property="og:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+property="og:description"[^>]*>/i, `<meta property="og:description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+property="og:url"[^>]*>/i, `<meta property="og:url" content="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(description)}" />`)
  if (schema) {
    output = output.replace('</head>', `<script id="route-structured-data" type="application/ld+json">${JSON.stringify(schema).replaceAll('<', '\\u003c')}</script>\n</head>`)
  }
  return output
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
          '@type': 'Question', name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
    ],
  }
}

function staticPageContent(page) {
  const sections = page.sections.map((section) => `
    <section>
      <h2>${escapeHtml(section.heading)}</h2>
      ${section.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
      ${section.bullets ? `<ul>${section.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
    </section>`).join('')
  const faq = page.faq.map((item) => `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`).join('')
  return `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><header><p class="seo-eyebrow">${escapeHtml(page.eyebrow)}</p><h1>${escapeHtml(page.title)}</h1><p>${escapeHtml(page.intro)}</p></header>${sections}<section class="seo-faq"><h2>Sık sorulan sorular</h2>${faq}</section><p><a href="/register">CV’nizi ücretsiz analiz edin</a></p></article></main>`
}

async function writeRoute(route, html) {
  const routeDir = path.join(distDir, route.replace(/^\//, '').replace(/\/$/, ''))
  await mkdir(routeDir, { recursive: true })
  await writeFile(path.join(routeDir, 'index.html'), html, 'utf8')
}

for (const page of SEO_PAGES) {
  const canonical = `${SITE_URL}${page.path}`
  let html = applyMeta(baseHtml, {
    title: page.seoTitle,
    description: page.description,
    canonical,
    schema: pageSchema(page),
  })
  html = html.replace('<div id="root"></div>', `<div id="root">${staticPageContent(page)}</div>`)
  await writeRoute(page.path, html)
}

for (const route of PUBLIC_ROUTES) {
  const canonical = `${SITE_URL}${route.path}`
  await writeRoute(route.path, applyMeta(baseHtml, { ...route, canonical }))
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

console.log(`Prerendered ${SEO_PAGES.length} SEO pages, ${PUBLIC_ROUTES.length} public routes and ${NOINDEX_ROUTES.length} noindex routes.`)
