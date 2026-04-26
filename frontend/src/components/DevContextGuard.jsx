import { useEffect } from 'react'

function isProviderContextError(message) {
  if (!message) return false
  const text = String(message)
  return text.includes('must be used within') && text.includes('Provider')
}

export default function DevContextGuard() {
  useEffect(() => {
    if (!import.meta.env.DEV) return undefined

    let warned = false

    function printGuidance(source, message, stack = '') {
      if (warned) return
      warned = true

      console.groupCollapsed('[DevContextGuard] Context/Provider mismatch detected')
      console.warn('Source:', source)
      console.warn('Message:', message)
      if (stack) console.warn('Stack:', stack)
      console.info('Likely cause: Fast Refresh/HMR recreated a context instance during live editing.')
      console.info('Suggested fix: hard refresh (Ctrl+F5) and restart dev server if it persists.')
      console.info('Note: HMR-safe singleton contexts are enabled for Auth, Theme, and Language.')
      console.groupEnd()
    }

    function onError(event) {
      const message = event?.error?.message || event?.message || ''
      const stack = event?.error?.stack || ''
      if (isProviderContextError(message)) {
        printGuidance('window.onerror', message, stack)
      }
    }

    function onUnhandledRejection(event) {
      const reason = event?.reason
      const message = reason?.message || String(reason || '')
      const stack = reason?.stack || ''
      if (isProviderContextError(message)) {
        printGuidance('unhandledrejection', message, stack)
      }
    }

    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onUnhandledRejection)

    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onUnhandledRejection)
    }
  }, [])

  return null
}
