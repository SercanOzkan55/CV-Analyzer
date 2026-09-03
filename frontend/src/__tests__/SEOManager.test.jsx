import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SEOManager from '../components/SEOManager'

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ lang: 'tr', setRouteLangOverride: () => {} }),
}))

function renderManager(pathname) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <SEOManager />
    </MemoryRouter>,
  )
}

afterEach(() => {
  document.getElementById('route-structured-data')?.remove()
  document.head.querySelectorAll('link[data-hreflang-managed="true"]').forEach((node) => node.remove())
})

describe('SEOManager', () => {
  it('sets route-specific indexable metadata and structured data', async () => {
    renderManager('/cv-analiz/')

    await waitFor(() => expect(document.title).toContain('Ücretsiz CV Analiz'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute('href', 'https://cvanalyzer.dev/cv-analiz/')
    expect(document.getElementById('route-structured-data')?.textContent).toContain('FAQPage')
  })

  it('marks authenticated application routes as noindex', async () => {
    renderManager('/dashboard')

    await waitFor(() => {
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow')
    })
  })

  it('indexes first-party editorial guides with their own canonical URL', async () => {
    renderManager('/rehber/profesyonel-ozet-nasil-yazilir/')

    await waitFor(() => expect(document.title).toContain('Profesyonel Özet'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://cvanalyzer.dev/rehber/profesyonel-ozet-nasil-yazilir/',
    )
    expect(document.getElementById('route-structured-data')?.textContent).toContain('Article')
  })

  it('indexes the editorial policy with its own canonical URL', async () => {
    renderManager('/editoryal-politika/')

    await waitFor(() => expect(document.title).toContain('Editoryal Politika'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://cvanalyzer.dev/editoryal-politika/',
    )
  })

  it('indexes the public ATS text tool with WebApplication schema', async () => {
    renderManager('/araclar/ats-metin-kontrolu/')

    await waitFor(() => expect(document.title).toContain('ATS Metin Ön Kontrolü'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://cvanalyzer.dev/araclar/ats-metin-kontrolu/',
    )
    expect(document.getElementById('route-structured-data')?.textContent).toContain('WebApplication')
  })

  it('indexes reviewed English guides with neutral English metadata', async () => {
    renderManager('/en/ai-cv-analyzer/')

    await waitFor(() => {
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    })
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute('href', 'https://cvanalyzer.dev/en/ai-cv-analyzer/')
    expect(document.querySelector('meta[property="og:locale"]')).toHaveAttribute('content', 'en_GB')
    expect(document.getElementById('route-structured-data')?.textContent).toContain('"inLanguage":"en"')
  })

  it('keeps deferred English product pages accessible but out of the index', async () => {
    const siteSchema = document.createElement('script')
    siteSchema.id = 'site-structured-data'
    siteSchema.type = 'application/ld+json'
    document.head.appendChild(siteSchema)
    renderManager('/en/job-application-tracker/')

    await waitFor(() => {
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, follow')
    })
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://cvanalyzer.dev/en/job-application-tracker/',
    )
    expect(document.getElementById('route-structured-data')).toBeNull()
    expect(document.querySelector('link[data-hreflang-managed="true"]')).toBeNull()
    expect(siteSchema).toHaveAttribute('type', 'application/json')
    siteSchema.remove()
  })

  it('indexes the fixed-language English guide hub', async () => {
    renderManager('/en/')

    await waitFor(() => expect(document.title).toContain('English CV, ATS'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute('href', 'https://cvanalyzer.dev/en/')
    expect(document.querySelector('link[hreflang="tr"]')).toHaveAttribute('href', 'https://cvanalyzer.dev/rehber/')
  })
})
