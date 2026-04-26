import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, Upload, FileText, Briefcase, Target, Zap,
  Copy, Check, AlertCircle, Linkedin, Award, TrendingUp,
  BookOpen, ChevronRight, Clipboard, GraduationCap, Code2, Users,
} from 'lucide-react'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import ScoreCircle from '../components/ScoreCircle'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { optimizeLinkedIn, fetchJobMatchScore, autoFixCv } from '../api'

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
}

const MODE_OPTIONS = [
  { value: 'junior', icon: GraduationCap, color: '#60a5fa' },
  { value: 'senior', icon: TrendingUp, color: '#a78bfa' },
  { value: 'manager', icon: Users, color: '#34d399' },
  { value: 'tech', icon: Code2, color: '#f97316' },
  { value: 'academic', icon: BookOpen, color: '#ec4899' },
]

export default function CareerStudioPage() {
  const { token } = useAuth()
  const { t, lang } = useLanguage()

  const [cvText, setCvText] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [targetRole, setTargetRole] = useState('Software Engineer')
  const [mode, setMode] = useState('senior')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [linkedInResult, setLinkedInResult] = useState(null)
  const [matchScoreResult, setMatchScoreResult] = useState(null)
  const [pdfFile, setPdfFile] = useState(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [inputTab, setInputTab] = useState('paste') // 'paste' | 'upload'
  const [copied, setCopied] = useState(null) // 'headline' | 'about' | null

  useEffect(() => {
    document.title = `${t('career.title')} — CV Analyzer`
  }, [t])

  async function handlePdfUpload(file) {
    setPdfFile(file)
    if (!file) return
    try {
      setPdfLoading(true)
      setError(null)
      const result = await autoFixCv(token, file, '', { lang, useAi: false })
      const text = result?.optimized_cv_text || result?.original_cv_text || result?.optimized_text || result?.original_text || ''
      if (text) {
        setCvText(text)
        setInputTab('paste')
      } else {
        setError(t('career.pdf_empty') || 'PDF could not be read. Please paste your CV text instead.')
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
      setError(t('career.cv_text') + ' is required')
      return
    }

    try {
      setLoading(true)
      const [linkedinData, matchData] = await Promise.all([
        optimizeLinkedIn(token, {
          cv_text: cv,
          target_role: targetRole,
          lang,
          mode,
          headline: '',
        }),
        fetchJobMatchScore(token, {
          cv_text: cv,
          job_description: jd || targetRole,
          lang,
          mode,
        }),
      ])

      setLinkedInResult(linkedinData?.result || null)
      setMatchScoreResult(matchData || null)
    } catch (err) {
      setError(err.message || 'Failed to generate career tools')
    } finally {
      setLoading(false)
    }
  }

  function handleCopy(field) {
    const text = field === 'headline' ? linkedInResult?.headline : linkedInResult?.about
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(field)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  const score = Math.round(matchScoreResult?.score || 0)
  const hasResults = linkedInResult || matchScoreResult

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial="hidden" animate="show" variants={containerVariants}>
          {/* ── Header ─────────────────────────────────────── */}
          <motion.div className="cs-header" variants={itemVariants}>
            <div className="cs-header-icon">
              <Sparkles size={28} strokeWidth={1.6} />
            </div>
            <div>
              <h1 className="cs-title">{t('career.title')}</h1>
              <p className="cs-subtitle">{t('career.subtitle')}</p>
            </div>
          </motion.div>

          <form onSubmit={handleGenerate}>
            <div className="cs-grid">
              {/* ── Left: CV Input ─────────────────────────── */}
              <motion.div className="cs-card" variants={itemVariants}>
                <div className="cs-card-top-bar" />
                <div className="cs-card-header">
                  <FileText size={18} className="cs-card-icon" />
                  <h2 className="cs-card-title">{t('career.cv_text')}</h2>
                </div>

                {/* Tab switcher */}
                <div className="cs-tab-bar">
                  <button
                    type="button"
                    className={`cs-tab ${inputTab === 'paste' ? 'cs-tab-active' : ''}`}
                    onClick={() => setInputTab('paste')}
                  >
                    <Clipboard size={14} />
                    {t('career.paste_text')}
                  </button>
                  <button
                    type="button"
                    className={`cs-tab ${inputTab === 'upload' ? 'cs-tab-active' : ''}`}
                    onClick={() => setInputTab('upload')}
                  >
                    <Upload size={14} />
                    {t('career.upload_pdf')}
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
                        className="cs-textarea"
                        rows={14}
                        value={cvText}
                        onChange={(e) => setCvText(e.target.value)}
                        placeholder={t('career.paste_cv')}
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
                        <p className="cs-extracting">
                          <span className="cs-spinner" />
                          {t('career.extracting')}
                        </p>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {cvText && (
                  <motion.div
                    className="cs-cv-status"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                  >
                    <Check size={14} />
                    {t('career.cv_loaded')} — {cvText.length.toLocaleString()} {t('career.cv_chars')}
                  </motion.div>
                )}
              </motion.div>

              {/* ── Right: Role & Settings ─────────────────── */}
              <motion.div className="cs-card" variants={itemVariants}>
                <div className="cs-card-top-bar" />
                <div className="cs-card-header">
                  <Target size={18} className="cs-card-icon" />
                  <h2 className="cs-card-title">{t('career.role_jd')}</h2>
                </div>

                <div className="cs-field">
                  <label className="cs-label">{t('career.target_role')}</label>
                  <div className="cs-input-wrap">
                    <Briefcase size={16} className="cs-input-icon" />
                    <input
                      className="cs-input"
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                      placeholder={t('career.target_role_placeholder')}
                    />
                  </div>
                </div>

                <div className="cs-field">
                  <label className="cs-label">{t('career.mode')}</label>
                  <div className="cs-mode-grid">
                    {MODE_OPTIONS.map(opt => {
                      const Icon = opt.icon
                      const active = mode === opt.value
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          className={`cs-mode-btn ${active ? 'cs-mode-active' : ''}`}
                          style={active ? { '--mode-color': opt.color } : {}}
                          onClick={() => setMode(opt.value)}
                        >
                          <Icon size={16} />
                          <span>{t(`career.mode_${opt.value}`)}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="cs-field">
                  <label className="cs-label">{t('career.paste_jd')}</label>
                  <textarea
                    className="cs-textarea cs-textarea-sm"
                    rows={6}
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    placeholder={t('career.paste_jd')}
                  />
                </div>
              </motion.div>
            </div>

            {/* ── Error ─────────────────────────────────────── */}
            <AnimatePresence>
              {error && (
                <motion.div
                  className="cs-error"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <AlertCircle size={16} />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Submit ────────────────────────────────────── */}
            <motion.div className="cs-submit-wrap" variants={itemVariants}>
              <button type="submit" className="cs-submit-btn" disabled={loading || !cvText.trim()}>
                {loading ? (
                  <>
                    <span className="cs-spinner" />
                    {t('common.loading')}
                  </>
                ) : (
                  <>
                    <Zap size={18} />
                    {t('career.generate_btn')}
                  </>
                )}
              </button>
            </motion.div>
          </form>

          {/* ── Results ──────────────────────────────────────── */}
          <AnimatePresence>
            {hasResults && (
              <motion.div
                className="cs-results"
                initial="hidden"
                animate="show"
                variants={containerVariants}
              >
                {/* Score Card */}
                {matchScoreResult && (
                  <motion.div className="cs-score-card" variants={itemVariants}>
                    <div className="cs-card-top-bar" />
                    <div className="cs-card-header">
                      <Award size={18} className="cs-card-icon" />
                      <h2 className="cs-card-title">{t('career.job_match')}</h2>
                      {matchScoreResult.mode && (
                        <span className="cs-mode-badge">{matchScoreResult.mode}</span>
                      )}
                    </div>
                    <div className="cs-score-body">
                      <ScoreCircle score={score} size={130} label="Match" />
                      <div className="cs-score-details">
                        {matchScoreResult.interpretation && (
                          <p className="cs-interpretation">{matchScoreResult.interpretation}</p>
                        )}
                        {matchScoreResult.keyword_coverage_pct !== undefined && (
                          <div className="cs-bar-row">
                            <span className="cs-bar-label">{t('career.keyword_coverage')}</span>
                            <div className="cs-bar-track">
                              <motion.div
                                className="cs-bar-fill"
                                style={{ background: '#a78bfa' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(matchScoreResult.keyword_coverage_pct, 100)}%` }}
                                transition={{ duration: 1, delay: 0.3 }}
                              />
                            </div>
                            <span className="cs-bar-value">{Math.round(matchScoreResult.keyword_coverage_pct)}%</span>
                          </div>
                        )}
                        {matchScoreResult.experience_match !== undefined && (
                          <div className="cs-bar-row">
                            <span className="cs-bar-label">{t('career.experience_match')}</span>
                            <div className="cs-bar-track">
                              <motion.div
                                className="cs-bar-fill"
                                style={{ background: '#34d399' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(matchScoreResult.experience_match, 100)}%` }}
                                transition={{ duration: 1, delay: 0.4 }}
                              />
                            </div>
                            <span className="cs-bar-value">{Math.round(matchScoreResult.experience_match)}%</span>
                          </div>
                        )}
                        {matchScoreResult.title_match !== undefined && matchScoreResult.title_match > 0 && (
                          <div className="cs-bar-row">
                            <span className="cs-bar-label">{t('career.title_match')}</span>
                            <div className="cs-bar-track">
                              <motion.div
                                className="cs-bar-fill"
                                style={{ background: '#60a5fa' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(matchScoreResult.title_match, 100)}%` }}
                                transition={{ duration: 1, delay: 0.5 }}
                              />
                            </div>
                            <span className="cs-bar-value">{Math.round(matchScoreResult.title_match)}%</span>
                          </div>
                        )}
                        {matchScoreResult.seniority_match !== undefined && matchScoreResult.seniority_match > 0 && (
                          <div className="cs-bar-row">
                            <span className="cs-bar-label">{t('career.seniority_match')}</span>
                            <div className="cs-bar-track">
                              <motion.div
                                className="cs-bar-fill"
                                style={{ background: '#fbbf24' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(matchScoreResult.seniority_match, 100)}%` }}
                                transition={{ duration: 1, delay: 0.6 }}
                              />
                            </div>
                            <span className="cs-bar-value">{Math.round(matchScoreResult.seniority_match)}%</span>
                          </div>
                        )}
                        {matchScoreResult.skill_match !== undefined && matchScoreResult.skill_match > 0 && (
                          <div className="cs-bar-row">
                            <span className="cs-bar-label">{t('career.skill_match')}</span>
                            <div className="cs-bar-track">
                              <motion.div
                                className="cs-bar-fill"
                                style={{ background: '#f472b6' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(matchScoreResult.skill_match, 100)}%` }}
                                transition={{ duration: 1, delay: 0.7 }}
                              />
                            </div>
                            <span className="cs-bar-value">{Math.round(matchScoreResult.skill_match)}%</span>
                          </div>
                        )}

                        {/* Strong Keywords */}
                        {matchScoreResult.strong_keywords?.length > 0 && (
                          <div className="cs-tag-section">
                            <span className="cs-tag-label">{t('career.strong_keywords')}</span>
                            <div className="cs-tags">
                              {matchScoreResult.strong_keywords.map((kw, i) => (
                                <span key={i} className="cs-tag cs-tag-green">{kw}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Missing Keywords */}
                        {matchScoreResult.missing_keywords?.length > 0 && (
                          <div className="cs-tag-section">
                            <span className="cs-tag-label">{t('career.missing_keywords')}</span>
                            <div className="cs-tags">
                              {matchScoreResult.missing_keywords.map((kw, i) => (
                                <span key={i} className="cs-tag cs-tag-red">{kw}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Recommendations */}
                        {matchScoreResult.recommendations?.length > 0 && (
                          <div className="cs-tag-section">
                            <span className="cs-tag-label">{t('career.recommendations')}</span>
                            <ul className="cs-rec-list">
                              {matchScoreResult.recommendations.map((rec, i) => (
                                <li key={i}>
                                  <ChevronRight size={12} />
                                  {rec}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* LinkedIn Card */}
                {linkedInResult && (
                  <motion.div className="cs-linkedin-card" variants={itemVariants}>
                    <div className="cs-card-top-bar" />
                    <div className="cs-card-header">
                      <Linkedin size={18} className="cs-card-icon" />
                      <h2 className="cs-card-title">{t('career.linkedin_opt')}</h2>
                      <span className="cs-mode-badge">{mode}</span>
                    </div>

                    {/* Headline */}
                    <div className="cs-li-section">
                      <div className="cs-li-section-head">
                        <span className="cs-li-label">{t('career.linkedin_headline')}</span>
                        <button
                          type="button"
                          className="cs-copy-btn"
                          onClick={() => handleCopy('headline')}
                        >
                          {copied === 'headline' ? <Check size={13} /> : <Copy size={13} />}
                          {copied === 'headline' ? t('career.copied') : t('career.copy_headline')}
                        </button>
                      </div>
                      <div className="cs-li-headline">{linkedInResult.headline}</div>
                    </div>

                    {/* About */}
                    <div className="cs-li-section">
                      <div className="cs-li-section-head">
                        <span className="cs-li-label">{t('career.linkedin_about')}</span>
                        <button
                          type="button"
                          className="cs-copy-btn"
                          onClick={() => handleCopy('about')}
                        >
                          {copied === 'about' ? <Check size={13} /> : <Copy size={13} />}
                          {copied === 'about' ? t('career.copied') : t('career.copy_about')}
                        </button>
                      </div>
                      <div className="cs-li-about">{linkedInResult.about}</div>
                    </div>

                    {/* Experience Highlights */}
                    {linkedInResult.experience_rewrite?.length > 0 && (
                      <div className="cs-li-section">
                        <span className="cs-li-label">{t('career.linkedin_experience')}</span>
                        <ul className="cs-exp-list">
                          {linkedInResult.experience_rewrite.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Top Skills */}
                    {linkedInResult.top_skills?.length > 0 && (
                      <div className="cs-li-section">
                        <span className="cs-li-label">{t('career.top_skills')}</span>
                        <div className="cs-tags">
                          {linkedInResult.top_skills.map((skill, i) => (
                            <span key={i} className="cs-tag cs-tag-accent">{skill}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Empty state ──────────────────────────────────── */}
          {!hasResults && !loading && (
            <motion.div className="cs-empty" variants={itemVariants}>
              <Sparkles size={40} strokeWidth={1.2} />
              <h3>{t('career.no_results_yet')}</h3>
              <p>{t('career.no_results_desc')}</p>
            </motion.div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
