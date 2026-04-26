import React from 'react'
import { motion } from 'framer-motion'

export default function SectionTitle({ title, subtitle, delay = 0, align = 'center' }) {
  return (
    <div style={{ textAlign: align, marginBottom: subtitle ? 0 : 16 }}>
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay }}
      >
        {title}
      </motion.h2>
      {subtitle && (
        <motion.p
          className="section-subtitle"
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: delay + 0.1 }}
        >
          {subtitle}
        </motion.p>
      )}
    </div>
  )
}
