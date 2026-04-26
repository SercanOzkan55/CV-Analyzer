import { describe, it, expect } from 'vitest'
import {
  getScoreColor,
  getScoreGradient,
  getScoreGlow,
  getGrade,
} from '../utils/scoreColors'

describe('getScoreColor', () => {
  it('returns green for scores >= 75', () => {
    expect(getScoreColor(75)).toBe('#22c55e')
    expect(getScoreColor(100)).toBe('#22c55e')
  })

  it('returns yellow for scores 50-74', () => {
    expect(getScoreColor(50)).toBe('#eab308')
    expect(getScoreColor(74)).toBe('#eab308')
  })

  it('returns red for scores < 50', () => {
    expect(getScoreColor(0)).toBe('#ef4444')
    expect(getScoreColor(49)).toBe('#ef4444')
  })
})

describe('getScoreGradient', () => {
  it('returns a CSS linear-gradient string', () => {
    const result = getScoreGradient(80)
    expect(result).toContain('linear-gradient')
    expect(result).toContain('#22c55e')
  })
})

describe('getScoreGlow', () => {
  it('returns green glow for high scores', () => {
    expect(getScoreGlow(80)).toContain('34, 197, 94')
  })

  it('returns yellow glow for medium scores', () => {
    expect(getScoreGlow(60)).toContain('234, 179, 8')
  })

  it('returns red glow for low scores', () => {
    expect(getScoreGlow(30)).toContain('239, 68, 68')
  })
})

describe('getGrade', () => {
  it('returns A+ for 90+', () => {
    expect(getGrade(95)).toEqual({ label: 'A+', color: '#22c55e' })
  })

  it('returns A for 80-89', () => {
    expect(getGrade(85)).toEqual({ label: 'A', color: '#22c55e' })
  })

  it('returns B for 70-79', () => {
    expect(getGrade(72)).toEqual({ label: 'B', color: '#4ade80' })
  })

  it('returns C for 60-69', () => {
    expect(getGrade(65)).toEqual({ label: 'C', color: '#eab308' })
  })

  it('returns D for 50-59', () => {
    expect(getGrade(55)).toEqual({ label: 'D', color: '#f97316' })
  })

  it('returns F for <50', () => {
    expect(getGrade(30)).toEqual({ label: 'F', color: '#ef4444' })
  })
})
