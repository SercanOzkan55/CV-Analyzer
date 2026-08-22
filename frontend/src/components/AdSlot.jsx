import React, { useEffect, useRef } from 'react'

// The AdSense loader lives in index.html so review crawlers find it in the raw
// HTML. Individual display units render only where this component is mounted,
// which is limited to public editorial routes with substantive content —
// AdSense policy forbids ads on login, empty, or utility screens.
//
// Slot ids come from env so the markup stays out of the build until real ad
// units exist in the AdSense dashboard. Until then this renders nothing, which
// is deliberate: an <ins> with an empty data-ad-slot is a policy violation and
// logs errors on every page view.
const AD_CLIENT = 'ca-pub-6737853186639192'

const SLOT_IDS = {
  article_top: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_TOP || '',
  article_mid: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_MID || '',
  article_end: import.meta.env.VITE_ADSENSE_SLOT_ARTICLE_END || '',
}

export default function AdSlot({ placement, className = '' }) {
  const insRef = useRef(null)
  const pushedRef = useRef(false)
  const slotId = SLOT_IDS[placement] || ''

  useEffect(() => {
    if (!slotId || pushedRef.current || !insRef.current) return

    try {
      // The loader defines window.adsbygoogle as a push-array before it
      // finishes downloading, so this is safe to call immediately.
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
