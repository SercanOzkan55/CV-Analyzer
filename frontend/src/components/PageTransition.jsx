import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'

const variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
}

export default function PageTransition({ children }) {
  const shouldReduceMotion = useReducedMotion()
  const activeVariants = shouldReduceMotion
    ? {
        initial: { opacity: 1 },
        animate: { opacity: 1 },
        exit: { opacity: 1 },
      }
    : variants

  return (
    <motion.div
      variants={activeVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: shouldReduceMotion ? 0 : 0.28, ease: [0.4, 0, 0.2, 1] }}
      style={{ minHeight: '100vh' }}
    >
      {children}
    </motion.div>
  )
}
