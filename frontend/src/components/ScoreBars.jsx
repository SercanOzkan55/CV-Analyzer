import React, { useRef, useState, useEffect } from 'react'
import { getScoreColor as getColor, getScoreGradient as getGradient } from '../utils/scoreColors'

export default function ScoreBars({ items }) {
  const containerRef = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.15 }
    )
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="score-bars" ref={containerRef}>
      {items.map((item, i) => {
        const value = item.value || 0
        const color = getColor(value)
        return (
          <div key={item.label} className="score-bar-row">
            <span className="bar-label">{item.label}</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: visible ? `${Math.min(value, 100)}%` : '0%',
                  background: getGradient(value),
                  transition: `width 1s cubic-bezier(0.25, 0.8, 0.25, 1) ${i * 80}ms`,
                  boxShadow: visible ? `0 0 8px ${color}55` : 'none',
                }}
              />
            </div>
            <span
              className="bar-value"
              style={{ color, fontFamily: "'JetBrains Mono', monospace" }}
            >
              {Math.round(value)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
