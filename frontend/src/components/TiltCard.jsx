import { useRef } from 'react'
import {
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  useReducedMotion,
} from 'framer-motion'

/**
 * Subtle pointer-following 3D tilt wrapper. Transform-only (GPU-friendly),
 * reacts only on hover, and fully disables under prefers-reduced-motion.
 * A drop-in replacement for a card `motion.div` — reveal props
 * (initial/animate/whileInView/transition/className) pass straight through.
 *
 * @param {{ children: React.ReactNode, className?: string, max?: number }} props
 */
export default function TiltCard({ children, className = '', max = 6, style, ...rest }) {
  const prefersReduced = useReducedMotion()
  const ref = useRef(null)
  const px = useMotionValue(0)
  const py = useMotionValue(0)
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [max, -max]), {
    stiffness: 180,
    damping: 20,
    mass: 0.6,
  })
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-max, max]), {
    stiffness: 180,
    damping: 20,
    mass: 0.6,
  })

  function handleMove(e) {
    if (!ref.current) return
    const b = ref.current.getBoundingClientRect()
    px.set((e.clientX - b.left) / b.width - 0.5)
    py.set((e.clientY - b.top) / b.height - 0.5)
  }
  function reset() {
    px.set(0)
    py.set(0)
  }

  if (prefersReduced) {
    return (
      <motion.div className={className} style={style} {...rest}>
        {children}
      </motion.div>
    )
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      onPointerMove={handleMove}
      onPointerLeave={reset}
      onPointerCancel={reset}
      style={{ ...style, rotateX, rotateY, transformPerspective: 1000 }}
      {...rest}
    >
      {children}
    </motion.div>
  )
}
