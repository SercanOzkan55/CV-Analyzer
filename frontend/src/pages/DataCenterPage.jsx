import React, { useEffect, useState } from 'react'
import { Database, Download, FileJson, RefreshCw, Trash2 } from 'lucide-react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import { deleteMyData, exportMyData, fetchMyDataSummary } from '../api'

function saveJsonFile(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export default function DataCenterPage() {
  const { token, user } = useAuth()
  const { addToast } = useToast()
  const [summary, setSummary] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [scope, setScope] = useState('stored_cvs')

  useEffect(() => {
    document.title = 'Data Center - CV Analyzer'
    loadSummary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function loadSummary() {
    if (!token) return
    setLoading(true)
    try {
      const data = await fetchMyDataSummary(token)
      setSummary(data)
    } catch (err) {
      addToast(err.message || 'Veri ozeti alinamadi', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleExport(includeRaw) {
    setLoading(true)
    try {
      const data = await exportMyData(token, { includeRaw })
      setPreview(data)
      saveJsonFile(data, includeRaw ? 'cv-analyzer-data-full.json' : 'cv-analyzer-data-redacted.json')
      addToast('Veri export dosyasi hazirlandi', 'success')
    } catch (err) {
      addToast(err.message || 'Export basarisiz', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    const label = scope === 'all' ? 'tum hesap verileri' : scope
    if (!window.confirm(`${label} silinsin mi? Bu islem geri alinamaz.`)) return
    setLoading(true)
    try {
      await deleteMyData(token, scope)
      addToast('Veri silme islemi tamamlandi', 'success')
      await loadSummary()
    } catch (err) {
      addToast(err.message || 'Silme islemi basarisiz', 'error')
    } finally {
      setLoading(false)
    }
  }

  const cards = [
    ['CV versions', summary?.cv_versions ?? 0],
    ['Stored files', summary?.stored_cv_files ?? 0],
    ['Analyses', summary?.analyses ?? 0],
    ['Reminders', summary?.reminders ?? 0],
    ['Candidate actions', summary?.candidate_actions ?? 0],
    ['Usage days', summary?.usage_days ?? 0],
  ]

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content data-center-page" id="main-content">
        <div className="ops-header">
          <div>
            <span className="ops-kicker">Privacy Control</span>
            <h1>Data Center</h1>
            <p className="text-muted">Stored CVs, analyses, reminders and recruiter workspace data for {user?.email || 'your account'}.</p>
          </div>
          <button className="btn-outline" onClick={loadSummary} disabled={loading}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        <section className="ops-grid">
          {cards.map(([label, value]) => (
            <div className="admin-card data-metric-card" key={label}>
              <Database size={20} />
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </section>

        <section className="ops-grid ops-grid-wide">
          <div className="admin-card">
            <div className="admin-card-header">
              <FileJson size={18} className="admin-card-icon" />
              <h2>Export</h2>
            </div>
            <p className="text-muted">Redacted export keeps raw CV and note text out. Full export includes the raw fields you own.</p>
            <div className="ops-action-row">
              <button className="btn-primary" onClick={() => handleExport(false)} disabled={loading}>
                <Download size={16} /> Export Redacted
              </button>
              <button className="btn-outline" onClick={() => handleExport(true)} disabled={loading}>
                <Download size={16} /> Export Full
              </button>
            </div>
          </div>

          <div className="admin-card">
            <div className="admin-card-header">
              <Trash2 size={18} className="admin-card-icon" />
              <h2>Delete Data</h2>
            </div>
            <p className="text-muted">Delete a specific workspace area without touching unrelated data.</p>
            <div className="ops-inline-form">
              <select value={scope} onChange={(e) => setScope(e.target.value)}>
                <option value="stored_cvs">Stored CVs</option>
                <option value="analyses">Analyses</option>
                <option value="workspace">Workspace</option>
                <option value="all">All</option>
              </select>
              <button className="btn-danger" onClick={handleDelete} disabled={loading}>
                <Trash2 size={16} /> Delete
              </button>
            </div>
          </div>
        </section>

        {preview && (
          <section className="admin-card">
            <div className="admin-card-header">
              <FileJson size={18} className="admin-card-icon" />
              <h2>Last Export Preview</h2>
            </div>
            <pre className="ops-json-preview">{JSON.stringify(preview, null, 2).slice(0, 6000)}</pre>
          </section>
        )}
      </main>
    </div>
  )
}
