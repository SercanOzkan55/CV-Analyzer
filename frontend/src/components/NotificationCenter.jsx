import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, X, Check, Trash2 } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

const NOTIF_KEY = 'cv_analyzer_notifications'

function getNotifications() {
  try {
    return JSON.parse(localStorage.getItem(NOTIF_KEY) || '[]')
  } catch { return [] }
}

function saveNotifications(items) {
  localStorage.setItem(NOTIF_KEY, JSON.stringify(items))
}

// Generate default "welcome" notification on first use
function ensureDefaults(t) {
  const items = getNotifications()
  if (items.length === 0) {
    const defaults = [
      {
        id: 'welcome',
        type: 'info',
        title: t('notifications.welcome_title'),
        message: t('notifications.welcome_msg'),
        read: false,
        createdAt: new Date().toISOString(),
      },
    ]
    saveNotifications(defaults)
    return defaults
  }
  return items
}

export default function NotificationCenter() {
  const { t } = useLanguage()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const ref = useRef(null)

  useEffect(() => {
    setNotifications(ensureDefaults(t))
  }, [t])

  // Re-read notifications when new ones are added from other parts of the app
  useEffect(() => {
    function onUpdate() {
      setNotifications(getNotifications())
    }
    window.addEventListener('cv-notif-update', onUpdate)
    return () => window.removeEventListener('cv-notif-update', onUpdate)
  }, [])

  // Close on click outside
  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const unreadCount = notifications.filter((n) => !n.read).length

  function markRead(id) {
    const updated = notifications.map((n) => n.id === id ? { ...n, read: true } : n)
    setNotifications(updated)
    saveNotifications(updated)
  }

  function markAllRead() {
    const updated = notifications.map((n) => ({ ...n, read: true }))
    setNotifications(updated)
    saveNotifications(updated)
  }

  function removeNotification(id) {
    const updated = notifications.filter((n) => n.id !== id)
    setNotifications(updated)
    saveNotifications(updated)
  }

  function clearAll() {
    setNotifications([])
    saveNotifications([])
  }

  return (
    <div className="notif-center" ref={ref}>
      <motion.button
        className="notif-bell"
        onClick={() => setOpen(true)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        aria-label={t('notifications.title')}
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <motion.span
            className="notif-badge"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
          >
            {unreadCount}
          </motion.span>
        )}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="notif-overlay"
              className="notif-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          />
        )}
        {open && (
          <motion.div
            key="notif-popover"
            className="notif-popover"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
              <div className="notif-header">
                <span className="notif-header-title">{t('notifications.title')}</span>
                <div className="notif-header-actions">
                  {unreadCount > 0 && (
                    <button className="notif-action" onClick={markAllRead} title={t('notifications.mark_all_read')}>
                      <Check size={14} />
                    </button>
                  )}
                  {notifications.length > 0 && (
                    <button className="notif-action" onClick={clearAll} title={t('notifications.clear_all')}>
                      <Trash2 size={14} />
                    </button>
                  )}
                  <button className="notif-action" onClick={() => setOpen(false)} title="Close">
                    <X size={16} />
                  </button>
                </div>
              </div>

            <div className="notif-list">
              {notifications.length === 0 ? (
                <div className="notif-empty">{t('notifications.empty')}</div>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`notif-item ${n.read ? '' : 'unread'}`}
                    onClick={() => markRead(n.id)}
                  >
                    <div className="notif-item-dot" />
                    <div className="notif-item-body">
                      <span className="notif-item-title">{n.title}</span>
                      <span className="notif-item-msg">{n.message}</span>
                    </div>
                    <button
                      className="notif-item-remove"
                      onClick={(e) => { e.stopPropagation(); removeNotification(n.id) }}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/**
 * Utility: push a notification from anywhere in the app.
 * Call addNotification({ title, message, type }) to add.
 */
export function addNotification({ title, message, type = 'info' }) {
  const items = getNotifications()
  const item = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    type,
    title,
    message,
    read: false,
    createdAt: new Date().toISOString(),
  }
  items.unshift(item)
  saveNotifications(items.slice(0, 50))
  // Dispatch event so NotificationCenter re-reads
  window.dispatchEvent(new Event('cv-notif-update'))
}
