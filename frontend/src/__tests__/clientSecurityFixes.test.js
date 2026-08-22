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
    expect(headers['Content-Security-Policy']).toContain('https://media2.dev.to')
    expect(headers['Content-Security-Policy']).toContain("frame-src 'self' blob:")
    expect(headers['Content-Security-Policy']).toContain("object-src 'none'")
    expect(headers['Content-Security-Policy']).toContain('pagead2.googlesyndication.com')
    expect(headers['Content-Security-Policy']).toContain('fundingchoicesmessages.google.com')
  })

  it('uses per-request nonces for AdSense scripts in production nginx', () => {
    const nginxConfig = fs.readFileSync(
      path.join(process.cwd(), '..', 'deploy', 'nginx.production.conf'),
      'utf8',
    )

    expect(nginxConfig).toContain("script-src 'nonce-$request_id'")
    expect(nginxConfig).toContain("'strict-dynamic'")
    expect(nginxConfig).toContain("sub_filter '<script' '<script nonce=\"$request_id\"'")
    expect(nginxConfig).toContain('location = /blog')
    expect(nginxConfig).toContain('location ^~ /blog/')
    expect(nginxConfig).toContain('X-Robots-Tag "noindex, nofollow"')
  })

  it('ships the AdSense loader and ownership tags review crawlers look for', () => {
    const html = fs.readFileSync(path.join(process.cwd(), 'index.html'), 'utf8')
    const adsTxt = fs.readFileSync(path.join(process.cwd(), 'public', 'ads.txt'), 'utf8')
    const robotsTxt = fs.readFileSync(path.join(process.cwd(), 'public', 'robots.txt'), 'utf8')
    const nginxConfig = fs.readFileSync(
      path.join(process.cwd(), '..', 'deploy', 'nginx.production.conf'),
      'utf8',
    )

    expect(html).toContain('name="google-adsense-account"')
    expect(html).toContain('id="site-structured-data"')
    // The loader must be in the raw HTML: AdSense review cannot approve a site
    // where the ad code is only reachable after client-side rendering.
    expect(html).toContain('pagead2.googlesyndication.com/pagead/js/adsbygoogle.js')
    expect(html).toContain('client=ca-pub-6737853186639192')
    expect(html).toContain('crossorigin="anonymous"')
    expect(adsTxt.trim()).toBe(
      'google.com, pub-6737853186639192, DIRECT, f08c47fec0942fa0',
    )
    expect(robotsTxt).toMatch(/^Allow: \/ads\.txt$/m)
    expect(nginxConfig).toContain('location = /ads.txt')
    expect(nginxConfig).toContain('try_files /ads.txt =404')
  })

  it('keeps the sitemap focused on reviewed first-party editorial pages', () => {
    const sitemap = fs.readFileSync(path.join(process.cwd(), 'public', 'sitemap.xml'), 'utf8')

    expect(sitemap).toContain('https://cvanalyzer.dev/editoryal-politika/')
    expect(sitemap).toContain('https://cvanalyzer.dev/en/ai-cv-analyzer/')
    expect(sitemap).toContain('https://cvanalyzer.dev/en/editorial-policy/')
    // Reachable contact information is an AdSense review requirement.
    expect(sitemap).toContain('https://cvanalyzer.dev/iletisim/')
    expect(sitemap).toContain('https://cvanalyzer.dev/en/contact/')
    expect(sitemap).not.toContain('https://cvanalyzer.dev/en/recruiter-cv-screening/')
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
