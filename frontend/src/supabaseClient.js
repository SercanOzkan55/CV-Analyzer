import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_KEY

if (!supabaseUrl || !supabaseKey) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_KEY environment variables')
}

const projectRef = new URL(supabaseUrl).hostname.split('.')[0]
export const SUPABASE_AUTH_STORAGE_KEY = `sb-${projectRef}-auth-token`

// Keep browser sessions scoped to the current tab. This narrows the window in
// which an XSS issue could recover a long-lived token from persistent storage.
const memoryFallback = new Map()
export const sessionAuthStorage = {
  getItem(key) {
    try {
      return window.sessionStorage.getItem(key) ?? memoryFallback.get(key) ?? null
    } catch {
      return memoryFallback.get(key) ?? null
    }
  },
  setItem(key, value) {
    try {
      window.sessionStorage.setItem(key, value)
      memoryFallback.delete(key)
    } catch {
      memoryFallback.set(key, value)
    }
  },
  removeItem(key) {
    try {
      window.sessionStorage.removeItem(key)
    } catch {}
    memoryFallback.delete(key)
  },
}

export function migrateLegacyAuthSession(storageKey = SUPABASE_AUTH_STORAGE_KEY) {
  if (typeof window === 'undefined') return

  try {
    const legacyKeys = []
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (key === storageKey || key?.startsWith(`${storageKey}.`)) legacyKeys.push(key)
    }

    for (const key of legacyKeys) {
      const legacyValue = window.localStorage.getItem(key)
      if (legacyValue !== null && sessionAuthStorage.getItem(key) === null) {
        sessionAuthStorage.setItem(key, legacyValue)
      }
      window.localStorage.removeItem(key)
    }
  } catch {
    // Storage can be blocked by the browser. Supabase will then use the
    // in-memory fallback above instead of persisting a token in localStorage.
  }
}

migrateLegacyAuthSession()

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    storage: sessionAuthStorage,
    storageKey: SUPABASE_AUTH_STORAGE_KEY,
    persistSession: true,
  },
})
