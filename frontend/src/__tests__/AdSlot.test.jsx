import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'

const LOADER_SELECTOR = '#adsense-page-loader'

async function loadAdSlot() {
  vi.resetModules()
  return (await import('../components/AdSlot')).default
}

describe('AdSlot', () => {
  beforeEach(() => {
    document.querySelectorAll(LOADER_SELECTOR).forEach((node) => node.remove())
    delete window.adsbygoogle
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllEnvs()
    document.querySelectorAll(LOADER_SELECTOR).forEach((node) => node.remove())
    delete window.adsbygoogle
  })

  it('loads AdSense only when the editorial ad component mounts', async () => {
    const AdSlot = await loadAdSlot()

    expect(document.querySelector(LOADER_SELECTOR)).toBeNull()
    render(<AdSlot placement="article_mid" />)

    const loader = document.querySelector(LOADER_SELECTOR)
    expect(loader).toHaveAttribute(
      'src',
      'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6737853186639192',
    )
    expect(loader).toHaveAttribute('crossorigin', 'anonymous')
    expect(loader.async).toBe(true)
  })

  it('reuses one loader and queues configured display units', async () => {
    vi.stubEnv('VITE_ADSENSE_SLOT_ARTICLE_MID', '1234567890')
    const AdSlot = await loadAdSlot()

    render(
      <>
        <AdSlot placement="article_mid" />
        <AdSlot placement="article_mid" />
      </>,
    )

    expect(document.querySelectorAll(LOADER_SELECTOR)).toHaveLength(1)
    expect(document.querySelectorAll('ins[data-ad-slot="1234567890"]')).toHaveLength(2)
    expect(window.adsbygoogle).toHaveLength(2)
  })
})
