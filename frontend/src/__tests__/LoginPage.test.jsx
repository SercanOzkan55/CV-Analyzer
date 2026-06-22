import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'

const mockSignIn = vi.fn()
const mockSignInWithGoogle = vi.fn()
const mockAddToast = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    signIn: mockSignIn,
    signInWithGoogle: mockSignInWithGoogle,
    user: null,
    token: null,
  }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    t: (key) => key,
    lang: 'en',
    setLang: vi.fn(),
    availableLanguages: ['en', 'tr'],
  }),
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: vi.fn(),
  }),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => ({ addToast: mockAddToast }),
  ToastProvider: ({ children }) => children,
}))

vi.mock('../components/NotificationCenter', () => ({
  default: () => <div data-testid="notification-center" />,
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form with email and password fields', () => {
    renderLoginPage()

    expect(screen.getByText('auth.login_title')).toBeInTheDocument()
    expect(screen.getByText('auth.email')).toBeInTheDocument()
    expect(document.querySelector('input[type="email"]')).toBeInTheDocument()
    expect(screen.getByText('auth.password')).toBeInTheDocument()
    expect(document.querySelector('input[type="password"]')).toBeInTheDocument()
  })

  it('renders Google sign-in button', () => {
    renderLoginPage()

    expect(screen.getByText('auth.sign_in_google')).toBeInTheDocument()
  })

  it('renders forgot password link', () => {
    renderLoginPage()

    expect(screen.getByText('auth.forgot_password')).toBeInTheDocument()
  })

  it('calls signIn with email and password on form submission', async () => {
    mockSignIn.mockResolvedValue({})
    renderLoginPage()

    const emailInput = document.querySelector('input[type="email"]')
    const passwordInput = document.querySelector('input[type="password"]')

    await userEvent.type(emailInput, 'user@test.com')
    await userEvent.type(passwordInput, 'password123')

    const submitBtn = screen.getByText('auth.sign_in')
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith('user@test.com', 'password123')
    })
  })

  it('navigates to dashboard on successful login', async () => {
    mockSignIn.mockResolvedValue({})
    renderLoginPage()

    const emailInput = document.querySelector('input[type="email"]')
    const passwordInput = document.querySelector('input[type="password"]')

    await userEvent.type(emailInput, 'user@test.com')
    await userEvent.type(passwordInput, 'password123')

    fireEvent.click(screen.getByText('auth.sign_in'))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
      expect(mockAddToast).toHaveBeenCalledWith('toast.login_success', 'success')
    })
  })

  it('displays error message on login failure', async () => {
    mockSignIn.mockRejectedValue(new Error('Invalid credentials'))
    renderLoginPage()

    const emailInput = document.querySelector('input[type="email"]')
    const passwordInput = document.querySelector('input[type="password"]')

    await userEvent.type(emailInput, 'user@test.com')
    await userEvent.type(passwordInput, 'wrong')

    fireEvent.click(screen.getByText('auth.sign_in'))

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })
  })

  it('calls signInWithGoogle when Google button is clicked', async () => {
    mockSignInWithGoogle.mockResolvedValue({})
    renderLoginPage()

    fireEvent.click(screen.getByText('auth.sign_in_google'))

    await waitFor(() => {
      expect(mockSignInWithGoogle).toHaveBeenCalledTimes(1)
    })
  })

  it('shows error when Google sign-in fails', async () => {
    mockSignInWithGoogle.mockRejectedValue(new Error('Google auth failed'))
    renderLoginPage()

    fireEvent.click(screen.getByText('auth.sign_in_google'))

    await waitFor(() => {
      expect(screen.getByText('Google auth failed')).toBeInTheDocument()
    })
  })

  it('disables submit button while loading', async () => {
    let resolveSignIn
    mockSignIn.mockImplementation(() => new Promise((resolve) => { resolveSignIn = resolve }))
    renderLoginPage()

    await userEvent.type(document.querySelector('input[type="email"]'), 'user@test.com')
    await userEvent.type(document.querySelector('input[type="password"]'), 'pass123')

    fireEvent.click(screen.getByText('auth.sign_in'))

    await waitFor(() => {
      const submitBtn = screen.getByRole('button', { name: 'common.loading' })
      expect(submitBtn).toBeDisabled()
    })

    resolveSignIn({})
  })
})
