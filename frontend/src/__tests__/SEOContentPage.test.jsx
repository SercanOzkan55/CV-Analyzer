import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SEOContentPage from '../pages/SEOContentPage'
import { SEO_PAGES } from '../content/seoPages'

vi.mock('../components/Navbar', () => ({ default: () => <nav>Navbar</nav> }))
vi.mock('../components/Footer', () => ({ default: () => <footer>Footer</footer> }))
let mockLang = 'tr'
vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ lang: mockLang }),
}))

describe('SEOContentPage', () => {
  beforeEach(() => {
    mockLang = 'tr'
  })

  it('renders original guidance, FAQs and conversion links', () => {
    const page = SEO_PAGES[0]
    render(
      <MemoryRouter>
        <SEOContentPage page={page} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: page.title })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'CV analizi neyi ölçer?' }),
    ).toBeInTheDocument()
    expect(screen.getByText('CV analizi ücretsiz mi?')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /ücretsiz/i }).length).toBeGreaterThan(0)
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByText('CV Analyzer Editoryal Ekibi')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'İçindekiler' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: page.sections[0].heading })).toHaveAttribute(
      'href',
      `#${page.slug}-section-1`,
    )
    expect(screen.getByText('Güncellendi: 14 Temmuz 2026')).toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: page.eyebrow, exact: true }),
    ).not.toBeInTheDocument()
  })

  it('keeps English fallback content left-to-right in Arabic UI', () => {
    mockLang = 'ar'
    render(
      <MemoryRouter>
        <SEOContentPage page={SEO_PAGES[0]} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('CV Analysis')
    expect(document.querySelector('.seo-guide-localized-copy')).toHaveAttribute('dir', 'ltr')
    expect(document.querySelector('.seo-article-main')).toHaveAttribute('lang', 'en')
    expect(document.querySelector('.seo-article-main')).toHaveAttribute('dir', 'ltr')
  })
})
