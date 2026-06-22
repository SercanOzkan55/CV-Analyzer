import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AnalyzePage from '../pages/AnalyzePage'

const mockCanAnalyze = vi.fn(() => true)
const mockRecordAnalysis = vi.fn()
const mockRefreshUsage = vi.fn()
const mockSignOut = vi.fn()
const mockAddToast = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'test@example.com', id: '123' },
    token: 'test-token',
    canAnalyze: mockCanAnalyze,
    recordAnalysis: mockRecordAnalysis,
    refreshUsage: mockRefreshUsage,
    signOut: mockSignOut,
    plan: 'free',
    planLoading: false,
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

const mockAnalyzePdf = vi.fn()
vi.mock('../api', async () => {
  const actual = await vi.importActual('../api')
  return {
    ...actual,
    analyzePdf: (...args) => mockAnalyzePdf(...args),
    autoFixCv: vi.fn(),
    buildSkillRoadmap: vi.fn(),
    exportAutoFixedCV: vi.fn(),
    fetchScoreBreakdown: vi.fn(),
    fetchJDTemplates: vi.fn().mockResolvedValue([]),
  }
})

vi.mock('../utils/historyStorage', () => ({
  addHistoryItem: vi.fn(),
}))

function createFile(name, sizeBytes, type) {
  const buffer = new ArrayBuffer(sizeBytes)
  return new File([buffer], name, { type })
}

function renderAnalyzePage() {
  return render(
    <MemoryRouter initialEntries={['/analyze']}>
      <AnalyzePage />
    </MemoryRouter>
  )
}

describe('AnalyzePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCanAnalyze.mockReturnValue(true)
  })

  describe('initial state', () => {
    it('renders the upload area', () => {
      renderAnalyzePage()

      expect(screen.getByText('analyze.upload_desc')).toBeInTheDocument()
    })

    it('renders the job description textarea', () => {
      renderAnalyzePage()

      expect(screen.getByPlaceholderText('analyze.job_desc_placeholder')).toBeInTheDocument()
    })

    it('renders the analyze button', () => {
      renderAnalyzePage()

      expect(screen.getByText('analyze.analyze_btn')).toBeInTheDocument()
    })

    it('does not show results before analysis', () => {
      renderAnalyzePage()

      expect(screen.queryByText('analyze.tab_overview')).not.toBeInTheDocument()
    })
  })

  describe('validation', () => {
    it('shows error when analyzing without a file', () => {
      renderAnalyzePage()

      const analyzeBtn = screen.getByText('analyze.analyze_btn')
      fireEvent.click(analyzeBtn)

      expect(screen.getByText('analyze.no_file')).toBeInTheDocument()
    })

    it('shows toast when daily limit is reached', () => {
      mockCanAnalyze.mockReturnValue(false)
      renderAnalyzePage()

      const dropZone = screen.getByRole('button', { name: /analyze\.upload_desc/i })
      const file = createFile('resume.pdf', 5000, 'application/pdf')
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

      const analyzeBtn = screen.getByText('analyze.analyze_btn')
      fireEvent.click(analyzeBtn)

      expect(mockAddToast).toHaveBeenCalledWith('toast.limit_reached', 'warning')
    })
  })

  describe('analysis flow', () => {
    it('calls analyzePdf and shows success toast on completion', async () => {
      const mockResult = {
        ats_score: 75,
        final_score: 78,
        ats: { section_scores: [] },
        skills: ['JavaScript', 'React'],
        missing_skills: [],
        warnings: [],
        score_suggestions: [],
      }
      mockAnalyzePdf.mockResolvedValue(mockResult)

      renderAnalyzePage()

      const dropZone = screen.getByRole('button', { name: /analyze\.upload_desc/i })
      const file = createFile('resume.pdf', 5000, 'application/pdf')
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

      const analyzeBtn = screen.getByText('analyze.analyze_btn')
      fireEvent.click(analyzeBtn)

      await waitFor(() => {
        expect(mockAnalyzePdf).toHaveBeenCalledWith(
          'test-token',
          expect.any(File),
          '',
          { lang: 'en' }
        )
      })

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalledWith('toast.analysis_complete', 'success')
        expect(mockRecordAnalysis).toHaveBeenCalled()
      })
    })

    it('handles API error and shows error message', async () => {
      mockAnalyzePdf.mockRejectedValue(new Error('Server error'))

      renderAnalyzePage()

      const dropZone = screen.getByRole('button', { name: /analyze\.upload_desc/i })
      const file = createFile('resume.pdf', 5000, 'application/pdf')
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

      const analyzeBtn = screen.getByText('analyze.analyze_btn')
      fireEvent.click(analyzeBtn)

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument()
      })
    })

    it('handles 401 error by signing out and navigating to login', async () => {
      mockAnalyzePdf.mockRejectedValue(new Error('Error 401: unauthorized'))

      renderAnalyzePage()

      const dropZone = screen.getByRole('button', { name: /analyze\.upload_desc/i })
      const file = createFile('resume.pdf', 5000, 'application/pdf')
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

      fireEvent.click(screen.getByText('analyze.analyze_btn'))

      await waitFor(() => {
        expect(mockSignOut).toHaveBeenCalled()
        expect(mockNavigate).toHaveBeenCalledWith('/login')
      })
    })

    it('handles 403 error by showing limit toast and refreshing usage', async () => {
      mockAnalyzePdf.mockRejectedValue(new Error('Error 403: forbidden'))

      renderAnalyzePage()

      const dropZone = screen.getByRole('button', { name: /analyze\.upload_desc/i })
      const file = createFile('resume.pdf', 5000, 'application/pdf')
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

      fireEvent.click(screen.getByText('analyze.analyze_btn'))

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalledWith('toast.limit_reached', 'warning')
        expect(mockRefreshUsage).toHaveBeenCalledWith('test-token', { background: true })
      })
    })
  })
})
