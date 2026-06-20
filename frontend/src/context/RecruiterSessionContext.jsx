import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext'

/**
 * @typedef {Object} RecruiterSessionContextValue
 * @property {Array} batchResults
 * @property {Array} candidateActions
 * @property {Array} decisions
 * @property {Object} usageRights
 * @property {function} saveBatchResult
 * @property {function} loadBatchResults
 * @property {function} saveCandidateAction
 * @property {function} loadCandidateActions
 * @property {function} saveDecision
 * @property {function} loadDecisions
 * @property {function} updateUsageRights
 * @property {function} loadUsageRights
 * @property {function} clearAllData
 */

const RECRUITER_SESSION_KEY = '__RECRUITER_SESSION__'

const RecruiterSessionContext = (() => {
  if (typeof globalThis !== 'undefined' && globalThis[RECRUITER_SESSION_KEY]) {
    return globalThis[RECRUITER_SESSION_KEY]
  }

  const ctx = createContext(/** @type {RecruiterSessionContextValue | null} */ (null))
  if (typeof globalThis !== 'undefined') {
    globalThis[RECRUITER_SESSION_KEY] = ctx
  }
  return ctx
})()

const DEFAULT_USAGE_RIGHTS = {
  batch_analyses: { used: 0, limit: 100 },
  exports: { used: 0, limit: 50 },
  custom_searches: { used: 0, limit: 50 },
  emails_sent: { used: 0, limit: 500 }
}

/**
 * Helper to safely manage localStorage
 */
function getStorageKey(type, userId) {
  const suffix = userId ? `_${userId}` : ''
  return `recruiter_${type}_${new Date().toISOString().slice(0, 7)}${suffix}`
}

function getUsageRightsKey(userId) {
  const suffix = userId ? `_${userId}` : ''
  return `recruiter_usage_rights${suffix}`
}

function safeJsonParse(str, defaultVal = null) {
  try {
    return JSON.parse(str)
  } catch {
    return defaultVal
  }
}

function safeJsonStringify(obj) {
  try {
    return JSON.stringify(obj)
  } catch {
    return null
  }
}

function defaultUsageRights() {
  return {
    ...DEFAULT_USAGE_RIGHTS,
    last_updated: new Date().toISOString()
  }
}

function normalizeUsageRights(current, updates = {}) {
  const normalized = { ...current }
  for (const [key, value] of Object.entries(updates)) {
    if (key === 'last_updated') continue
    const previous = current[key] || DEFAULT_USAGE_RIGHTS[key] || { used: 0, limit: 0 }
    if (typeof value === 'number') {
      normalized[key] = { ...previous, used: value }
    } else if (value && typeof value === 'object') {
      normalized[key] = { ...previous, ...value }
    } else {
      normalized[key] = value
    }
  }
  normalized.last_updated = updates.last_updated || new Date().toISOString()
  return normalized
}

/**
 * RecruiterSessionProvider - Persists recruiter session data
 */
export function RecruiterSessionProvider({ children }) {
  let user = null
  try {
    const auth = useAuth()
    user = auth?.user
  } catch (e) {
    // Safely ignore if rendered outside AuthProvider (e.g. in context unit tests)
  }
  const userId = user?.id || ''

  const [batchResults, setBatchResults] = useState([])
  const [candidateActions, setCandidateActions] = useState({}) // { candidateId: 'accepted'|'rejected' }
  const [decisions, setDecisions] = useState([]) // Array of { id, candidate_name, action, date, job_id }
  const [usageRights, setUsageRights] = useState(defaultUsageRights)

  // Load initial data from localStorage
  useEffect(() => {
    try {
      // Load batch results
      const batchKey = getStorageKey('batch_results', userId)
      const saved = localStorage.getItem(batchKey)
      if (saved) {
        const parsed = safeJsonParse(saved, [])
        setBatchResults(parsed)
      } else {
        setBatchResults([])
      }

      // Load candidate actions
      const actionsKey = getStorageKey('candidate_actions', userId)
      const savedActions = localStorage.getItem(actionsKey)
      if (savedActions) {
        const parsed = safeJsonParse(savedActions, {})
        setCandidateActions(parsed)
      } else {
        setCandidateActions({})
      }

      // Load decisions
      const decisionsKey = getStorageKey('decisions', userId)
      const savedDecisions = localStorage.getItem(decisionsKey)
      if (savedDecisions) {
        const parsed = safeJsonParse(savedDecisions, [])
        setDecisions(parsed)
      } else {
        setDecisions([])
      }

      // Load usage rights
      const usageKey = getUsageRightsKey(userId)
      const savedUsage = localStorage.getItem(usageKey)
      if (savedUsage) {
        const parsed = safeJsonParse(savedUsage, {})
        setUsageRights(prev => normalizeUsageRights(prev, parsed))
      } else {
        setUsageRights(defaultUsageRights())
      }
    } catch (e) {
      console.warn('Failed to load recruiter session data:', e)
    }
  }, [userId])

  // Batch Results
  const saveBatchResult = useCallback((result) => {
    try {
      const updated = [...batchResults, {
        ...result,
        id: result.id || `batch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        saved_at: new Date().toISOString()
      }]
      setBatchResults(updated)
      const batchKey = getStorageKey('batch_results', userId)
      const serialized = safeJsonStringify(updated)
      if (serialized) {
        localStorage.setItem(batchKey, serialized)
      }
    } catch (e) {
      console.error('Failed to save batch result:', e)
    }
  }, [batchResults, userId])

  const loadBatchResults = useCallback(() => {
    return batchResults
  }, [batchResults])

  // Candidate Actions
  const saveCandidateAction = useCallback((candidateId, action) => {
    try {
      const updated = { ...candidateActions, [candidateId]: action }
      setCandidateActions(updated)
      const actionsKey = getStorageKey('candidate_actions', userId)
      const serialized = safeJsonStringify(updated)
      if (serialized) {
        localStorage.setItem(actionsKey, serialized)
      }
    } catch (e) {
      console.error('Failed to save candidate action:', e)
    }
  }, [candidateActions, userId])

  const loadCandidateActions = useCallback(() => {
    return candidateActions
  }, [candidateActions])

  // Decisions
  const saveDecision = useCallback((decision) => {
    try {
      const updated = [...decisions, {
        ...decision,
        id: `decision_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        saved_at: new Date().toISOString()
      }]
      setDecisions(updated)
      const decisionsKey = getStorageKey('decisions', userId)
      const serialized = safeJsonStringify(updated)
      if (serialized) {
        localStorage.setItem(decisionsKey, serialized)
      }
    } catch (e) {
      console.error('Failed to save decision:', e)
    }
  }, [decisions, userId])

  const loadDecisions = useCallback(() => {
    return decisions
  }, [decisions])

  // Usage Rights
  const updateUsageRights = useCallback((updates) => {
    try {
      const updated = normalizeUsageRights(usageRights, updates)
      setUsageRights(updated)
      const usageKey = getUsageRightsKey(userId)
      const serialized = safeJsonStringify(updated)
      if (serialized) {
        localStorage.setItem(usageKey, serialized)
      }
    } catch (e) {
      console.error('Failed to update usage rights:', e)
    }
  }, [usageRights, userId])

  const loadUsageRights = useCallback(() => {
    return usageRights
  }, [usageRights])

  // Clear all data
  const clearAllData = useCallback(() => {
    try {
      setBatchResults([])
      setCandidateActions({})
      setDecisions([])
      setUsageRights(defaultUsageRights())
      
      // Clear localStorage
      const batchKey = getStorageKey('batch_results', userId)
      const actionsKey = getStorageKey('candidate_actions', userId)
      const decisionsKey = getStorageKey('decisions', userId)
      const usageKey = getUsageRightsKey(userId)
      localStorage.removeItem(batchKey)
      localStorage.removeItem(actionsKey)
      localStorage.removeItem(decisionsKey)
      localStorage.removeItem(usageKey)
    } catch (e) {
      console.error('Failed to clear data:', e)
    }
  }, [userId])

  const value = {
    batchResults,
    candidateActions,
    decisions,
    usageRights,
    saveBatchResult,
    loadBatchResults,
    saveCandidateAction,
    loadCandidateActions,
    saveDecision,
    loadDecisions,
    updateUsageRights,
    loadUsageRights,
    clearAllData
  }

  return (
    <RecruiterSessionContext.Provider value={value}>
      {children}
    </RecruiterSessionContext.Provider>
  )
}

/**
 * Hook to use RecruiterSessionContext
 */
export function useRecruiterSession() {
  const context = useContext(RecruiterSessionContext)
  if (!context) {
    throw new Error('useRecruiterSession must be used within RecruiterSessionProvider')
  }
  return context
}
