import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SEO_PAGES } from '../src/content/seoPages.js'
import { EN_SEO_PAGES, EN_EQUIVALENT_BY_TR_PATH } from '../src/content/enSeoPages.js'

const SITE_URL = 'https://cvanalyzer.dev'
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distDir = path.join(rootDir, 'dist')
const baseHtml = await readFile(path.join(distDir, 'index.html'), 'utf8')

const PUBLIC_ROUTES = [
  { path: '/', title: 'Ücretsiz CV Analiz ve ATS Kontrolü | CV Analyzer', description: 'CV’nizi ücretsiz analiz edin; ATS uyumunu, iş ilanı eşleşmesini, beceri boşluklarını ve geliştirme önerilerini tek ekranda görün.' },
  { path: '/rehber/', title: 'CV Hazırlama ve ATS Rehberleri | CV Analyzer', description: 'CV hazırlama, ATS okunabilirliği, mülakat, ön yazı ve role özel CV örnekleri için özgün ve uygulanabilir rehberleri inceleyin.' },
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

function applyMeta(html, { title, description, canonical, robots = 'index, follow, max-image-preview:large', schema, htmlLang = 'tr', alternates = [] }) {
  let output = html.replace(/<html\s+lang="[^"]*"/, `<html lang="${htmlLang}"`)
  output = output.replace(/<title>.*?<\/title>/s, `<title>${escapeHtml(title)}</title>`)
  output = replaceTag(output, /<meta\s+name="description"[^>]*>/i, `<meta name="description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+name="robots"[^>]*>/i, `<meta name="robots" content="${escapeHtml(robots)}" />`)
  output = replaceTag(output, /<link\s+rel="canonical"[^>]*>/i, `<link rel="canonical" href="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+property="og:title"[^>]*>/i, `<meta property="og:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+property="og:description"[^>]*>/i, `<meta property="og:description" content="${escapeHtml(description)}" />`)
  output = replaceTag(output, /<meta\s+property="og:url"[^>]*>/i, `<meta property="og:url" content="${escapeHtml(canonical)}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(title)}" />`)
  output = replaceTag(output, /<meta\s+name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(description)}" />`)
  if (alternates.length) {
    const links = alternates.map(({ hreflang, href }) => `<link rel="alternate" hreflang="${escapeHtml(hreflang)}" href="${escapeHtml(href)}" />`).join('')
    output = output.replace('</head>', `${links}\n</head>`)
  }
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

function enPageSchema(page) {
  const canonical = `${SITE_URL}${page.path}`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article', headline: page.title, description: page.description,
        datePublished: page.updatedAt, dateModified: page.updatedAt, inLanguage: 'en-US',
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
        <a href="/pricing/">Pricing</a>
        <a href="/about/">About</a>
      </nav>
    </header>
    ${content}
    <footer data-prerendered="true">
      <nav aria-label="Footer">
        <a href="/privacy/">Privacy Policy</a>
        <a href="/terms/">Terms of Use</a>
        <a href="mailto:support@cvanalyzer.dev">Contact</a>
      </nav>
      <p>© 2026 CV Analyzer</p>
    </footer>`
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

function staticPublicChrome(content) {
  return `
    <header data-prerendered="true">
      <nav aria-label="Ana navigasyon">
        <a href="/">CV Analyzer</a>
        <a href="/rehber/">CV rehberleri</a>
        <a href="/pricing/">Fiyatlandırma</a>
        <a href="/about/">Hakkımızda</a>
      </nav>
    </header>
    ${content}
    <footer data-prerendered="true">
      <nav aria-label="Alt bilgi">
        <a href="/privacy/">Gizlilik Politikası</a>
        <a href="/terms/">Kullanım Koşulları</a>
        <a href="mailto:support@cvanalyzer.dev">İletişim</a>
      </nav>
      <p>© 2026 CV Analyzer</p>
    </footer>`
}

function staticPublicPage(routePath) {
  if (routePath === '/rehber/') {
    const guides = SEO_PAGES.map(
      (page) => `<article><h2><a href="${escapeHtml(page.path)}">${escapeHtml(page.title)}</a></h2><p>${escapeHtml(page.description)}</p></article>`,
    ).join('')
    return staticPublicChrome(
      `<main id="main-content" class="seo-container seo-article" data-prerendered="true"><article class="seo-article-main"><h1>CV hazırlama ve ATS rehberleri</h1><p>CV’nizi ilk kez hazırlamadan hedef ilana uyarlamaya, mülakat planından ön yazıya kadar ihtiyaç duyacağınız kaynakları tek yerde inceleyin.</p>${guides}</article></main>`,
    )
  }

  const pages = {
    '/': {
      title: 'CV’nizi ATS ve hedef iş ilanına göre değerlendirin',
      intro: 'CV Analyzer; özgeçmişinizin okunabilirliğini, bölüm yapısını, deneyim ve beceri anlatımını ve hedef rolle ilişkisini ayrı başlıklarda incelemenize yardımcı olur.',
      sections: [
        ['Tek puandan daha açıklayıcı sonuçlar', 'Analiz; iletişim bilgileri, standart bölüm başlıkları, metin çıkarma kalitesi, deneyim anlatımı, beceriler ve iş ilanı eşleşmesi gibi sinyalleri ayrı ayrı gösterir. Böylece hangi değişikliğin neden gerekli olduğunu görebilirsiniz.'],
        ['Gerçekleri koruyan öneriler', 'CV’nizde bulunmayan deneyim, sonuç veya becerileri eklemenizi önermeyiz. Amaç, sahip olduğunuz bilgileri daha açık ve hedef rolle ilişkili biçimde sunmanıza yardımcı olmaktır.'],
        ['Ücretsiz başlayın', 'Hesap oluşturarak CV dosyanızı analiz edebilir, ATS görünümünü inceleyebilir ve geliştirme adımlarını kendi belgeniz üzerinde uygulayabilirsiniz.'],
        ['Kariyer rehberleri', 'CV hazırlama, ATS okunabilirliği, yeni mezun ve yazılım mühendisi CV örnekleri için herkese açık rehber merkezini ziyaret edin.'],
      ],
    },
    '/pricing/': {
      title: 'CV Analyzer planları',
      intro: 'CV analizi, ATS okunabilirlik kontrolü ve iş ilanı karşılaştırması için sunulan planları karşılaştırın.',
      sections: [
        ['Ücretsiz başlangıç', 'Temel CV analizi ve açıklanabilir geliştirme önerileriyle ürünü deneyebilirsiniz. Güncel kullanım sınırları hesap ekranında gösterilir.'],
        ['Bireysel ve ekip kullanımı', 'Daha yüksek analiz ihtiyacı olan kullanıcılar ile aday havuzu yöneten ekipler için farklı kullanım seçenekleri sunulur. Satın alma öncesinde özellik ve limitleri fiyatlandırma ekranından doğrulayın.'],
      ],
    },
    '/about/': {
      title: 'CV Analyzer hakkında',
      intro: 'CV Analyzer, özgeçmiş değerlendirmesini tek bir puan yerine anlaşılır bulgulara ve uygulanabilir adımlara dönüştürmek amacıyla geliştirilen bağımsız bir üründür.',
      sections: [
        ['Yaklaşımımız', 'CV’nin bölüm yapısını, metin okunabilirliğini, deneyim ve beceri anlatımını ve hedef iş ilanıyla ilişkisini ayrı sinyaller olarak değerlendiririz. Sonuçlar işe alınma garantisi değil, adayın kendi belgesini gözden geçirmesine yardımcı olan rehberliktir.'],
        ['Şeffaflık ve kontrol', 'Önerilerin gerçekte CV’de bulunan bilgilere dayanmasını, uydurma deneyim veya beceri eklememesini hedefleriz. Kullanıcılar kayıtlı analizlerini ve CV sürümlerini hesaplarından yönetebilir ve silebilir.'],
        ['İletişim', 'Ürün, gizlilik veya içeriklerle ilgili sorularınızı support@cvanalyzer.dev adresine iletebilirsiniz.'],
      ],
    },
    '/privacy/': {
      title: 'Gizlilik Politikası',
      intro: 'Bu politika; hesap, CV dosyası, analiz sonucu, çerez ve reklam teknolojileriyle ilişkili verilerin nasıl işlendiğini açıklar.',
      sections: [
        ['Saklanan veriler', 'Hesap bilgileri, analiz sonuçları ve kaydetmeyi seçtiğiniz CV sürümleri, geçmişinize erişebilmeniz için siz silene kadar saklanabilir. Kayıtları Veri Merkezi üzerinden veya hesabınızı silerek kaldırabilirsiniz.'],
        ['Çerezler ve reklamlar', 'Kimlik doğrulama ve tercih çerezleri hizmetin çalışması için kullanılır. Reklamlar etkinleştirildiğinde Google AdSense çerezleri ve benzer tanımlayıcılar, geçerli onay tercihleri doğrultusunda kullanılabilir.'],
        ['Haklar ve iletişim', 'Verilerinize erişme veya silme talepleri için uygulamadaki veri kontrollerini ya da support@cvanalyzer.dev adresini kullanabilirsiniz.'],
      ],
    },
    '/terms/': {
      title: 'Kullanım Koşulları',
      intro: 'CV Analyzer sonuçları kariyer kararlarını destekleyen otomatik değerlendirmelerdir; işe alınma sonucu veya kesin profesyonel görüş garantisi vermez.',
      sections: [
        ['Kullanıcı sorumluluğu', 'Yüklediğiniz içeriğin doğruluğundan, paylaşma yetkinizden ve üretilen önerileri kullanmadan önce gözden geçirmekten siz sorumlusunuz.'],
        ['Hizmet sınırları', 'Puanlar ve öneriler farklı ATS ürünlerinin kesin davranışını temsil etmez. İşverenlerin değerlendirme yöntemleri değişebilir.'],
        ['İçerik sahipliği', 'Yüklediğiniz içeriğin hakları sizde kalır. Hizmetin marka, tasarım ve yazılım bileşenleri sağlayıcıya aittir.'],
      ],
    },
  }
  const page = pages[routePath]
  if (!page) return ''
  const sections = page.sections
    .map(([heading, body]) => `<section><h2>${escapeHtml(heading)}</h2><p>${escapeHtml(body)}</p></section>`)
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
  const trUrl = `${SITE_URL}${page.trPath}`
  let html = applyMeta(baseHtml, {
    title: page.seoTitle,
    description: page.description,
    canonical,
    schema: enPageSchema(page),
    htmlLang: 'en',
    alternates: [
      { hreflang: 'en', href: canonical },
      { hreflang: 'tr', href: trUrl },
      { hreflang: 'x-default', href: canonical },
    ],
  })
  html = html.replace('<div id="root"></div>', `<div id="root">${staticEnPublicChrome(staticEnPageContent(page))}</div>`)
  await writeRoute(page.path, html)
}

for (const route of PUBLIC_ROUTES) {
  const canonical = `${SITE_URL}${route.path}`
  let html = applyMeta(baseHtml, { ...route, canonical })
  html = html.replace('<div id="root"></div>', `<div id="root">${staticPublicPage(route.path)}</div>`)
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

console.log(`Prerendered ${SEO_PAGES.length} SEO pages, ${EN_SEO_PAGES.length} English SEO pages, ${PUBLIC_ROUTES.length} public routes and ${NOINDEX_ROUTES.length} noindex routes.`)
