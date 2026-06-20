import { describe, expect, it, beforeEach, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

vi.mock('../supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signUp: vi.fn(),
      signInWithPassword: vi.fn(),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
      resetPasswordForEmail: vi.fn(),
      updateUser: vi.fn(),
    },
    rpc: vi.fn(),
  },
}))

describe('client security fixes', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('keeps camera, microphone, and blob previews allowed by deployment headers', () => {
    const vercelConfig = JSON.parse(
      fs.readFileSync(path.join(process.cwd(), 'vercel.json'), 'utf8'),
    )
    const headers = vercelConfig.headers[0].headers.reduce((acc, header) => {
      acc[header.key] = header.value
      return acc
    }, {})

    expect(headers['Permissions-Policy']).toContain('camera=(self)')
    expect(headers['Permissions-Policy']).toContain('microphone=(self)')
    expect(headers['Permissions-Policy']).toContain('geolocation=()')
    expect(headers['Content-Security-Policy']).toContain("img-src 'self' data: blob:")
    expect(headers['Content-Security-Policy']).toContain("frame-src 'self' blob:")
    expect(headers['Content-Security-Policy']).toContain("object-src 'self' blob:")
  })

  it('clears only the current user scoped local data plus legacy global keys', async () => {
    const { clearLocalUserData } = await import('../context/AuthContext')

    localStorage.setItem('recruiter_batch_results_2026-06_user-a', 'remove')
    localStorage.setItem('recruiter_batch_results_2026-06_user-b', 'keep')
    localStorage.setItem('cv_analyzer_job_tracker_user-a', 'remove')
    localStorage.setItem('cv_analyzer_job_tracker_user-b', 'keep')
    localStorage.setItem('cv-analyzer:interview-session-v2_user-a', 'remove')
    localStorage.setItem('cv-analyzer:interview-session-v2_user-b', 'keep')
    localStorage.setItem('cv_analyzer_job_tracker', 'legacy-remove')
    localStorage.setItem('cv-analyzer:interview-session-v2', 'legacy-remove')
    localStorage.setItem('recruiter_batch_results_2026-06', 'legacy-remove')

    clearLocalUserData('user-a')

    expect(localStorage.getItem('recruiter_batch_results_2026-06_user-a')).toBeNull()
    expect(localStorage.getItem('cv_analyzer_job_tracker_user-a')).toBeNull()
    expect(localStorage.getItem('cv-analyzer:interview-session-v2_user-a')).toBeNull()
    expect(localStorage.getItem('cv_analyzer_job_tracker')).toBeNull()
    expect(localStorage.getItem('cv-analyzer:interview-session-v2')).toBeNull()
    expect(localStorage.getItem('recruiter_batch_results_2026-06')).toBeNull()
    expect(localStorage.getItem('recruiter_batch_results_2026-06_user-b')).toBe('keep')
    expect(localStorage.getItem('cv_analyzer_job_tracker_user-b')).toBe('keep')
    expect(localStorage.getItem('cv-analyzer:interview-session-v2_user-b')).toBe('keep')
  })
})
