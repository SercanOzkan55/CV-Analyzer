import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'
import Modal from '../components/Modal'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'

function getHistory() {
  try { return JSON.parse(localStorage.getItem('cv-analyzer-history') || '[]') }
  catch { return [] }
}

function setHistory(h) {
  localStorage.setItem('cv-analyzer-history', JSON.stringify(h))
}

export default function HistoryPage() {
  const { t } = useLanguage()
  const { addToast } = useToast()
  const [history, setHistoryState] = useState(getHistory)
  const [selected, setSelected] = useState(null)

  function handleDelete(id) {
    const updated = history.filter((h) => h.id !== id)
    setHistory(updated)
    setHistoryState(updated)
    addToast(t('toast.analysis_deleted'), 'info')
    if (selected?.id === id) setSelected(null)
  }

  function handleClearAll() {
    setHistory([])
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
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>{t('history.title')}</h1>
            <p className="text-muted">{t('history.subtitle')}</p>
          </div>
          {history.length > 0 && (
            <button className="btn-outline btn-danger" onClick={handleClearAll}>{t('history.delete_all')}</button>
          )}
        </div>

        {history.length > 0 ? (
          <div className="history-grid">
            {/* History List */}
            <div className="history-list">
              {history.map((item) => (
                <div
                  key={item.id}
                  className={`history-item ${selected?.id === item.id ? 'active' : ''}`}
                  onClick={() => setSelected(item)}
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
                  <button
                    className="btn-icon btn-danger-icon"
                    onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                    title={t('history.delete')}
                  >
                    🗑
                  </button>
                </div>
              ))}
            </div>

            {/* Detail Panel */}
            <div className="history-detail">
              {selected?.result ? (
                <div className="detail-content">
                  <div className="card result-score-card">
                    <ScoreCircle score={selected.result.final_score} size={120} label={t('results.final_score')} />
                    <h3>{selected.result.interpretation}</h3>
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

                  {selected.result.missing_skills?.length > 0 && (
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
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon">👈</div>
                  <h3>{t('history.details')}</h3>
                  <p className="text-muted">Select an analysis to view details</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card empty-state">
            <div className="empty-icon">📋</div>
            <h3>{t('history.no_history')}</h3>
            <p>{t('history.no_history_desc')}</p>
            <Link to="/analyze" className="btn-primary">{t('history.start_analyzing')}</Link>
          </div>
        )}
      </main>
    </div>
  )
}
