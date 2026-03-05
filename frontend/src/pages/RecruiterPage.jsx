import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import Modal from '../components/Modal'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'

function getHistory() {
  try { return JSON.parse(localStorage.getItem('cv-analyzer-history') || '[]') }
  catch { return [] }
}

export default function RecruiterPage() {
  const { t } = useLanguage()
  const history = getHistory()
  const [selected, setSelected] = useState(null)

  // Simulated candidates from history
  const candidates = history.map((h, i) => ({
    id: h.id,
    name: h.fileName?.replace('.pdf', '') || `Candidate ${i + 1}`,
    score: h.score,
    date: h.date,
    interpretation: h.result?.interpretation,
    result: h.result,
  }))

  const sorted = [...candidates].sort((a, b) => b.score - a.score)
  const avgScore = candidates.length
    ? Math.round(candidates.reduce((sum, c) => sum + c.score, 0) / candidates.length)
    : 0

  function getScoreColor(score) {
    if (score >= 75) return '#22c55e'
    if (score >= 50) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content">
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
              <span className="stat-value">{sorted.filter(c => c.score >= 75).length}</span>
              <span className="stat-label">{t('recruiter.top_candidates')}</span>
            </div>
          </div>
        </div>

        {candidates.length > 0 ? (
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
                  {sorted.map((c, i) => (
                    <tr key={c.id}>
                      <td>{i + 1}</td>
                      <td>{c.name}</td>
                      <td>
                        <span className="score-badge" style={{ color: getScoreColor(c.score) }}>
                          {Math.round(c.score)}%
                        </span>
                      </td>
                      <td className="text-muted">{new Date(c.date).toLocaleDateString()}</td>
                      <td>
                        <button className="btn-outline btn-sm" onClick={() => setSelected(c)}>
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
                  <h3>{selected.name}</h3>
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
              {selected.result.missing_skills?.length > 0 && (
                <>
                  <h4>{t('results.missing_skills')}</h4>
                  <SkillTags skills={selected.result.missing_skills} variant="missing" />
                </>
              )}
            </div>
          )}
        </Modal>
      </main>
    </div>
  )
}
