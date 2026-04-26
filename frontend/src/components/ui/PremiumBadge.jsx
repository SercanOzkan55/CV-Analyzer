import React from 'react'
import { motion } from 'framer-motion'
import { Crown, Lock, Sparkles } from 'lucide-react'

export default function PremiumBadge({ plan = 'free', size = 'md' }) {
  const isPremium = plan === 'pro' || plan === 'enterprise' || plan === 'admin'
  const sizeClass = size === 'sm' ? 'premium-badge-sm' : ''

  return (
    <motion.span
      className={`premium-badge ${isPremium ? 'premium-badge-active' : ''} ${sizeClass}`}
      whileHover={{ scale: 1.05 }}
      transition={{ duration: 0.2 }}
    >
      {isPremium ? <Sparkles size={size === 'sm' ? 12 : 14} /> : <Lock size={size === 'sm' ? 12 : 14} />}
      {isPremium ? 'Premium' : 'Free'}
    </motion.span>
  )
}
