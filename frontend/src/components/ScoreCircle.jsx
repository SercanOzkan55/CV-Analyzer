import React, { useEffect, useState } from 'react'
import CircularProgress from './CircularProgress'
import { getScoreColor, getScoreGlow } from '../utils/scoreColors'

export default function ScoreCircle({ score, size = 140, label }) {
  const [animated, setAnimated] = useState(false)
  const safeScore = Math.min(100, Math.max(0, Number(score) || 0))
  const color = getScoreColor(safeScore)
  const glow = getScoreGlow(safeScore)
  const strokeWidth = Math.max(5, Math.round(size * 0.07))

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 60)
    return () => clearTimeout(timer)
  }, [])

  return (
    <CircularProgress
      value={animated ? safeScore : 0}
      size={size}
      strokeWidth={strokeWidth}
      color={color}
      trackColor="var(--score-ring-track, color-mix(in srgb, var(--color-border) 78%, transparent))"
      glow={glow}
      label={label ? `${label}: ${Math.round(safeScore)}%` : `${Math.round(safeScore)}%`}
      className="score-circle-wrapper"
    >
      <div className="score-circle-text">
        <span
          className="score-number"
          style={{
            color,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: size * 0.3,
          }}
        >
          {Math.round(safeScore)}
        </span>
        {label && <span className="score-label" style={{ fontSize: size * 0.1 }}>{label}</span>}
      </div>
    </CircularProgress>
  )
}
