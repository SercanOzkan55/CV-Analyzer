import React from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Loader2 } from 'lucide-react'

export default function GradientButton({
  children,
  onClick,
  href,
  variant = 'primary',
  size = 'md',
  icon,
  arrow = false,
  loading = false,
  disabled = false,
  className = '',
  ...props
}) {
  const sizeClass = size === 'lg' ? 'btn-lg' : size === 'sm' ? 'btn-sm' : ''
  const variantClass = variant === 'outline' ? 'btn-outline' : variant === 'ghost' ? 'btn-ghost' : 'btn-primary'
  const cls = `${variantClass} ${sizeClass} ${className}`.trim()

  const content = (
    <>
      {loading && <Loader2 size={16} className="spin-icon" />}
      {!loading && icon}
      {children}
      {!loading && arrow && <ArrowRight size={16} />}
    </>
  )

  if (href) {
    return (
      <motion.a
        href={href}
        className={cls}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        {...props}
      >
        {content}
      </motion.a>
    )
  }

  return (
    <motion.button
      className={cls}
      onClick={onClick}
      disabled={disabled || loading}
      whileHover={!disabled ? { scale: 1.02 } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      {...props}
    >
      {content}
    </motion.button>
  )
}
