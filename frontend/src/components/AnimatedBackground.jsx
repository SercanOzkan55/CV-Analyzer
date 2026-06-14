import React, { useEffect, useRef } from 'react'

export default function AnimatedBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const ctx = canvas.getContext('2d')
    let animId
    let tick = 0

    function resize() {
      canvas.width = document.documentElement.clientWidth || window.innerWidth
      canvas.height = document.documentElement.clientHeight || window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    function drawGrid() {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const major = 96
      const minor = 24
      const offset = reducedMotion ? 0 : tick % major
      const isLight = document.documentElement.getAttribute('data-theme') === 'light'
      const minorColor = isLight ? 'rgba(22, 72, 99, 0.055)' : 'rgba(148, 196, 196, 0.05)'
      const majorColor = isLight ? 'rgba(22, 72, 99, 0.12)' : 'rgba(148, 196, 196, 0.1)'

      ctx.lineWidth = 1
      for (let x = -offset; x < canvas.width + major; x += minor) {
        ctx.beginPath()
        ctx.strokeStyle = Math.round((x + offset) / minor) % 4 === 0 ? majorColor : minorColor
        ctx.moveTo(x, 0)
        ctx.lineTo(x, canvas.height)
        ctx.stroke()
      }
      for (let y = -offset; y < canvas.height + major; y += minor) {
        ctx.beginPath()
        ctx.strokeStyle = Math.round((y + offset) / minor) % 4 === 0 ? majorColor : minorColor
        ctx.moveTo(0, y)
        ctx.lineTo(canvas.width, y)
        ctx.stroke()
      }

      ctx.strokeStyle = isLight ? 'rgba(11, 95, 105, 0.16)' : 'rgba(35, 214, 196, 0.13)'
      ctx.lineWidth = 1.4
      ctx.beginPath()
      ctx.moveTo(canvas.width * 0.08, canvas.height * 0.22)
      ctx.lineTo(canvas.width * 0.24, canvas.height * 0.22)
      ctx.lineTo(canvas.width * 0.24, canvas.height * 0.36)
      ctx.moveTo(canvas.width * 0.76, canvas.height * 0.68)
      ctx.lineTo(canvas.width * 0.92, canvas.height * 0.68)
      ctx.lineTo(canvas.width * 0.92, canvas.height * 0.54)
      ctx.stroke()
    }

    function animate() {
      drawGrid()
      tick += 0.12
      if (!reducedMotion) animId = requestAnimationFrame(animate)
    }

    if (reducedMotion) drawGrid()
    else animate()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <>
      <div className="animated-bg-material" aria-hidden="true" />
      <canvas
        ref={canvasRef}
        className="animated-bg-canvas"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          opacity: 0.62,
          transition: 'opacity 0.4s ease',
        }}
      />
    </>
  )
}
