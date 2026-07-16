import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import CookieConsent from '../components/CookieConsent'

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ t: (key) => key }),
}))

describe('CookieConsent', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    document.querySelector('meta[name="google-adsense-account"]')?.remove()
  })

  afterEach(() => {
    vi.useRealTimers()
    document.querySelector('meta[name="google-adsense-account"]')?.remove()
  })

  it('defers consent UI to Google CMP when the AdSense account tag exists', () => {
    const meta = document.createElement('meta')
    meta.name = 'google-adsense-account'
    meta.content = 'ca-pub-test'
    document.head.appendChild(meta)

    render(<MemoryRouter><CookieConsent /></MemoryRouter>)
    act(() => vi.advanceTimersByTime(2000))

    expect(screen.queryByRole('button', { name: 'cookie.accept' })).not.toBeInTheDocument()
  })

  it('keeps the fallback banner for deployments without Google CMP', () => {
    render(<MemoryRouter><CookieConsent /></MemoryRouter>)
    act(() => vi.advanceTimersByTime(2000))

    expect(screen.getByRole('button', { name: 'cookie.accept' })).toBeInTheDocument()
  })
})
