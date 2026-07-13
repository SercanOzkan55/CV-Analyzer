import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ATSValidationCenter from '../components/ATSValidationCenter'

const result = {
  original_cv_text: 'Jane Doe\nBuilt APIs',
  optimized_cv_text: 'Jane Doe\nDeveloped reliable APIs',
  before_ats: { overall_score: 60 },
  after_ats: { overall_score: 82 },
  validation_center: {
    quality_score: 96,
    blocking_issues: [],
    checks: [
      { id: 'export_gate', status: 'pass', blocking: true, label: 'Safe export gate', detail: 'Passed.' },
    ],
    review_operations: [
      { id: '0', kind: 'equal', before_lines: ['Jane Doe'], after_lines: ['Jane Doe'], accepted: true },
      { id: '1', kind: 'replace', before_lines: ['Built APIs'], after_lines: ['Developed reliable APIs'], accepted: true },
    ],
    recruiter_snapshot: {
      full_name: 'Jane Doe',
      title: 'Backend Engineer',
      summary: 'Backend engineer focused on reliable services.',
      top_skills: ['Python', 'FastAPI'],
      latest_experience: { title: 'Engineer', company: 'Acme' },
      project_count: 2,
      education_count: 1,
    },
  },
}

function renderCenter(onEditedTextChange = vi.fn()) {
  render(
    <ATSValidationCenter
      result={result}
      editedText={result.optimized_cv_text}
      onEditedTextChange={onEditedTextChange}
      onExport={vi.fn()}
      onSaveVersion={vi.fn()}
      jobDescription="Backend Engineer"
      benchmark={{ percentile: 78 }}
      lang="en"
    />,
  )
  return onEditedTextChange
}

describe('ATSValidationCenter', () => {
  it('shows safety state and recruiter snapshot', () => {
    renderCenter()

    expect(screen.getByText('Safe')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /recruiter 10 sec/i }))
    expect(screen.getByText('Backend Engineer')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
  })

  it('restores the source block when a generated change is rejected', () => {
    const onEditedTextChange = renderCenter()

    fireEvent.click(screen.getByTitle('Reject'))

    expect(onEditedTextChange).toHaveBeenLastCalledWith('Jane Doe\nBuilt APIs')
  })
})
