import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import PricingPage from '../pages/PricingPage'

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: null,
  }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    t: (key) => key,
  }),
}))

vi.mock('../components/Navbar', () => ({ default: () => <nav /> }))
vi.mock('../components/Footer', () => ({ default: () => <footer /> }))

beforeAll(() => {
  vi.stubGlobal(
    'IntersectionObserver',
    class IntersectionObserver {
      disconnect() {}
      observe() {}
      takeRecords() { return [] }
      unobserve() {}
    },
  )
})

describe('PricingPage', () => {
  it('shows a single free plan with no paid CTAs or billing copy', () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('pricing.title')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'pricing.free_cta' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: 'pricing.local_worker_cta' })).toHaveAttribute('href', '/recruiter')

    expect(screen.queryByText(/upgrade/i)).not.toBeInTheDocument()
    expect(screen.queryByText('pricing.billing_title')).not.toBeInTheDocument()
    expect(screen.queryByText(/599 TL|3999 TL|\$19|\$100/)).not.toBeInTheDocument()
  })
})
