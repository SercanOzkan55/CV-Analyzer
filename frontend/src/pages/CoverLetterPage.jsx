import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Briefcase, Sparkles, Copy, Check, Download,
  Upload, Clipboard, AlertCircle, Building2, Palette,
  GraduationCap, TrendingUp, Users, Code2, BookOpen, Zap,
} from 'lucide-react'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { generateCoverLetter, autoFixCv } from '../api'

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
}

const TONE_OPTIONS = [
  { value: 'professional', icon: Briefcase, color: '#a78bfa', labelKey: 'cl.tone_professional' },
  { value: 'enthusiastic', icon: Zap, color: '#fbbf24', labelKey: 'cl.tone_enthusiastic' },
  { value: 'confident', icon: TrendingUp, color: '#34d399', labelKey: 'cl.tone_confident' },
  { value: 'creative', icon: Palette, color: '#f472b6', labelKey: 'cl.tone_creative' },
  { value: 'formal', icon: Building2, color: '#60a5fa', labelKey: 'cl.tone_formal' },
]

const MODE_OPTIONS = [
  { value: 'junior', icon: GraduationCap, color: '#60a5fa' },
  { value: 'senior', icon: TrendingUp, color: '#a78bfa' },
  { value: 'manager', icon: Users, color: '#34d399' },
  { value: 'tech', icon: Code2, color: '#f97316' },
  { value: 'academic', icon: BookOpen, color: '#ec4899' },
]

export default function CoverLetterPage() {
  const { token } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()

  const [cvText, setCvText] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [tone, setTone] = useState('professional')
  const [mode, setMode] = useState('senior')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)
  const [inputTab, setInputTab] = useState('paste')
  const [pdfFile, setPdfFile] = useState(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [editedLetter, setEditedLetter] = useState('')
  const [wordCount, setWordCount] = useState(0)

  useEffect(() => {
    document.title = `${t('cl.title')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    const text = editedLetter || result?.cover_letter || result?.text || ''
    setWordCount(text.trim() ? text.trim().split(/\s+/).length : 0)
  }, [editedLetter, result])

  async function handlePdfUpload(file) {
    setPdfFile(file)
    if (!file) return
    try {
      setPdfLoading(true)
      setError(null)
      const res = await autoFixCv(token, file, '', { lang, useAi: false })
      const text = res?.optimized_cv_text || res?.original_cv_text || res?.optimized_text || res?.original_text || ''
      if (text) {
        setCvText(text)
        setInputTab('paste')
        addToast(t('cl.pdf_extracted'), 'success')
      } else {
        setError(t('cl.pdf_empty'))
      }
    } catch (err) {
      setError(err.message || 'PDF extraction failed')
    } finally {
      setPdfLoading(false)
    }
  }

  async function handleGenerate(e) {
    e.preventDefault()
    setError(null)

    const cv = String(cvText || '').trim()
    const jd = String(jobDescription || '').trim()

    if (!cv) {
      setError(t('cl.error_no_cv'))
      return
    }
    if (!jd) {
      setError(t('cl.error_no_jd'))
      return
    }

    try {
      setLoading(true)
      const data = await generateCoverLetter(token, {
        cv_text: cv,
        job_description: jd,
        company_name: companyName.trim(),
        lang,
        tone,
        mode,
        low_token: true,
      })

      const letterText = data?.result?.cover_letter || data?.result?.text || data?.result || ''
      setResult(typeof letterText === 'string' ? { text: letterText } : letterText)
      setEditedLetter(typeof letterText === 'string' ? letterText : letterText?.cover_letter || letterText?.text || '')
      addToast(t('cl.generated_success'), 'success')
    } catch (err) {
      setError(err.message || t('cl.error_generic'))
    } finally {
      setLoading(false)
    }
  }

  function handleCopy() {
    const text = editedLetter || result?.text || ''
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      addToast(t('cl.copied'), 'success')
      setTimeout(() => setCopied(false), 2500)
    })
  }

  function handleDownloadTxt() {
    const text = editedLetter || result?.text || ''
    if (!text) return
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cover_letter_${companyName?.replace(/\s+/g, '_') || 'document'}.txt`
    a.click()
    URL.revokeObjectURL(url)
    addToast(t('cl.downloaded'), 'success')
  }

  function handleReset() {
    setResult(null)
    setEditedLetter('')
    setError(null)
    setCopied(false)
  }

  const hasResult = !!result

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial="hidden" animate="show" variants={containerVariants}>

          {/* ── Hero Header ──────────────────── */}
          <motion.div className="cl-header" variants={itemVariants}>
            <div className="cl-header-icon">
              <FileText size={28} strokeWidth={1.6} />
              <div className="cl-header-icon-glow" />
            </div>
            <div>
              <h1 className="cl-title">{t('cl.title')}</h1>
              <p className="cl-subtitle">{t('cl.subtitle')}</p>
            </div>
          </motion.div>

          <AnimatePresence mode="wait">
          {!hasResult ? (
            <motion.form
              key="form"
              onSubmit={handleGenerate}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
            >
              <div className="cl-grid">
                {/* ── Left: CV Input ──────────────────── */}
                <motion.div className="cl-card" variants={itemVariants}>
                  <div className="cl-card-accent" />
                  <div className="cl-card-header">
                    <FileText size={18} className="cl-card-icon" />
                    <h2 className="cl-card-title">{t('cl.cv_input')}</h2>
                  </div>

                  {/* Tab switcher */}
                  <div className="cl-tab-bar">
                    <button
                      type="button"
                      className={`cl-tab ${inputTab === 'paste' ? 'cl-tab-active' : ''}`}
                      onClick={() => setInputTab('paste')}
                    >
                      <Clipboard size={14} />
                      {t('cl.tab_paste')}
                    </button>
                    <button
                      type="button"
                      className={`cl-tab ${inputTab === 'upload' ? 'cl-tab-active' : ''}`}
                      onClick={() => setInputTab('upload')}
                    >
                      <Upload size={14} />
                      {t('cl.tab_upload')}
                    </button>
                  </div>

                  <AnimatePresence mode="wait">
                    {inputTab === 'paste' ? (
                      <motion.div
                        key="paste"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 10 }}
                        transition={{ duration: 0.2 }}
                      >
                        <textarea
                          className="cl-textarea"
                          rows={14}
                          value={cvText}
                          onChange={(e) => setCvText(e.target.value)}
                          placeholder={t('cl.cv_placeholder')}
                        />
                      </motion.div>
                    ) : (
                      <motion.div
                        key="upload"
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        transition={{ duration: 0.2 }}
                      >
                        <DragDropUpload
                          onFileSelect={handlePdfUpload}
                          file={pdfFile}
                          onRemove={() => setPdfFile(null)}
                        />
                        {pdfLoading && (
                          <p className="cl-extracting">
                            <span className="cl-spinner" />
                            {t('cl.extracting')}
                          </p>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {cvText && (
                    <motion.div
                      className="cl-cv-status"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <Check size={14} />
                      {t('cl.cv_loaded')} — {cvText.length.toLocaleString()} {t('cl.chars')}
                    </motion.div>
                  )}
                </motion.div>

                {/* ── Right: Job Description & Settings ── */}
                <motion.div className="cl-card" variants={itemVariants}>
                  <div className="cl-card-accent" />
                  <div className="cl-card-header">
                    <Briefcase size={18} className="cl-card-icon" />
                    <h2 className="cl-card-title">{t('cl.job_settings')}</h2>
                  </div>

                  {/* Company Name */}
                  <div className="cl-field">
                    <label className="cl-label">{t('cl.company_name')}</label>
                    <div className="cl-input-wrap">
                      <Building2 size={16} className="cl-input-icon" />
                      <input
                        className="cl-input"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        placeholder={t('cl.company_placeholder')}
                      />
                    </div>
                  </div>

                  {/* Job Description */}
                  <div className="cl-field">
                    <label className="cl-label">{t('cl.job_description')}</label>
                    <textarea
                      className="cl-textarea cl-textarea-sm"
                      rows={6}
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      placeholder={t('cl.jd_placeholder')}
                    />
                  </div>

                  {/* Tone Selector */}
                  <div className="cl-field">
                    <label className="cl-label">{t('cl.tone_label')}</label>
                    <div className="cl-tone-grid">
                      {TONE_OPTIONS.map(opt => {
                        const Icon = opt.icon
                        const active = tone === opt.value
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            className={`cl-tone-btn ${active ? 'cl-tone-active' : ''}`}
                            style={active ? { '--tone-color': opt.color } : {}}
                            onClick={() => setTone(opt.value)}
                          >
                            <Icon size={16} />
                            <span>{t(opt.labelKey)}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Mode Selector */}
                  <div className="cl-field">
                    <label className="cl-label">{t('cl.mode_label')}</label>
                    <div className="cl-mode-grid">
                      {MODE_OPTIONS.map(opt => {
                        const Icon = opt.icon
                        const active = mode === opt.value
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            className={`cl-mode-btn ${active ? 'cl-mode-active' : ''}`}
                            style={active ? { '--mode-color': opt.color } : {}}
                            onClick={() => setMode(opt.value)}
                          >
                            <Icon size={14} />
                            <span>{t(`cl.mode_${opt.value}`)}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </motion.div>
              </div>

              {/* ── Error ──────────────────── */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    className="cl-error"
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                  >
                    <AlertCircle size={16} />
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* ── Submit ─────────────────── */}
              <motion.div className="cl-submit-wrap" variants={itemVariants}>
                <button
                  type="submit"
                  className="cl-submit-btn"
                  disabled={loading || !cvText.trim() || !jobDescription.trim()}
                >
                  {loading ? (
                    <>
                      <span className="cl-spinner" />
                      {t('cl.generating')}
                    </>
                  ) : (
                    <>
                      <Sparkles size={18} />
                      {t('cl.generate_btn')}
                    </>
                  )}
                </button>
              </motion.div>
            </motion.form>
          ) : (
            /* ── Results ────────────────────── */
            <motion.div
              key="results"
              className="cl-results"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -24 }}
              transition={{ duration: 0.5 }}
            >
              {/* Result Header */}
              <div className="cl-result-header">
                <div className="cl-result-header-left">
                  <h2>{t('cl.result_title')}</h2>
                  <div className="cl-result-meta">
                    {companyName && (
                      <span className="cl-result-badge cl-badge-company">
                        <Building2 size={12} />
                        {companyName}
                      </span>
                    )}
                    <span className="cl-result-badge cl-badge-tone">
                      {t(`cl.tone_${tone}`)}
                    </span>
                    <span className="cl-result-badge cl-badge-mode">
                      {t(`cl.mode_${mode}`)}
                    </span>
                    <span className="cl-result-badge cl-badge-words">
                      {wordCount} {t('cl.words')}
                    </span>
                  </div>
                </div>
                <div className="cl-result-actions">
                  <motion.button
                    type="button"
                    className="cl-action-btn"
                    onClick={handleCopy}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                    {copied ? t('cl.copied') : t('cl.copy_btn')}
                  </motion.button>
                  <motion.button
                    type="button"
                    className="cl-action-btn cl-action-secondary"
                    onClick={handleDownloadTxt}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Download size={16} />
                    {t('cl.download_btn')}
                  </motion.button>
                  <motion.button
                    type="button"
                    className="cl-action-btn cl-action-ghost"
                    onClick={handleReset}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {t('cl.new_letter')}
                  </motion.button>
                </div>
              </div>

              {/* Editable Cover Letter */}
              <motion.div
                className="cl-letter-card"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
              >
                <div className="cl-letter-toolbar">
                  <span className="cl-letter-toolbar-label">
                    <FileText size={14} />
                    {t('cl.editable_hint')}
                  </span>
                </div>
                <textarea
                  className="cl-letter-textarea"
                  value={editedLetter}
                  onChange={(e) => setEditedLetter(e.target.value)}
                  rows={20}
                />
              </motion.div>
            </motion.div>
          )}
          </AnimatePresence>

          {/* ── Empty State ───────────────── */}
          {!hasResult && !loading && !cvText && (
            <motion.div className="cl-empty" variants={itemVariants}>
              <Sparkles size={40} strokeWidth={1.2} />
              <h3>{t('cl.empty_title')}</h3>
              <p>{t('cl.empty_desc')}</p>
            </motion.div>
          )}

        </motion.div>
      </main>
    </div>
  )
}
