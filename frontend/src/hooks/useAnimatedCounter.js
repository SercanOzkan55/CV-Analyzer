import { useState, useEffect, useRef } from 'react'

/**
 * Animates a numeric value from 0 to `target` over `duration` ms using easeOutCubic.
 */
export default function useAnimatedCounter(target, duration = 1200) {
  const [count, setCount] = useState(0)
  const rafRef = useRef(null)

  useEffect(() => {
    if (!target) { setCount(0); return }
    const startTime = Date.now()

    function tick() {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.round(target * eased))
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return count
}
