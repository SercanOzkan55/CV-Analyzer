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

const COUNTRY_TO_REGION = {
  TR: 'TR', RU: 'RU', GB: 'GB', MX: 'MX', AR: 'AR', SA: 'SA', AE: 'AE',
  DE: 'EU', FR: 'EU', ES: 'EU', IT: 'EU', NL: 'EU', BE: 'EU', AT: 'EU', FI: 'EU', PT: 'EU', IE: 'EU'
}

const PRICING_CONFIG = {
  TR: { pro: '599 TL', free: '0 TL', enterprise: '3999 TL', periodKey: 'pricing.period_monthly' },
  EU: { pro: '€19', free: '€0', enterprise: '€100', periodKey: 'pricing.period_monthly' },
  GB: { pro: '£17', free: '£0', enterprise: '£85', periodKey: 'pricing.period_monthly' },
  RU: { pro: '1500 ₽', free: '0 ₽', enterprise: '10000 ₽', periodKey: 'pricing.period_monthly' },
  MX: { pro: '$350 MXN', free: '$0', enterprise: '$2000 MXN', periodKey: 'pricing.period_monthly' },
  AR: { pro: '$4500 ARS', free: '$0', enterprise: '$25000 ARS', periodKey: 'pricing.period_monthly' },
  SA: { pro: '70 SR', free: '0 SR', enterprise: '400 SR', periodKey: 'pricing.period_monthly' },
  AE: { pro: '70 DH', free: '0 DH', enterprise: '400 DH', periodKey: 'pricing.period_monthly' },
  DEFAULT: { pro: '$19', free: '$0', enterprise: '$100', periodKey: 'pricing.period_monthly' }
}

/**
 * @typedef {Object} LanguageContextValue
 * @property {string} lang
 * @property {(newLang: string) => void} setLang
 * @property {(path: string) => any} t
 * @property {string[]} availableLanguages
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
  // Start with browser language instantly (no flash of wrong language)
  const [lang, setLangState] = useState(getBrowserLang)
  const [countryCode, setCountryCode] = useState(() => {
    try {
      const cached = localStorage.getItem('cv_ip_lang_cache')
      if (cached) return JSON.parse(cached).cc || 'US'
    } catch {}
    return 'US'
  })

  const regionKey = COUNTRY_TO_REGION[countryCode] || 'DEFAULT'
  const pricing = PRICING_CONFIG[regionKey]

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
    function tryDetect() {
      const hasConsent = localStorage.getItem('cookie_consent') === 'accepted'
      if (!hasConsent) return

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
      detectLanguageByIP().then(({ lang: detectedLang, cc }) => {
        setCountryCode(cc)
        const manual = (() => { try { return sessionStorage.getItem('cv_lang_manual') } catch { return null } })()
        if (!manual && detectedLang && translations[detectedLang]) {
          setLangState(detectedLang)
          document.documentElement.lang = detectedLang
          document.documentElement.dir = RTL_LANGUAGES.includes(detectedLang) ? 'rtl' : 'ltr'
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
    <LanguageContext.Provider value={{ lang, setLang, t, countryCode, pricing, availableLanguages: ['en', 'tr'] }}>
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
