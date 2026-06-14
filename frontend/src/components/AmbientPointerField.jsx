import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

const MAX_SPARKS = 18

export default function AmbientPointerField() {
  const prefersReducedMotion = useReducedMotion()
  const [sparks, setSparks] = useState([])
  const draggingRef = useRef(false)
  const lastSpawnRef = useRef(0)
  const idRef = useRef(0)
  const cleanupTimersRef = useRef([])

  const spawnSpark = useCallback((x, y, intensity = 1) => {
    const id = idRef.current + 1
    idRef.current = id

    const spark = {
      id,
      x,
      y,
      size: Math.round(7 + Math.random() * 13 * intensity),
      driftX: Math.round((Math.random() - 0.5) * 76 * intensity),
      driftY: Math.round(-20 - Math.random() * 70 * intensity),
      hue: Math.random() > 0.55 ? 'warm' : 'cool',
    }

    setSparks((current) => [spark, ...current].slice(0, MAX_SPARKS))

    const timer = window.setTimeout(() => {
      setSparks((current) => current.filter((item) => item.id !== id))
    }, 780)
    cleanupTimersRef.current.push(timer)
  }, [])

  useEffect(() => {
    if (prefersReducedMotion || typeof window === 'undefined') return undefined

    function handlePointerDown(event) {
      draggingRef.current = true
      spawnSpark(event.clientX, event.clientY, 1.25)
    }

    function handlePointerUp() {
      draggingRef.current = false
    }

    function handlePointerMove(event) {
      const now = window.performance.now()
      const isDragging = draggingRef.current || event.buttons > 0
      const cadence = isDragging ? 38 : 130

      if (now - lastSpawnRef.current < cadence) return
      lastSpawnRef.current = now

      if (isDragging) {
        spawnSpark(event.clientX, event.clientY, 1.15)
      } else if (event.target === document.body || event.target === document.documentElement) {
        spawnSpark(event.clientX, event.clientY, 0.45)
      }
    }

    window.addEventListener('pointerdown', handlePointerDown, { passive: true })
    window.addEventListener('pointerup', handlePointerUp, { passive: true })
    window.addEventListener('pointercancel', handlePointerUp, { passive: true })
    window.addEventListener('pointermove', handlePointerMove, { passive: true })

    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerUp)
      window.removeEventListener('pointermove', handlePointerMove)
      cleanupTimersRef.current.forEach((timer) => window.clearTimeout(timer))
      cleanupTimersRef.current = []
    }
  }, [prefersReducedMotion, spawnSpark])

  if (prefersReducedMotion) return null

  return (
    <div className="ambient-pointer-field" aria-hidden="true">
      {sparks.map((spark) => (
        <span
          key={spark.id}
          className={`ambient-spark ambient-spark-${spark.hue}`}
          style={{
            left: spark.x,
            top: spark.y,
            width: spark.size,
            height: spark.size,
            '--spark-drift-x': `${spark.driftX}px`,
            '--spark-drift-y': `${spark.driftY}px`,
          }}
        />
      ))}
    </div>
  )
}
