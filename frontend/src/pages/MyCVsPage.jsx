import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Plus, Trash2, Download, Clock, Edit3 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'
import { deleteCvVersion, getCvVersion, listCvVersions, saveCvVersion } from '../api'

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
  const { user, token } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const userId = user?.id || user?.email || 'anon'

  const [cvs, setCvs] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')
  const [loadingRemote, setLoadingRemote] = useState(false)

  useEffect(() => {
    let cancelled = false
    const localItems = getVault(userId)
    setCvs(localItems)
    if (!token) return () => { cancelled = true }

    setLoadingRemote(true)
    listCvVersions(token, 50)
      .then(async (res) => {
        const items = Array.isArray(res?.items) ? res.items : []
        const detailed = await Promise.all(
          items.map((item) => getCvVersion(token, item.id).catch(() => item)),
        )
        if (cancelled) return
        const remoteItems = detailed.map((row) => ({
          id: `remote-${row.id}`,
          remoteId: row.id,
          name: row.version_label || row.source || `CV ${row.id}`,
          content: row.optimized_cv_text || row.cv_text || '',
          source: row.source || 'remote',
          score: row.match_score,
          createdAt: row.created_at || new Date().toISOString(),
          updatedAt: row.created_at || new Date().toISOString(),
        }))
        const localOnly = localItems.filter((item) => !item.remoteId)
        setCvs([...remoteItems, ...localOnly])
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingRemote(false) })

    return () => { cancelled = true }
  }, [userId, token])

  useEffect(() => {
    document.title = `${t('vault.title')} — CV Analyzer`
  }, [t])

  async function handleSave() {
    const name = newName.trim() || `CV ${cvs.length + 1}`
    const content = newContent.trim()
    if (!content) return
    let item = {
      id: Date.now().toString(36),
      name,
      content,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    if (token) {
      try {
        const saved = await saveCvVersion(token, {
          cv_text: content,
          version_label: name,
          source: 'vault',
          lang: 'en',
        })
        item = {
          ...item,
          id: `remote-${saved.id}`,
          remoteId: saved.id,
          source: saved.source || 'vault',
          score: saved.match_score,
          createdAt: saved.created_at || item.createdAt,
          updatedAt: saved.created_at || item.updatedAt,
        }
      } catch (err) {
        addToast(err?.message || 'Remote save failed; saved locally', 'warning')
      }
    }
    const updated = [item, ...cvs]
    setCvs(updated)
    setVault(userId, updated.filter((cv) => !cv.remoteId))
    setShowAdd(false)
    setNewName('')
    setNewContent('')
    addToast(t('vault.saved'), 'success')
  }

  async function handleDelete(id) {
    if (!window.confirm(t('vault.delete_confirm'))) return
    const current = cvs.find((c) => c.id === id)
    if (token && current?.remoteId) {
      try {
        await deleteCvVersion(token, current.remoteId)
      } catch (err) {
        addToast(err?.message || 'Remote delete failed', 'error')
        return
      }
    }
    const updated = cvs.filter((c) => c.id !== id)
    setCvs(updated)
    setVault(userId, updated.filter((cv) => !cv.remoteId))
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
        {loadingRemote && <p className="text-muted text-sm" style={{ marginBottom: '1rem' }}>Syncing saved CV versions...</p>}

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
