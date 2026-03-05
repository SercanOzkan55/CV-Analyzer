import React, { useEffect, useState } from 'react'
import { fetchCandidates, fetchTopCandidates } from '../api'

export default function Dashboard({ token }) {
  const [candidates, setCandidates] = useState([])
  const [top, setTop] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const c = await fetchCandidates(token)
        const t = await fetchTopCandidates(token)
        setCandidates(c || [])
        setTop(t || [])
      } catch (err) {
        setError(err.message || 'Fetch failed')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [token])

  if (loading) return <p>Loading recruiter data...</p>
  if (error) return <p className="error">{error}</p>

  return (
    <div>
      <h3>Candidates</h3>
      <ul>
        {candidates.map((c) => (
          <li key={c.id}>{c.name || c.email || c.id}</li>
        ))}
      </ul>

      <h3>Top Candidates</h3>
      <ul>
        {top.map((t) => (
          <li key={t.id}>{t.name || t.email || t.id} — {t.score ?? ''}</li>
        ))}
      </ul>
    </div>
  )
}
