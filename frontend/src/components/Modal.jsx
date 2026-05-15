import React, { useEffect, useId, useRef } from 'react'

export default function Modal({ open, onClose, title, children }) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined

    previousFocusRef.current = document.activeElement
    dialogRef.current?.focus()

    return () => {
      previousFocusRef.current?.focus?.()
    }
  }, [open])

  if (!open) return null

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
      return
    }

    if (e.key !== 'Tab' || !dialogRef.current) return

    const focusable = dialogRef.current.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )

    if (!focusable.length) {
      e.preventDefault()
      dialogRef.current.focus()
      return
    }

    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="modal-header">
          {title && <h3 id={titleId}>{title}</h3>}
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close modal">
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  )
}
