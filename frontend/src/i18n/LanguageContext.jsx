import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import en from './en.json'
import tr from './tr.json'

const translations = { en, tr }

const LanguageContext = createContext(null)

function detectLanguage() {
  const saved = localStorage.getItem('cv-analyzer-lang')
  if (saved && translations[saved]) return saved
  const browserLang = navigator.language?.slice(0, 2) || 'en'
  return translations[browserLang] ? browserLang : 'en'
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(detectLanguage)

  const setLang = useCallback((newLang) => {
    if (translations[newLang]) {
      setLangState(newLang)
      localStorage.setItem('cv-analyzer-lang', newLang)
      document.documentElement.lang = newLang
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  function t(path) {
    const keys = path.split('.')
    let val = translations[lang]
    for (const k of keys) {
      val = val?.[k]
    }
    return val || path
  }

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, availableLanguages: Object.keys(translations) }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
