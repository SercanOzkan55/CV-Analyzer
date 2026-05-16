import React, { useEffect, useState } from 'react'
import { ArrowRight, LayoutTemplate, Lock, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import { fetchTemplateMarketplace } from '../api'

export default function TemplateMarketplacePage() {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [templates, setTemplates] = useState([])
  const [plan, setPlan] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    document.title = 'Template Marketplace - CV Analyzer'
    loadTemplates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function loadTemplates() {
    if (!token) return
    setLoading(true)
    try {
      const data = await fetchTemplateMarketplace(token)
      setPlan(data.plan || '')
      setTemplates(Array.isArray(data.templates) ? data.templates : [])
    } catch (err) {
      addToast(err.message || 'Template listesi alinamadi', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content template-marketplace-page" id="main-content">
        <div className="ops-header">
          <div>
            <span className="ops-kicker">CV Builder</span>
            <h1>Template Marketplace</h1>
            <p className="text-muted">Pick ATS-safe templates by role, seniority and use case. Current plan: {plan || '-'}</p>
          </div>
          <button className="btn-outline" onClick={loadTemplates} disabled={loading}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        <section className="template-market-grid">
          {templates.map((item) => (
            <article className={`admin-card template-market-card ${item.available ? '' : 'template-locked'}`} key={item.id}>
              <div className="template-preview-box">
                <div className="template-preview-line template-preview-title" />
                <div className="template-preview-line" />
                <div className="template-preview-line short" />
                <div className="template-preview-section" />
                <div className="template-preview-line" />
                <div className="template-preview-line" />
                <div className="template-preview-line short" />
              </div>
              <div className="template-market-body">
                <div className="template-market-title">
                  <LayoutTemplate size={18} />
                  <h2>{item.name}</h2>
                  {!item.available && <Lock size={16} />}
                </div>
                <span className="template-category">{item.category}</span>
                <p className="text-muted">{item.description}</p>
                <div className="template-tags">
                  {(item.best_for || []).map((tag) => <span key={tag}>{tag}</span>)}
                </div>
                <Link className={item.available ? 'btn-primary btn-sm' : 'btn-outline btn-sm'} to={item.available ? `/cv-builder?template=${item.id}` : '/pricing'}>
                  {item.available ? 'Use Template' : 'Upgrade'} <ArrowRight size={14} />
                </Link>
              </div>
            </article>
          ))}
        </section>
      </main>
    </div>
  )
}
