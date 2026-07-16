import { afterEach, describe, expect, it } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SEOManager from '../components/SEOManager'

function renderManager(pathname) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <SEOManager />
    </MemoryRouter>,
  )
}

afterEach(() => {
  document.getElementById('route-structured-data')?.remove()
})

describe('SEOManager', () => {
  it('sets route-specific indexable metadata and structured data', async () => {
    renderManager('/cv-analiz/')

    await waitFor(() => expect(document.title).toContain('Ücretsiz CV Analiz'))
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', expect.stringContaining('index'))
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute('href', 'https://cvanalyzer.dev/cv-analiz/')
    expect(document.getElementById('route-structured-data')?.textContent).toContain('FAQPage')
  })

  it('marks authenticated application routes as noindex', async () => {
    renderManager('/dashboard')

    await waitFor(() => {
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow')
    })
  })
})
