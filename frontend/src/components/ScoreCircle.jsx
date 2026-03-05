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

  const color = getColor(score)

  return (
    <div className="score-circle-wrapper" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="8"
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div className="score-circle-text">
        <span className="score-number" style={{ color }}>{Math.round(score)}</span>
        {label && <span className="score-label">{label}</span>}
      </div>
    </div>
  )
}
