import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Bell, BellRing, Check, CheckCircle2, Info, Sparkles, Trash2, X } from 'lucide-react'
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

function getNotificationMeta(type) {
  switch (String(type || 'info').toLowerCase()) {
    case 'success':
      return { icon: CheckCircle2, tone: 'success', label: 'Completed' }
    case 'warning':
    case 'warn':
      return { icon: AlertTriangle, tone: 'warning', label: 'Needs attention' }
    case 'error':
    case 'danger':
      return { icon: AlertTriangle, tone: 'danger', label: 'Action needed' }
    default:
      return { icon: Info, tone: 'info', label: 'Update' }
  }
}

function formatNotificationTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
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
        type="button"
        onClick={() => setOpen((value) => !value)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        aria-label={t('notifications.title')}
      >
        {unreadCount > 0 ? <BellRing size={18} /> : <Bell size={18} />}
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
                <div className="notif-header-copy">
                  <span className="notif-header-title">{t('notifications.title')}</span>
                  <small>{unreadCount > 0 ? `${unreadCount} unread update` : 'All caught up'}</small>
                </div>
                <div className="notif-header-actions">
                  {unreadCount > 0 && (
                    <button type="button" className="notif-action" onClick={markAllRead} title={t('notifications.mark_all_read')}>
                      <Check size={14} />
                    </button>
                  )}
                  {notifications.length > 0 && (
                    <button type="button" className="notif-action" onClick={clearAll} title={t('notifications.clear_all')}>
                      <Trash2 size={14} />
                    </button>
                  )}
                  <button type="button" className="notif-action" onClick={() => setOpen(false)} title="Close">
                    <X size={16} />
                  </button>
                </div>
              </div>

            <div className="notif-list">
              {notifications.length === 0 ? (
                <div className="notif-empty">
                  <Sparkles size={22} />
                  <strong>{t('notifications.empty')}</strong>
                  <span>New analysis, billing, and workflow updates will land here.</span>
                </div>
              ) : (
                notifications.map((n) => {
                  const meta = getNotificationMeta(n.type)
                  const Icon = meta.icon
                  const time = formatNotificationTime(n.createdAt)

                  return (
                    <div
                      key={n.id}
                      className={`notif-item notif-item-${meta.tone} ${n.read ? '' : 'unread'}`}
                      onClick={() => markRead(n.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') markRead(n.id)
                      }}
                    >
                      <div className="notif-item-icon">
                        <Icon size={15} />
                      </div>
                      <div className="notif-item-body">
                        <span className="notif-item-kicker">
                          <span>{meta.label}</span>
                          {time && <time dateTime={n.createdAt}>{time}</time>}
                        </span>
                        <span className="notif-item-title">{n.title}</span>
                        <span className="notif-item-msg">{n.message}</span>
                      </div>
                      <button
                        type="button"
                        className="notif-item-remove"
                        aria-label="Remove notification"
                        onClick={(e) => { e.stopPropagation(); removeNotification(n.id) }}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  )
                })
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
