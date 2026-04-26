import React from 'react'
import { motion } from 'framer-motion'

export default function LoadingScreen({ text = 'CV Analyzer' }) {
  return (
    <motion.div
      className="loading-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.3 } }}
      transition={{ duration: 0.2 }}
    >
      {/* Floating orbs */}
      <div className="ls-orb ls-orb-1" />
      <div className="ls-orb ls-orb-2" />
      <div className="ls-orb ls-orb-3" />

      <div className="ls-content">
        {/* Animated ring */}
        <div className="ls-ring-wrapper">
          <svg className="ls-ring" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Track ring */}
            <circle cx="40" cy="40" r="34" stroke="rgba(192,132,252,0.12)" strokeWidth="3" />
            {/* Spinning gradient arc */}
            <motion.circle
              cx="40"
              cy="40"
              r="34"
              stroke="url(#ls-gradient)"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="54 160"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '40px 40px' }}
            />
            <defs>
              <linearGradient id="ls-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#a855f7" />
                <stop offset="50%" stopColor="#a78bfa" />
                <stop offset="100%" stopColor="#f472b6" />
              </linearGradient>
            </defs>
          </svg>

          {/* Logo icon in center */}
          <motion.div
            className="ls-logo-icon"
            animate={{ scale: [1, 1.08, 1], opacity: [0.8, 1, 0.8] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            ◆
          </motion.div>
        </div>

        {/* App name */}
        <motion.span
          className="ls-text"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          {text}
        </motion.span>

        {/* Pulsing dots */}
        <div className="ls-dots">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="ls-dot"
              animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.2,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  )
}
