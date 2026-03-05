import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { analyzePdf } from '../api'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'

function saveToHistory(result, fileName, jobDesc) {
  try {
    const history = JSON.parse(localStorage.getItem('cv-analyzer-history') || '[]')
    history.unshift({
      id: Date.now(),
      date: new Date().toISOString(),
      fileName,
      jobTitle: jobDesc.slice(0, 60),
      score: result.final_score,
      interpretation: result.interpretation,
      result,
    })
    // Keep last 50 entries
    localStorage.setItem('cv-analyzer-history', JSON.stringify(history.slice(0, 50)))
  } catch { /* ignore storage errors */ }
}

export default function AnalyzePage() {
  const { token, canAnalyze, recordAnalysis, signOut } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [file, setFile] = useState(null)
  const [jobDesc, setJobDesc] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  async function handleAnalyze(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setSaved(false)

    if (!file) return setError(t('analyze.no_file'))
    if (file.type !== 'application/pdf') return setError(t('analyze.invalid_file'))
    if (file.size > 10 * 1024 * 1024) return setError(t('analyze.file_too_large'))
    if (!jobDesc.trim()) return setError(t('analyze.no_job_desc'))

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

      const data = await analyzePdf(token, file, jobDesc)

      clearInterval(progressInterval)
      setProgress(100)
      setResult(data)
      recordAnalysis()
      saveToHistory(data, file.name, jobDesc)
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

  function handleReset() {
    setFile(null)
    setJobDesc('')
    setResult(null)
    setError(null)
    setSaved(false)
  }

  function getInterpretation(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('strong')) return t('results.strong_match')
    if (lower.includes('moderate')) return t('results.moderate_match')
    return t('results.weak_match')
  }

  function getRiskLabel(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('low')) return t('results.low_risk')
    if (lower.includes('medium')) return t('results.medium_risk')
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
          /* Results Section */
          <div className="results-layout">
            {/* Score Overview */}
            <div className="results-top">
              <div className="card result-score-card">
                <ScoreCircle score={result.final_score} size={160} label={t('results.final_score')} />
                <h3 className="result-interpretation">{result.interpretation}</h3>
                <span className="risk-badge" style={{ background: getRiskColor(result.risk_level) }}>
                  {result.risk_level}
                </span>
              </div>

              {/* Industry */}
              <div className="card">
                <h3>{t('results.industry')}</h3>
                <p className="industry-name">{result.industry?.industry_name}</p>
                <p className="text-muted">{result.industry?.specialization_name}</p>
              </div>

              {/* Quick Stats */}
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

            {/* Detail Cards */}
            <div className="results-details">
              {/* Detected Skills */}
              {result.detected_skills?.length > 0 && (
                <div className="card">
                  <h3>{t('results.detected_skills')}</h3>
                  <SkillTags skills={result.detected_skills} variant="detected" />
                </div>
              )}

              {/* Missing Skills */}
              {result.missing_skills?.length > 0 && (
                <div className="card">
                  <h3>{t('results.missing_skills')}</h3>
                  <SkillTags skills={result.missing_skills} variant="missing" />
                </div>
              )}

              {/* ATS Suggestions */}
              {result.ats?.suggestions?.length > 0 && (
                <div className="card">
                  <h3>{t('results.ats_suggestions')}</h3>
                  <ul className="suggestion-list">
                    {result.ats.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              {/* Recommendations */}
              {result.recommendations?.length > 0 && (
                <div className="card">
                  <h3>{t('results.recommendations')}</h3>
                  <ul className="suggestion-list">
                    {result.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
