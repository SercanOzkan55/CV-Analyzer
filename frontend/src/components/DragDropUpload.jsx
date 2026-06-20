import React, { useRef, useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from './Toast'

export default function DragDropUpload({ onFileSelect, file, onRemove }) {
  const { t } = useLanguage()
  const { addToast } = useToast()
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  function handleFile(f) {
    if (!f) return

    // 10MB limit check
    const maxSize = 10 * 1024 * 1024
    if (f.size > maxSize) {
      addToast(t('analyze.error_file_size') || 'File is too large (max 10MB)', 'error')
      return
    }

    // Ext and MIME type check
    const ext = String(f.name || '').split('.').pop()?.toLowerCase()
    const allowedExtensions = ['pdf', 'txt', 'docx']
    const allowedMimeTypes = [
      'application/pdf',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]

    if (!allowedExtensions.includes(ext) && !allowedMimeTypes.includes(f.type)) {
      addToast(t('analyze.error_file_format') || 'Unsupported format. Allowed: PDF, TXT, DOCX', 'error')
      return
    }

    onFileSelect(f)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      handleFile(dropped)
    }
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave() {
    setDragOver(false)
  }

  function handleInputChange(e) {
    const f = e.target.files[0]
    if (f) {
      handleFile(f)
    }
  }

  function handleKeyDown(e) {
    if (file) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <label
      className={`drag-drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      tabIndex={file ? -1 : 0}
      onKeyDown={handleKeyDown}
      role="button"
      aria-label={file ? `${t('analyze.has_file') || 'File'}: ${file.name}` : t('analyze.upload_desc')}
      style={{ cursor: file ? 'default' : 'pointer', display: 'block' }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />

      {file ? (
        <div className="file-preview">
          <div className="file-icon" aria-hidden="true">CV</div>
          <div className="file-info">
            <span className="file-name">{file.name}</span>
            <span className="file-size">{(file.size / 1024).toFixed(0)} KB</span>
          </div>
          <button
            type="button"
            className="file-remove"
            aria-label={`${t('analyze.remove_file') || 'Remove'} ${file.name}`}
            onClick={(e) => {
              e.stopPropagation()
              e.preventDefault()
              onRemove()
              if (inputRef.current) inputRef.current.value = ''
            }}
          >
            x
          </button>
        </div>
      ) : (
        <div className="drop-content">
          <div className="drop-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="drop-text">{t('analyze.upload_desc')}</p>
          <span className="btn-outline btn-sm" style={{ display: 'inline-block' }}>{t('analyze.browse')}</span>
          <p className="drop-hint">{t('analyze.upload_hint')}</p>
        </div>
      )}
    </label>
  )
}
