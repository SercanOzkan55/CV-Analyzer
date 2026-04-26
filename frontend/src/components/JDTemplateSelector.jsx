import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Plus, Trash2, ChevronDown, Save } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchJDTemplates, createJDTemplate, deleteJDTemplate } from '../api'

export default function JDTemplateSelector({ onSelect, currentText }) {
  const { token, plan } = useAuth()
  const [templates, setTemplates] = useState([])
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveTitle, setSaveTitle] = useState('')
  const [showSave, setShowSave] = useState(false)

  useEffect(() => {
    if (!token) return
    fetchJDTemplates(token)
      .then(res => setTemplates(res?.templates || []))
      .catch(() => {})
  }, [token])

  async function handleSave() {
    if (!saveTitle.trim() || !currentText?.trim()) return
    setSaving(true)
    try {
      const res = await createJDTemplate(token, saveTitle.trim(), currentText.trim())
      setTemplates(prev => [{ id: res.id, title: res.title, description: currentText.trim() }, ...prev])
      setSaveTitle('')
      setShowSave(false)
    } catch (err) {
      alert(err?.message || 'Şablon kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    try {
      await deleteJDTemplate(token, id)
      setTemplates(prev => prev.filter(t => t.id !== id))
    } catch { /* ignore */ }
  }

  return (
    <div className="jd-template-selector">
      <div className="jd-template-row">
        <button
          className="jd-template-toggle"
          onClick={() => setOpen(!open)}
          type="button"
        >
          <FileText size={14} />
          Şablonlar ({templates.length})
          <ChevronDown size={14} className={open ? 'rotated' : ''} />
        </button>
        {currentText?.trim() && (
          <button
            className="jd-template-save-btn"
            onClick={() => setShowSave(!showSave)}
            type="button"
            title="Mevcut JD'yi şablon olarak kaydet"
          >
            <Save size={14} />
            Kaydet
          </button>
        )}
      </div>

      <AnimatePresence>
        {showSave && (
          <motion.div
            className="jd-template-save-form"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <input
              type="text"
              placeholder="Şablon adı (örn: Frontend Developer)"
              value={saveTitle}
              onChange={(e) => setSaveTitle(e.target.value)}
              maxLength={120}
            />
            <button
              className="btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving || !saveTitle.trim()}
            >
              {saving ? '...' : 'Kaydet'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <motion.div
            className="jd-template-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            {templates.length === 0 ? (
              <p className="jd-template-empty">Henüz şablon yok. JD yazıp kaydedin.</p>
            ) : (
              templates.map(t => (
                <div key={t.id} className="jd-template-item">
                  <button
                    className="jd-template-item-btn"
                    onClick={() => { onSelect(t.description); setOpen(false) }}
                    type="button"
                  >
                    <span className="jd-template-item-title">{t.title}</span>
                    <span className="jd-template-item-preview">
                      {t.description?.slice(0, 80)}...
                    </span>
                  </button>
                  <button
                    className="btn-icon btn-danger-icon btn-xs"
                    onClick={() => handleDelete(t.id)}
                    title="Şablonu sil"
                    type="button"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
            {plan === 'free' && templates.length >= 3 && (
              <p className="jd-template-limit">Free planda max 3 şablon. Pro'ya yükseltin.</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
