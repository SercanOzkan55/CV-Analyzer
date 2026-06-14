import React, { useId } from 'react'

function clampPercent(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  return Math.min(100, Math.max(0, numeric))
}

export default function CircularProgress({
  value = 0,
  size = 96,
  strokeWidth = 8,
  color = 'var(--color-success)',
  trackColor = 'var(--color-border)',
  className = '',
  children,
  label,
  linecap = 'round',
  glow = false,
  style,
}) {
  const gradientId = useId()
  const progress = clampPercent(value)
  const dimension = Math.max(32, Number(size) || 96)
  const stroke = Math.max(1, Number(strokeWidth) || 8)
  const center = dimension / 2
  const radius = Math.max(1, (dimension - stroke) / 2)
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - progress / 100)
  const strokeLinecap = progress <= 0 || progress >= 99.95 ? 'butt' : linecap
  const ariaLabel = label || `${Math.round(progress)}%`

  return (
    <div
      className={`circular-progress ${className}`.trim()}
      style={{
        width: dimension,
        height: dimension,
        '--circular-progress-size': `${dimension}px`,
        '--circular-progress-color': color,
        '--circular-progress-track': trackColor,
        ...style,
      }}
      role="img"
      aria-label={ariaLabel}
    >
      <svg
        className="circular-progress-svg"
        width={dimension}
        height={dimension}
        viewBox={`0 0 ${dimension} ${dimension}`}
        focusable="false"
        aria-hidden="true"
        style={glow ? { filter: `drop-shadow(0 0 ${Math.max(8, dimension * 0.1)}px ${glow})` } : undefined}
      >
        <defs>
          <linearGradient id={gradientId} x1="20%" y1="4%" x2="86%" y2="96%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.72" />
          </linearGradient>
        </defs>
        <circle
          className="circular-progress-track"
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={stroke}
          vectorEffect="non-scaling-stroke"
        />
        <circle
          className="circular-progress-value"
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap={strokeLinecap}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={dashOffset}
          transform={`rotate(-90 ${center} ${center})`}
          pathLength={circumference}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {children && <div className="circular-progress-content">{children}</div>}
    </div>
  )
}
