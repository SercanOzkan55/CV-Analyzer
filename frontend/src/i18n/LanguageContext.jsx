import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import en from './en.json'
import tr from './tr.json'
import fr from './fr.json'
import ar from './ar.json'
import de from './de.json'
import es from './es.json'

const translations = { en, tr, fr, ar, de, es }

const RTL_LANGUAGES = ['ar']

// IP country code → language mapping (6 supported languages)
const COUNTRY_TO_LANG = {
  TR: 'tr',
  US: 'en', GB: 'en', AU: 'en', CA: 'en', NZ: 'en', IE: 'en',
  FR: 'fr', BE: 'fr', CH: 'fr', LU: 'fr', MC: 'fr',
  DE: 'de', AT: 'de', LI: 'de',
  ES: 'es', MX: 'es', AR: 'es', CO: 'es', CL: 'es', PE: 'es', VE: 'es', EC: 'es',
  SA: 'ar', EG: 'ar', AE: 'ar', MA: 'ar', DZ: 'ar', IQ: 'ar', JO: 'ar', KW: 'ar', QA: 'ar',
}

const LanguageContext = createContext(null)

// Browser language as instant fallback (only tr/en for initial render)
function getBrowserLang() {
  const bl = (navigator.language || '').slice(0, 2).toLowerCase()
  return bl === 'tr' ? 'tr' : 'en'
}

// Detect language by IP geolocation — supports all 6 languages
async function detectLanguageByIP() {
  const apis = [
    {
      url: 'https://ipwho.is/',
      parse: (d) => (d.country_code || '').toUpperCase(),
    },
    {
      url: 'https://ipapi.co/json/',
      parse: (d) => (d.country_code || '').toUpperCase(),
    },
  ]

  for (const api of apis) {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 3000)
      const res = await fetch(api.url, { signal: controller.signal })
      clearTimeout(timeout)
      if (!res.ok) continue
      const data = await res.json()
      const cc = api.parse(data)
      if (cc && COUNTRY_TO_LANG[cc]) return COUNTRY_TO_LANG[cc]
      if (cc) return 'en' // known country but not in map → English
    } catch {
      continue
    }
  }
  return null
}

export function LanguageProvider({ children }) {
  // Start with browser language instantly (no flash of wrong language)
  const [lang, setLangState] = useState(getBrowserLang)

  // Manual selection by user (EN/TR buttons) — persists across navigation
  const setLang = useCallback((newLang) => {
    if (translations[newLang]) {
      setLangState(newLang)
      // Mark as manually selected so IP detection won't override during this session
      try { sessionStorage.setItem('cv_lang_manual', newLang) } catch {}
      document.documentElement.lang = newLang
      document.documentElement.dir = RTL_LANGUAGES.includes(newLang) ? 'rtl' : 'ltr'
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = RTL_LANGUAGES.includes(lang) ? 'rtl' : 'ltr'
  }, [lang])

  // IP-based detection on every page load (F5).
  // sessionStorage is cleared on tab close but survives navigation.
  // On F5 within same tab, sessionStorage persists — we clear the manual flag
  // using a performance.navigation check so IP re-detects on refresh.
  useEffect(() => {
    // Clear manual flag on hard refresh so IP detection kicks in
    const isReload = performance?.navigation?.type === 1 ||
      (performance?.getEntriesByType?.('navigation')?.[0]?.type === 'reload')
    if (isReload) {
      try { sessionStorage.removeItem('cv_lang_manual') } catch {}
    }

    // If user manually selected a language in this session, keep it
    const manual = (() => { try { return sessionStorage.getItem('cv_lang_manual') } catch { return null } })()
    if (manual && translations[manual]) {
      setLangState(manual)
      document.documentElement.lang = manual
      document.documentElement.dir = RTL_LANGUAGES.includes(manual) ? 'rtl' : 'ltr'
      return
    }

    // Otherwise detect by IP
    detectLanguageByIP().then((detectedLang) => {
      if (detectedLang && translations[detectedLang]) {
        setLangState(detectedLang)
        document.documentElement.lang = detectedLang
        document.documentElement.dir = RTL_LANGUAGES.includes(detectedLang) ? 'rtl' : 'ltr'
      }
    })
  }, [])

  function t(path) {
    const keys = path.split('.')
    let val = translations[lang]
    for (const k of keys) {
      val = val?.[k]
    }
    if (val) return val

    let fallback = translations.en
    for (const k of keys) {
      fallback = fallback?.[k]
    }
    return fallback || path
  }

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, availableLanguages: ['en', 'tr'] }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
