import React from 'react'

function getColor(value) {
  if (value >= 75) return '#22c55e'
  if (value >= 50) return '#eab308'
  return '#ef4444'
}

export default function ScoreBars({ items }) {
  return (
    <div className="score-bars">
      {items.map((item) => (
        <div key={item.label} className="score-bar-row">
          <span className="bar-label">{item.label}</span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${Math.min(item.value || 0, 100)}%`,
                background: getColor(item.value || 0),
              }}
            />
          </div>
          <span className="bar-value">{Math.round(item.value || 0)}%</span>
        </div>
      ))}
    </div>
  )
}
