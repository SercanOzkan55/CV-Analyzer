import React, { useState } from 'react'
import { analyzePdf } from '../api'
import { CV_UPLOAD_ACCEPT, isSupportedCvUpload } from '../utils/fileTypes'

export default function UploadForm({ setResult, token }) {
  const [file, setFile] = useState(null)
  const [jobDesc, setJobDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleAnalyze(e) {
    e.preventDefault()
    setError(null)
    if (!file) return setError('Please select a CV file')
    if (!isSupportedCvUpload(file)) return setError('Please select a PDF, DOCX, or TXT file')

    try {
      setLoading(true)
      const data = await analyzePdf(token, file, jobDesc)
      setResult(data)
    } catch (err) {
      setError(err.message || 'Analyze failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleAnalyze} className="upload-form">
      <label>
        CV seç
        <input
          type="file"
          accept={CV_UPLOAD_ACCEPT}
          onChange={(e) => setFile(e.target.files[0])}
        />
      </label>

      <label>
        Job description
        <textarea
          rows={6}
          placeholder="Paste job description here"
          value={jobDesc}
          onChange={(e) => setJobDesc(e.target.value)}
        />
      </label>

      <div className="row">
        <button type="submit" disabled={loading}>
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
        {error && <span className="error">{error}</span>}
      </div>
    </form>
  )
}
