import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import Modal from '../components/Modal'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'
import {
  fetchCandidates,
  fetchTopCandidates,
  searchRecruiter,
  fetchRecruiterCandidateDetail,
  recruiterBatchRank,
} from '../api'

export default function RecruiterPage() {
  const { t } = useLanguage()
  const { token } = useAuth()
  const [candidates, setCandidates] = useState([])
  const [topCandidates, setTopCandidates] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [jdText, setJdText] = useState('')
  const [jdFile, setJdFile] = useState(null)
  const [cvFiles, setCvFiles] = useState([])
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState(null)

  useEffect(() => {
    document.title = `${t('nav.recruiter')} — CV Analyzer`
  }, [t])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!token) {
        if (!cancelled) {
          setCandidates([])
          setTopCandidates([])
          setLoading(false)
        }
        return
      }
      setLoading(true)
      setError(null)
      try {
        const [all, top] = await Promise.all([
          fetchCandidates(token),
          fetchTopCandidates(token),
        ])
        if (cancelled) return
        setCandidates(Array.isArray(all?.candidates) ? all.candidates : [])
        setTopCandidates(Array.isArray(top?.top_candidates) ? top.top_candidates : [])
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to load candidates')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [token])

  async function handleSearch(e) {
    e.preventDefault()
    const q = searchQuery.trim()
    if (!q || !token) {
      setSearchResults([])
      return
    }
    setError(null)
    try {
      const res = await searchRecruiter(token, q)
      setSearchResults(Array.isArray(res?.results) ? res.results : [])
    } catch (e) {
      setError(e.message || 'Search failed')
      setSearchResults([])
    }
  }

  async function handleBatchRank(e) {
    e.preventDefault()
    if (!token) return
    if (cvFiles.length === 0) {
      setError('En az bir CV PDF dosyasi secin')
      return
    }
    if (!jdText.trim() && !jdFile) {
      setError('Job description metni girin veya JD dosyasi yukleyin')
      return
    }
    setError(null)
    setBatchLoading(true)
    try {
      const result = await recruiterBatchRank(token, {
        jobDescription: jdText,
        jdFile,
        cvFiles,
      })
      setBatchResult(result)
    } catch (e) {
      setError(e.message || 'Batch ranking failed')
    } finally {
      setBatchLoading(false)
    }
  }

  async function openCandidateDetail(candidate) {
    if (!candidate?.analysis_id || !token) {
      setSelected(candidate)
      return
    }
    try {
      const detail = await fetchRecruiterCandidateDetail(token, candidate.analysis_id)
      setSelected({ ...candidate, result: detail })
    } catch {
      setSelected(candidate)
    }
  }

  function getScoreColor(score) {
    if (score >= 75) return '#22c55e'
    if (score >= 50) return '#eab308'
    return '#ef4444'
  }

  function downloadTextFile(content, fileName, mimeType) {
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  function exportBatchCsv() {
    const rows = batchResult?.ranking || []
    if (!rows.length) return

    const header = [
      'rank',
      'candidate_name',
      'file_name',
      'final_score',
      'ats_score',
      'skill_score',
      'missing_skills_count',
    ]

    const csvLines = [header.join(',')]
    rows.forEach((r) => {
      const line = [
        r.rank || '',
        `"${String(r.candidate_name || '').replace(/"/g, '""')}"`,
        `"${String(r.file_name || '').replace(/"/g, '""')}"`,
        Number(r.final_score || 0).toFixed(2),
        Number(r.ats_score || 0).toFixed(2),
        Number(r.skill_score || 0).toFixed(2),
        Array.isArray(r.missing_skills) ? r.missing_skills.length : 0,
      ]
      csvLines.push(line.join(','))
    })

    downloadTextFile(
      csvLines.join('\n'),
      `batch-ranking-${new Date().toISOString().slice(0, 10)}.csv`,
      'text/csv;charset=utf-8;'
    )
  }

  function downloadRankedReport() {
    if (!batchResult) return
    const payload = {
      generated_at: new Date().toISOString(),
      total_candidates: batchResult.total_candidates || 0,
      analytics: batchResult.analytics || {},
      ranking: batchResult.ranking || [],
      job_description_preview: batchResult.job_description_preview || '',
    }
    downloadTextFile(
      JSON.stringify(payload, null, 2),
      `ranked-report-${new Date().toISOString().slice(0, 10)}.json`,
      'application/json;charset=utf-8;'
    )
  }

  const avgScore = candidates.length
    ? Math.round(candidates.reduce((sum, c) => sum + (c.final_score || c.similarity_score || 0), 0) / candidates.length)
    : 0

  const distribution = batchResult?.analytics?.candidate_distribution || {
    high: 0,
    medium: 0,
    low: 0,
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <div className="page-header">
          <div>
            <h1>{t('recruiter.title')}</h1>
            <p className="text-muted">{t('recruiter.subtitle')}</p>
          </div>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">👥</div>
            <div className="stat-info">
              <span className="stat-value">{candidates.length}</span>
              <span className="stat-label">{t('recruiter.total_analyzed')}</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-info">
                <span className="stat-value">{avgScore}%</span>
              <span className="stat-label">{t('recruiter.avg_score')}</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🏆</div>
            <div className="stat-info">
              <span className="stat-value">{topCandidates.length}</span>
              <span className="stat-label">{t('recruiter.top_candidates')}</span>
            </div>
          </div>
        </div>

        {/* JD + Batch Ranking */}
        <div className="card card-accent-top" style={{ marginTop: '1.5rem' }}>
          <h2 className="recruiter-section-title">
            <span className="section-icon">📋</span>
            {t('recruiter.batch_title')}
          </h2>
          <form onSubmit={handleBatchRank}>
            <div className="recruiter-form-group">
              <label>
                <span className="label-icon">📝</span>
                {t('recruiter.jd_text_label')}
              </label>
              <textarea
                className="recruiter-textarea"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                rows={6}
                placeholder={t('recruiter.jd_text_placeholder')}
              />
            </div>

            <div className="recruiter-form-group">
              <label>
                <span className="label-icon">📎</span>
                {t('recruiter.jd_file_label')}
              </label>
              <input
                type="file"
                accept=".txt,.pdf,text/plain,application/pdf"
                onChange={(e) => setJdFile(e.target.files?.[0] || null)}
              />
            </div>

            <div className="recruiter-form-group">
              <label>
                <span className="label-icon">📄</span>
                {t('recruiter.cv_upload_label')}
              </label>
              <input
                type="file"
                multiple
                accept="application/pdf,.pdf"
                onChange={(e) => setCvFiles(Array.from(e.target.files || []).slice(0, 50))}
              />
            </div>

            <button className="btn-rank" type="submit" disabled={batchLoading}>
              {batchLoading ? '⏳' : '🚀'}
              {batchLoading ? t('recruiter.ranking_in_progress') : t('recruiter.run_batch_ranking')}
            </button>
          </form>
          <div className="cv-count-badge">
            📊 {t('recruiter.cv_count')}: {cvFiles.length} / 50
          </div>
        </div>

        {/* Recruiter Analytics */}
        {batchResult?.analytics && (
          <div className="card card-accent-top" style={{ marginTop: '1.5rem' }}>
            <h2 className="recruiter-section-title">
              <span className="section-icon">📊</span>
              {t('recruiter.recruiter_analytics')}
            </h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">📊</div>
                <div className="stat-info">
                  <span className="stat-value">{batchResult.analytics.avg_score}%</span>
                  <span className="stat-label">{t('recruiter.avg_score')}</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">🧠</div>
                <div className="stat-info">
                  <span className="stat-value">{batchResult.analytics.top_skills?.[0]?.skill || '-'}</span>
                  <span className="stat-label">{t('recruiter.top_skill')}</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">📦</div>
                <div className="stat-info">
                  <span className="stat-value">H:{distribution.high} M:{distribution.medium} L:{distribution.low}</span>
                  <span className="stat-label">{t('recruiter.candidate_distribution')}</span>
                </div>
              </div>
            </div>
            {batchResult.analytics.top_skills?.length > 0 && (
              <>
                <h3 style={{ marginTop: 12 }}>{t('recruiter.top_skills')}</h3>
                <SkillTags
                  skills={batchResult.analytics.top_skills.map((x) => `${x.skill} (${x.count})`)}
                  variant="normal"
                />
              </>
            )}
          </div>
        )}

        {/* Batch Ranking Table */}
        {batchResult?.ranking?.length > 0 && (
          <div className="card card-accent-top" style={{ marginTop: '1.5rem' }}>
            <div className="card-header">
              <h2 className="recruiter-section-title">
                <span className="section-icon">🏆</span>
                {t('recruiter.batch_ranking')}
              </h2>
              <div className="export-group">
                <button className="btn-outline btn-sm" onClick={exportBatchCsv}>
                  📥 {t('recruiter.export_csv')}
                </button>
                <button className="btn-outline btn-sm" onClick={downloadRankedReport}>
                  📋 {t('recruiter.download_report')}
                </button>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t('recruiter.candidates')}</th>
                    <th>{t('results.final_score')}</th>
                    <th>ATS</th>
                    <th>Skill</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {batchResult.ranking.map((r, i) => (
                    <tr key={`${r.file_name}-${i}`}>
                      <td>{r.rank || i + 1}</td>
                      <td>{r.candidate_name}</td>
                      <td>
                        <span className="score-badge" style={{ color: getScoreColor(r.final_score) }}>
                          {Math.round(r.final_score)}%
                        </span>
                      </td>
                      <td>{Math.round(r.ats_score)}%</td>
                      <td>{Math.round(r.skill_score)}%</td>
                      <td>
                        <button
                          className="btn-outline btn-sm"
                          onClick={() => setSelected({ name: r.candidate_name, result: r })}
                        >
                          {t('common.details')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="card search-card" style={{ marginTop: '1.5rem' }}>
          <form className="search-row" onSubmit={handleSearch}>
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={t('recruiter.search_placeholder')}
            />
            <button className="btn-outline btn-sm" type="submit">🔍 {t('recruiter.search')}</button>
          </form>
          {error && <p className="text-danger" style={{ marginTop: '0.5rem' }}>{error}</p>}
        </div>

        {searchResults.length > 0 && (
            <div className="card" style={{ marginTop: 12 }}>
              <h3>{t('recruiter.search_results')}</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Preview</th>
                      <th>Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResults.map((r) => (
                      <tr key={r.id}>
                        <td>{r.id}</td>
                        <td>{r.cv_preview || '-'}</td>
                        <td>{typeof r.rank === 'number' ? r.rank.toFixed(3) : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
        )}

        {loading ? (
          <div className="card empty-state">
            <div className="empty-icon">⏳</div>
            <h3>{t('common.loading')}</h3>
          </div>
        ) : candidates.length > 0 ? (
          <div className="card">
            <h2>{t('recruiter.candidates')}</h2>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t('recruiter.candidates')}</th>
                    <th>{t('dashboard.score')}</th>
                    <th>{t('dashboard.date')}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {candidates
                    .slice()
                    .sort((a, b) => (b.final_score || b.similarity_score || 0) - (a.final_score || a.similarity_score || 0))
                    .map((c, i) => (
                    <tr key={c.id || c.analysis_id || i}>
                      <td>{i + 1}</td>
                      <td>{c.name || c.candidate_name || `Candidate ${i + 1}`}</td>
                      <td>
                        <span className="score-badge" style={{ color: getScoreColor(c.final_score || c.similarity_score || 0) }}>
                          {Math.round(c.final_score || c.similarity_score || 0)}%
                        </span>
                      </td>
                      <td className="text-muted">{c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}</td>
                      <td>
                        <button className="btn-outline btn-sm" onClick={() => openCandidateDetail(c)}>
                          {t('recruiter.view_cv')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="card empty-state">
            <div className="empty-icon">👔</div>
            <h3>{t('recruiter.no_candidates')}</h3>
            <p>{t('recruiter.no_candidates_desc')}</p>
          </div>
        )}

        {/* Candidate Detail Modal */}
        <Modal open={!!selected} onClose={() => setSelected(null)} title={t('recruiter.candidate_detail')}>
          {selected?.result && (
            <div className="modal-detail">
              <div className="modal-score-row">
                <ScoreCircle score={selected.result.final_score} size={100} />
                <div>
                  <h3>{selected.name || selected.candidate_name}</h3>
                  <p className="text-muted">{selected.result.interpretation}</p>
                </div>
              </div>
              <ScoreBars items={[
                { label: t('results.semantic'), value: selected.result.semantic_score },
                { label: t('results.keyword'), value: selected.result.keyword_score },
                { label: t('results.skill'), value: selected.result.skill_score },
                { label: t('results.experience'), value: selected.result.experience_score },
                { label: t('results.ats'), value: selected.result.ats_score },
              ]} />
              {selected.result.score_breakdown && (
                <>
                  <h4>{t('results.ats_breakdown')}</h4>
                  <ScoreBars items={[
                    { label: t('results.skills_dimension'), value: selected.result.score_breakdown.skills },
                    { label: t('results.keywords_dimension'), value: selected.result.score_breakdown.keywords },
                    { label: t('results.format_dimension'), value: selected.result.score_breakdown.format },
                    { label: t('results.experience_dimension'), value: selected.result.score_breakdown.experience },
                  ]} />
                </>
              )}
              {selected.result.missing_skills?.length > 0 && (
                <>
                  <h4>{t('results.missing_skills')}</h4>
                  <SkillTags skills={selected.result.missing_skills} variant="missing" />
                </>
              )}
              {selected.result.keyword_gap?.missing_words?.length > 0 && (
                <>
                  <h4>{t('results.missing_keywords')}</h4>
                  <SkillTags skills={selected.result.keyword_gap.missing_words} variant="missing" />
                </>
              )}
            </div>
          )}
        </Modal>
      </main>
    </div>
  )
}
