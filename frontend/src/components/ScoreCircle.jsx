import React, { useState, useEffect } from 'react'
import { getScoreColor, getScoreGlow } from '../utils/scoreColors'

export default function ScoreCircle({ score, size = 140, label }) {
  const [animated, setAnimated] = useState(false)

  // Trigger animation after mount so CSS transition fires
  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 60)
    return () => clearTimeout(timer)
  }, [])

  const sw = Math.max(3, size * 0.06)
  const r = (size - sw * 2) / 2
  const circumference = 2 * Math.PI * r
  const offset = animated
    ? circumference - (Math.min(score, 100) / 100) * circumference
    : circumference

  const color = getScoreColor(score)
  const glow = getScoreGlow(score)

  return (
    <div className="score-circle-wrapper" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ filter: `drop-shadow(0 0 ${size * 0.1}px ${glow})` }}>
        <defs>
          <linearGradient id={`scoreGrad-${size}-${Math.round(score)}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.5" />
          </linearGradient>
        </defs>
        {/* Background track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={sw}
          opacity="0.5"
        />
        {/* Animated progress arc */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={`url(#scoreGrad-${size}-${Math.round(score)})`}
          strokeWidth={sw}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 1.4s cubic-bezier(0.25, 0.8, 0.25, 1)' }}
        />
      </svg>
      <div className="score-circle-text">
        <span className="score-number" style={{ color, fontFamily: "'JetBrains Mono', monospace", fontSize: size * 0.32 }}>
          {Math.round(score)}
        </span>
        {label && <span className="score-label" style={{ fontSize: size * 0.1 }}>{label}</span>}
      </div>
    </div>
  )
}
