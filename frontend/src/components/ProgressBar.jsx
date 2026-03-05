import React from 'react'

export default function ProgressBar({ progress, label }) {
  return (
    <div className="progress-wrapper">
      {label && <span className="progress-label">{label}</span>}
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>
      <span className="progress-text">{Math.round(progress)}%</span>
    </div>
  )
}
