import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'

function loadGoogleFonts() {
  if (typeof document === 'undefined') return
  if (document.getElementById('google-fonts-stylesheet')) return

  const link1 = document.createElement('link')
  link1.rel = 'preconnect'
  link1.href = 'https://fonts.googleapis.com'
  document.head.appendChild(link1)

  const link2 = document.createElement('link')
  link2.rel = 'preconnect'
  link2.href = 'https://fonts.gstatic.com'
  link2.crossOrigin = 'anonymous'
  document.head.appendChild(link2)

  const link3 = document.createElement('link')
  link3.id = 'google-fonts-stylesheet'
  link3.rel = 'stylesheet'
  link3.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap'
  document.head.appendChild(link3)
}

export default function CookieConsent() {
  const { t } = useLanguage()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const consent = localStorage.getItem('cookie_consent')
    if (consent === 'accepted') {
      loadGoogleFonts()
    } else {
      const timer = setTimeout(() => setVisible(true), 1500)
      return () => clearTimeout(timer)
    }
  }, [])

  const accept = () => {
    localStorage.setItem('cookie_consent', 'accepted')
    loadGoogleFonts()
    setVisible(false)
    window.dispatchEvent(new Event('cv-cookie-consent-accepted'))
  }

  if (!visible) return null

  return (
    <div className="cookie-banner">
      <div className="cookie-content">
        <p>
          {t('cookie.message')}{' '}
          <Link to="/privacy">{t('cookie.learn_more')}</Link>
        </p>
        <button className="cookie-accept" onClick={accept}>
          {t('cookie.accept')}
        </button>
      </div>
    </div>
  )
}
