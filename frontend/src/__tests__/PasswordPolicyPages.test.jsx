import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RegisterPage from '../pages/RegisterPage'
import SettingsPage from '../pages/SettingsPage'

const mocks = vi.hoisted(() => ({
  signUp: vi.fn(),
  updatePassword: vi.fn(),
  deleteUser: vi.fn(),
  addToast: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'user@example.com' },
    plan: 'free',
    planLoading: false,
    signUp: mocks.signUp,
    signInWithGoogle: vi.fn(),
    updatePassword: mocks.updatePassword,
    deleteUser: mocks.deleteUser,
  }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ t: (key) => key, lang: 'en', setLang: vi.fn() }),
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', setTheme: vi.fn() }),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => ({ addToast: mocks.addToast }),
}))

vi.mock('../components/Navbar', () => ({ default: () => <nav /> }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

function renderPage(page) {
  return render(<MemoryRouter>{page}</MemoryRouter>)
}

describe('new password surfaces', () => {
  beforeEach(() => vi.clearAllMocks())

  it('enforces 12 characters during registration', () => {
    const { container } = renderPage(<RegisterPage />)
    const passwordInputs = container.querySelectorAll('input[type="password"]')

    expect(passwordInputs).toHaveLength(2)
    expect(passwordInputs[0]).toHaveAttribute('minlength', '12')
    expect(passwordInputs[1]).toHaveAttribute('minlength', '12')

    fireEvent.change(container.querySelector('input[type="email"]'), { target: { value: 'user@example.com' } })
    fireEvent.change(passwordInputs[0], { target: { value: 'short-pass' } })
    fireEvent.change(passwordInputs[1], { target: { value: 'short-pass' } })
    fireEvent.submit(container.querySelector('form'))

    expect(screen.getByText('auth.password_min_length')).toBeInTheDocument()
    expect(mocks.signUp).not.toHaveBeenCalled()
  })

  it('enforces 12 characters when changing a password', () => {
    const { container } = renderPage(<SettingsPage />)
    const passwordInputs = container.querySelectorAll('input[type="password"]')

    expect(passwordInputs).toHaveLength(2)
    expect(passwordInputs[0]).toHaveAttribute('minlength', '12')
    expect(passwordInputs[1]).toHaveAttribute('minlength', '12')

    fireEvent.change(passwordInputs[0], { target: { value: 'short-pass' } })
    fireEvent.change(passwordInputs[1], { target: { value: 'short-pass' } })
    fireEvent.submit(passwordInputs[0].closest('form'))

    expect(screen.getByText('auth.password_min_length')).toBeInTheDocument()
    expect(mocks.updatePassword).not.toHaveBeenCalled()
  })
})
