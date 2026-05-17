import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Star, Download, Share2, StickyNote, Copy, Check } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'
import Modal from '../components/Modal'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'
import { getHistory, removeHistoryItem, clearHistory } from '../utils/historyStorage'
import { toggleFavorite, fetchFavoriteIds, exportHistoryCSV, createShareLink, saveAnalysisNote, fetchAnalysisNote, downloadAnalysisReport } from '../api'
import UpgradePrompt from '../components/UpgradePrompt'

export default function HistoryPage() {
  const { user, token, plan } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const [history, setHistoryState] = useState(() => getHistory(user))
  const [selected, setSelected] = useState(null)
  const [favoriteIds, setFavoriteIds] = useState(new Set())
  const [togglingFav, setTogglingFav] = useState(null)

  useEffect(() => {
    document.title = `${t('nav.history')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    setHistoryState(getHistory(user))
    setSelected(null)
  }, [user])

  // Load favorited analysis IDs
  useEffect(() => {
    if (!token) return
    fetchFavoriteIds(token)
      .then(res => setFavoriteIds(new Set(res?.ids || [])))
      .catch(() => {})
  }, [token])

  async function handleToggleFavorite(e, item) {
    e.stopPropagation()
    if (!item.analysis_id || !token) {
      addToast('Bu analiz favorilere eklenemez', 'warning')
      return
    }
    setTogglingFav(item.analysis_id)
    try {
      const res = await toggleFavorite(token, item.analysis_id)
      setFavoriteIds(prev => {
        const next = new Set(prev)
        if (res.favorited) next.add(item.analysis_id)
        else next.delete(item.analysis_id)
        return next
      })
      addToast(res.favorited ? 'Favorilere eklendi ⭐' : 'Favorilerden çıkarıldı', 'success')
    } catch (err) {
      addToast(err?.message || 'Favori işlemi başarısız', 'error')
    } finally {
      setTogglingFav(null)
    }
  }

  // CSV export
  const [exporting, setExporting] = useState(false)
  const [showUpgrade, setShowUpgrade] = useState(false)
  const [upgradeFeature, setUpgradeFeature] = useState('')

  async function handleExportCSV() {
    if (plan === 'free') {
      setUpgradeFeature('CSV Dışa Aktarım')
      setShowUpgrade(true)
      return
    }
    setExporting(true)
    try {
      await exportHistoryCSV(token)
      addToast('CSV indirildi!', 'success')
    } catch (err) {
      addToast(err?.message || 'Export başarısız', 'error')
    } finally {
      setExporting(false)
    }
  }

  // Share link
  const [shareUrl, setShareUrl] = useState(null)
  const [copied, setCopied] = useState(false)

  async function handleShare(item) {
    if (!item?.analysis_id) {
      addToast('Bu analiz paylaşılamaz', 'warning')
      return
    }
    if (plan === 'free') {
      setUpgradeFeature('Analiz Paylaşımı')
      setShowUpgrade(true)
      return
    }
    try {
      const res = await createShareLink(token, item.analysis_id)
      const url = `${window.location.origin}/shared/${res.share_token}`
      setShareUrl(url)
      await navigator.clipboard.writeText(url)
      setCopied(true)
      addToast('Paylaşım linki kopyalandı!', 'success')
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      addToast(err?.message || 'Paylaşım başarısız', 'error')
    }
  }

  // Inline note
  const [noteText, setNoteText] = useState('')
  const [noteLoading, setNoteLoading] = useState(false)
  const [noteSaved, setNoteSaved] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)

  useEffect(() => {
    if (!selected?.analysis_id || !token) { setNoteText(''); return }
    setShareUrl(null)
    fetchAnalysisNote(token, selected.analysis_id)
      .then(res => setNoteText(res?.content || ''))
      .catch(() => setNoteText(''))
  }, [selected?.analysis_id, token])

  async function handleSaveNote() {
    if (!selected?.analysis_id || !token) return
    setNoteLoading(true)
    try {
      await saveAnalysisNote(token, selected.analysis_id, noteText)
      setNoteSaved(true)
      setTimeout(() => setNoteSaved(false), 2000)
    } catch { /* ignore */ }
    finally { setNoteLoading(false) }
  }

  async function handleDownloadReport(item) {
    if (!item?.analysis_id || !token) {
      addToast('Bu analiz rapor olarak indirilemez', 'warning')
      return
    }
    setReportLoading(true)
    try {
      await downloadAnalysisReport(token, item.analysis_id)
      addToast('PDF rapor indirildi', 'success')
    } catch (err) {
      addToast(err?.message || 'Rapor indirilemedi', 'error')
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    document.title = `${t('nav.history')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    setHistoryState(getHistory(user))
    setSelected(null)
  }, [user])

  function handleDelete(id) {
    const updated = removeHistoryItem(user, id)
    setHistoryState(updated)
    addToast(t('toast.analysis_deleted'), 'info')
    if (selected?.id === id) setSelected(null)
  }

  function handleClearAll() {
    clearHistory(user)
    setHistoryState([])
    setSelected(null)
    addToast(t('toast.history_cleared'), 'info')
  }

  function getScoreColor(score) {
    if (score >= 75) return '#22c55e'
    if (score >= 50) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div>
            <h1>{t('history.title')}</h1>
            <p className="text-muted">{t('history.subtitle')}</p>
          </div>
          <div className="history-header-actions">
            {history.length > 0 && (
              <motion.button
                className="btn-outline btn-sm"
                onClick={handleExportCSV}
                disabled={exporting}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                title="CSV olarak indir"
              >
                <Download size={14} /> {exporting ? '...' : 'CSV'}
              </motion.button>
            )}
            {history.length > 0 && (
              <motion.button
                className="btn-outline btn-danger"
                onClick={handleClearAll}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
              >
                {t('history.delete_all')}
              </motion.button>
            )}
          </div>
        </motion.div>

        {history.length > 0 ? (
          <div className="history-grid">
            {/* History List */}
            <div className="history-list">
              {history.map((item, i) => (
                <motion.div
                  key={item.id}
                  className={`history-item ${selected?.id === item.id ? 'active' : ''}`}
                  onClick={() => setSelected(item)}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.3 }}
                  whileHover={{ x: 6, transition: { duration: 0.15 } }}
                >
                  <div className="history-item-left">
                    <span className="score-badge" style={{ color: getScoreColor(item.score) }}>
                      {Math.round(item.score)}%
                    </span>
                    <div>
                      <p className="history-job">{item.jobTitle || item.fileName || '-'}</p>
                      <p className="text-muted text-xs">{new Date(item.date).toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="history-item-actions">
                    <button
                      className={`btn-icon btn-fav-icon ${item.analysis_id && favoriteIds.has(item.analysis_id) ? 'active' : ''}`}
                      onClick={(e) => handleToggleFavorite(e, item)}
                      disabled={togglingFav === item.analysis_id}
                      title={favoriteIds.has(item.analysis_id) ? 'Favorilerden çıkar' : 'Favorilere ekle'}
                    >
                      <Star size={16} fill={item.analysis_id && favoriteIds.has(item.analysis_id) ? 'currentColor' : 'none'} />
                    </button>
                    <button
                      className="btn-icon btn-danger-icon"
                      onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                      title={t('history.delete')}
                    >
                      🗑
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Detail Panel */}
            <div className="history-detail">
              <AnimatePresence mode="wait">
              {selected?.result ? (
                <motion.div
                  key={selected.id}
                  className="detail-content"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="card result-score-card">
                    <ScoreCircle score={selected.result.final_score} size={120} label={selected.hasJobDesc ? t('results.final_score') : t('results.analysis_score')} />
                    <h3>{selected.hasJobDesc ? selected.result.interpretation : (
                      selected.result.final_score >= 75 ? t('results.excellent_quality') :
                      selected.result.final_score >= 50 ? t('results.good_quality') :
                      t('results.needs_improvement')
                    )}</h3>
                  </div>

                  <div className="card">
                    <h3>{t('results.breakdown_title')}</h3>
                    <ScoreBars items={[
                      { label: t('results.semantic'), value: selected.result.semantic_score },
                      { label: t('results.keyword'), value: selected.result.keyword_score },
                      { label: t('results.skill'), value: selected.result.skill_score },
                      { label: t('results.experience'), value: selected.result.experience_score },
                      { label: t('results.ats'), value: selected.result.ats_score },
                    ]} />
                  </div>

                  {selected.hasJobDesc && selected.result.missing_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.missing_skills')}</h3>
                      <SkillTags skills={selected.result.missing_skills} variant="missing" />
                    </div>
                  )}

                  {selected.result.recommendations?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.recommendations')}</h3>
                      <ul className="suggestion-list">
                        {selected.result.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    </div>
                  )}

                  {/* Share & Notes */}
                  <div className="history-detail-actions">
                    <button
                      className="btn-outline btn-sm"
                      onClick={() => handleShare(selected)}
                      title="Paylaşım linki oluştur"
                    >
                      <Share2 size={14} /> Paylaş
                    </button>
                    <button
                      className="btn-outline btn-sm"
                      onClick={() => handleDownloadReport(selected)}
                      disabled={reportLoading}
                      title="PDF rapor indir"
                    >
                      <Download size={14} /> {reportLoading ? '...' : 'PDF Rapor'}
                    </button>
                    {shareUrl && (
                      <div className="share-url-row">
                        <input type="text" value={shareUrl} readOnly className="share-url-input" />
                        <button
                          className="btn-icon"
                          onClick={() => { navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
                        >
                          {copied ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                    )}
                  </div>

                  {selected.analysis_id && (
                    <div className="card history-note-card">
                      <div className="history-note-header">
                        <StickyNote size={14} />
                        <span>Not</span>
                        {noteSaved && <span className="note-saved-badge">✓ Kaydedildi</span>}
                      </div>
                      <textarea
                        className="history-note-input"
                        rows={3}
                        placeholder="Bu analiz hakkında not ekleyin..."
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        maxLength={2000}
                      />
                      <button
                        className="btn-primary btn-sm"
                        onClick={handleSaveNote}
                        disabled={noteLoading}
                        style={{ alignSelf: 'flex-end', marginTop: 6 }}
                      >
                        {noteLoading ? '...' : 'Notu Kaydet'}
                      </button>
                    </div>
                  )}
                </motion.div>
              ) : (
                <motion.div
                  key="empty-detail"
                  className="empty-state"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="empty-icon">👈</div>
                  <h3>{t('history.details')}</h3>
                  <p className="text-muted">Select an analysis to view details</p>
                </motion.div>
              )}
              </AnimatePresence>
            </div>
          </div>
        ) : (
          <motion.div
            className="card empty-state"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <div className="empty-icon">📋</div>
            <h3>{t('history.no_history')}</h3>
            <p>{t('history.no_history_desc')}</p>
            <Link to="/analyze" className="btn-primary">{t('history.start_analyzing')}</Link>
          </motion.div>
        )}
      </main>
      <UpgradePrompt
        show={showUpgrade}
        onClose={() => setShowUpgrade(false)}
        feature={upgradeFeature}
        description="Pro plana yükselterek bu özelliğin kilidini açın."
      />
    </div>
  )
}
