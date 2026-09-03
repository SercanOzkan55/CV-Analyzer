import { beforeEach, describe, expect, it, vi } from 'vitest'

const createClient = vi.fn(() => ({ auth: {} }))

vi.mock('@supabase/supabase-js', () => ({ createClient }))

describe('Supabase browser auth storage', () => {
  beforeEach(() => {
    vi.resetModules()
    createClient.mockClear()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('uses sessionStorage while preserving same-tab reloads', async () => {
    const { sessionAuthStorage, SUPABASE_AUTH_STORAGE_KEY } = await import('../supabaseClient')
    sessionAuthStorage.setItem(SUPABASE_AUTH_STORAGE_KEY, 'session-value')

    expect(sessionAuthStorage.getItem(SUPABASE_AUTH_STORAGE_KEY)).toBe('session-value')
    expect(sessionStorage.getItem(SUPABASE_AUTH_STORAGE_KEY)).toBe('session-value')
    expect(localStorage.getItem(SUPABASE_AUTH_STORAGE_KEY)).toBeNull()

    const options = createClient.mock.calls[0][2]
    expect(options.auth).toMatchObject({
      storage: sessionAuthStorage,
      storageKey: SUPABASE_AUTH_STORAGE_KEY,
      persistSession: true,
    })
  })

  it('migrates and removes a legacy localStorage session', async () => {
    const projectRef = new URL(import.meta.env.VITE_SUPABASE_URL).hostname.split('.')[0]
    const storageKey = `sb-${projectRef}-auth-token`
    localStorage.setItem(storageKey, 'legacy-session')
    localStorage.setItem(`${storageKey}.0`, 'legacy-session-chunk')

    const { SUPABASE_AUTH_STORAGE_KEY } = await import('../supabaseClient')

    expect(SUPABASE_AUTH_STORAGE_KEY).toBe(storageKey)
    expect(sessionStorage.getItem(storageKey)).toBe('legacy-session')
    expect(sessionStorage.getItem(`${storageKey}.0`)).toBe('legacy-session-chunk')
    expect(localStorage.getItem(storageKey)).toBeNull()
    expect(localStorage.getItem(`${storageKey}.0`)).toBeNull()
  })
})

describe('password policy', () => {
  it('requires at least 12 characters for newly created passwords', async () => {
    const { MIN_PASSWORD_LENGTH, meetsPasswordLength } = await import('../utils/passwordPolicy')

    expect(MIN_PASSWORD_LENGTH).toBe(12)
    expect(meetsPasswordLength('12345678901')).toBe(false)
    expect(meetsPasswordLength('123456789012')).toBe(true)
  })
})
