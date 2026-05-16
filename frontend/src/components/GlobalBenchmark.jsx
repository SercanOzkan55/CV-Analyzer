import React from 'react'
import { motion } from 'framer-motion'
import { useLanguage } from '../i18n/LanguageContext'

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }

function getColor(delta) {
  if (delta > 0) return '#22c55e'
  if (delta < 0) return '#ef4444'
  return '#94a3b8'
}

function DeltaBadge({ value }) {
  const num = parseFloat(value)
  const color = getColor(num)
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 8,
      fontSize: '0.8rem',
      fontWeight: 700,
      fontFamily: "'JetBrains Mono', monospace",
      background: `${color}18`,
      color,
    }}>
      {value}
    </span>
  )
}

function PercentileBar({ percentile, label }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text)' }}>
          {label}
        </span>
        <span style={{
          fontSize: '0.85rem',
          fontWeight: 700,
          fontFamily: "'JetBrains Mono', monospace",
          color: percentile >= 75 ? '#22c55e' : percentile >= 50 ? '#eab308' : '#ef4444',
        }}>
          {percentile}%
        </span>
      </div>
      <div style={{
        height: 8,
        borderRadius: 4,
        background: 'var(--color-bg-tertiary, #1e1b2e)',
        overflow: 'hidden',
        position: 'relative',
      }}>
        <motion.div
          style={{
            height: '100%',
            borderRadius: 4,
            background: `linear-gradient(90deg, #a78bfa, ${percentile >= 75 ? '#22c55e' : percentile >= 50 ? '#eab308' : '#ef4444'})`,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${percentile}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
        {/* Marker lines at 25%, 50%, 75% */}
        {[25, 50, 75].map(p => (
          <div key={p} style={{
            position: 'absolute', top: 0, bottom: 0,
            left: `${p}%`,
            width: 1,
            background: 'var(--color-text-secondary, #666)',
            opacity: 0.3,
          }} />
        ))}
      </div>
    </div>
  )
}

export default function GlobalBenchmark({ data }) {
  const { t } = useLanguage()
  if (!data) return null

  const {
    user_score,
    global: g,
    profession: p,
    percentile,
    rank_label,
    rank_description,
  } = data

  return (
    <motion.div
      className="card"
      initial="hidden"
      whileInView="show"
      viewport={{ once: true }}
      variants={fadeUp}
      style={{ marginTop: 16 }}
    >
      <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: '1.3rem' }}>🌍</span>
        <h2 style={{ margin: 0 }}>{t('benchmark.global_title') || 'Global ATS Benchmark'}</h2>
      </div>

      {/* Rank Label */}
      <div style={{
        textAlign: 'center',
        padding: '16px 0 8px',
      }}>
        <span style={{
          display: 'inline-block',
          padding: '6px 20px',
          borderRadius: 20,
          fontSize: '0.95rem',
          fontWeight: 700,
          background: percentile >= 75 ? '#22c55e18' : percentile >= 50 ? '#eab30818' : '#ef444418',
          color: percentile >= 75 ? '#22c55e' : percentile >= 50 ? '#eab308' : '#ef4444',
          border: `1px solid ${percentile >= 75 ? '#22c55e33' : percentile >= 50 ? '#eab30833' : '#ef444433'}`,
        }}>
          {rank_label}
        </span>
        {rank_description && (
          <p style={{
            marginTop: 8,
            fontSize: '0.85rem',
            color: 'var(--color-text-secondary)',
          }}>
            {rank_description}
          </p>
        )}
      </div>

      {/* Comparison Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 12,
        marginTop: 12,
      }}>
        {/* Your Score */}
        <div style={{
          padding: '14px 16px',
          borderRadius: 12,
          background: 'var(--color-bg-secondary, #0f0d1a)',
          border: '1px solid var(--color-border, #2a2540)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            {t('benchmark.your_score') || 'Your Score'}
          </div>
          <div style={{
            fontSize: '1.8rem',
            fontWeight: 800,
            fontFamily: "'JetBrains Mono', monospace",
            color: 'var(--color-accent, #a78bfa)',
          }}>
            {Math.round(user_score)}
          </div>
        </div>

        {/* Global Avg */}
        <div style={{
          padding: '14px 16px',
          borderRadius: 12,
          background: 'var(--color-bg-secondary, #0f0d1a)',
          border: '1px solid var(--color-border, #2a2540)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            {t('benchmark.global_avg') || 'Global Avg'}
          </div>
          <div style={{
            fontSize: '1.8rem',
            fontWeight: 800,
            fontFamily: "'JetBrains Mono', monospace",
            color: 'var(--color-text)',
          }}>
            {g?.avg ? Math.round(g.avg) : '—'}
          </div>
          {g?.delta && <DeltaBadge value={g.delta} />}
        </div>

        {/* Profession Avg */}
        <div style={{
          padding: '14px 16px',
          borderRadius: 12,
          background: 'var(--color-bg-secondary, #0f0d1a)',
          border: '1px solid var(--color-border, #2a2540)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            {p?.display_name || p?.name || 'Profession'}
          </div>
          <div style={{
            fontSize: '1.8rem',
            fontWeight: 800,
            fontFamily: "'JetBrains Mono', monospace",
            color: 'var(--color-text)',
          }}>
            {p?.avg ? Math.round(p.avg) : '—'}
          </div>
          {p?.delta && <DeltaBadge value={p.delta} />}
        </div>
      </div>

      {/* Percentile Bar */}
      <PercentileBar
        percentile={percentile || 50}
        label={t('benchmark.percentile') || 'Percentile Rank'}
      />

      {/* Stats footer */}
      {g?.total_cvs > 0 && (
        <div style={{
          marginTop: 14,
          fontSize: '0.78rem',
          color: 'var(--color-text-secondary)',
          textAlign: 'center',
          opacity: 0.7,
        }}>
          {t('benchmark.based_on') || 'Based on'} {g.total_cvs.toLocaleString()} {t('benchmark.cvs_analyzed') || 'CVs analyzed globally'}
          {p?.total_cvs > 0 && ` · ${p.total_cvs.toLocaleString()} ${p.display_name || p.name}s`}
        </div>
      )}
    </motion.div>
  )
}
