import React from 'react'

export default function GlowBadge({ children, color = 'accent', className = '' }) {
  return (
    <span className={`glow-badge glow-badge-${color} ${className}`}>
      {children}
    </span>
  )
}
