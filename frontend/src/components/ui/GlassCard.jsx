import React from 'react'
import { motion } from 'framer-motion'

export default function GlassCard({
  children,
  className = '',
  hover = true,
  glow = false,
  delay = 0,
  ...props
}) {
  return (
    <motion.div
      className={`glass-card ${glow ? 'glass-card-glow' : ''} ${className}`}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.5, delay, ease: [0.25, 0.1, 0.25, 1] }}
      whileHover={hover ? { y: -2, transition: { duration: 0.15 } } : undefined}
      {...props}
    >
      {children}
    </motion.div>
  )
}
