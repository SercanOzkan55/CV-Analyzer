const DEFAULT_BASE = (() => {
  if (typeof window === 'undefined') return 'http://127.0.0.1:8001'
  const host = window.location.hostname
  if (host === 'localhost' || host === '127.0.0.1') {
    return 'http://127.0.0.1:8001'
  }
  return ''
})()

const BASE = import.meta.env.VITE_API_BASE || DEFAULT_BASE

function authHeaderFrom(token) {
  if (!token) return undefined
  const t = String(token).trim()
  return t.toLowerCase().startsWith('bearer ') ? t : `Bearer ${t}`
}

function notifyBillableUsage() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event('cv-analyzer:billable-usage'))
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function pollAnalysis(token, jobId, { timeoutMs = 60000, intervalMs = 1000 } = {}) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const started = Date.now()
  // Simple polling loop; stops on completed/failed or timeout
  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (Date.now() - started > timeoutMs) {
      throw new Error('Analysis timed out, please try again')
    }

    const res = await fetch(`${BASE}/api/v1/analysis/${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers,
    })

    if (!res.ok) {
      throw new Error(`Analysis status failed: ${res.status}`)
    }

    const data = await res.json()
    const status = data.status || ''

    if (status === 'completed') {
      // Backend wraps pipeline result under `result`
      return data.result || data
    }
    if (status === 'failed') {
      throw new Error(data.error || 'Analysis failed')
    }

    await sleep(intervalMs)
  }
}

export async function analyzePdf(token, file, jobDescription, { lang = 'en' } = {}) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('job_description', jobDescription)
  fd.append('lang', lang)

  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/analyze-pdf`, {
    method: 'POST',
    body: fd,
    headers,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Analyze failed: ${res.status}`)
  }

  const data = await res.json()

  // If the backend queued the job (Celery path), poll until it's ready.
  if (data && data.task_id && data.status && data.status === 'queued') {
    return pollAnalysis(token, data.task_id)
  }

  // LocalTask / synchronous mode returns the final pipeline result directly.
  return data
}

export async function autoFixCv(token, file, jobDescription, { lang = 'en', useAi = true, mode } = {}) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('job_description', jobDescription || '')
  fd.append('lang', lang)
  fd.append('use_ai', String(useAi))
  fd.append('mode', mode || (useAi ? 'strict' : 'safe'))

  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv/auto-fix`, {
    method: 'POST',
    body: fd,
    headers,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Auto-fix failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

export async function optimizeLinkedIn(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/linkedin/optimize`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `LinkedIn optimize failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

export async function fetchJobMatchScore(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/job/match-score`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Job match score failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

export async function exportAutoFixedCV(token, payload) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv/auto-fix/export`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Auto-fix export failed: ${res.status}`)
  }

  return res
}

export async function submitFeedback(token, payload) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/feedback`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload || {}),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Feedback failed: ${res.status}`)
  }

  return res.json()
}

export async function fetchFeedback(token, { limit = 30 } = {}) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/feedback?limit=${encodeURIComponent(limit)}`, {
    method: 'GET',
    headers,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Feedback fetch failed: ${res.status}`)
  }

  return res.json()
}

export async function parseAutoFixedCV(token, payload) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv/auto-fix/parse`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Auto-fix parse failed: ${res.status}`)
  }

  return res.json()
}

export async function fetchMe(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/me`, { headers })
  if (!res.ok) throw new Error(`fetchMe failed: ${res.status}`)
  return res.json()
}

export async function fetchSpecializationBenchmarks(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/benchmark/specializations`, { headers })
  if (!res.ok) throw new Error(`fetchSpecializationBenchmarks failed: ${res.status}`)
  return res.json()
}

export async function fetchGlobalBenchmark() {
  const res = await fetch(`${BASE}/api/v1/benchmark/global`)
  if (!res.ok) throw new Error(`fetchGlobalBenchmark failed: ${res.status}`)
  return res.json()
}

export async function fetchProfessionBenchmarks() {
  const res = await fetch(`${BASE}/api/v1/benchmark/professions`)
  if (!res.ok) throw new Error(`fetchProfessionBenchmarks failed: ${res.status}`)
  return res.json()
}

export async function fetchBlogFeed() {
  const res = await fetch(`${BASE}/api/v1/blog/feed`)
  if (!res.ok) throw new Error(`fetchBlogFeed failed: ${res.status}`)
  return res.json()
}

export async function fetchCandidates(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/candidates`, { headers })
  if (!res.ok) return []
  return res.json()
}

export async function fetchTopCandidates(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/top_candidates`, { headers })
  if (!res.ok) return []
  return res.json()
}

export async function searchRecruiter(token, query) {
  const q = String(query || '').trim()
  if (!q) return { results: [] }
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const url = `${BASE}/api/v1/recruiter/search?q=${encodeURIComponent(q)}`
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

export async function fetchRecruiterCandidateDetail(token, analysisId) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/candidate/${encodeURIComponent(analysisId)}`, { headers })
  if (!res.ok) throw new Error(`Candidate detail failed: ${res.status}`)
  return res.json()
}

export async function recruiterBatchRank(token, { jobDescription = '', jdFile = null, cvFiles = [] } = {}) {
  if (!Array.isArray(cvFiles) || cvFiles.length === 0) {
    throw new Error('At least one CV is required')
  }

  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const fd = new FormData()
  const jd = String(jobDescription || '').trim()
  if (jd) fd.append('job_description', jd)
  if (jdFile) fd.append('jd_file', jdFile)
  cvFiles.forEach((f) => fd.append('files', f))

  const res = await fetch(`${BASE}/api/v1/recruiter/batch-rank`, {
    method: 'POST',
    headers,
    body: fd,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Batch rank failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

export async function fetchUsage(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/usage`, { headers })
  if (!res.ok) throw new Error(`Usage fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchUsageHistory(token, days = 30) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/usage-history?days=${days}`, { headers })
  if (!res.ok) throw new Error(`Usage history fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchFavorites(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/favorites`, { headers })
  if (!res.ok) throw new Error(`Favorites fetch failed: ${res.status}`)
  return res.json()
}

export async function toggleFavorite(token, analysisId, note = '') {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/favorites/toggle`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ analysis_id: analysisId, note }),
  })
  if (!res.ok) throw new Error(`Toggle favorite failed: ${res.status}`)
  return res.json()
}

export async function fetchFavoriteIds(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/favorites/ids`, { headers })
  if (!res.ok) throw new Error(`Favorite IDs fetch failed: ${res.status}`)
  return res.json()
}

// â”€â”€ JD Templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function fetchJDTemplates(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/jd-templates`, { headers })
  if (!res.ok) throw new Error(`JD templates fetch failed: ${res.status}`)
  return res.json()
}

export async function createJDTemplate(token, title, description) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/jd-templates`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ title, description }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Create template failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteJDTemplate(token, templateId) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/jd-templates/${templateId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(`Delete template failed: ${res.status}`)
  return res.json()
}

// â”€â”€ Analysis Sharing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function createShareLink(token, analysisId) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/share`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ analysis_id: analysisId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Share failed: ${res.status}`)
  }
  return res.json()
}

export async function revokeShareLink(token, shareToken) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/share/${shareToken}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(`Revoke share failed: ${res.status}`)
  return res.json()
}

export async function fetchSharedAnalysis(shareToken) {
  const res = await fetch(`${BASE}/api/v1/shared/${shareToken}`)
  if (!res.ok) throw new Error(`Shared analysis not found: ${res.status}`)
  return res.json()
}

// â”€â”€ History CSV Export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function exportHistoryCSV(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/history/export`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Export failed: ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'cv_analysis_history.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// â”€â”€ Analysis Notes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function saveAnalysisNote(token, analysisId, content) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/notes`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ analysis_id: analysisId, content }),
  })
  if (!res.ok) throw new Error(`Save note failed: ${res.status}`)
  return res.json()
}

export async function fetchAnalysisNote(token, analysisId) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/notes/${analysisId}`, { headers })
  if (!res.ok) throw new Error(`Fetch note failed: ${res.status}`)
  return res.json()
}

export async function deleteAnalysisNote(token, analysisId) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/notes/${analysisId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(`Delete note failed: ${res.status}`)
  return res.json()
}

// â”€â”€ Usage Streak â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function fetchUsageStreak(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/usage-streak`, { headers })
  if (!res.ok) throw new Error(`Streak fetch failed: ${res.status}`)
  return res.json()
}

// â”€â”€ Dashboard Insights â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function fetchInsights(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/insights`, { headers })
  if (!res.ok) throw new Error(`Insights fetch failed: ${res.status}`)
  return res.json()
}

export async function createCheckoutSession(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/billing/checkout-session`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Checkout session failed: ${res.status}`)
  return res.json()
}

export async function createBillingPortalSession(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/billing/portal-session`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Billing portal failed: ${res.status}`)
  return res.json()
}

export async function createContactSalesRequest(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/billing/contact-sales`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Contact sales failed: ${res.status}`)
  return res.json()
}

export async function activatePremiumTrial(token, payload = {}) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/billing/activate-trial`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Activate premium trial failed: ${res.status}`)
  return res.json()
}

export async function fetchCVTemplates(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/cv-builder/templates`, { headers })
  if (!res.ok) throw new Error(`Fetch templates failed: ${res.status}`)
  return res.json()
}

export async function fetchFonts() {
  const res = await fetch(`${BASE}/api/v1/fonts`)
  if (!res.ok) throw new Error(`Fetch fonts failed: ${res.status}`)
  return res.json()
}

export async function generateCV(token, payload) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv-builder/generate`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `CV generation failed: ${res.status}`)
  }
  return res
}

export async function previewCV(token, payload) {
  const headers = {
    'Content-Type': 'application/json',
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv-builder/preview`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`CV preview failed: ${res.status}`)
  return res.json()
}

export async function suggestSummary(token, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv-builder/suggest-summary`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Summary suggestion failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

function withBillingAdminHeaders(token, adminToken, contentTypeJson = true) {
  const headers = {}
  if (contentTypeJson) {
    headers['Content-Type'] = 'application/json'
  }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  if (adminToken) headers['X-Billing-Admin-Token'] = String(adminToken).trim()
  return headers
}

export async function billingAdminMe(token, adminToken) {
  const res = await fetch(`${BASE}/api/v1/billing/admin/me`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Billing admin access check failed: ${res.status}`)
  }
  return res.json()
}

export async function billingAdminListUsers(token, adminToken, query = {}) {
  const params = new URLSearchParams()
  const limit = Number(query.limit ?? 50)
  const offset = Number(query.offset ?? 0)
  params.set('limit', String(Number.isFinite(limit) ? limit : 50))
  params.set('offset', String(Number.isFinite(offset) ? offset : 0))

  const email = String(query.email || '').trim()
  if (email) params.set('email', email)
  const planType = String(query.plan_type || '').trim()
  if (planType) params.set('plan_type', planType)

  const res = await fetch(`${BASE}/api/v1/billing/admin/users?${params.toString()}`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Billing admin users fetch failed: ${res.status}`)
  }
  return res.json()
}

export async function billingAdminSetUserPlan(token, adminToken, payload = {}) {
  const res = await fetch(`${BASE}/api/v1/billing/admin/set-user-plan`, {
    method: 'POST',
    headers: withBillingAdminHeaders(token, adminToken, true),
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Billing admin set plan failed: ${res.status}`)
  }
  return res.json()
}

export async function billingAdminListFeedback(token, adminToken, { limit = 50 } = {}) {
  const res = await fetch(`${BASE}/api/v1/billing/admin/feedback?limit=${encodeURIComponent(limit)}`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Billing admin feedback fetch failed: ${res.status}`)
  }
  return res.json()
}

export async function adminOpsHealth(token, adminToken) {
  const res = await fetch(`${BASE}/api/v1/admin/ops/health`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Ops health failed: ${res.status}`)
  }
  return res.json()
}

export async function adminOpsCost(token, adminToken) {
  const res = await fetch(`${BASE}/api/v1/admin/ops/cost`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Ops cost failed: ${res.status}`)
  }
  return res.json()
}

export async function adminOpsSecurity(token, adminToken) {
  const res = await fetch(`${BASE}/api/v1/admin/ops/security`, {
    method: 'GET',
    headers: withBillingAdminHeaders(token, adminToken, false),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Ops security failed: ${res.status}`)
  }
  return res.json()
}

export async function adminOpsEmailTest(token, adminToken, payload = {}) {
  const res = await fetch(`${BASE}/api/v1/admin/ops/email/test`, {
    method: 'POST',
    headers: withBillingAdminHeaders(token, adminToken, true),
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Email test failed: ${res.status}`)
  }
  return res.json()
}

export async function adminParserRegression(token, adminToken, payload = {}) {
  const res = await fetch(`${BASE}/api/v1/admin/parser/regression`, {
    method: 'POST',
    headers: withBillingAdminHeaders(token, adminToken, true),
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Parser regression failed: ${res.status}`)
  }
  return res.json()
}


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// CV Optimizer â€” Rewrite + Keyword Optimization + Score Breakdown
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

export async function rewriteCV(token, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv/rewrite`, {
    method: 'POST', headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Rewrite failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

export async function optimizeKeywords(token, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/cv/optimize-keywords`, {
    method: 'POST', headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Keyword optimize failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

export async function fetchScoreBreakdown(token, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/score/breakdown`, {
    method: 'POST', headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Score breakdown failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

export async function recruiterAdvancedSearch(token, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/recruiter/advanced-search`, {
    method: 'POST', headers,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Advanced search failed: ${res.status}`)
  }
  return res.json()
}

// â”€â”€ Recruiter Dashboard API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function _recruiterJson(token, path, method = 'GET', payload = null) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const opts = { method, headers }
  if (payload) opts.body = JSON.stringify(payload)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = Array.isArray(err.detail)
      ? err.detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ')
      : err.detail
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export async function recruiterScanCV(token, formData) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/scan-cv`, {
    method: 'POST',
    headers,
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = Array.isArray(err.detail)
      ? err.detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ')
      : err.detail
    throw new Error(detail || `Scan failed: ${res.status}`)
  }
  notifyBillableUsage()
  return res.json()
}

// â”€â”€ Cover Letter Generator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function generateCoverLetter(token, payload = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/rewrite/cover-letter`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Cover letter generation failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

// â”€â”€ Interview Simulator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export async function generateInterviewQuestions(token, payload = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/interview/questions`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Interview questions failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

export async function evaluateInterviewAnswer(token, payload = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const res = await fetch(`${BASE}/api/v1/interview/evaluate`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Interview evaluation failed: ${res.status}`)
  }

  notifyBillableUsage()
  return res.json()
}

// ── User reminders / job tracker notifications ─────────────────────────────

async function _reminderJson(token, path, method = 'GET', payload = null) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth

  const opts = { method, headers }
  if (payload) opts.body = JSON.stringify(payload)

  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = Array.isArray(err.detail)
      ? err.detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ')
      : err.detail
    throw new Error(detail || `Reminder request failed: ${res.status}`)
  }
  return res.json()
}

export async function listReminders(token) {
  return _reminderJson(token, '/api/v1/reminders')
}

export async function createReminder(token, payload) {
  return _reminderJson(token, '/api/v1/reminders', 'POST', payload)
}

export async function updateReminder(token, reminderId, payload) {
  return _reminderJson(token, `/api/v1/reminders/${reminderId}`, 'PUT', payload)
}

export async function deleteReminder(token, reminderId) {
  return _reminderJson(token, `/api/v1/reminders/${reminderId}`, 'DELETE')
}

export async function sendReminderTest(token, reminderId) {
  return _reminderJson(token, `/api/v1/reminders/${reminderId}/send-test`, 'POST')
}

export async function fetchMyDataSummary(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/me/data-summary`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Data summary failed: ${res.status}`)
  }
  return res.json()
}

export async function exportMyData(token, { includeRaw = false } = {}) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/me/data-export?include_raw=${includeRaw ? 'true' : 'false'}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Data export failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteMyData(token, scope = 'stored_cvs') {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const params = new URLSearchParams({ scope, confirm: 'DELETE' })
  const res = await fetch(`${BASE}/api/v1/me/data?${params.toString()}`, { method: 'DELETE', headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Data delete failed: ${res.status}`)
  }
  return res.json()
}

export async function fetchTemplateMarketplace(token) {
  const headers = {}
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/cv-builder/template-marketplace`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Template marketplace failed: ${res.status}`)
  }
  return res.json()
}

export async function fetchDemoSampleWorkspace() {
  const res = await fetch(`${BASE}/api/v1/demo/sample-workspace`)
  if (!res.ok) throw new Error(`Demo workspace failed: ${res.status}`)
  return res.json()
}

export async function checkJobDescriptionQuality(token, jobDescription, jdSkills = []) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/job-description/quality`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ job_description: jobDescription, jd_skills: jdSkills }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `JD quality failed: ${res.status}`)
  }
  return res.json()
}

export async function diffCvText(token, originalText, optimizedText) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/cv/diff`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ original_text: originalText, optimized_text: optimizedText }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `CV diff failed: ${res.status}`)
  }
  return res.json()
}


// ¦¦ Recruiter SaaS Batch Hub ¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦

// --- Recruiter SaaS Functions (Enterprise) ---

export async function recruiterListJobs(token) {
  const headers = { 'Content-Type': 'application/json' };
  const auth = authHeaderFrom(token);
  if (auth) headers['Authorization'] = auth;

  const res = await fetch(`${BASE}/api/v1/recruiter/jobs`, { headers });
  if (!res.ok) throw new Error('Failed to fetch jobs');
  return res.json();
}

export async function recruiterDashboardActions(token, jobId) {
  const headers = { 'Content-Type': 'application/json' };
  const auth = authHeaderFrom(token);
  if (auth) headers['Authorization'] = auth;

  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/actions/${jobId}`, { headers });
  if (!res.ok) throw new Error('Failed to fetch candidates');
  return res.json();
}

export async function recruiterPipeline(token, jobId) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/pipeline/${jobId}`, { headers })
  if (!res.ok) throw new Error('Failed to fetch pipeline')
  return res.json()
}

export async function recruiterUpdateActionStage(token, actionId, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const auth = authHeaderFrom(token)
  if (auth) headers['Authorization'] = auth
  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/actions/${actionId}/stage`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update pipeline stage')
  }
  return res.json()
}

export async function recruiterSaaSBatchUpload(token, jobId, files) {
  const headers = {};
  const auth = authHeaderFrom(token);
  if (auth) headers['Authorization'] = auth;

  const fd = new FormData();
  fd.append('job_id', jobId);
  files.forEach((f) => fd.append('files', f));

  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/batch-upload`, {
    method: 'POST',
    headers,
    body: fd,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Batch upload failed');
  }
  notifyBillableUsage();
  return res.json();
}

export async function downloadRecruiterReport(token, jobId) {
  const headers = {};
  const auth = authHeaderFrom(token);
  if (auth) headers['Authorization'] = auth;

  const res = await fetch(`${BASE}/api/v1/recruiter/report/${jobId}`, { headers });
  if (!res.ok) throw new Error('Download failed');
  return res.blob();
}


// --- Legacy Recruiter Functions (Keeping for compatibility) ---

export const recruiterCreateJob = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/jobs`, {
    method: 'POST',
    headers: { 
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  return res.json();
}

export const recruiterDashboardRank = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/rank`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (res.ok) notifyBillableUsage();
  return res.json();
}

export const recruiterDashboardPreview = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/preview`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (res.ok) notifyBillableUsage();
  return res.json();
}

export const recruiterDashboardAction = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/dashboard/action`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}

export const recruiterCreateTemplate = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/templates`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}

export const recruiterListTemplates = async (token) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/templates`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
}

export const recruiterDeleteTemplate = async (token, templateId) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/templates/${templateId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
}

export const recruiterPreviewTemplate = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/templates/preview`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}

export const recruiterSendEmail = async (token, payload) => {
  const res = await fetch(`${BASE}/api/v1/recruiter/send-email`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}
