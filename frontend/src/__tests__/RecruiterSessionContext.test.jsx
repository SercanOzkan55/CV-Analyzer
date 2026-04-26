import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { RecruiterSessionProvider, useRecruiterSession } from '../context/RecruiterSessionContext'

describe('RecruiterSessionContext', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
  })

  describe('saveBatchResult', () => {
    it('saves batch result to localStorage', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      const mockBatch = {
        id: 'batch-1',
        job_title: 'Developer',
        results: [],
        created_at: new Date().toISOString()
      }

      act(() => {
        result.current.saveBatchResult(mockBatch)
      })

      expect(result.current.batchResults).toEqual(
        expect.arrayContaining([expect.objectContaining({ id: 'batch-1' })])
      )
    })

    it('preserves existing batch results', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      const batch1 = { id: 'batch-1', job_title: 'Dev1', results: [] }
      const batch2 = { id: 'batch-2', job_title: 'Dev2', results: [] }

      act(() => {
        result.current.saveBatchResult(batch1)
      })

      act(() => {
        result.current.saveBatchResult(batch2)
      })

      expect(result.current.batchResults.length).toBe(2)
    })
  })

  describe('updateUsageRights', () => {
    it('updates usage quota', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.updateUsageRights({
          batch_analyses: 5,
          exports: 3,
          custom_searches: 10,
          emails_sent: 2
        })
      })

      expect(result.current.usageRights.batch_analyses.used).toBe(5)
      expect(result.current.usageRights.exports.used).toBe(3)
    })

    it('increments existing usage', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.updateUsageRights({ batch_analyses: 5 })
      })

      act(() => {
        result.current.updateUsageRights({ batch_analyses: 3 })
      })

      // Should sum up
      expect(result.current.usageRights.batch_analyses.used).toBeGreaterThanOrEqual(3)
    })
  })

  describe('saveCandidateAction', () => {
    it('saves accept decision', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.saveCandidateAction('candidate-1', 'accept')
      })

      expect(result.current.candidateActions['candidate-1']).toBe('accept')
    })

    it('saves reject decision', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.saveCandidateAction('candidate-1', 'reject')
      })

      expect(result.current.candidateActions['candidate-1']).toBe('reject')
    })

    it('overwrites previous decision', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.saveCandidateAction('candidate-1', 'accept')
      })

      act(() => {
        result.current.saveCandidateAction('candidate-1', 'reject')
      })

      expect(result.current.candidateActions['candidate-1']).toBe('reject')
    })
  })

  describe('clearAllData', () => {
    it('clears all session data', () => {
      const { result } = renderHook(() => useRecruiterSession(), {
        wrapper: RecruiterSessionProvider
      })

      act(() => {
        result.current.saveBatchResult({ id: 'batch-1', job_title: 'Dev' })
        result.current.updateUsageRights({ batch_analyses: 5 })
        result.current.saveCandidateAction('cand-1', 'accept')
      })

      act(() => {
        result.current.clearAllData()
      })

      expect(result.current.batchResults.length).toBe(0)
      expect(Object.keys(result.current.candidateActions).length).toBe(0)
      expect(result.current.usageRights.batch_analyses.used).toBe(0)
    })
  })
})
