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

/**
 * @typedef {Object} LanguageContextValue
 * @property {string} lang
 * @property {(newLang: string) => void} setLang
 * @property {(path: string) => any} t
 * @property {string[]} availableLanguages Languages exposed for manual selection.
 * @property {(lang: string | null) => void} setRouteLangOverride Non-persisting override for fixed-language routes (e.g. /en/... SEO pages).
 */

const LANGUAGE_CONTEXT_KEY = '__CV_ANALYZER_LANGUAGE_CONTEXT__'

const LanguageContext = (() => {
  if (typeof globalThis !== 'undefined' && globalThis[LANGUAGE_CONTEXT_KEY]) {
    return globalThis[LANGUAGE_CONTEXT_KEY]
  }

  const ctx = createContext(/** @type {LanguageContextValue | null} */ (null))
  if (typeof globalThis !== 'undefined') {
    globalThis[LANGUAGE_CONTEXT_KEY] = ctx
  }
  return ctx
})()

// Browser language as instant fallback (only tr/en for initial render)
function getBrowserLang() {
  const bl = (navigator.language || '').slice(0, 2).toLowerCase()
  const supported = { tr: 'tr', fr: 'fr', de: 'de', es: 'es', ar: 'ar' }
  return supported[bl] || 'en'
}

// Initial language: a persisted manual choice wins over everything (survives
// refresh and new sessions); otherwise fall back to the browser language.
function getInitialLang() {
  try {
    const manual = localStorage.getItem('cv_lang_manual')
    if (manual && translations[manual]) return manual
  } catch {}
  return getBrowserLang()
}

// Detect language by IP geolocation — supports all 6 languages
async function detectLanguageByIP() {
  const CACHE_KEY = 'cv_ip_lang_cache'
  const SESSION_FLAG = 'cv_ip_checked'

  // Only use cache if already checked this browser session
  // This ensures a location change (VPN etc.) is detected on new session
  const checkedThisSession = sessionStorage.getItem(SESSION_FLAG)
  if (checkedThisSession) {
    try {
      const cachedRaw = localStorage.getItem(CACHE_KEY)
      if (cachedRaw) {
        const cached = JSON.parse(cachedRaw)
        if (cached?.lang) return cached
      }
    } catch {}
  }

  const apis = [
    {
      url: 'https://ipapi.co/json/',
      parse: (d) => (d.country_code || '').toUpperCase(),
    },
    {
      url: 'https://ipwhois.app/json/',
      parse: (d) => (d.country_code || '').toUpperCase(),
    },
    {
      url: 'https://ipinfo.io/json',
      parse: (d) => (d.country || '').toUpperCase(),
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
      if (cc) {
        const detected = COUNTRY_TO_LANG[cc] || 'en'
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({ lang: detected, cc, ts: Date.now() }))
          sessionStorage.setItem(SESSION_FLAG, '1')
        } catch {}
        return { lang: detected, cc }
      }
    } catch {
      continue
    }
  }
  return { lang: 'en', cc: 'US' }
}

export function LanguageProvider({ children }) {
  // Start with the persisted manual choice (or browser language) instantly.
  const [lang, setLangState] = useState(getInitialLang)
  const [countryCode, setCountryCode] = useState(() => {
    try {
      const cached = localStorage.getItem('cv_ip_lang_cache')
      if (cached) return JSON.parse(cached).cc || 'US'
    } catch {}
    return 'US'
  })

  // Non-persisting override used by fixed-language routes (e.g. /en/... SEO
  // pages) so the whole UI can render in a specific language regardless of
  // IP detection or the manual toggle, without touching `cv_lang_manual` or
  // affecting any other route once the override is cleared.
  const [routeLangOverride, setRouteLangOverride] = useState(null)
  const effectiveLang = routeLangOverride || lang

  // Manual selection by user (EN/TR buttons) — persisted so it survives
  // navigation, hard refresh, and future sessions; IP detection never overrides it.
  const setLang = useCallback((newLang) => {
    if (translations[newLang]) {
      setLangState(newLang)
      try { localStorage.setItem('cv_lang_manual', newLang) } catch {}
      document.documentElement.lang = newLang
      document.documentElement.dir = RTL_LANGUAGES.includes(newLang) ? 'rtl' : 'ltr'
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = effectiveLang
    document.documentElement.dir = RTL_LANGUAGES.includes(effectiveLang) ? 'rtl' : 'ltr'
  }, [effectiveLang])

  // IP-based detection on every page load (F5).
  // sessionStorage is cleared on tab close but survives navigation.
  // On F5 within same tab, sessionStorage persists — we clear the manual flag
  // using a performance.navigation check so IP re-detects on refresh.
  useEffect(() => {
    function tryDetect() {
      const hasConsent = localStorage.getItem('cookie_consent') === 'accepted'
      if (!hasConsent) return

      // A persisted manual choice always wins and is never overridden by IP —
      // it survives navigation, hard refresh and future sessions.
      // (document.documentElement.lang/dir is derived reactively from
      // effectiveLang above, so it isn't set directly here.)
      const manual = (() => { try { return localStorage.getItem('cv_lang_manual') } catch { return null } })()
      if (manual && translations[manual]) {
        setLangState(manual)
        return
      }

      // Otherwise detect by IP
      detectLanguageByIP().then(({ lang: detectedLang, cc }) => {
        setCountryCode(cc)
        const manual = (() => { try { return localStorage.getItem('cv_lang_manual') } catch { return null } })()
        if (!manual && detectedLang && translations[detectedLang]) {
          setLangState(detectedLang)
        }
      }).catch(() => {
        // IP detection failed — keep browser language, no user-visible error
      })
    }

    tryDetect()

    window.addEventListener('cv-cookie-consent-accepted', tryDetect)
    return () => window.removeEventListener('cv-cookie-consent-accepted', tryDetect)
  }, [])

  function t(path) {
    const keys = path.split('.')
    let val = translations[effectiveLang]
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

  // Automatic IP/browser detection may still select any language in `translations`.
  // Only English and Turkish are intentionally exposed as manual controls.
  return (
    <LanguageContext.Provider
      value={{ lang: effectiveLang, setLang, t, countryCode, availableLanguages: ['en', 'tr'], setRouteLangOverride }}
    >
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  /** @type {LanguageContextValue | null} */
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
