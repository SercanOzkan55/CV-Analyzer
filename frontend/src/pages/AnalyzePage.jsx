import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { analyzePdf, autoFixCv, exportAutoFixedCV, fetchScoreBreakdown } from '../api'
import { addHistoryItem } from '../utils/historyStorage'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import ScoreBreakdown from '../components/ScoreBreakdown'
import SkillTags from '../components/SkillTags'
import GlobalBenchmark from '../components/GlobalBenchmark'
import QuotaWarningBanner from '../components/QuotaWarningBanner'
import JDTemplateSelector from '../components/JDTemplateSelector'

function saveToHistory(result, fileName, jobDesc, user) {
  try {
    addHistoryItem(user, {
      id: Date.now(),
      analysis_id: result.analysis_id || null,
      date: new Date().toISOString(),
      fileName,
      jobTitle: jobDesc.slice(0, 60),
      score: result.final_score,
      interpretation: result.interpretation,
      hasJobDesc: !!(jobDesc && jobDesc.trim()),
      result,
    })
  } catch { /* ignore storage errors */ }
}

export default function AnalyzePage() {
  const { user, token, canAnalyze, recordAnalysis, refreshUsage, signOut } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [file, setFile] = useState(null)
  const [jobDesc, setJobDesc] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [autoFixResult, setAutoFixResult] = useState(null)
  const [autoFixLoading, setAutoFixLoading] = useState(false)
  const [autoFixError, setAutoFixError] = useState(null)
  const [exportLoading, setExportLoading] = useState(null)
  const [editedText, setEditedText] = useState('')
  const [scoreBreakdown, setScoreBreakdown] = useState(null)
  const [breakdownLoading, setBreakdownLoading] = useState(false)

  // Helper: pick current language from bilingual {en, tr} objects
  const L = (val) => {
    if (!val) return val
    if (typeof val === 'string') return val
    return val[lang] || val.en || val.tr || ''
  }

  async function handleAnalyze(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setSaved(false)

    if (!file) return setError(t('analyze.no_file'))
    if (file.type !== 'application/pdf') return setError(t('analyze.invalid_file'))
    if (file.size > 10 * 1024 * 1024) return setError(t('analyze.file_too_large'))
    // Job description is optional for ATS-focused checks

    if (!canAnalyze()) {
      addToast(t('toast.limit_reached'), 'warning')
      return
    }

    try {
      setLoading(true)
      // Simulate progress
      setProgress(10)
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 15, 85))
      }, 500)

      const data = await analyzePdf(token, file, jobDesc, { lang })

      clearInterval(progressInterval)
      setProgress(100)
      setResult(data)
      setActiveTab('overview')
      setAutoFixResult(null)
      setAutoFixError(null)
      setEditedText('')
      recordAnalysis()
      saveToHistory(data, file.name, jobDesc, user)
      addToast(t('toast.analysis_complete'), 'success')
    } catch (err) {
      if (err.message.includes('403')) {
        addToast(t('toast.limit_reached'), 'warning')
        refreshUsage(token, { background: true })
      } else if (err.message.includes('401')) {
        addToast(t('toast.session_expired'), 'error')
        await signOut()
        navigate('/login')
        return
      } else {
        setError(err.message || t('toast.error_generic'))
      }
    } finally {
      setLoading(false)
      setTimeout(() => setProgress(0), 500)
    }
  }

  async function handleAutoFix(useAi = true) {
    if (!file) {
      setAutoFixError(t('analyze.no_file'))
      return
    }

    try {
      setAutoFixLoading(true)
      setAutoFixError(null)

      const data = await autoFixCv(token, file, jobDesc, { lang, useAi })

      setAutoFixResult(data)
      setEditedText(data.optimized_cv_text || '')
      addToast(t('toast.analysis_complete'), 'success')
    } catch (err) {
      console.error('Auto-fix error:', err)
      const msg = err.message || t('toast.error_generic')
      setAutoFixError(msg)
    } finally {
      setAutoFixLoading(false)
    }
  }

  async function handleExportAutoFix(format) {
    if (!autoFixResult || !editedText.trim()) {
      setAutoFixError(t('analyze.no_file'))
      return
    }

    try {
      setExportLoading(format)
      setAutoFixError(null)

      const response = await exportAutoFixedCV(token, {
        optimized_cv_text: editedText,
        output_format: format,
      })

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const baseName = (file?.name || 'optimized_cv').replace(/\.pdf$/i, '')
      a.href = url
      a.download = `${baseName}_optimized.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setAutoFixError(err.message || t('toast.error_generic'))
    } finally {
      setExportLoading(null)
    }
  }

  function handleReset() {
    setFile(null)
    setJobDesc('')
    setResult(null)
    setError(null)
    setSaved(false)
    setActiveTab('overview')
    setAutoFixResult(null)
    setAutoFixError(null)
    setExportLoading(null)
    setEditedText('')
  }

  function getInterpretation(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('strong') || lower.includes('güçlü') || lower.includes('forte') || lower.includes('stark') || lower.includes('fuerte') || lower.includes('قوي')) return t('results.strong_match')
    if (lower.includes('moderate') || lower.includes('orta') || lower.includes('modér') || lower.includes('moderat') || lower.includes('moderada') || lower.includes('متوسط')) return t('results.moderate_match')
    return t('results.weak_match')
  }

  function getRiskLabel(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('low') || lower.includes('düşük') || lower.includes('faible') || lower.includes('niedrig') || lower.includes('bajo') || lower.includes('منخفض')) return t('results.low_risk')
    if (lower.includes('medium') || lower.includes('orta') || lower.includes('moyen') || lower.includes('mittel') || lower.includes('medio') || lower.includes('متوسط')) return t('results.medium_risk')
    return t('results.high_risk')
  }

  function getRiskColor(level) {
    const lower = (level || '').toLowerCase()
    // Support multiple languages: "low risk", "düşük risk", "risque faible", etc.
    if (lower.includes('low') || lower.includes('düşük') || lower.includes('faible') || lower.includes('bajo') || lower.includes('منخفضة') || lower.includes('baixo') || lower.includes('basso') || lower.includes('laag') || lower.includes('низкий') || lower.includes('低')) return '#22c55e'
    if (lower.includes('medium') || lower.includes('orta') || lower.includes('moyen') || lower.includes('medio') || lower.includes('متوسطة') || lower.includes('médio') || lower.includes('gemiddeld') || lower.includes('средний') || lower.includes('中')) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content">
        <QuotaWarningBanner />
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1>{t('analyze.title')}</h1>
          {result && (
            <motion.button
              className="btn-outline"
              onClick={handleReset}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              {t('analyze.new_analysis')}
            </motion.button>
          )}
        </motion.div>

        <AnimatePresence mode="wait">
        {!result ? (
          <motion.form
            key="form"
            onSubmit={handleAnalyze}
            className="analyze-form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4 }}
          >
            <div className="analyze-grid">
              {/* Upload Section */}
              <motion.div
                className="card"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
              >
                <h2>{t('analyze.upload_title')}</h2>
                <DragDropUpload
                  file={file}
                  onFileSelect={setFile}
                  onRemove={() => setFile(null)}
                />
              </motion.div>

              {/* Job Description */}
              <motion.div
                className="card"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 }}
              >
                <h2>{t('analyze.job_desc_title')}</h2>
                <JDTemplateSelector
                  onSelect={(desc) => setJobDesc(desc)}
                  currentText={jobDesc}
                />
                <textarea
                  className="job-desc-input"
                  rows={12}
                  placeholder={t('analyze.job_desc_placeholder')}
                  value={jobDesc}
                  onChange={(e) => setJobDesc(e.target.value)}
                />
              </motion.div>
            </div>

            {/* Progress */}
            <AnimatePresence>
            {loading && (
              <motion.div
                className="progress-wrapper"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="progress-track">
                  <motion.div
                    className="progress-fill"
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                  />
                </div>
                <span className="progress-text">{t('analyze.upload_progress')}</span>
              </motion.div>
            )}
            </AnimatePresence>

            {error && <p className="error">{error}</p>}

            <motion.button
              type="submit"
              className="btn-primary btn-lg btn-full"
              disabled={loading}
              whileHover={!loading ? { scale: 1.01 } : undefined}
              whileTap={!loading ? { scale: 0.99 } : undefined}
            >
              {loading ? t('analyze.analyzing') : t('analyze.analyze_btn')}
            </motion.button>
          </motion.form>
        ) : (
          <motion.div
            key="results"
            className="results-layout"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* File info header */}
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>{file?.name || 'CV'}</span>
                {jobDesc?.trim() ? (
                  /* JD provided → show match level */
                  result.final_score >= 75 ? (
                    <span style={{ background: '#166534', color: '#4ade80', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.strong_match')}
                    </span>
                  ) : result.final_score >= 50 ? (
                    <span style={{ background: '#854d0e', color: '#facc15', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.moderate_match')}
                    </span>
                  ) : (
                    <span style={{ background: '#991b1b', color: '#f87171', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.weak_match')}
                    </span>
                  )
                ) : (
                  /* No JD → show CV quality level */
                  result.final_score >= 75 ? (
                    <span style={{ background: '#166534', color: '#4ade80', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.excellent_quality')}
                    </span>
                  ) : result.final_score >= 50 ? (
                    <span style={{ background: '#854d0e', color: '#facc15', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.good_quality')}
                    </span>
                  ) : (
                    <span style={{ background: '#991b1b', color: '#f87171', padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {t('results.needs_improvement')}
                    </span>
                  )
                )}
              </div>
              <p className="text-muted text-xs">{new Date().toLocaleDateString(lang, { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
            </div>

            {/* Resume Analysis Results header card */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h2 style={{ margin: '0 0 0.5rem 0' }}>{t('results.title')}</h2>
                  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                    <span style={{ color: '#4ade80' }}>✓ {result.ats?.passed_checks ?? 0} {t('results.passed_checks')}</span>
                    <span style={{ color: '#facc15' }}>⚠ {result.ats?.warning_checks ?? 0} {t('results.warnings')}</span>
                    <span style={{ color: '#f87171' }}>✕ {result.ats?.failed_checks ?? 0} {t('results.issues')}</span>
                  </div>
                </div>
                <ScoreCircle score={result.final_score} size={100} label={jobDesc?.trim() ? t('results.final_score') : t('results.analysis_score')} />
              </div>

              {/* Score Decomposition: ATS Quality vs Job Match */}
              {jobDesc?.trim() && result.score_decomposition && (
                <div style={{
                  marginTop: '1.25rem',
                  paddingTop: '1.25rem',
                  borderTop: '1px solid rgba(148,163,184,0.15)',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                    {/* CV Quality */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>
                          📄 {t('results.cv_quality') || 'CV Quality'}
                        </span>
                        <span style={{
                          fontSize: '1rem', fontWeight: 700,
                          color: (result.score_decomposition.ats_quality || 0) >= 70 ? '#4ade80'
                               : (result.score_decomposition.ats_quality || 0) >= 50 ? '#facc15' : '#f87171',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {Math.round(result.score_decomposition.ats_quality || 0)}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(100, result.score_decomposition.ats_quality || 0)}%`,
                          height: '100%', borderRadius: '3px',
                          background: 'linear-gradient(90deg, #3b82f6, #60a5fa)',
                          transition: 'width 0.8s ease',
                        }} />
                      </div>
                    </div>
                    {/* Job Match */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>
                          🎯 {t('results.job_match') || 'Job Match'}
                        </span>
                        <span style={{
                          fontSize: '1rem', fontWeight: 700,
                          color: (result.score_decomposition.job_match || 0) >= 70 ? '#4ade80'
                               : (result.score_decomposition.job_match || 0) >= 40 ? '#facc15' : '#f87171',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {Math.round(result.score_decomposition.job_match || 0)}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(100, result.score_decomposition.job_match || 0)}%`,
                          height: '100%', borderRadius: '3px',
                          background: (result.score_decomposition.job_match || 0) >= 70
                            ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                            : (result.score_decomposition.job_match || 0) >= 40
                              ? 'linear-gradient(90deg, #eab308, #facc15)'
                              : 'linear-gradient(90deg, #ef4444, #f87171)',
                          transition: 'width 0.8s ease',
                        }} />
                      </div>
                    </div>
                  </div>
                  {/* Interpretation message */}
                  <div style={{
                    background: (result.score_decomposition.job_match || 0) >= 70
                      ? 'rgba(34,197,94,0.08)' : (result.score_decomposition.job_match || 0) >= 40
                        ? 'rgba(234,179,8,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${(result.score_decomposition.job_match || 0) >= 70
                      ? 'rgba(34,197,94,0.2)' : (result.score_decomposition.job_match || 0) >= 40
                        ? 'rgba(234,179,8,0.2)' : 'rgba(239,68,68,0.2)'}`,
                    borderRadius: '0.5rem',
                    padding: '0.5rem 0.75rem',
                    fontSize: '0.82rem',
                    color: '#cbd5e1',
                  }}>
                    {result.score_decomposition.interpretation}
                  </div>
                </div>
              )}
            </div>

            {/* Info banner when no job description */}
            {!jobDesc?.trim() && (
              <div style={{
                background: 'rgba(56,189,248,0.08)',
                border: '1px solid rgba(56,189,248,0.25)',
                borderRadius: '0.75rem',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.85rem',
                color: '#7dd3fc',
              }}>
                <span style={{ fontSize: '1.1rem' }}>ℹ️</span>
                {t('results.no_jd_info')}
              </div>
            )}

            {/* Analysis warnings */}
            {result.warnings?.length > 0 && (
              <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
                <strong>⚠ {t('results.warnings')}</strong>
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
                  {result.warnings.map((w, i) => <li key={i} style={{ marginBottom: '0.25rem' }}>{w}</li>)}
                </ul>
              </div>
            )}

            {/* Tabs */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem', flexWrap: 'wrap' }}>
              {[
                { id: 'overview', icon: '📊', label: t('analyze.tab_overview') },
                { id: 'detailed', icon: '📋', label: t('analyze.tab_detailed') },
                { id: 'recommendations', icon: '💡', label: t('analyze.tab_recommendations') },
                { id: 'nextsteps', icon: '◎', label: t('analyze.tab_next_steps') },
                { id: 'scorebreakdown', icon: '🎯', label: t('analyze.tab_score_breakdown') },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    background: activeTab === tab.id ? 'rgba(192,132,252,0.1)' : 'transparent',
                    color: activeTab === tab.id ? '#c084fc' : '#94a3b8',
                    border: 'none',
                    borderBottom: activeTab === tab.id ? '2px solid #c084fc' : '2px solid transparent',
                    padding: '0.5rem 1rem',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                    fontWeight: activeTab === tab.id ? 600 : 400,
                    transition: 'all 0.2s',
                  }}
                  type="button"
                >
                  {tab.icon} {tab.label}
                </button>
              ))}
            </div>

            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                  {(result.ats?.section_scores || []).map((section, idx) => (
                    <div key={idx} className="card" style={{ margin: 0, padding: '1rem 1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span>{section.icon}</span>
                          <strong>{section.label?.[lang] || section.label?.en || section.name}</strong>
                        </div>
                        <span style={{ fontSize: '1.25rem', fontWeight: 700, color: section.score >= 70 ? '#4ade80' : section.score >= 50 ? '#facc15' : '#f87171' }}>
                          {Math.round(section.score)}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                        {section.status === 'pass' && <span style={{ color: '#4ade80', fontSize: '0.8rem' }}>✓ {t('results.status_pass')}</span>}
                        {section.status === 'warning' && <span style={{ color: '#facc15', fontSize: '0.8rem' }}>⚠ {t('results.status_warning')}</span>}
                        {section.status === 'fail' && <span style={{ color: '#f87171', fontSize: '0.8rem' }}>✕ {t('results.status_fail')}</span>}
                      </div>
                      {/* Score bar */}
                      <div style={{ width: '100%', height: '4px', background: '#1e293b', borderRadius: '2px', marginBottom: '0.5rem' }}>
                        <div style={{
                          width: `${Math.min(100, section.score)}%`,
                          height: '100%',
                          borderRadius: '2px',
                          background: section.score >= 70 ? '#22c55e' : section.score >= 50 ? '#eab308' : '#ef4444',
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                      <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>{L(section.message) || (section.score >= 70 ? t('results.looking_good') : t('results.improvements_recommended'))}</p>
                    </div>
                  ))}
                </div>

                {/* Skills & Keyword overview */}
                <div className="results-details">
                  {result.detected_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.detected_skills')}</h3>
                      <SkillTags skills={result.detected_skills} variant="detected" />
                    </div>
                  )}

                  {jobDesc?.trim() && result.missing_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.missing_skills')}</h3>
                      <SkillTags skills={result.missing_skills} variant="missing" />
                    </div>
                  )}

                  {/* Score Suggestions — actionable improvement tips */}
                  {jobDesc?.trim() && result.score_suggestions?.length > 0 && (
                    <div className="card" style={{ borderLeft: '3px solid #a855f7' }}>
                      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, color: '#c084fc' }}>
                        💡 {t('results.suggestions_title') || 'How to Improve Your Score'}
                      </h3>
                      <p style={{ fontSize: '0.82rem', color: '#94a3b8', margin: '0 0 0.75rem 0' }}>
                        {t('results.suggestions_desc') || 'Add these to your CV for the highest impact:'}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {result.score_suggestions.map((s, i) => (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'center', gap: '0.75rem',
                            background: 'rgba(168,85,247,0.06)',
                            borderRadius: '0.5rem',
                            padding: '0.6rem 0.75rem',
                          }}>
                            <span style={{
                              fontSize: '1rem',
                              minWidth: '24px', textAlign: 'center',
                            }}>
                              {s.category === 'skill' ? '🎯' : s.category === 'keyword' ? '🔑' : '📄'}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <span style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>{s.action}</span>
                            </div>
                            <span style={{
                              background: 'linear-gradient(135deg, #a855f7, #6366f1)',
                              color: '#fff',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              fontFamily: "'JetBrains Mono', monospace",
                              whiteSpace: 'nowrap',
                              flexShrink: 0,
                            }}>
                              +{s.impact.toFixed(1)} pts
                            </span>
                          </div>
                        ))}
                      </div>
                      <p style={{ fontSize: '0.72rem', color: '#64748b', margin: '0.75rem 0 0 0', fontStyle: 'italic' }}>
                        {t('results.suggestions_disclaimer') || '* Point estimates are approximate and based on current scoring weights.'}
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* DETAILED RESULTS TAB */}
            {activeTab === 'detailed' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(result.ats?.section_scores || []).map((section, idx) => (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      margin: 0,
                      padding: '1rem 1.25rem',
                      borderLeft: `3px solid ${section.status === 'pass' ? '#22c55e' : section.status === 'warning' ? '#eab308' : '#ef4444'}`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {section.status === 'pass' && <span style={{ color: '#4ade80' }}>✓</span>}
                        {section.status === 'warning' && <span style={{ color: '#facc15' }}>⚠</span>}
                        {section.status === 'fail' && <span style={{ color: '#f87171' }}>✕</span>}
                        <span>{section.icon}</span>
                        <strong>{section.label?.[lang] || section.label?.en || section.name}</strong>
                      </div>
                      <span style={{ fontSize: '1.1rem', fontWeight: 700, color: section.score >= 70 ? '#4ade80' : section.score >= 50 ? '#facc15' : '#f87171' }}>
                        {Math.round(section.score)}
                      </span>
                    </div>
                    <p style={{ margin: '0.25rem 0 0.5rem 0', fontSize: '0.9rem', color: '#94a3b8' }}>{L(section.message)}</p>
                    {section.recommendations?.length > 0 && (
                      <div>
                        <strong style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{t('results.recommendations')}:</strong>
                        <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                          {section.recommendations.map((rec, i) => <li key={i} style={{ marginBottom: '2px' }}>{L(rec)}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}

                {/* Score components breakdown */}
                <div className="card" style={{ margin: 0 }}>
                  <h3>{t('results.breakdown_title')}</h3>
                  <ScoreBars items={[
                    { label: t('results.semantic'), value: result.semantic_score },
                    { label: t('results.keyword'), value: result.keyword_score },
                    { label: t('results.skill'), value: result.skill_score },
                    { label: t('results.experience'), value: result.experience_score },
                    { label: t('results.ats'), value: result.ats_score },
                    { label: t('results.soft_skills') || 'Soft Skills', value: result.soft_skills_score ?? 0 },
                  ]} />
                </div>

                {/* Global ATS Benchmark */}
                {result.global_benchmark && (
                  <GlobalBenchmark data={result.global_benchmark} />
                )}
              </div>
            )}

            {/* RECOMMENDATIONS TAB */}
            {activeTab === 'recommendations' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                  {/* High Priority */}
                  {result.ats?.priority_recommendations?.high?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid #ef4444' }}>
                      <h3 style={{ color: '#f87171', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        ◎ {t('results.high_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.high.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: '#fca5a5' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Medium Priority */}
                  {result.ats?.priority_recommendations?.medium?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid #eab308' }}>
                      <h3 style={{ color: '#facc15', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        🔶 {t('results.medium_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.medium.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: '#fde68a' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Low Priority */}
                  {result.ats?.priority_recommendations?.low?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid #a855f7' }}>
                      <h3 style={{ color: '#c084fc', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        💡 {t('results.low_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.low.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: '#d8b4fe' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Industry-Specific Tips */}
                {result.ats?.industry_tips?.length > 0 && (
                  <div className="card" style={{ borderLeft: '3px solid #a855f7' }}>
                    <h3 style={{ color: '#c084fc', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                      ☆ {t('results.industry_tips')}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {result.ats.industry_tips.map((tip, i) => (
                        <div key={i} style={{ background: 'rgba(168,85,247,0.08)', borderRadius: '0.5rem', padding: '0.75rem 1rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
                          {L(tip)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* NEXT STEPS TAB */}
            {activeTab === 'nextsteps' && (
              <>
                <div className="card">
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                    ◎ {t('results.next_steps_title')}
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {(result.ats?.next_steps || []).map((step, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'start', gap: '0.75rem',
                        background: 'rgba(192,132,252,0.06)', borderRadius: '0.5rem',
                        padding: '0.75rem 1rem',
                      }}>
                        <span style={{
                          background: '#1e40af', color: '#93c5fd', borderRadius: '0.375rem',
                          minWidth: '28px', height: '28px', display: 'flex', alignItems: 'center',
                          justifyContent: 'center', fontWeight: 700, fontSize: '0.85rem', flexShrink: 0,
                        }}>{i + 1}</span>
                        <span style={{ fontSize: '0.9rem', color: '#cbd5e1', paddingTop: '3px' }}>{L(step)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Download report section */}
                <div className="card" style={{ textAlign: 'center', marginTop: '1rem' }}>
                  <h3 style={{ marginTop: 0 }}>{t('results.download_report_title')}</h3>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => setActiveTab('autofix')}
                  >
                    ⬇ {t('results.download_report_btn')}
                  </button>
                  <p className="text-muted text-xs" style={{ marginTop: '0.5rem' }}>{t('results.download_report_desc')}</p>
                </div>
              </>
            )}

            {/* SCORE BREAKDOWN TAB */}
            {activeTab === 'scorebreakdown' && (
              <>
                {!scoreBreakdown && !breakdownLoading && (
                  <div className="card" style={{ textAlign: 'center' }}>
                    <p className="text-muted" style={{ marginBottom: '1rem' }}>
                      {t('analyze.score_breakdown_desc')}
                    </p>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={async () => {
                        try {
                          setBreakdownLoading(true)
                          const data = await fetchScoreBreakdown(token, {
                            cv_text: result.cv_text || '',
                            job_description: jobDesc || '',
                            lang,
                          })
                          setScoreBreakdown(data)
                        } catch (err) {
                          addToast(err.message, 'error')
                        } finally {
                          setBreakdownLoading(false)
                        }
                      }}
                    >
                      {breakdownLoading ? t('analyze.score_breakdown_loading') : t('analyze.score_breakdown_btn')}
                    </button>
                  </div>
                )}

                {breakdownLoading && (
                  <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
                    {t('analyze.scores_calculating')}
                  </div>
                )}

                {scoreBreakdown && (
                  <ScoreBreakdown
                    atsScores={scoreBreakdown.ats_scores}
                    jobMatch={jobDesc?.trim() ? scoreBreakdown.job_match : null}
                    recruiter={scoreBreakdown.recruiter}
                    feedback={scoreBreakdown.feedback}
                    lang={lang}
                  />
                )}
              </>
            )}

            {/* AUTOFIX TAB (kept from original) */}
            {activeTab === 'autofix' && (
              <div className="card">
                <h3>{t('analyze.autofix_title')}</h3>
                <p className="text-muted" style={{ marginBottom: '1rem' }}>
                  {t('analyze.autofix_desc')}
                </p>

                {autoFixError && <p className="error">{autoFixError}</p>}

                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                  <button type="button" className="btn-primary" onClick={() => handleAutoFix(true)} disabled={autoFixLoading}>
                    {autoFixLoading ? t('analyze.autofix_processing') : t('analyze.autofix_ai_fix')}
                  </button>
                  <button type="button" className="btn-outline" onClick={() => handleAutoFix(false)} disabled={autoFixLoading}>
                    {autoFixLoading ? t('analyze.autofix_processing') : t('analyze.autofix_quick_fix')}
                  </button>
                </div>

                {autoFixResult && (
                  <>
                    <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                      <div className="card" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                        <div className="text-muted">{t('analyze.autofix_before_ats')}</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{autoFixResult.before_ats?.overall_score ?? 0}</div>
                      </div>
                      <div className="card" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                        <div className="text-muted">{t('analyze.autofix_after_ats')}</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#22c55e' }}>{autoFixResult.after_ats?.overall_score ?? 0}</div>
                      </div>
                    </div>

                    <div className="card" style={{ margin: '0 0 1rem 0', padding: '0.75rem 1rem' }}>
                      <div className="text-muted" style={{ marginBottom: '0.5rem' }}>
                        {t('analyze.autofix_changes_title')}
                      </div>
                      {Array.isArray(autoFixResult.applied_changes) && autoFixResult.applied_changes.length > 0 ? (
                        <ul className="suggestion-list" style={{ marginBottom: 0 }}>
                          {autoFixResult.applied_changes.map((change, idx) => (
                            <li key={`change-${idx}`}>{change}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-muted" style={{ margin: 0 }}>{t('analyze.autofix_changes_empty')}</p>
                      )}
                    </div>

                    <textarea
                      className="job-desc-input"
                      rows={14}
                      value={editedText}
                      onChange={(e) => setEditedText(e.target.value)}
                    />

                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => handleExportAutoFix('pdf')}
                        disabled={exportLoading === 'pdf'}
                      >
                        {exportLoading === 'pdf' ? t('analyze.autofix_exporting') : t('analyze.autofix_export_pdf')}
                      </button>
                      <button
                        type="button"
                        className="btn-outline"
                        onClick={() => handleExportAutoFix('docx')}
                        disabled={exportLoading === 'docx'}
                      >
                        {exportLoading === 'docx' ? t('analyze.autofix_exporting') : t('analyze.autofix_export_docx')}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </motion.div>
        )}
        </AnimatePresence>

      </main>
    </div>
  )
}
