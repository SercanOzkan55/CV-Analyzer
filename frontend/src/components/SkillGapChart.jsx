import React, { useRef, useState, useEffect } from 'react'
import { getScoreColor } from '../utils/scoreColors'

const DEFAULT_COLOR_FN = getScoreColor

/**
 * Animated skill gap visualization — horizontal bars.
 * items: [{ label, found, total }] or [{ label, value, color }]
 */
export default function SkillGapChart({ items = [], colorFn = DEFAULT_COLOR_FN }) {
  const containerRef = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.1 }
    )
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  if (!items.length) return null

  return (
    <div className="skill-gap-chart" ref={containerRef}>
      {items.map((item, i) => {
        const value = item.value !== undefined
          ? item.value
          : item.total > 0 ? Math.round((item.found / item.total) * 100) : 0
        const color = item.color || colorFn(value)

        return (
          <div key={i} className="sgc-row">
            <span className="sgc-label">{item.label}</span>
            <div className="sgc-track">
              <div
                className="sgc-fill"
                style={{
                  width: visible ? `${Math.min(value, 100)}%` : '0%',
                  background: `linear-gradient(90deg, ${color}cc, ${color})`,
                  transition: `width 1s cubic-bezier(0.25, 0.8, 0.25, 1) ${i * 80}ms`,
                }}
              />
            </div>
            <span className="sgc-value" style={{ color }}>{value}%</span>
          </div>
        )
      })}
    </div>
  )
}
