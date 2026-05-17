import React, { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { GitCompare, ArrowRight, ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import { getHistory } from '../utils/historyStorage'
import { diffCvText } from '../api'

function RadarChart({ dimensions, labelA, labelB }) {
  const n = dimensions.length
  const cx = 150, cy = 150, r = 110
  const angleStep = (2 * Math.PI) / n
  const startAngle = -Math.PI / 2 // start at top

  function polarToXY(angle, radius) {
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]
  }

  // Grid rings
  const rings = [25, 50, 75, 100]
  const gridLines = rings.map(pct => {
    const radius = (pct / 100) * r
    const points = Array.from({ length: n }, (_, i) => polarToXY(startAngle + i * angleStep, radius))
    return points.map(p => p.join(',')).join(' ')
  })

  // Axis lines
  const axes = Array.from({ length: n }, (_, i) => {
    const [x, y] = polarToXY(startAngle + i * angleStep, r)
    return { x, y, label: dimensions[i].label || dimensions[i].key }
  })

  // Data polygons
  function makePolygon(getter) {
    return Array.from({ length: n }, (_, i) => {
      const val = Math.min(100, Math.max(0, getter(dimensions[i])))
      return polarToXY(startAngle + i * angleStep, (val / 100) * r)
    }).map(p => p.join(',')).join(' ')
  }

  const polyA = makePolygon(d => d.aVal)
  const polyB = makePolygon(d => d.bVal)

  return (
    <div className="radar-chart-wrapper">
      <svg viewBox="0 0 300 300" className="radar-chart-svg">
        {/* Grid rings */}
        {gridLines.map((pts, i) => (
          <polygon key={i} points={pts} fill="none" stroke="var(--color-border)" strokeWidth={0.5} opacity={0.5} />
        ))}
        {/* Axes */}
        {axes.map((a, i) => (
          <g key={i}>
            <line x1={cx} y1={cy} x2={a.x} y2={a.y} stroke="var(--color-border)" strokeWidth={0.5} opacity={0.3} />
            <text
              x={a.x + (a.x - cx) * 0.15}
              y={a.y + (a.y - cy) * 0.15}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="10"
              fill="var(--color-text-muted)"
            >
              {a.label}
            </text>
          </g>
        ))}
        {/* Data A */}
        <polygon points={polyA} fill="rgba(99, 102, 241, 0.15)" stroke="#6366f1" strokeWidth={2} />
        {/* Data B */}
        <polygon points={polyB} fill="rgba(34, 197, 94, 0.15)" stroke="#22c55e" strokeWidth={2} />
        {/* Data points */}
        {Array.from({ length: n }, (_, i) => {
          const [ax, ay] = polarToXY(startAngle + i * angleStep, (Math.min(100, dimensions[i].aVal) / 100) * r)
          const [bx, by] = polarToXY(startAngle + i * angleStep, (Math.min(100, dimensions[i].bVal) / 100) * r)
          return (
            <g key={i}>
              <circle cx={ax} cy={ay} r={3} fill="#6366f1" />
              <circle cx={bx} cy={by} r={3} fill="#22c55e" />
            </g>
          )
        })}
      </svg>
      <div className="radar-legend">
        <span className="radar-legend-item"><span className="radar-dot" style={{ background: '#6366f1' }} />{labelA}</span>
        <span className="radar-legend-item"><span className="radar-dot" style={{ background: '#22c55e' }} />{labelB}</span>
      </div>
    </div>
  )
}

export default function ComparePage() {
  const { user, token } = useAuth()
  const { t } = useLanguage()
  const { addToast } = useToast()
  const history = getHistory(user)
  const [idxA, setIdxA] = useState(0)
  const [idxB, setIdxB] = useState(Math.min(1, history.length - 1))
  const [originalText, setOriginalText] = useState('')
  const [optimizedText, setOptimizedText] = useState('')
  const [diffSummary, setDiffSummary] = useState(null)
  const [diffLoading, setDiffLoading] = useState(false)

  const a = history[idxA] || null
  const b = history[idxB] || null

  const dimensions = useMemo(() => {
    if (!a || !b) return []
    // Prefer result-level scores when available, fallback to breakdown
    const scoreKeys = [
      { key: 'semantic', label: 'Semantic', field: 'semantic_score' },
      { key: 'keyword', label: 'Keyword', field: 'keyword_score' },
      { key: 'skill', label: 'Skill', field: 'skill_score' },
      { key: 'experience', label: 'Experience', field: 'experience_score' },
      { key: 'ats', label: 'ATS', field: 'ats_score' },
    ]
    const aRes = a.result || {}
    const bRes = b.result || {}
    const dims = scoreKeys
      .map(({ key, label, field }) => ({
        key,
        label,
        aVal: Math.round(aRes[field] ?? a.breakdown?.[key] ?? 0),
        bVal: Math.round(bRes[field] ?? b.breakdown?.[key] ?? 0),
      }))
      .filter(d => d.aVal > 0 || d.bVal > 0)

    // If no known keys had data, fallback to breakdown keys
    if (dims.length === 0) {
      const aBreak = a.breakdown || {}
      const bBreak = b.breakdown || {}
      const allKeys = [...new Set([...Object.keys(aBreak), ...Object.keys(bBreak)])]
      return allKeys.map((key) => ({
        key,
        label: key,
        aVal: Math.round(aBreak[key] || 0),
        bVal: Math.round(bBreak[key] || 0),
      }))
    }
    return dims
  }, [a, b])

  async function handleTextDiff() {
    if (!originalText.trim() || !optimizedText.trim()) {
      addToast('Paste both CV versions first', 'warning')
      return
    }
    setDiffLoading(true)
    try {
      const res = await diffCvText(token, originalText, optimizedText)
      setDiffSummary(res.change_summary || res)
    } catch (err) {
      addToast(err?.message || 'CV diff failed', 'error')
    } finally {
      setDiffLoading(false)
    }
  }

  const textDiffCard = (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{ marginBottom: '1.25rem' }}
    >
      <h3 style={{ marginBottom: '0.75rem' }}>Original vs Optimized CV Diff</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
        <textarea
          className="job-desc-input"
          rows={8}
          value={originalText}
          onChange={(e) => setOriginalText(e.target.value)}
          placeholder="Paste original CV text"
        />
        <textarea
          className="job-desc-input"
          rows={8}
          value={optimizedText}
          onChange={(e) => setOptimizedText(e.target.value)}
          placeholder="Paste optimized CV text"
        />
      </div>
      <button className="btn-primary btn-sm" onClick={handleTextDiff} disabled={diffLoading} style={{ marginTop: '0.9rem' }}>
        <GitCompare size={14} /> {diffLoading ? 'Comparing...' : 'Compare Text'}
      </button>
      {diffSummary && (
        <div className="compare-table" style={{ marginTop: '1rem' }}>
          <div className="compare-table-row">
            <span>Lines</span>
            <span>{diffSummary.original_lines || 0}</span>
            <span>{diffSummary.optimized_lines || 0}</span>
            <span>{(diffSummary.added_line_count || 0) - (diffSummary.removed_line_count || 0)}</span>
          </div>
          {(diffSummary.summary || []).map((item, index) => (
            <div className="compare-table-row" key={index}>
              <span>{item}</span>
              <span />
              <span />
              <span />
            </div>
          ))}
          {(diffSummary.added_examples || []).slice(0, 4).map((item, index) => (
            <div className="compare-table-row" key={`add-${index}`}>
              <span className="positive">+ {item}</span>
              <span />
              <span />
              <span />
            </div>
          ))}
          {(diffSummary.removed_examples || []).slice(0, 4).map((item, index) => (
            <div className="compare-table-row" key={`remove-${index}`}>
              <span className="negative">- {item}</span>
              <span />
              <span />
              <span />
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )

  if (history.length < 2) {
    return (
      <div className="app-layout">
        <Navbar />
        <main className="main-content" id="main-content">
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
            <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <GitCompare size={24} style={{ color: 'var(--color-accent)' }} />
              {t('compare.title')}
            </h1>
            <p className="text-muted" style={{ marginBottom: '1.5rem' }}>{t('compare.subtitle')}</p>
          </motion.div>
          {textDiffCard}
          <div className="db-empty-state" style={{ marginTop: '3rem' }}>
            <motion.span className="db-empty-icon" animate={{ y: [0, -8, 0] }} transition={{ duration: 3.5, repeat: Infinity }}>
              📊
            </motion.span>
            <h3>{t('compare.need_two')}</h3>
            <p className="text-muted">{t('compare.need_two_desc')}</p>
          </div>
        </main>
      </div>
    )
  }

  const scoreA = Math.round(a?.score || 0)
  const scoreB = Math.round(b?.score || 0)
  const diff = scoreB - scoreA

  function DiffIcon({ val }) {
    if (val > 0) return <ArrowUp size={14} style={{ color: '#34d399' }} />
    if (val < 0) return <ArrowDown size={14} style={{ color: '#ef4444' }} />
    return <Minus size={14} style={{ color: 'var(--color-text-muted)' }} />
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <GitCompare size={24} style={{ color: 'var(--color-accent)' }} />
            {t('compare.title')}
          </h1>
          <p className="text-muted" style={{ marginBottom: '1.5rem' }}>{t('compare.subtitle')}</p>
        </motion.div>

        {textDiffCard}

        {/* Selectors */}
        <div className="compare-selectors">
          <div className="compare-select-wrap">
            <label>{t('compare.cv_a')}</label>
            <select className="job-desc-input" value={idxA} onChange={(e) => setIdxA(Number(e.target.value))}>
              {history.map((h, i) => (
                <option key={i} value={i}>
                  {h.jobTitle || h.fileName || `#${i + 1}`} — {Math.round(h.score || 0)}%
                </option>
              ))}
            </select>
          </div>
          <ArrowRight size={20} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          <div className="compare-select-wrap">
            <label>{t('compare.cv_b')}</label>
            <select className="job-desc-input" value={idxB} onChange={(e) => setIdxB(Number(e.target.value))}>
              {history.map((h, i) => (
                <option key={i} value={i}>
                  {h.jobTitle || h.fileName || `#${i + 1}`} — {Math.round(h.score || 0)}%
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Score comparison */}
        <motion.div
          className="compare-scores"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.35 }}
        >
          <div className="compare-score-col">
            <ScoreCircle score={scoreA} size={90} />
            <span className="compare-score-label">{a?.jobTitle || a?.fileName || t('compare.cv_a')}</span>
          </div>
          <div className="compare-diff">
            <DiffIcon val={diff} />
            <span className={`compare-diff-value ${diff > 0 ? 'positive' : diff < 0 ? 'negative' : ''}`}>
              {diff > 0 ? '+' : ''}{diff}%
            </span>
          </div>
          <div className="compare-score-col">
            <ScoreCircle score={scoreB} size={90} />
            <span className="compare-score-label">{b?.jobTitle || b?.fileName || t('compare.cv_b')}</span>
          </div>
        </motion.div>

        {/* Radar Chart */}
        {dimensions.length >= 3 && (
          <motion.div
            className="card compare-radar-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            <h3 style={{ marginBottom: '1rem' }}>Radar Karşılaştırma</h3>
            <RadarChart dimensions={dimensions} labelA={a?.jobTitle || t('compare.cv_a')} labelB={b?.jobTitle || t('compare.cv_b')} />
          </motion.div>
        )}

        {/* Dimension comparison */}
        {dimensions.length > 0 && (
          <motion.div
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.4 }}
          >
            <h3 style={{ marginBottom: '1rem' }}>{t('compare.breakdown')}</h3>
            <div className="compare-table">
              <div className="compare-table-header">
                <span>{t('compare.dimension')}</span>
                <span>{t('compare.cv_a')}</span>
                <span>{t('compare.cv_b')}</span>
                <span>{t('compare.diff')}</span>
              </div>
              {dimensions.map((d) => {
                const dv = d.bVal - d.aVal
                return (
                  <div className="compare-table-row" key={d.key}>
                    <span style={{ textTransform: 'capitalize' }}>{d.label || d.key}</span>
                    <span>{d.aVal}%</span>
                    <span>{d.bVal}%</span>
                    <span className={dv > 0 ? 'positive' : dv < 0 ? 'negative' : ''}>
                      <DiffIcon val={dv} /> {dv > 0 ? '+' : ''}{dv}
                    </span>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </main>
    </div>
  )
}
