import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Plus, Trash2, Download, Clock, Edit3 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'

const VAULT_KEY = 'cv_analyzer_vault'

function getVault(userId) {
  try {
    const key = `${VAULT_KEY}:${userId}`
    const data = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(data) ? data : []
  } catch { return [] }
}

function setVault(userId, items) {
  const key = `${VAULT_KEY}:${userId}`
  localStorage.setItem(key, JSON.stringify(items))
}

export default function MyCVsPage() {
  const { user } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const userId = user?.id || user?.email || 'anon'

  const [cvs, setCvs] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')

  useEffect(() => {
    setCvs(getVault(userId))
  }, [userId])

  useEffect(() => {
    document.title = `${t('vault.title')} — CV Analyzer`
  }, [t])

  function handleSave() {
    const name = newName.trim() || `CV ${cvs.length + 1}`
    const content = newContent.trim()
    if (!content) return
    const item = {
      id: Date.now().toString(36),
      name,
      content,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    const updated = [item, ...cvs]
    setCvs(updated)
    setVault(userId, updated)
    setShowAdd(false)
    setNewName('')
    setNewContent('')
    addToast(t('vault.saved'), 'success')
  }

  function handleDelete(id) {
    if (!window.confirm(t('vault.delete_confirm'))) return
    const updated = cvs.filter((c) => c.id !== id)
    setCvs(updated)
    setVault(userId, updated)
    addToast(t('vault.deleted'), 'success')
  }

  function handleDownload(cv) {
    const blob = new Blob([cv.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${cv.name.replace(/[^a-zA-Z0-9_-]/g, '_')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
            <div>
              <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={24} style={{ color: 'var(--color-accent)' }} />
                {t('vault.title')}
              </h1>
              <p className="text-muted">{t('vault.subtitle')}</p>
            </div>
            <motion.button
              className="btn-primary"
              onClick={() => setShowAdd(!showAdd)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              <Plus size={16} /> {t('vault.add_cv')}
            </motion.button>
          </div>
        </motion.div>

        {/* Add form */}
        <AnimatePresence>
          {showAdd && (
            <motion.div
              className="card"
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.3 }}
              style={{ overflow: 'hidden' }}
            >
              <h3>{t('vault.add_cv')}</h3>
              <div className="settings-field">
                <label>{t('vault.cv_name')}</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('vault.name_placeholder')}
                  className="job-desc-input"
                  style={{ maxWidth: 360 }}
                />
              </div>
              <div className="settings-field">
                <label>{t('vault.cv_content')}</label>
                <textarea
                  className="job-desc-input"
                  rows={8}
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder={t('vault.content_placeholder')}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn-primary btn-sm" onClick={handleSave}>{t('vault.save')}</button>
                <button className="btn-outline btn-sm" onClick={() => setShowAdd(false)}>{t('common.cancel')}</button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* CV list */}
        {cvs.length === 0 ? (
          <div className="db-empty-state" style={{ marginTop: '2rem' }}>
            <motion.span className="db-empty-icon" animate={{ y: [0, -8, 0] }} transition={{ duration: 3.5, repeat: Infinity }}>
              📁
            </motion.span>
            <h3>{t('vault.empty')}</h3>
            <p className="text-muted">{t('vault.empty_desc')}</p>
          </div>
        ) : (
          <motion.div
            className="vault-grid"
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.06 } } }}
          >
            {cvs.map((cv) => (
              <motion.div
                key={cv.id}
                className="vault-card"
                variants={{ hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }}
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
              >
                <div className="vault-card-header">
                  <FileText size={18} style={{ color: 'var(--color-accent)' }} />
                  <span className="vault-card-name">{cv.name}</span>
                </div>
                <p className="vault-card-preview">{cv.content.slice(0, 120)}…</p>
                <div className="vault-card-meta">
                  <Clock size={12} />
                  <span>{new Date(cv.updatedAt || cv.createdAt).toLocaleDateString()}</span>
                </div>
                <div className="vault-card-actions">
                  <Link to={`/cv-builder`} className="btn-outline btn-sm" title={t('vault.open_builder')}>
                    <Edit3 size={13} /> {t('vault.open_builder')}
                  </Link>
                  <button className="btn-outline btn-sm" onClick={() => handleDownload(cv)} title={t('vault.download')}>
                    <Download size={13} />
                  </button>
                  <button className="btn-outline btn-sm btn-danger-outline" onClick={() => handleDelete(cv.id)} title={t('vault.delete')}>
                    <Trash2 size={13} />
                  </button>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </main>
    </div>
  )
}
