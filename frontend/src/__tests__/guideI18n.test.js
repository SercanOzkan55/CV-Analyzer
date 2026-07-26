import { describe, expect, it } from 'vitest'
import { getGuideUi, getLocalizedSeoPage, SUPPORTED_GUIDE_LANGUAGES } from '../content/guideI18n'
import { SEO_PAGES } from '../content/seoPages'

describe('guide localization', () => {
  it('provides localized guide chrome for every supported application language', () => {
    expect(SUPPORTED_GUIDE_LANGUAGES).toEqual(['en', 'tr', 'fr', 'de', 'es', 'ar'])

    SUPPORTED_GUIDE_LANGUAGES.forEach((lang) => {
      const ui = getGuideUi(lang)
      expect(ui.hubTitle).toBeTruthy()
      expect(ui.categories).toHaveLength(4)
      expect(ui.locale).toBeTruthy()
    })
  })

  it('uses complete English article copy outside Turkish and marks translated-shell fallbacks', () => {
    const sourcePage = SEO_PAGES.find((page) => page.slug === 'mulakat-hazirligi')
    const englishPage = getLocalizedSeoPage(sourcePage, 'en')
    const frenchPage = getLocalizedSeoPage(sourcePage, 'fr')

    expect(englishPage.title).toContain('Job Interview')
    expect(englishPage.sections.length).toBeGreaterThanOrEqual(3)
    expect(englishPage.faq.length).toBeGreaterThanOrEqual(3)
    expect(englishPage.isFallback).toBe(false)
    expect(frenchPage.contentLanguage).toBe('en')
    expect(frenchPage.isFallback).toBe(true)
  })

  it('preserves the original Turkish article', () => {
    const sourcePage = SEO_PAGES[0]
    const localizedPage = getLocalizedSeoPage(sourcePage, 'tr')

    expect(localizedPage.title).toBe(sourcePage.title)
    expect(localizedPage.sections).toEqual(sourcePage.sections)
    expect(localizedPage.contentLanguage).toBe('tr')
  })
})
