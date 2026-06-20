import { describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({
  autoFixCv: vi.fn(),
  evaluateInterviewAnswer: vi.fn(),
  generateInterviewQuestions: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 'user-a' } }),
}))

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ lang: 'en', t: (key) => key }),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => ({ addToast: vi.fn() }),
}))

vi.mock('../components/Navbar', () => ({
  default: () => null,
}))

describe('interview session key helper', () => {
  it('uses a user-scoped key when user id is available', async () => {
    const { getInterviewSessionKey } = await import('../pages/InterviewSimulatorPage')

    expect(getInterviewSessionKey('user-a')).toBe('cv-analyzer:interview-session-v2_user-a')
  })

  it('falls back to the legacy key without a user id', async () => {
    const { getInterviewSessionKey } = await import('../pages/InterviewSimulatorPage')

    expect(getInterviewSessionKey('')).toBe('cv-analyzer:interview-session-v2')
  })
})
