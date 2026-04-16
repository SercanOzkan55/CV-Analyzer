import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { analyzePdf, autoFixCv, exportAutoFixedCV } from '../api'
import { addHistoryItem } from '../utils/historyStorage'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'

function saveToHistory(result, fileName, jobDesc, user) {
  try {
    addHistoryItem(user, {
      id: Date.now(),
      date: new Date().toISOString(),
      fileName,
      jobTitle: jobDesc.slice(0, 60),
      score: result.final_score,
      interpretation: result.interpretation,
      result,
    })
  } catch { /* ignore storage errors */ }
}

export default function AnalyzePage() {
  const { user, token, canAnalyze, recordAnalysis, signOut } = useAuth()
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
  const [activeTab, setActiveTab] = useState('results')
  const [autoFixResult, setAutoFixResult] = useState(null)
  const [autoFixLoading, setAutoFixLoading] = useState(false)
  const [autoFixError, setAutoFixError] = useState(null)
  const [exportLoading, setExportLoading] = useState(null)
  const [editedText, setEditedText] = useState('')

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
      setActiveTab('results')
      setAutoFixResult(null)
      setAutoFixError(null)
      setEditedText('')
      recordAnalysis()
      saveToHistory(data, file.name, jobDesc, user)
      addToast(t('toast.analysis_complete'), 'success')
    } catch (err) {
      if (err.message.includes('403')) {
        addToast(t('toast.limit_reached'), 'warning')
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
    setActiveTab('results')
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
        <div className="page-header">
          <h1>{t('analyze.title')}</h1>
          {result && (
            <button className="btn-outline" onClick={handleReset}>{t('analyze.new_analysis')}</button>
          )}
        </div>

        {!result ? (
          <form onSubmit={handleAnalyze} className="analyze-form">
            <div className="analyze-grid">
              {/* Upload Section */}
              <div className="card">
                <h2>{t('analyze.upload_title')}</h2>
                <DragDropUpload
                  file={file}
                  onFileSelect={setFile}
                  onRemove={() => setFile(null)}
                />
              </div>

              {/* Job Description */}
              <div className="card">
                <h2>{t('analyze.job_desc_title')}</h2>
                <textarea
                  className="job-desc-input"
                  rows={12}
                  placeholder={t('analyze.job_desc_placeholder')}
                  value={jobDesc}
                  onChange={(e) => setJobDesc(e.target.value)}
                />
              </div>
            </div>

            {/* Progress */}
            {loading && (
              <div className="progress-wrapper">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <span className="progress-text">{t('analyze.upload_progress')}</span>
              </div>
            )}

            {error && <p className="error">{error}</p>}

            <button type="submit" className="btn-primary btn-lg btn-full" disabled={loading}>
              {loading ? t('analyze.analyzing') : t('analyze.analyze_btn')}
            </button>
          </form>
        ) : (
          <div className="results-layout">
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
              {[
                { id: 'results', label: t('analyze.tab_results') },
                { id: 'ats', label: t('analyze.tab_ats_check') },
                { id: 'autofix', label: t('analyze.tab_autofix') },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={activeTab === tab.id ? 'btn-primary' : 'btn-outline'}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'results' && (
              <>
                <div className="results-top">
                  <div className="card result-score-card">
                    <ScoreCircle score={result.final_score} size={160} label={t('results.final_score')} />
                    <h3 className="result-interpretation">{getInterpretation(result.interpretation)}</h3>
                    <span className="risk-badge" style={{ background: getRiskColor(result.risk_level) }}>
                      {getRiskLabel(result.risk_level)}
                    </span>
                  </div>

                  <div className="card">
                    <h3>{t('results.industry')}</h3>
                    <p className="industry-name">{result.industry?.industry_name}</p>
                    <p className="text-muted">{result.industry?.specialization_name}</p>
                  </div>

                  <div className="card">
                    <h3>{t('results.breakdown_title')}</h3>
                    <ScoreBars items={[
                      { label: t('results.semantic'), value: result.semantic_score },
                      { label: t('results.keyword'), value: result.keyword_score },
                      { label: t('results.skill'), value: result.skill_score },
                      { label: t('results.experience'), value: result.experience_score },
                      { label: t('results.ats'), value: result.ats_score },
                    ]} />
                  </div>
                </div>

                <div className="results-details">
                  {result.detected_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.detected_skills')}</h3>
                      <SkillTags skills={result.detected_skills} variant="detected" />
                    </div>
                  )}

                  {result.missing_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.missing_skills')}</h3>
                      <SkillTags skills={result.missing_skills} variant="missing" />
                    </div>
                  )}

                  {result.ats?.suggestions?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.ats_suggestions')}</h3>
                      <ul className="suggestion-list">
                        {result.ats.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}

                  {result.recommendations?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.recommendations')}</h3>
                      <ul className="suggestion-list">
                        {result.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </>
            )}

            {activeTab === 'ats' && (
              <>
                <div className="results-top">
                  <div className="card result-score-card">
                    <ScoreCircle score={result.ats_score} size={160} label="ATS" />
                    <h3 className="result-interpretation">{t('analyze.ats_check_title')}</h3>
                  </div>

                  <div className="card">
                    <h3>{t('results.breakdown_title')}</h3>
                    <ScoreBars items={[
                      { label: t('results.ats'), value: result.ats_score },
                      { label: t('results.skill'), value: result.skill_score },
                      { label: t('results.keyword'), value: result.keyword_score },
                    ]} />
                  </div>
                </div>

                <div className="results-details">
                  {result.detected_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.detected_skills')}</h3>
                      <SkillTags skills={result.detected_skills} variant="detected" />
                    </div>
                  )}

                  {result.missing_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.missing_skills')}</h3>
                      <SkillTags skills={result.missing_skills} variant="missing" />
                    </div>
                  )}

                  {result.ats?.suggestions?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.ats_suggestions')}</h3>
                      <ul className="suggestion-list">
                        {result.ats.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </>
            )}

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
          </div>
        )}

      </main>
    </div>
  )
}
