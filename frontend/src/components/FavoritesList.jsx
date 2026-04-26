import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Star, ExternalLink, Trash2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchFavorites, toggleFavorite } from '../api'

export default function FavoritesList() {
  const { token } = useAuth()
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    setLoading(true)
    fetchFavorites(token)
      .then(res => { if (!cancelled) setFavorites(res?.favorites || []) })
      .catch(() => { if (!cancelled) setFavorites([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  async function handleRemove(analysisId) {
    try {
      await toggleFavorite(token, analysisId)
      setFavorites(prev => prev.filter(f => f.analysis_id !== analysisId))
    } catch { /* ignore */ }
  }

  if (loading) {
    return (
      <div className="favorites-skeleton">
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton skeleton-line" style={{ height: 48, marginBottom: 8 }} />
        ))}
      </div>
    )
  }

  if (!favorites.length) {
    return (
      <div className="favorites-empty">
        <Star size={24} style={{ opacity: 0.3 }} />
        <p>Henüz favori analiz yok</p>
        <span className="text-muted text-xs">Geçmiş sayfasından analizleri favorilere ekleyebilirsiniz</span>
      </div>
    )
  }

  return (
    <div className="favorites-list">
      <AnimatePresence>
        {favorites.map((fav, i) => {
          const a = fav.analysis
          const score = a?.similarity_score ?? 0
          return (
            <motion.div
              key={fav.id}
              className="favorites-item"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 12, height: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <div className="favorites-item-left">
                <Star size={14} fill="currentColor" className="favorites-star" />
                <div>
                  <span className="favorites-score" style={{ color: score >= 75 ? '#22c55e' : score >= 50 ? '#eab308' : '#ef4444' }}>
                    {Math.round(score)}%
                  </span>
                  <span className="favorites-title">
                    {a?.job_title || a?.interpretation?.slice(0, 40) || 'Analiz'}
                  </span>
                </div>
              </div>
              <div className="favorites-item-actions">
                <span className="text-muted text-xs">
                  {fav.created_at ? new Date(fav.created_at).toLocaleDateString('tr-TR') : ''}
                </span>
                <button
                  className="btn-icon btn-danger-icon"
                  onClick={() => handleRemove(fav.analysis_id)}
                  title="Favoriden çıkar"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
