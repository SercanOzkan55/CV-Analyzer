import React from 'react'
import { motion } from 'framer-motion'

export default function GlassPanel({ children, className = '', delay = 0, ...props }) {
  return (
    <motion.div
      className={`glass-panel ${className}`}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 0.5, delay, ease: [0.25, 0.1, 0.25, 1] }}
      {...props}
    >
      {children}
    </motion.div>
  )
}
