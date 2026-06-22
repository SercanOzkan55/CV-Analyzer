import React from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../components/Toast'
import { vi } from 'vitest'

const defaultAuthValue = {
  user: null,
  token: null,
  loading: false,
  planLoading: false,
  plan: 'free',
  role: 'user',
  usageToday: 0,
  dailyLimit: 5,
  usageSource: 'local',
  isBillingAdmin: false,
  signUp: vi.fn(),
  signIn: vi.fn(),
  signInWithGoogle: vi.fn(),
  signOut: vi.fn(),
  deleteUser: vi.fn(),
  resetPassword: vi.fn(),
  updatePassword: vi.fn(),
  canAnalyze: vi.fn(() => true),
  recordAnalysis: vi.fn(),
  refreshUsage: vi.fn(),
}

const defaultLangValue = {
  t: (key) => key,
  lang: 'en',
  setLang: vi.fn(),
  availableLanguages: ['en', 'tr'],
  region: 'DEFAULT',
  pricing: { pro: '$19', free: '$0', enterprise: '$100', periodKey: 'pricing.period_monthly' },
}

const defaultThemeValue = {
  theme: 'light',
  setTheme: vi.fn(),
  toggleTheme: vi.fn(),
}

export function createMockAuth(overrides = {}) {
  return { ...defaultAuthValue, ...overrides }
}

export function createMockLang(overrides = {}) {
  return { ...defaultLangValue, ...overrides }
}

export function createMockTheme(overrides = {}) {
  return { ...defaultThemeValue, ...overrides }
}

/**
 * Render a component wrapped with all required providers.
 * Pass `authValue`, `langValue`, `themeValue` in options to override defaults.
 * Pass `route` to set the initial MemoryRouter entry.
 */
export function renderWithProviders(ui, options = {}) {
  const {
    authValue = defaultAuthValue,
    langValue = defaultLangValue,
    themeValue = defaultThemeValue,
    route = '/',
    ...renderOptions
  } = options

  // We mock the context hooks at the module level in each test file,
  // so the wrapper only needs Router and Toast.
  function Wrapper({ children }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <ToastProvider>
          {children}
        </ToastProvider>
      </MemoryRouter>
    )
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}
