import React from 'react'

export default function SkeletonLoader({ lines = 3, circle = false }) {
  return (
    <div className="skeleton-wrapper">
      {circle && <div className="skeleton skeleton-circle" />}
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton skeleton-line"
          style={{ width: `${100 - i * 15}%` }}
        />
      ))}
    </div>
  )
}
