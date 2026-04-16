const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

function authHeaderFrom(token) {
  if (!token) return undefined
  const t = String(token).trim()
  return t.toLowerCase().startsWith('bearer ') ? t : `Bearer ${t}`
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

export async function autoFixCv(token, file, jobDescription, { lang = 'en', useAi = true } = {}) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('job_description', jobDescription || '')
  fd.append('lang', lang)
  fd.append('use_ai', String(useAi))

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
