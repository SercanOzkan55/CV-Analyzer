import React, { useRef, useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext'

export default function DragDropUpload({ onFileSelect, file, onRemove }) {
  const { t } = useLanguage()
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  function isSupported(fileValue) {
    const ext = String(fileValue?.name || '').split('.').pop()?.toLowerCase()
    return (
      ['pdf', 'txt', 'docx'].includes(ext) ||
      [
        'application/pdf',
        'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ].includes(fileValue?.type)
    )
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && isSupported(dropped)) {
      onFileSelect(dropped)
    }
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave() {
    setDragOver(false)
  }

  function handleBrowse() {
    inputRef.current?.click()
  }

  function handleInputChange(e) {
    const f = e.target.files[0]
    if (f) onFileSelect(f)
  }

  return (
    <div
      className={`drag-drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={!file ? handleBrowse : undefined}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleInputChange}
        hidden
      />

      {file ? (
        <div className="file-preview">
          <div className="file-icon">📄</div>
          <div className="file-info">
            <span className="file-name">{file.name}</span>
            <span className="file-size">{(file.size / 1024).toFixed(0)} KB</span>
          </div>
          <button
            type="button"
            className="file-remove"
            onClick={(e) => {
              e.stopPropagation()
              onRemove()
              if (inputRef.current) inputRef.current.value = ''
            }}
          >
            ✕
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
          <button type="button" className="btn-outline btn-sm">{t('analyze.browse')}</button>
          <p className="drop-hint">{t('analyze.upload_hint')}</p>
        </div>
      )}
    </div>
  )
}
