import React from 'react'

export default function ScoreCircle({ score, size = 140, label }) {
  const r = (size - 16) / 2
  const circumference = 2 * Math.PI * r
  const offset = circumference - (Math.min(score, 100) / 100) * circumference

  function getColor(s) {
    if (s >= 75) return '#22c55e'
    if (s >= 50) return '#eab308'
    return '#ef4444'
  }

  function getGlow(s) {
    if (s >= 75) return 'rgba(34, 197, 94, 0.3)'
    if (s >= 50) return 'rgba(234, 179, 8, 0.3)'
    return 'rgba(239, 68, 68, 0.3)'
  }

  const color = getColor(score)
  const glow = getGlow(score)

  return (
    <div className="score-circle-wrapper" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ filter: `drop-shadow(0 0 12px ${glow})` }}>
        <defs>
          <linearGradient id={`scoreGrad-${score}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.6" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="8"
          opacity="0.5"
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={`url(#scoreGrad-${score})`}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.25, 0.8, 0.25, 1)' }}
        />
      </svg>
      <div className="score-circle-text">
        <span className="score-number" style={{ color }}>{Math.round(score)}</span>
        {label && <span className="score-label">{label}</span>}
      </div>
    </div>
  )
}
