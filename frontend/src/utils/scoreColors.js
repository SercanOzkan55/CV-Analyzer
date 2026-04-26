/** Shared score → color mapping used across all score components. */

export function getScoreColor(value) {
  if (value >= 75) return '#22c55e'
  if (value >= 50) return '#eab308'
  return '#ef4444'
}

export function getScoreGradient(value) {
  const c = getScoreColor(value)
  return `linear-gradient(90deg, ${c}99, ${c})`
}

export function getScoreGlow(value) {
  if (value >= 75) return 'rgba(34, 197, 94, 0.35)'
  if (value >= 50) return 'rgba(234, 179, 8, 0.35)'
  return 'rgba(239, 68, 68, 0.35)'
}

export function getGrade(score) {
  if (score >= 90) return { label: 'A+', color: '#22c55e' }
  if (score >= 80) return { label: 'A', color: '#22c55e' }
  if (score >= 70) return { label: 'B', color: '#4ade80' }
  if (score >= 60) return { label: 'C', color: '#eab308' }
  if (score >= 50) return { label: 'D', color: '#f97316' }
  return { label: 'F', color: '#ef4444' }
}
