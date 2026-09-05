import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Navbar from '../components/Navbar'

const mockSignOut = vi.fn()
let mockUser = null
let mockPlan = 'free'
let mockPlanLoading = false
const mockSetLang = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    signOut: mockSignOut,
    plan: mockPlan,
    planLoading: mockPlanLoading,
  }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    t: (key) => key,
    lang: 'en',
    setLang: mockSetLang,
    availableLanguages: ['en', 'tr'],
  }),
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: vi.fn(),
  }),
}))

vi.mock('../components/NotificationCenter', () => ({
  default: () => <div data-testid="notification-center" />,
}))

function renderNavbar(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Navbar />
    </MemoryRouter>
  )
}

describe('Navbar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = null
    mockPlan = 'free'
    mockPlanLoading = false
  })

  describe('unauthenticated (landing)', () => {
    it('shows login and register links when user is not signed in', () => {
      renderNavbar()

      expect(screen.getByText('nav.login')).toBeInTheDocument()
      expect(screen.getByText('nav.register')).toBeInTheDocument()
    })

    it('shows landing navigation links', () => {
      renderNavbar()

      expect(screen.getByText('nav.features')).toBeInTheDocument()
      expect(screen.getByText('nav.tools')).toBeInTheDocument()
      expect(screen.getByText('nav.faq')).toBeInTheDocument()
      expect(screen.getByText('CV writing and ATS guides')).toBeInTheDocument()
    })

    it('hides the blog link while VITE_ENABLE_BLOG is off', () => {
      renderNavbar()

      expect(screen.queryByText('Blog')).not.toBeInTheDocument()
    })

    it('does not show dashboard or analyze links', () => {
      renderNavbar()

      expect(screen.queryByText('nav.dashboard')).not.toBeInTheDocument()
      expect(screen.queryByText('nav.analyze')).not.toBeInTheDocument()
    })
  })

  describe('authenticated', () => {
    beforeEach(() => {
      mockUser = { email: 'test@example.com' }
    })

    it('shows authenticated navigation links', () => {
      renderNavbar('/dashboard')

      expect(screen.getByText('nav.dashboard')).toBeInTheDocument()
      expect(screen.getByText('nav.analyze')).toBeInTheDocument()
      expect(screen.getByText('nav.history')).toBeInTheDocument()
    })

    it('shows user email prefix', () => {
      renderNavbar('/dashboard')

      expect(screen.getByText('test')).toBeInTheDocument()
    })

    it('shows logout button and calls signOut on click', async () => {
      renderNavbar('/dashboard')

      const logoutBtn = screen.getByText('nav.logout')
      expect(logoutBtn).toBeInTheDocument()

      fireEvent.click(logoutBtn)
      expect(mockSignOut).toHaveBeenCalledTimes(1)
    })

    it('does not show login/register links when authenticated', () => {
      renderNavbar('/dashboard')

      expect(screen.queryByText('nav.login')).not.toBeInTheDocument()
    })

    it('shows tools dropdown with expected items', () => {
      renderNavbar('/dashboard')

      expect(screen.getByText('nav.tools')).toBeInTheDocument()
      expect(screen.getByText('nav.cv_builder')).toBeInTheDocument()
      expect(screen.getByText('nav.cover_letter')).toBeInTheDocument()
      expect(screen.getByText('nav.interview')).toBeInTheDocument()
      expect(screen.getByText('nav.job_tracker')).toBeInTheDocument()
    })
  })

  describe('mobile toggle', () => {
    it('has accessible hamburger button', () => {
      renderNavbar()

      const toggle = screen.getByLabelText('Open menu')
      expect(toggle).toBeInTheDocument()

      const spans = toggle.querySelectorAll('[aria-hidden="true"]')
      expect(spans).toHaveLength(3)
    })

    it('toggles aria-expanded on click', () => {
      renderNavbar()

      const toggle = screen.getByLabelText('Open menu')
      expect(toggle).toHaveAttribute('aria-expanded', 'false')

      fireEvent.click(toggle)
      expect(toggle).toHaveAttribute('aria-expanded', 'true')
    })
  })

  describe('accessibility', () => {
    it('has logo link with aria-label', () => {
      renderNavbar()

      expect(screen.getByLabelText('CV Analyzer home')).toBeInTheDocument()
    })

    it('has theme toggle with aria-label', () => {
      renderNavbar()

      expect(screen.getByLabelText('Toggle theme')).toBeInTheDocument()
    })

    it('shows only the manual English and Turkish language controls', () => {
      renderNavbar()

      const languageGroup = screen.getByRole('group', { name: 'settings.language' })
      expect(languageGroup).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('button', { name: 'TR' })).toHaveAttribute('aria-pressed', 'false')
      expect(screen.queryByRole('combobox', { name: 'settings.language' })).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'TR' }))
      expect(mockSetLang).toHaveBeenCalledWith('tr')
    })
  })
})
