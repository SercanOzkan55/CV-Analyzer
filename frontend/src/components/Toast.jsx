import React, { createContext, useContext, useState, useCallback } from 'react'
import { addNotification } from './NotificationCenter'

/**
 * @typedef {'success' | 'error' | 'info' | 'warning'} ToastType
 * @typedef {Object} ToastContextValue
 * @property {(message: string, type?: ToastType, duration?: number) => number} addToast
 * @property {(id: number) => void} removeToast
 */

const ToastContext = createContext(/** @type {ToastContextValue | null} */ (null))

let toastId = 0

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
    // Persist to notification center
    addNotification({ title: type.charAt(0).toUpperCase() + type.slice(1), message, type })
    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <span className="toast-icon">
              {toast.type === 'success' && '✓'}
              {toast.type === 'error' && '✕'}
              {toast.type === 'info' && 'ℹ'}
              {toast.type === 'warning' && '⚠'}
            </span>
            <span className="toast-message">{toast.message}</span>
            <button className="toast-close" onClick={() => removeToast(toast.id)}>×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  /** @type {ToastContextValue | null} */
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return {
    ...ctx,
    success: (msg, duration) => ctx.addToast(msg, 'success', duration),
    error: (msg, duration) => ctx.addToast(msg, 'error', duration),
    info: (msg, duration) => ctx.addToast(msg, 'info', duration),
    warning: (msg, duration) => ctx.addToast(msg, 'warning', duration),
  }
}
