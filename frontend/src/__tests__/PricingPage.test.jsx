import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import PricingPage from '../pages/PricingPage'

const createCheckoutSession = vi.fn()

vi.mock('../api', () => ({
  createBillingPortalSession: vi.fn(),
  createCheckoutSession: (...args) => createCheckoutSession(...args),
  createContactSalesRequest: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    plan: 'free',
    refreshUsage: vi.fn(),
    token: 'test-token',
    user: { email: 'user@gmail.com' },
  }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    countryCode: 'TR',
    pricing: {
      enterprise: 'Custom',
      free: '$0',
      periodKey: 'pricing.period_monthly',
      pro: '$19',
    },
    t: (key) => key,
  }),
}))

vi.mock('../components/Navbar', () => ({ default: () => <nav /> }))
vi.mock('../components/Footer', () => ({ default: () => <footer /> }))
vi.mock('../components/Toast', () => ({
  useToast: () => ({ addToast: vi.fn() }),
}))

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
  it('keeps paid checkout unavailable while billing is disabled', () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>,
    )

    const paidPlanButtons = screen.getAllByRole('button', {
      name: 'pricing.billing_coming_soon',
    })

    expect(paidPlanButtons).toHaveLength(2)
    paidPlanButtons.forEach((button) => expect(button).toBeDisabled())
    expect(screen.queryByText('pricing.billing_title')).not.toBeInTheDocument()
    expect(createCheckoutSession).not.toHaveBeenCalled()
  })
})
