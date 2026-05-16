import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { BarChart2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchUsageHistory } from '../api'

/**
 * Usage activity heatmap / bar chart for the dashboard.
 * Shows daily analysis counts for the last 30 days.
 */
export default function UsageChart() {
  const { token } = useAuth()
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    setLoading(true)
    fetchUsageHistory(token, 30)
      .then(res => { if (!cancelled) setData(res?.days || []) })
      .catch(() => { if (!cancelled) setData([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  // Build 30-day grid (fill missing days with 0)
  const days = []
  const now = new Date()
  const dataMap = {}
  for (const d of data) {
    dataMap[d.date] = d.count
  }
  for (let i = 29; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    const key = date.toISOString().split('T')[0]
    days.push({
      date: key,
      count: dataMap[key] || 0,
      label: date.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' }),
      weekday: date.toLocaleDateString('tr-TR', { weekday: 'short' }),
    })
  }

  const maxCount = Math.max(1, ...days.map(d => d.count))

  if (loading) {
    return (
      <div className="usage-chart-skeleton">
        <div className="skeleton skeleton-line" style={{ width: '100%', height: 120 }} />
      </div>
    )
  }

  return (
    <div className="usage-chart">
      <div className="usage-chart-bars">
        {days.map((d, i) => {
          const h = Math.max(4, (d.count / maxCount) * 100)
          const isToday = i === days.length - 1
          return (
            <div key={d.date} className="usage-chart-col" title={`${d.label}: ${d.count} analiz`}>
              <motion.div
                className={`usage-chart-bar ${isToday ? 'today' : ''} ${d.count === 0 ? 'empty' : ''}`}
                initial={{ height: 0 }}
                animate={{ height: `${h}%` }}
                transition={{ duration: 0.5, delay: i * 0.015, ease: [0.25, 0.8, 0.25, 1] }}
              />
              {d.count > 0 && (
                <span className="usage-chart-count">{d.count}</span>
              )}
            </div>
          )
        })}
      </div>
      <div className="usage-chart-labels">
        {days.map((d, i) => (
          (i % 5 === 0 || i === days.length - 1) && (
            <span key={d.date} className="usage-chart-label" style={{ left: `${(i / 29) * 100}%` }}>
              {d.label}
            </span>
          )
        ))}
      </div>
      <div className="usage-chart-summary">
        <span>Son 30 gün: <strong>{days.reduce((s, d) => s + d.count, 0)}</strong> analiz</span>
        <span>Bugün: <strong>{days[days.length - 1]?.count || 0}</strong></span>
      </div>
    </div>
  )
}
