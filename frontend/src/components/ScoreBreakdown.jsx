import React from 'react'
import ScoreBars from './ScoreBars'
import { getGrade } from '../utils/scoreColors'

function PriorityBadge({ priority }) {
  const colors = {
    high: { bg: 'rgba(239,68,68,0.15)', text: '#f87171', label: 'High' },
    medium: { bg: 'rgba(234,179,8,0.15)', text: '#facc15', label: 'Medium' },
    low: { bg: 'rgba(168,85,247,0.15)', text: '#c084fc', label: 'Low' },
  }
  const c = colors[priority] || colors.low
  return (
    <span style={{
      background: c.bg, color: c.text,
      padding: '2px 8px', borderRadius: '4px',
      fontSize: '0.75rem', fontWeight: 600,
    }}>
      {c.label}
    </span>
  )
}

/**
 * ScoreBreakdown — Full score dashboard.
 *
 * Props:
 *   atsScores:  { overall, structure, keywords, experience, education, languages, ats, length }
 *   jobMatch:   { match_score, keyword_score, semantic_score, keyword_coverage_pct,
 *                 missing_keywords, weak_keywords, strong_keywords, suggested_keywords }
 *   recruiter:  { interest, hireability, shortlist_probability, strengths, concerns }
 *   feedback:   { score_before, potential_score, items: [{ category, priority, message }] }
 *   lang:       'en' | 'tr'
 */
export default function ScoreBreakdown({ atsScores, jobMatch, recruiter, feedback, lang = 'en' }) {
  const t = lang === 'tr' ? TR : EN

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Overall Score ─────────────────────────────── */}
      {atsScores && (
        <div className="card" style={{ margin: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0 }}>{t.atsTitle}</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{
                fontSize: '2rem', fontWeight: 800,
                fontFamily: "'JetBrains Mono', monospace",
                color: getGrade(atsScores.overall).color,
              }}>
                {Math.round(atsScores.overall)}
              </span>
              <span style={{
                background: getGrade(atsScores.overall).color + '22',
                color: getGrade(atsScores.overall).color,
                padding: '2px 10px', borderRadius: '6px',
                fontWeight: 700, fontSize: '1rem',
              }}>
                {getGrade(atsScores.overall).label}
              </span>
            </div>
          </div>

          <ScoreBars items={[
            { label: t.structure, value: atsScores.structure },
            { label: t.keywords, value: atsScores.keywords },
            { label: t.experience, value: atsScores.experience },
            { label: t.education, value: atsScores.education },
            { label: t.ats, value: atsScores.ats },
            { label: t.length, value: atsScores.length },
            { label: t.languages, value: atsScores.languages },
          ]} />
        </div>
      )}

      {/* ── Job Match ─────────────────────────────────── */}
      {jobMatch && (
        <div className="card" style={{ margin: 0 }}>
          <h3 style={{ marginTop: 0 }}>{t.matchTitle}</h3>

          <ScoreBars items={[
            { label: t.matchOverall, value: jobMatch.match_score },
            { label: t.keyword, value: jobMatch.keyword_score },
            { label: t.semantic, value: jobMatch.semantic_score },
          ]} />

          <div style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: '#94a3b8' }}>
            {t.coverage}: <strong style={{ color: '#e2e8f0' }}>{Math.round(jobMatch.keyword_coverage_pct || 0)}%</strong>
          </div>

          {/* Keyword tags */}
          {jobMatch.missing_keywords?.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', color: '#f87171', marginBottom: '0.3rem', fontWeight: 600 }}>
                {t.missing} ({jobMatch.missing_keywords.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                {jobMatch.missing_keywords.slice(0, 15).map((kw) => (
                  <span key={kw} style={{
                    background: 'rgba(239,68,68,0.12)',
                    color: '#fca5a5', padding: '2px 8px',
                    borderRadius: '4px', fontSize: '0.8rem',
                  }}>{kw}</span>
                ))}
              </div>
            </div>
          )}

          {jobMatch.strong_keywords?.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.85rem', color: '#4ade80', marginBottom: '0.3rem', fontWeight: 600 }}>
                {t.strong} ({jobMatch.strong_keywords.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                {jobMatch.strong_keywords.slice(0, 10).map((kw) => (
                  <span key={kw} style={{
                    background: 'rgba(34,197,94,0.12)',
                    color: '#86efac', padding: '2px 8px',
                    borderRadius: '4px', fontSize: '0.8rem',
                  }}>{kw}</span>
                ))}
              </div>
            </div>
          )}

          {jobMatch.suggested_keywords?.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.85rem', color: '#38bdf8', marginBottom: '0.3rem', fontWeight: 600 }}>
                {t.suggested} ({jobMatch.suggested_keywords.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                {jobMatch.suggested_keywords.slice(0, 12).map((kw) => (
                  <span key={kw} style={{
                    background: 'rgba(56,189,248,0.12)',
                    color: '#7dd3fc', padding: '2px 8px',
                    borderRadius: '4px', fontSize: '0.8rem',
                  }}>{kw}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Recruiter Score ───────────────────────────── */}
      {recruiter && (
        <div className="card" style={{ margin: 0 }}>
          <h3 style={{ marginTop: 0 }}>{t.recruiterTitle}</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
            <ScoreGauge label={t.interest} value={recruiter.interest} />
            <ScoreGauge label={t.hireability} value={recruiter.hireability} />
            <ScoreGauge label={t.shortlist} value={recruiter.shortlist_probability} />
          </div>

          {recruiter.strengths?.length > 0 && (
            <div style={{ marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.85rem', color: '#4ade80', fontWeight: 600, marginBottom: '0.3rem' }}>
                {t.strengths}
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                {recruiter.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}

          {recruiter.concerns?.length > 0 && (
            <div>
              <div style={{ fontSize: '0.85rem', color: '#f87171', fontWeight: 600, marginBottom: '0.3rem' }}>
                {t.concerns}
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                {recruiter.concerns.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ── Feedback / Improvement Suggestions ────────── */}
      {feedback && feedback.items?.length > 0 && (
        <div className="card" style={{ margin: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0 }}>{t.feedbackTitle}</h3>
            <div style={{ fontSize: '0.9rem', color: '#94a3b8' }}>
              {feedback.score_before} → <strong style={{ color: '#4ade80' }}>{feedback.potential_score}</strong>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {feedback.items.map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '0.5rem', padding: '0.6rem 0.8rem',
              }}>
                <PriorityBadge priority={item.priority} />
                <span style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{item.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreGauge({ label, value }) {
  const grade = getGrade(value)
  return (
    <div style={{
      textAlign: 'center', padding: '0.75rem',
      background: 'rgba(255,255,255,0.03)',
      borderRadius: '0.75rem',
    }}>
      <div style={{
        fontSize: '1.8rem', fontWeight: 800,
        fontFamily: "'JetBrains Mono', monospace",
        color: grade.color,
      }}>
        {Math.round(value)}
      </div>
      <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.2rem' }}>{label}</div>
    </div>
  )
}

const EN = {
  atsTitle: 'ATS Score Breakdown',
  structure: 'Structure', keywords: 'Keywords', experience: 'Experience',
  education: 'Education', ats: 'ATS Compatibility', length: 'Length',
  languages: 'Languages',
  matchTitle: 'Job Match Analysis',
  matchOverall: 'Overall Match', keyword: 'Keyword Match', semantic: 'Semantic Match',
  coverage: 'Keyword Coverage',
  missing: 'Missing Keywords', strong: 'Strong Keywords', suggested: 'Add These',
  recruiterTitle: 'Recruiter Score',
  interest: 'Interest', hireability: 'Hireability', shortlist: 'Shortlist',
  strengths: 'Strengths', concerns: 'Concerns',
  feedbackTitle: 'Improvement Suggestions',
}

const TR = {
  atsTitle: 'ATS Puan Detayi',
  structure: 'Yapi', keywords: 'Anahtar Kelimeler', experience: 'Deneyim',
  education: 'Egitim', ats: 'ATS Uyumluluk', length: 'Uzunluk',
  languages: 'Diller',
  matchTitle: 'Is Eslesmesi Analizi',
  matchOverall: 'Genel Eslesme', keyword: 'Anahtar Kelime', semantic: 'Semantik Eslesme',
  coverage: 'Anahtar Kelime Kapsami',
  missing: 'Eksik Kelimeler', strong: 'Guclu Kelimeler', suggested: 'Bunlari Ekleyin',
  recruiterTitle: 'Ise Alim Puani',
  interest: 'Ilgi', hireability: 'Ise Alinabilirlik', shortlist: 'Kisa Liste',
  strengths: 'Guclu Yanlar', concerns: 'Endiseler',
  feedbackTitle: 'Iyilestirme Onerileri',
}
