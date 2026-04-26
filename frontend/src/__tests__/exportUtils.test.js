import { describe, it, expect, vi } from 'vitest'
import {
  escapeCsv,
  escapeHtml,
  getMatchInterpretation,
  exportBatchToCSV
} from '../utils/exportUtils'

describe('exportUtils', () => {
  describe('escapeCsv', () => {
    it('escapes quotes in CSV fields', () => {
      expect(escapeCsv('John "Johnny" Doe')).toBe('"John ""Johnny"" Doe"')
    })

    it('escapes commas in CSV fields', () => {
      expect(escapeCsv('Doe, John')).toBe('"Doe, John"')
    })

    it('handles newlines', () => {
      expect(escapeCsv('Line 1\nLine 2')).toBe('"Line 1\nLine 2"')
    })

    it('returns quoted string for safety', () => {
      const result = escapeCsv('simple')
      expect(result.startsWith('"')).toBe(true)
      expect(result.endsWith('"')).toBe(true)
    })
  })

  describe('escapeHtml', () => {
    it('escapes HTML special characters', () => {
      expect(escapeHtml('<script>alert("XSS")</script>')).toContain('&lt;')
      expect(escapeHtml('<script>alert("XSS")</script>')).toContain('&gt;')
    })

    it('escapes ampersands', () => {
      expect(escapeHtml('A & B')).toBe('A &amp; B')
    })

    it('handles quotes', () => {
      expect(escapeHtml('Say "Hello"')).toContain('&quot;')
    })
  })

  describe('getMatchInterpretation', () => {
    it('returns Excellent for high scores', () => {
      expect(getMatchInterpretation(0.9)).toBe('Excellent Match')
      expect(getMatchInterpretation(1.0)).toBe('Excellent Match')
    })

    it('returns Good for mid-high scores', () => {
      expect(getMatchInterpretation(0.7)).toBe('Good Match')
      expect(getMatchInterpretation(0.75)).toBe('Good Match')
    })

    it('returns Fair for mid scores', () => {
      expect(getMatchInterpretation(0.5)).toBe('Fair Match')
      expect(getMatchInterpretation(0.6)).toBe('Fair Match')
    })

    it('returns Poor for low scores', () => {
      expect(getMatchInterpretation(0.3)).toBe('Poor Match')
      expect(getMatchInterpretation(0.0)).toBe('Poor Match')
    })
  })

  describe('exportBatchToCSV', () => {
    it('generates valid CSV with headers', () => {
      const mockBatch = {
        job_title: 'Senior Developer',
        results: [
          {
            candidate_name: 'John Doe',
            email: 'john@example.com',
            file_name: 'CV_John.pdf',
            final_score: 85,
            ats_score: 0.85,
            keyword_score: 0.82,
            skill_score: 0.79,
            semantic_score: 0.88,
            experience_score: 0.91,
            detected_strengths: 'Good backend skills',
            missing_skills: 'Frontend',
            skill_coverage: 0.75
          }
        ],
        created_at: new Date().toISOString()
      }

      const csv = exportBatchToCSV(mockBatch)
      
      // Check for headers
      expect(csv).toContain('Rank')
      expect(csv).toContain('Candidate Name')
      expect(csv).toContain('Email')
      expect(csv).toContain('Final Score')
      
      // Check for data
      expect(csv).toContain('John Doe')
      expect(csv).toContain('john@example.com')
    })

    it('handles multiple candidates', () => {
      const mockBatch = {
        job_title: 'Developer',
        results: [
          {
            candidate_name: 'John Doe',
            email: 'john@example.com',
            file_name: 'CV1.pdf',
            final_score: 85,
            ats_score: 0.85,
            keyword_score: 0.82,
            skill_score: 0.79,
            semantic_score: 0.88,
            experience_score: 0.91,
            detected_strengths: 'Strong',
            missing_skills: 'None',
            skill_coverage: 0.85
          },
          {
            candidate_name: 'Jane Smith',
            email: 'jane@example.com',
            file_name: 'CV2.pdf',
            final_score: 92,
            ats_score: 0.92,
            keyword_score: 0.90,
            skill_score: 0.88,
            semantic_score: 0.95,
            experience_score: 0.89,
            detected_strengths: 'Excellent',
            missing_skills: 'None',
            skill_coverage: 0.95
          }
        ],
        created_at: new Date().toISOString()
      }

      const csv = exportBatchToCSV(mockBatch)
      const lines = csv.trim().split('\n')
      
      // Header + 2 data rows
      expect(lines.length).toBe(3)
      expect(csv).toContain('Jane Smith')
    })
  })
})
