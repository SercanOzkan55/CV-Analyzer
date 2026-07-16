import { describe, expect, it } from 'vitest'
import { applyReviewDecisions, reviewDecisionMap } from '../utils/cvReview'

const operations = [
  { id: '0', kind: 'equal', before_lines: ['Jane Doe'], after_lines: ['Jane Doe'], accepted: true },
  { id: '1', kind: 'replace', before_lines: ['Built APIs'], after_lines: ['Developed reliable APIs'], accepted: true },
  { id: '2', kind: 'insert', before_lines: [], after_lines: ['SKILLS', 'Python'], accepted: true },
]

describe('CV review decisions', () => {
  it('accepts every generated change by default', () => {
    const decisions = reviewDecisionMap(operations)

    expect(applyReviewDecisions(operations, decisions)).toBe(
      'Jane Doe\nDeveloped reliable APIs\nSKILLS\nPython',
    )
  })

  it('restores source blocks when changes are rejected', () => {
    const decisions = { ...reviewDecisionMap(operations), 1: false, 2: false }

    expect(applyReviewDecisions(operations, decisions)).toBe('Jane Doe\nBuilt APIs')
  })
})
