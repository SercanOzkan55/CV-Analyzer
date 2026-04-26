import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Flame, Trophy, Calendar } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchUsageStreak } from '../api'

export default function StreakBadge() {
  const { token } = useAuth()
  const [streak, setStreak] = useState(null)

  useEffect(() => {
    if (!token) return
    fetchUsageStreak(token)
      .then(setStreak)
      .catch(() => {})
  }, [token])

  if (!streak || streak.total_active_days === 0) return null

  const { current_streak, longest_streak, total_active_days } = streak

  return (
    <div className="streak-badges">
      {current_streak > 0 && (
        <motion.div
          className={`streak-badge ${current_streak >= 7 ? 'hot' : ''}`}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', damping: 15 }}
          title={`${current_streak} günlük seri!`}
        >
          <Flame size={16} />
          <span className="streak-count">{current_streak}</span>
          <span className="streak-label">gün seri</span>
        </motion.div>
      )}
      {longest_streak > current_streak && (
        <div className="streak-badge muted" title={`En uzun seri: ${longest_streak} gün`}>
          <Trophy size={14} />
          <span className="streak-count">{longest_streak}</span>
          <span className="streak-label">rekor</span>
        </div>
      )}
      <div className="streak-badge muted" title={`Toplam ${total_active_days} aktif gün`}>
        <Calendar size={14} />
        <span className="streak-count">{total_active_days}</span>
        <span className="streak-label">aktif gün</span>
      </div>
    </div>
  )
}
