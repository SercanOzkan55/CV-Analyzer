import React, { createContext, useCallback, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { addNotification } from './NotificationCenter'

/**
 * @typedef {'success' | 'error' | 'info' | 'warning'} ToastType
 * @typedef {Object} ToastContextValue
 * @property {(message: string, type?: ToastType, duration?: number) => number} addToast
 * @property {(id: number) => void} removeToast
 */

const ToastContext = createContext(/** @type {ToastContextValue | null} */ (null))

let toastId = 0

const toastIcons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, duration)
    }
    addNotification({ title: type.charAt(0).toUpperCase() + type.slice(1), message, type })
    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="toast-container" aria-live="polite" aria-relevant="additions removals">
        {toasts.map((toast) => {
          const Icon = toastIcons[toast.type] || Info
          return (
            <div key={toast.id} className={`toast toast-${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}>
              <span className="toast-icon" aria-hidden="true">
                <Icon size={18} strokeWidth={2} />
              </span>
              <span className="toast-message">{toast.message}</span>
              <button type="button" className="toast-close" onClick={() => removeToast(toast.id)} aria-label="Dismiss notification">
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  /** @type {ToastContextValue | null} */
  const ctx = React.useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return {
    ...ctx,
    success: (msg, duration) => ctx.addToast(msg, 'success', duration),
    error: (msg, duration) => ctx.addToast(msg, 'error', duration),
    info: (msg, duration) => ctx.addToast(msg, 'info', duration),
    warning: (msg, duration) => ctx.addToast(msg, 'warning', duration),
  }
}
