import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Share2, Eye, Calendar } from 'lucide-react'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import { fetchSharedAnalysis } from '../api'

export default function SharedAnalysisPage() {
  const { shareToken } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Paylaşılan Analiz — CV Analyzer'
    fetchSharedAnalysis(shareToken)
      .then(setData)
      .catch(() => setError('Bu paylaşım linki bulunamadı veya süresi dolmuş.'))
      .finally(() => setLoading(false))
  }, [shareToken])

  if (loading) {
    return (
      <div className="shared-page">
        <div className="shared-loading">Yükleniyor...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="shared-page">
        <div className="shared-error">
          <Share2 size={40} style={{ opacity: 0.3 }} />
          <h2>Link Bulunamadı</h2>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  const result = data?.result || {}

  return (
    <div className="shared-page">
      <motion.div
        className="shared-container"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="shared-header">
          <Share2 size={20} style={{ color: 'var(--color-accent)' }} />
          <h1>CV Analiz Sonucu</h1>
          <div className="shared-meta">
            {data.created_at && (
              <span><Calendar size={14} /> {new Date(data.created_at).toLocaleDateString('tr-TR')}</span>
            )}
            <span><Eye size={14} /> {data.views} görüntülenme</span>
          </div>
        </div>

        <div className="shared-score-section">
          <ScoreCircle score={data.score || 0} size={130} label="Skor" />
          {data.interpretation && <p className="shared-interpretation">{data.interpretation}</p>}
          {data.job_title && <p className="text-muted">{data.job_title}</p>}
        </div>

        {(result.semantic_score || result.keyword_score) && (
          <div className="card shared-breakdown">
            <h3>Skor Dağılımı</h3>
            <ScoreBars items={[
              { label: 'Semantic', value: result.semantic_score },
              { label: 'Keyword', value: result.keyword_score },
              { label: 'Skill', value: result.skill_score },
              { label: 'Experience', value: result.experience_score },
              { label: 'ATS', value: result.ats_score },
            ].filter(i => i.value != null)} />
          </div>
        )}

        <div className="shared-footer">
          <p>CV Analyzer ile analiz edildi</p>
          <a href="/" className="btn-primary btn-sm">CV Analyzer'ı Dene</a>
        </div>
      </motion.div>
    </div>
  )
}
