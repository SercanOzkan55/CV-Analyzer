import React, { createContext, useContext, useState, useEffect } from 'react'

/**
 * @typedef {Object} ThemeContextValue
 * @property {'light' | 'dark'} theme
 * @property {(t: 'light' | 'dark') => void} setTheme
 * @property {() => void} toggleTheme
 */

const THEME_CONTEXT_KEY = '__CV_ANALYZER_THEME_CONTEXT__'

const ThemeContext = (() => {
  if (typeof globalThis !== 'undefined' && globalThis[THEME_CONTEXT_KEY]) {
    return globalThis[THEME_CONTEXT_KEY]
  }

  const ctx = createContext(/** @type {ThemeContextValue | null} */ (null))
  if (typeof globalThis !== 'undefined') {
    globalThis[THEME_CONTEXT_KEY] = ctx
  }
  return ctx
})()

function detectTheme() {
  const saved = localStorage.getItem('cv-analyzer-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(detectTheme)

  function setTheme(t) {
    document.documentElement.classList.add('theme-transition')
    setThemeState(t)
    localStorage.setItem('cv-analyzer-theme', t)
    const timer = setTimeout(() => {
      document.documentElement.classList.remove('theme-transition')
    }, 450)
    return () => clearTimeout(timer)
  }

  function toggleTheme() {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  /** @type {ThemeContextValue | null} */
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
