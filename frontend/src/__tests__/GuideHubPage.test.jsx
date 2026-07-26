import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import GuideHubPage from '../pages/GuideHubPage'
import { SEO_PAGES } from '../content/seoPages'

vi.mock('../components/Navbar', () => ({ default: () => <nav>Navbar</nav> }))
vi.mock('../components/Footer', () => ({ default: () => <footer>Footer</footer> }))
vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ lang: 'tr' }),
}))

describe('GuideHubPage', () => {
  it('makes every public guide discoverable', () => {
    render(
      <MemoryRouter>
        <GuideHubPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'CV hazırlama ve ATS rehberleri',
    )

    SEO_PAGES.forEach((page) => {
      expect(screen.getByRole('link', { name: page.title })).toHaveAttribute('href', page.path)
    })
  })
})
