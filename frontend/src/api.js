const BASE = import.meta.env.VITE_API_BASE || ''

export async function analyzePdf(token, file, jobDescription) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('job_description', jobDescription)

  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}/api/v1/analyze-pdf`, {
    method: 'POST',
    body: fd,
    headers,
  })

  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  return res.json()
}

export async function fetchCandidates(token) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/api/v1/recruiter/candidates`, { headers })
  if (!res.ok) return []
  return res.json()
}

export async function fetchTopCandidates(token) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/api/v1/recruiter/top_candidates`, { headers })
  if (!res.ok) return []
  return res.json()
}
