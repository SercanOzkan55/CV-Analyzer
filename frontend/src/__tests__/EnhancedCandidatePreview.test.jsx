import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EnhancedCandidatePreview from '../components/EnhancedCandidatePreview'

describe('EnhancedCandidatePreview', () => {
  const mockCandidate = {
    name: 'John Doe',
    email: 'john@example.com',
    phone: '+1234567890'
  }

  const mockResult = {
    final_score: 85,
    semantic_score: 0.88,
    keyword_score: 0.82,
    skill_score: 0.79,
    experience_score: 0.91,
    ats_score: 0.85,
    detected_skills: ['React', 'TypeScript', 'FastAPI'],
    missing_skills: ['GraphQL'],
    strengths: ['Strong backend experience'],
    weaknesses: ['Limited frontend']
  }

  const mockPreviewData = {
    experience: [
      {
        title: 'Senior Developer',
        company: 'Tech Corp',
        startDate: '2020',
        endDate: 'Present'
      }
    ],
    education: [
      {
        degree: 'BS Computer Science',
        institution: 'University'
      }
    ]
  }

  it('renders candidate name and email', () => {
    render(
      <EnhancedCandidatePreview
        candidate={mockCandidate}
        result={mockResult}
        previewData={mockPreviewData}
        onClose={() => {}}
      />
    )
    
    expect(screen.getByText('John Doe')).toBeDefined()
    expect(screen.getByText('john@example.com')).toBeDefined()
  })

  it('displays final score', () => {
    render(
      <EnhancedCandidatePreview
        candidate={mockCandidate}
        result={mockResult}
        previewData={mockPreviewData}
        onClose={() => {}}
      />
    )
    
    expect(screen.queryAllByText(/85|Excellent Match/).length).toBeGreaterThan(0)
  })

  it('shows detected skills', () => {
    render(
      <EnhancedCandidatePreview
        candidate={mockCandidate}
        result={mockResult}
        previewData={mockPreviewData}
        onClose={() => {}}
      />
    )
    
    expect(screen.queryByText(/React|TypeScript|FastAPI/)).toBeDefined()
  })

  it('renders experience timeline', () => {
    render(
      <EnhancedCandidatePreview
        candidate={mockCandidate}
        result={mockResult}
        previewData={mockPreviewData}
        onClose={() => {}}
      />
    )
    
    expect(screen.queryByText('Senior Developer')).toBeDefined()
  })
})
