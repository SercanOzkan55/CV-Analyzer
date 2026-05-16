import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getHistoryStorageKey,
  getHistory,
  setHistory,
  addHistoryItem,
  removeHistoryItem,
  clearHistory,
} from '../utils/historyStorage'

// Mock localStorage
const localStorageMock = (() => {
  let store = {}
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => { store[key] = String(value) }),
    removeItem: vi.fn((key) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
  }
})()

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

const testUser = { id: 'u1', email: 'test@example.com' }

beforeEach(() => {
  localStorageMock.clear()
  vi.clearAllMocks()
})

describe('getHistoryStorageKey', () => {
  it('uses user id when present', () => {
    expect(getHistoryStorageKey({ id: '42' })).toBe('cv-analyzer-history:42')
  })

  it('falls back to email', () => {
    expect(getHistoryStorageKey({ email: 'A@B.COM' })).toBe('cv-analyzer-history:a@b.com')
  })

  it('falls back to anonymous', () => {
    expect(getHistoryStorageKey({})).toBe('cv-analyzer-history:anonymous')
  })
})

describe('getHistory', () => {
  it('returns empty array for new user', () => {
    expect(getHistory(testUser)).toEqual([])
  })

  it('returns stored items', () => {
    const key = getHistoryStorageKey(testUser)
    localStorageMock.setItem(key, JSON.stringify([{ id: 1 }]))
    expect(getHistory(testUser)).toEqual([{ id: 1 }])
  })

  it('returns empty array on corrupt data', () => {
    const key = getHistoryStorageKey(testUser)
    localStorageMock.setItem(key, 'not-json{{{')
    expect(getHistory(testUser)).toEqual([])
  })
})

describe('setHistory', () => {
  it('stores items and respects limit', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ id: i }))
    const result = setHistory(testUser, items, { limit: 3 })
    expect(result).toHaveLength(3)
    expect(result[0].id).toBe(0)
  })
})

describe('addHistoryItem', () => {
  it('prepends item to history', () => {
    setHistory(testUser, [{ id: 'old' }])
    const result = addHistoryItem(testUser, { id: 'new' })
    expect(result[0].id).toBe('new')
    expect(result[1].id).toBe('old')
  })
})

describe('removeHistoryItem', () => {
  it('removes item by id', () => {
    setHistory(testUser, [{ id: 'a' }, { id: 'b' }])
    const result = removeHistoryItem(testUser, 'a')
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('b')
  })
})

describe('clearHistory', () => {
  it('clears all items', () => {
    setHistory(testUser, [{ id: 1 }])
    clearHistory(testUser)
    expect(getHistory(testUser)).toEqual([])
  })
})
