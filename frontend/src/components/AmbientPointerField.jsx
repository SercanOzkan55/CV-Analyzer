import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

const MAX_SPARKS = 34

export default function AmbientPointerField() {
  const prefersReducedMotion = useReducedMotion()
  const [sparks, setSparks] = useState([])
  const draggingRef = useRef(false)
  const lastSpawnRef = useRef(0)
  const lastPointRef = useRef(null)
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
      const previous = lastPointRef.current
      const distance = previous
        ? Math.hypot(event.clientX - previous.x, event.clientY - previous.y)
        : 0
      const cadence = isDragging ? 28 : distance > 26 ? 28 : 58

      lastPointRef.current = { x: event.clientX, y: event.clientY }

      if (now - lastSpawnRef.current < cadence) return
      if (!isDragging && distance < 4) return
      lastSpawnRef.current = now

      const movementIntensity = Math.min(1.28, Math.max(0.72, distance / 34))
      spawnSpark(event.clientX, event.clientY, isDragging ? 1.25 : movementIntensity)

      if (!isDragging && distance > 22) {
        const echoX = previous ? event.clientX - (event.clientX - previous.x) * 0.34 : event.clientX
        const echoY = previous ? event.clientY - (event.clientY - previous.y) * 0.34 : event.clientY
        spawnSpark(echoX, echoY, movementIntensity * 0.72)
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
