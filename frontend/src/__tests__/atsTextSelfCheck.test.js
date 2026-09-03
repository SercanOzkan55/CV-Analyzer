import { describe, expect, it } from 'vitest'
import { analyzeATSText, SAMPLE_ATS_TEXT } from '../utils/atsTextSelfCheck'

describe('ATS text self-check', () => {
  it('returns a neutral empty result without inventing findings', () => {
    expect(analyzeATSText('')).toEqual({
      score: 0,
      wordCount: 0,
      checks: [],
      recommendations: [],
      detectedSections: [],
      actionVerbCount: 0,
      metricCount: 0,
    })
  })

  it('recognises the disclosed fictional sample and explains every score component', () => {
    const result = analyzeATSText(SAMPLE_ATS_TEXT)

    expect(result.score).toBeGreaterThanOrEqual(70)
    expect(result.detectedSections).toEqual(expect.arrayContaining(['experience', 'education', 'skills', 'summary', 'projects']))
    expect(result.checks).toHaveLength(5)
    expect(result.checks.reduce((sum, check) => sum + check.maximum, 0)).toBe(100)
    expect(result.metricCount).toBeGreaterThan(0)
  })

  it('keeps a thin CV low and returns concrete recommendations', () => {
    const result = analyzeATSText('ÖZET\nÇalışkan bir adayım.')

    expect(result.score).toBeLessThan(55)
    expect(result.recommendations).toEqual(expect.arrayContaining([
      expect.stringContaining('Deneyim'),
      expect.stringContaining('İletişim'),
    ]))
  })
})
