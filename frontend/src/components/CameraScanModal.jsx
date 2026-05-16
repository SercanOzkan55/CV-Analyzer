import React, { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Camera, X, Plus, Trash2, FileText, Download, RotateCcw, Loader2, CheckCircle, AlertTriangle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { recruiterScanCV } from '../api'
import ScoreCircle from './ScoreCircle'
import Modal from './Modal'

function getScoreColor(s) {
  if (s >= 75) return '#22c55e'
  if (s >= 50) return '#eab308'
  return '#ef4444'
}

export default function CameraScanModal({ open, onClose }) {
  const { token } = useAuth()
  const { t, lang } = useLanguage()
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)

  const [phase, setPhase] = useState('capture') // capture | preview | analyzing | results
  const [capturedPages, setCapturedPages] = useState([]) // {dataUrl, blob}[]
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Start camera
  const startCamera = useCallback(async () => {
    setCameraError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setCameraActive(true)
    } catch (err) {
      setCameraError('Camera access denied or not available. You can also upload images directly.')
      setCameraActive(false)
    }
  }, [])

  // Stop camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    setCameraActive(false)
  }, [])

  // Start camera when modal opens in capture mode
  useEffect(() => {
    if (open && phase === 'capture') {
      startCamera()
    }
    return () => stopCamera()
  }, [open, phase])

  // Capture photo from video
  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return
    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    canvas.toBlob((blob) => {
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
      setCapturedPages(prev => [...prev, { dataUrl, blob }])
    }, 'image/jpeg', 0.85)
  }, [])

  // Handle file upload (alternative to camera)
  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files)
    files.forEach(file => {
      if (!file.type.startsWith('image/')) return
      const reader = new FileReader()
      reader.onload = () => {
        setCapturedPages(prev => [...prev, { dataUrl: reader.result, blob: file }])
      }
      reader.readAsDataURL(file)
    })
    e.target.value = ''
  }

  const removePage = (index) => {
    setCapturedPages(prev => prev.filter((_, i) => i !== index))
  }

  const resetScan = () => {
    setCapturedPages([])
    setPhase('capture')
    setResult(null)
    setError('')
    startCamera()
  }

  // Send to backend
  const handleAnalyze = async () => {
    if (!token || !capturedPages.length) return
    stopCamera()
    setPhase('analyzing')
    setAnalyzing(true)
    setError('')

    try {
      const formData = new FormData()
      capturedPages.forEach((page, i) => {
        formData.append('images', page.blob, `cv_page_${i + 1}.jpg`)
      })
      formData.append('job_description', '')
      formData.append('lang', lang || 'en')

      const data = await recruiterScanCV(token, formData)
      setResult(data)
      setPhase('results')
    } catch (err) {
      setError(err.message || 'Analysis failed')
      setPhase('preview')
    } finally {
      setAnalyzing(false)
    }
  }

  // Download PDF
  const handleDownloadPdf = () => {
    if (!result?.pdf_base64) return
    const byteChars = atob(result.pdf_base64)
    const byteNumbers = new Array(byteChars.length)
    for (let i = 0; i < byteChars.length; i++) {
      byteNumbers[i] = byteChars.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    const blob = new Blob([byteArray], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `scanned_cv_${Date.now()}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClose = () => {
    stopCamera()
    setCapturedPages([])
    setPhase('capture')
    setResult(null)
    setError('')
    onClose()
  }

  if (!open) return null

  return (
    <div style={styles.overlay} onClick={handleClose}>
      <motion.div
        style={styles.modal}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerLeft}>
            <Camera size={22} />
            <h2 style={styles.title}>
              {phase === 'results' ? 'Scan Results' : phase === 'analyzing' ? 'Analyzing...' : 'Scan CV'}
            </h2>
          </div>
          <button style={styles.closeBtn} onClick={handleClose}>
            <X size={20} />
          </button>
        </div>

        {/* ── Results ── */}
        {phase === 'results' && result && (
          <div style={styles.body}>
            <div style={styles.resultsGrid}>
              {/* Score card */}
              <div style={styles.scoreCard}>
                <ScoreCircle score={Math.round(result.ats_score ?? result.final_score ?? 0)} size={120} />
                <div style={{ marginTop: 12 }}>
                  <span style={{
                    fontSize: 14, fontWeight: 600,
                    color: getScoreColor(result.ats_score ?? 0),
                  }}>
                    {(result.ats_score ?? 0) >= 75 ? '✅ Strong' : (result.ats_score ?? 0) >= 50 ? '⚠️ Moderate' : '❌ Needs Work'}
                  </span>
                </div>
                <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
                  {result.scan_pages} page{result.scan_pages > 1 ? 's' : ''} scanned
                </p>
              </div>

              {/* Section breakdown */}
              {result.ats?.section_scores?.length > 0 && (
                <div style={styles.sectionCard}>
                  <h3 style={styles.cardTitle}>Section Breakdown</h3>
                  {result.ats.section_scores.map((sec, i) => (
                    <div key={i} style={styles.sectionRow}>
                      <span style={{ fontSize: 13, color: '#334155' }}>
                        {sec.label?.en || sec.label || `Section ${i + 1}`}
                      </span>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <div style={styles.progressBar}>
                          <div style={{
                            ...styles.progressFill,
                            width: `${sec.score}%`,
                            backgroundColor: getScoreColor(sec.score),
                          }} />
                        </div>
                        <span style={{
                          fontSize: 12, fontWeight: 700,
                          color: getScoreColor(sec.score),
                          minWidth: 35, textAlign: 'right',
                        }}>{sec.score}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Skills */}
            {result.detected_skills?.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3 style={styles.cardTitle}>Detected Skills</h3>
                <div style={styles.skillsWrap}>
                  {result.detected_skills.map((s, i) => (
                    <span key={i} style={{ ...styles.skillChip, backgroundColor: '#eef2ff', color: '#4f46e5' }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {result.missing_skills?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <h3 style={styles.cardTitle}>Missing Skills</h3>
                <div style={styles.skillsWrap}>
                  {result.missing_skills.map((s, i) => (
                    <span key={i} style={{ ...styles.skillChip, backgroundColor: '#fee2e2', color: '#dc2626' }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted text */}
            <details style={{ marginTop: 16 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: 14, color: '#334155' }}>
                📄 Extracted Text
              </summary>
              <pre style={styles.ocrPre}>{result.ocr_text || '(empty)'}</pre>
            </details>

            {/* Actions */}
            <div style={styles.actionsRow}>
              {result.pdf_base64 && (
                <button style={styles.primaryBtn} onClick={handleDownloadPdf}>
                  <Download size={16} /> Download PDF
                </button>
              )}
              <button style={styles.outlineBtn} onClick={resetScan}>
                <RotateCcw size={16} /> New Scan
              </button>
            </div>
          </div>
        )}

        {/* ── Analyzing ── */}
        {phase === 'analyzing' && (
          <div style={styles.centerBox}>
            <Loader2 size={48} style={{ animation: 'spin 1s linear infinite', color: '#6366f1' }} />
            <p style={{ fontWeight: 600, fontSize: 18, marginTop: 16, color: '#1e293b' }}>Analyzing scanned CV...</p>
            <p style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>OCR extraction + ATS analysis + PDF generation</p>
          </div>
        )}

        {/* ── Preview ── */}
        {(phase === 'preview' || (phase === 'capture' && capturedPages.length > 0)) && (
          <div style={styles.body}>
            <div style={styles.previewHeader}>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>
                📄 Captured Pages ({capturedPages.length})
              </h3>
              <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
                Click a page to remove it. Add more pages or start analysis.
              </p>
            </div>

            <div style={styles.pagesGrid}>
              {capturedPages.map((page, idx) => (
                <div key={idx} style={styles.pageCard} onClick={() => removePage(idx)}>
                  <img src={page.dataUrl} style={styles.pageImg} alt={`Page ${idx + 1}`} />
                  <div style={styles.pageLabel}>
                    <span>Page {idx + 1}</span>
                    <Trash2 size={14} />
                  </div>
                </div>
              ))}

              {/* Add more */}
              <div
                style={styles.addPageCard}
                onClick={() => { setPhase('capture'); startCamera() }}
              >
                <Camera size={24} style={{ color: '#6366f1' }} />
                <span style={{ color: '#6366f1', fontWeight: 600, fontSize: 13 }}>Camera</span>
              </div>
              <div
                style={styles.addPageCard}
                onClick={() => fileInputRef.current?.click()}
              >
                <Plus size={24} style={{ color: '#6366f1' }} />
                <span style={{ color: '#6366f1', fontWeight: 600, fontSize: 13 }}>Upload</span>
              </div>
            </div>

            {error && (
              <div style={styles.errorBox}>
                <AlertTriangle size={16} /> {error}
              </div>
            )}

            <div style={styles.actionsRow}>
              <button
                style={{ ...styles.primaryBtn, opacity: capturedPages.length === 0 ? 0.5 : 1 }}
                onClick={handleAnalyze}
                disabled={capturedPages.length === 0 || analyzing}
              >
                <FileText size={16} /> Analyze CV ({capturedPages.length} page{capturedPages.length !== 1 ? 's' : ''})
              </button>
              <button style={styles.dangerBtn} onClick={resetScan}>
                <Trash2 size={16} /> Clear All
              </button>
            </div>
          </div>
        )}

        {/* ── Camera Capture ── */}
        {phase === 'capture' && capturedPages.length === 0 && (
          <div style={styles.body}>
            {cameraError ? (
              <div style={styles.cameraFallback}>
                <Camera size={48} style={{ color: '#94a3b8' }} />
                <p style={{ color: '#64748b', textAlign: 'center', margin: '12px 0' }}>{cameraError}</p>
                <button style={styles.outlineBtn} onClick={() => fileInputRef.current?.click()}>
                  <Plus size={16} /> Upload Image Instead
                </button>
              </div>
            ) : (
              <div style={styles.cameraBox}>
                <div style={styles.videoWrapper}>
                  <video ref={videoRef} style={styles.video} autoPlay playsInline muted />
                  {/* Corner guides */}
                  <div style={{ ...styles.corner, top: 16, left: 16 }} />
                  <div style={{ ...styles.corner, top: 16, right: 16, borderLeft: 'none', borderRight: '3px solid #fff' }} />
                  <div style={{ ...styles.corner, bottom: 16, left: 16, borderTop: 'none', borderBottom: '3px solid #fff' }} />
                  <div style={{ ...styles.corner, bottom: 16, right: 16, borderTop: 'none', borderLeft: 'none', borderBottom: '3px solid #fff', borderRight: '3px solid #fff' }} />
                  <div style={styles.guideOverlay}>
                    <span style={styles.guideText}>📄 Position the CV within the frame</span>
                  </div>
                </div>

                <div style={styles.cameraControls}>
                  <button style={styles.captureBtn} onClick={capturePhoto}>
                    <div style={styles.captureBtnInner} />
                  </button>
                  <button style={styles.outlineBtn} onClick={() => fileInputRef.current?.click()}>
                    <Plus size={16} /> Upload
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileUpload}
        />

        {/* Hidden canvas for photo capture */}
        <canvas ref={canvasRef} style={{ display: 'none' }} />

        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </motion.div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 9999, padding: 20,
  },
  modal: {
    backgroundColor: '#fff', borderRadius: 16,
    width: '100%', maxWidth: 800, maxHeight: '90vh',
    overflow: 'auto', boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #e2e8f0',
    position: 'sticky', top: 0, backgroundColor: '#fff', zIndex: 10,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 10 },
  title: { margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' },
  closeBtn: {
    background: 'none', border: 'none', cursor: 'pointer', padding: 6,
    borderRadius: 8, color: '#64748b',
  },
  body: { padding: 20 },

  // Camera
  cameraBox: { display: 'flex', flexDirection: 'column', gap: 16 },
  videoWrapper: {
    position: 'relative', borderRadius: 12, overflow: 'hidden',
    backgroundColor: '#000', aspectRatio: '4/3',
  },
  video: { width: '100%', height: '100%', objectFit: 'cover' },
  corner: {
    position: 'absolute', width: 30, height: 30,
    borderTop: '3px solid #fff', borderLeft: '3px solid #fff',
  },
  guideOverlay: {
    position: 'absolute', top: 0, left: 0, right: 0,
    padding: '12px 16px', textAlign: 'center',
  },
  guideText: {
    color: '#fff', fontSize: 14, fontWeight: 600,
    textShadow: '0 1px 4px rgba(0,0,0,0.5)',
    backgroundColor: 'rgba(0,0,0,0.3)', padding: '4px 12px',
    borderRadius: 8,
  },
  cameraControls: {
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
  },
  captureBtn: {
    width: 64, height: 64, borderRadius: 32, border: '4px solid #6366f1',
    backgroundColor: 'transparent', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 0,
  },
  captureBtnInner: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: '#6366f1',
    transition: 'transform 0.1s',
  },
  cameraFallback: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: 40, gap: 8,
  },

  // Preview
  previewHeader: { marginBottom: 16 },
  pagesGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
    gap: 12, marginBottom: 16,
  },
  pageCard: {
    position: 'relative', borderRadius: 10, overflow: 'hidden',
    border: '1px solid #e2e8f0', cursor: 'pointer', aspectRatio: '3/4',
    transition: 'box-shadow 0.2s',
  },
  pageImg: { width: '100%', height: '100%', objectFit: 'cover' },
  pageLabel: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: 'rgba(0,0,0,0.6)', color: '#fff',
    padding: '4px 8px', fontSize: 12, fontWeight: 600,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  addPageCard: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', gap: 6,
    border: '2px dashed #6366f1', borderRadius: 10,
    cursor: 'pointer', aspectRatio: '3/4',
    backgroundColor: 'rgba(99,102,241,0.04)',
    transition: 'background-color 0.2s',
  },

  // Results
  resultsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  scoreCard: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: 20,
    borderRadius: 12, border: '1px solid #e2e8f0',
  },
  sectionCard: {
    padding: 16, borderRadius: 12, border: '1px solid #e2e8f0',
  },
  cardTitle: { fontSize: 14, fontWeight: 700, margin: '0 0 12px', color: '#1e293b' },
  sectionRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 0', borderBottom: '1px solid #f1f5f9',
  },
  progressBar: {
    width: 80, height: 6, backgroundColor: '#f1f5f9', borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', borderRadius: 3, transition: 'width 0.5s' },

  // Skills
  skillsWrap: { display: 'flex', flexWrap: 'wrap', gap: 6 },
  skillChip: {
    padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
  },

  // OCR text
  ocrPre: {
    backgroundColor: '#f8fafc', border: '1px solid #e2e8f0',
    borderRadius: 8, padding: 12, fontSize: 12, lineHeight: 1.5,
    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    maxHeight: 200, overflow: 'auto', marginTop: 8,
  },

  // Buttons
  actionsRow: { display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' },
  primaryBtn: {
    display: 'flex', alignItems: 'center', gap: 8,
    backgroundColor: '#6366f1', color: '#fff',
    border: 'none', borderRadius: 10, padding: '10px 20px',
    fontSize: 14, fontWeight: 600, cursor: 'pointer',
  },
  outlineBtn: {
    display: 'flex', alignItems: 'center', gap: 8,
    backgroundColor: 'transparent', color: '#6366f1',
    border: '1.5px solid #6366f1', borderRadius: 10, padding: '10px 20px',
    fontSize: 14, fontWeight: 600, cursor: 'pointer',
  },
  dangerBtn: {
    display: 'flex', alignItems: 'center', gap: 8,
    backgroundColor: 'transparent', color: '#ef4444',
    border: '1.5px solid #ef4444', borderRadius: 10, padding: '10px 20px',
    fontSize: 14, fontWeight: 600, cursor: 'pointer',
  },
  errorBox: {
    display: 'flex', alignItems: 'center', gap: 8,
    backgroundColor: '#fee2e2', color: '#dc2626',
    padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 500,
    marginBottom: 16,
  },
  centerBox: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: 60,
  },
}
