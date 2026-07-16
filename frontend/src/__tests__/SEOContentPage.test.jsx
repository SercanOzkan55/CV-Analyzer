import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SEOContentPage from '../pages/SEOContentPage'
import { SEO_PAGES } from '../content/seoPages'

vi.mock('../components/Navbar', () => ({ default: () => <nav>Navbar</nav> }))
vi.mock('../components/Footer', () => ({ default: () => <footer>Footer</footer> }))

describe('SEOContentPage', () => {
  it('renders original guidance, FAQs and conversion links', () => {
    const page = SEO_PAGES[0]
    render(
      <MemoryRouter>
        <SEOContentPage page={page} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: page.title })).toBeInTheDocument()
    expect(screen.getByText('CV analizi neyi ölçer?')).toBeInTheDocument()
    expect(screen.getByText('CV analizi ücretsiz mi?')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /ücretsiz/i }).length).toBeGreaterThan(0)
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })
})
