import React from 'react'
import { motion } from 'framer-motion'

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
}

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

const scaleIn = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1 },
}

const slideLeft = {
  hidden: { opacity: 0, x: -30 },
  visible: { opacity: 1, x: 0 },
}

const slideRight = {
  hidden: { opacity: 0, x: 30 },
  visible: { opacity: 1, x: 0 },
}

const variants = { fadeUp, fadeIn, scaleIn, slideLeft, slideRight }

export default function AnimatedContainer({
  children,
  variant = 'fadeUp',
  delay = 0,
  duration = 0.5,
  className,
  as = 'div',
  once = true,
  amount = 0.2,
  ...props
}) {
  const v = variants[variant] || fadeUp
  const Component = motion[as] || motion.div

  return (
    <Component
      variants={v}
      initial="hidden"
      whileInView="visible"
      viewport={{ once, amount }}
      transition={{ duration, delay, ease: [0.25, 0.1, 0.25, 1] }}
      className={className}
      {...props}
    >
      {children}
    </Component>
  )
}
