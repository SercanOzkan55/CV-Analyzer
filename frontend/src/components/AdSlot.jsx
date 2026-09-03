import React, { useEffect, useRef } from 'react'

// Slot ids come from env so the markup stays out of the build until real ad
// units exist in the AdSense dashboard. Until then this renders nothing, which
// is deliberate: an <ins> with an empty data-ad-slot is a policy violation and
// logs errors on every page view.
const AD_CLIENT = 'ca-pub-6737853186639192'
const ADSENSE_LOADER_ID = 'adsense-page-loader'
const ADSENSE_LOADER_SRC = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CLIENT}`

const SLOT_IDS = {
  article_top: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_TOP || '',
  article_mid: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_MID || '',
  article_end: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_END || '',
}

function ensureAdSenseLoader() {
  if (typeof document === 'undefined') return

  const existingLoader = document.getElementById(ADSENSE_LOADER_ID)
    || document.querySelector('script[src^="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"]')

  if (existingLoader) return

  const script = document.createElement('script')
  script.id = ADSENSE_LOADER_ID
  script.async = true
  script.src = ADSENSE_LOADER_SRC
  script.crossOrigin = 'anonymous'
  document.head.appendChild(script)
}

export default function AdSlot({ placement, className = '' }) {
  const insRef = useRef(null)
  const pushedRef = useRef(false)
  const slotId = SLOT_IDS[placement] || ''

  useEffect(() => {
    // AdSlot is mounted only by reviewed, substantive editorial pages. Loading
    // the script here prevents Auto ads from appearing on auth, account,
    // private app, loading, error, and other utility routes. It also lets Auto
    // ads run on editorial pages before manual display-unit ids are configured.
    ensureAdSenseLoader()

    if (!slotId || pushedRef.current || !insRef.current) return

    try {
      // Queue the display unit while the async loader is downloading.
      ;(window.adsbygoogle = window.adsbygoogle || []).push({})
      pushedRef.current = true
    } catch {
      // A blocked or failed loader must never break the article around it.
    }
  }, [slotId])

  if (!slotId) return null

  return (
    <aside className={`ad-slot ${className}`.trim()} aria-label="Reklam">
      <span className="ad-slot-label">Reklam</span>
      <ins
        ref={insRef}
        className="adsbygoogle"
        style={{ display: 'block' }}
        data-ad-client={AD_CLIENT}
        data-ad-slot={slotId}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </aside>
  )
}
