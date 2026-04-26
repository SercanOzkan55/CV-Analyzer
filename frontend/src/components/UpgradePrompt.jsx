import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, Crown, Zap, X } from 'lucide-react'
import { Link } from 'react-router-dom'

/**
 * Reusable upgrade prompt modal/banner.
 * Shows when free users try to access Pro features.
 */
export default function UpgradePrompt({ show, onClose, feature, description }) {
  if (!show) return null

  return (
    <AnimatePresence>
      <motion.div
        className="upgrade-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="upgrade-modal"
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="upgrade-close" onClick={onClose}>
            <X size={18} />
          </button>
          <div className="upgrade-icon-wrap">
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <Crown size={40} />
            </motion.div>
          </div>
          <h2>Pro'ya Yükselt</h2>
          <p className="upgrade-feature">
            <Lock size={14} />
            <strong>{feature}</strong> Pro özelliğidir
          </p>
          {description && <p className="upgrade-desc">{description}</p>}
          <div className="upgrade-benefits">
            <div className="upgrade-benefit"><Zap size={14} /> Sınırsız analiz</div>
            <div className="upgrade-benefit"><Zap size={14} /> CSV dışa aktarım</div>
            <div className="upgrade-benefit"><Zap size={14} /> Paylaşım linkleri</div>
            <div className="upgrade-benefit"><Zap size={14} /> Sınırsız şablon</div>
          </div>
          <Link to="/pricing" className="btn-primary upgrade-cta" onClick={onClose}>
            Planları Gör
          </Link>
          <button className="upgrade-skip" onClick={onClose}>
            Şimdilik devam et
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

/**
 * Inline feature lock badge — shows a lock icon with tooltip.
 */
export function FeatureLock({ label = 'Pro', small = false }) {
  return (
    <span className={`feature-lock-badge ${small ? 'small' : ''}`}>
      <Lock size={small ? 10 : 12} />
      {label}
    </span>
  )
}
