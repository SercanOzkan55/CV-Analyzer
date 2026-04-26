import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Lightbulb } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchInsights } from '../api'

export default function InsightsPanel() {
  const { token } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    fetchInsights(token)
      .then(res => { if (!cancelled) setData(res) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  if (loading || !data?.insights?.length) return null

  const typeColors = {
    positive: '#22c55e',
    warning: '#eab308',
    tip: '#6366f1',
    achievement: '#f59e0b',
  }

  return (
    <div className="insights-panel">
      {data.insights.map((insight, i) => (
        <motion.div
          key={i}
          className="insight-item"
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08 }}
          style={{ borderLeftColor: typeColors[insight.type] || 'var(--color-border)' }}
        >
          <span className="insight-icon">{insight.icon}</span>
          <span className="insight-text">{insight.text}</span>
        </motion.div>
      ))}
    </div>
  )
}
