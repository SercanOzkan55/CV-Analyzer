import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'

export default function LoadingScreen({ text = 'CV Analyzer' }) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      className="loading-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: shouldReduceMotion ? 0 : 0.2 } }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.2 }}
      role="status"
      aria-live="polite"
    >
      <div className="ls-depth-field" aria-hidden="true">
        <span className="ls-depth-line ls-depth-line-a" />
        <span className="ls-depth-line ls-depth-line-b" />
        <span className="ls-depth-line ls-depth-line-c" />
      </div>

      <div className="ls-content">
        <div className="ls-status-copy">
          <span className="ls-kicker">Workspace gateway</span>
          <strong>{text}</strong>
        </div>

        <div className="ls-ring-wrapper" aria-hidden="true">
          <svg className="ls-ring" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="40" cy="40" r="34" stroke="var(--color-border)" strokeWidth="3" />
            <motion.circle
              cx="40"
              cy="40"
              r="34"
              stroke="url(#ls-gradient)"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="54 160"
              animate={shouldReduceMotion ? undefined : { rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '40px 40px' }}
            />
            <defs>
              <linearGradient id="ls-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="var(--color-accent)" />
                <stop offset="100%" stopColor="var(--color-accent-pink)" />
              </linearGradient>
            </defs>
          </svg>

          <motion.div
            className="ls-logo-icon"
            animate={shouldReduceMotion ? undefined : { scale: [1, 1.06, 1], opacity: [0.82, 1, 0.82] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            CV
          </motion.div>
        </div>

        <motion.span
          className="ls-text"
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: shouldReduceMotion ? 0 : 0.12, duration: shouldReduceMotion ? 0 : 0.3 }}
        >
          Preparing secure session
        </motion.span>

        <div className="ls-dots" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="ls-dot"
              animate={shouldReduceMotion ? undefined : { opacity: [0.35, 1, 0.35], y: [0, -4, 0] }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.18,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  )
}
