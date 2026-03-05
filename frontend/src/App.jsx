import React, { useState } from 'react'
import UploadForm from './components/UploadForm'
import Dashboard from './components/Dashboard'

export default function App() {
  const [result, setResult] = useState(null)
  const [token, setToken] = useState('')

  return (
    <div className="container">
      <h1>CV Analyzer</h1>

      <section className="card">
        <h2>CV Upload</h2>
        <UploadForm setResult={setResult} token={token} />
      </section>

      <section className="card">
        <h2>Job Description</h2>
        <p>Use the form above to paste the job description and upload a PDF CV.</p>
      </section>

      <section className="card">
        <h2>API Token</h2>
        <input
          placeholder="Bearer token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </section>

      <section className="card">
        <h2>Result</h2>
        {result ? (
          <div>
            <p><strong>Score:</strong> {result.score ?? '—'}%</p>
            <p><strong>Matched skills:</strong></p>
            <ul>
              {(result.matched_skills || []).map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p>No result yet. Click Analyze to get a score.</p>
        )}
      </section>

      <section className="card">
        <h2>Recruiter Dashboard</h2>
        <Dashboard token={token} />
      </section>
    </div>
  )
}
