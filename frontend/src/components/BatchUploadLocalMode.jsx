import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../api'
import './BatchUploadLocalMode.css'

/**
 * Local mode batch upload - zero data retention.
 * Processes CVs and returns results for download.
 */
export const BatchUploadLocalMode = ({
  apiKey,
  jobs = [],
  onSuccess = null,
  onError = null
}) => {
  const inputRef = useRef(null)
  const linkedinInputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [uploadMode, setUploadMode] = useState('individual') // 'individual' or 'linkedin'

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)

    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.txt')
    )

    if (dropped.length === 0) {
      setError('Only PDF and TXT files are supported')
      return
    }

    setFiles((prev) => [...prev, ...dropped])
    setError(null)
  }

  const handleBrowse = () => {
    inputRef.current?.click()
  }

  const handleInputChange = (e) => {
    const selected = Array.from(e.target.files || []).filter((f) =>
      f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.txt')
    )

    if (selected.length === 0) {
      setError('Only PDF and TXT files are supported')
      return
    }

    setFiles((prev) => [...prev, ...selected])
    setError(null)
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleLinkedinZipSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Please select a ZIP file from LinkedIn export')
      return
    }

    setFiles([file]) // Only one ZIP file
    setError(null)
  }

  const handleProcess = async () => {
    if (files.length === 0) {
      setError('Please select files to process')
      return
    }

    if (!selectedJobId) {
      setError('Please select a job position')
      return
    }

    if (!apiKey) {
      setError('API key is required')
      return
    }

    setProcessing(true)
    setError(null)
    setResults(null)

    const formData = new FormData()
    formData.append('job_id', selectedJobId)

    if (uploadMode === 'linkedin') {
      // LinkedIn export processing
      formData.append('zip_file', files[0])

      try {
        const response = await api.post(
          '/recruiter/process-linkedin-export',
          formData,
          {
            headers: {
              'X-API-Key': apiKey,
              'Content-Type': 'multipart/form-data',
            },
          }
        )

        setResults(response.data)

        if (onSuccess) {
          onSuccess(response.data)
        }
      } catch (error) {
        console.error('LinkedIn processing error:', error)
        const errorMessage = error.response?.data?.detail ||
                            error.message ||
                            'LinkedIn export processing failed'
        setError(errorMessage)

        if (onError) {
          onError(error)
        }
      }
    } else {
      // Individual file processing
      if (files.length > 500) {
        setError('Maximum 500 files per upload')
        return
      }

      files.forEach((file) => {
        formData.append('files', file)
      })

      try {
        const response = await api.post(
          '/recruiter/process-local',
          formData,
          {
            headers: {
              'X-API-Key': apiKey,
              'Content-Type': 'multipart/form-data',
            },
          }
        )

        setResults(response.data)

        if (onSuccess) {
          onSuccess(response.data)
        }
      } catch (error) {
        console.error('Processing error:', error)
        const errorMessage = error.response?.data?.detail ||
                            error.message ||
                            'Processing failed'
        setError(errorMessage)

        if (onError) {
          onError(error)
        }
      }
    }

    setProcessing(false)
  }

  const downloadFile = (url, filename) => {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const resetForm = () => {
    setFiles([])
    setResults(null)
    setError(null)
    setSelectedJobId(null)
    setUploadMode('individual')
  }

  return (
    <div className="batch-upload-local">
      {/* Header */}
      <div className="bul-header">
        <h2>Local CV Processing</h2>
        <div className="bul-subtitle">
          Process CVs without saving data to our servers
        </div>
        {apiKey && (
          <div className="bul-api-key">
            API Key: <code>{apiKey.substring(0, 20)}...</code>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="bul-content">
        {/* Upload Mode Selector */}
        <div className="bul-mode-selector">
          <div className="bul-mode-tabs">
            <button
              className={`bul-mode-tab ${uploadMode === 'individual' ? 'active' : ''}`}
              onClick={() => {
                setUploadMode('individual')
                setFiles([])
                setError(null)
              }}
            >
              Individual CVs
            </button>
            <button
              className={`bul-mode-tab ${uploadMode === 'linkedin' ? 'active' : ''}`}
              onClick={() => {
                setUploadMode('linkedin')
                setFiles([])
                setError(null)
              }}
            >
              LinkedIn Export
            </button>
          </div>
        </div>

        {results ? (
          /* Results View */
          <motion.div
            className="bul-results"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h3>Processing Complete</h3>

            {/* Summary */}
            <div className="bul-summary">
              <div className="bul-stat">
                <span className="bul-stat-value">{results.summary.total_cvs}</span>
                <span className="bul-stat-label">CVs Processed</span>
              </div>
              <div className="bul-stat">
                <span className="bul-stat-value">{results.usage.remaining}</span>
                <span className="bul-stat-label">Monthly Remaining</span>
              </div>
            </div>

            {/* Top Results Preview */}
            <div className="bul-preview">
              <h4>Top Rankings</h4>
              <div className="bul-rankings">
                {results.results.slice(0, 5).map((result, idx) => (
                  <div key={idx} className="bul-ranking-item">
                    <span className="bul-rank">#{idx + 1}</span>
                    <span className="bul-filename">{result.filename}</span>
                    <span className="bul-score">
                      {result.final_score?.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Download Buttons */}
            <div className="bul-downloads">
              <button
                className="bul-btn bul-btn-primary"
                onClick={() => downloadFile(results.downloads.json, 'rankings.json')}
              >
                📄 Download JSON
              </button>
              <button
                className="bul-btn bul-btn-secondary"
                onClick={() => downloadFile(results.downloads.csv, 'rankings.csv')}
              >
                📊 Download CSV
              </button>
            </div>

            {/* Actions */}
            <div className="bul-actions">
              <button className="bul-btn bul-btn-outline" onClick={resetForm}>
                Process More CVs
              </button>
            </div>
          </motion.div>
        ) : (
          /* Upload View */
          <div className="bul-upload-section">
            {/* Job Selection */}
            {jobs && jobs.length > 0 && (
              <div className="bul-job-selection">
                <label htmlFor="job-select" className="bul-job-label">
                  Select Job Position
                </label>
                <select
                  id="job-select"
                  className="bul-job-select"
                  value={selectedJobId || ''}
                  onChange={(e) =>
                    setSelectedJobId(e.target.value ? parseInt(e.target.value) : null)
                  }
                  disabled={processing}
                >
                  <option value="">-- Choose a job --</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title || `Job ${job.id}`} ({job.salary_min || 'N/A'} - {job.salary_max || 'N/A'})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Drop Zone */}
            <div
              className={`bul-drop-zone ${dragOver ? 'drag-over' : ''}`}
              onDrop={uploadMode === 'individual' ? handleDrop : undefined}
              onDragOver={uploadMode === 'individual' ? (e) => {
                e.preventDefault()
                setDragOver(true)
              } : undefined}
              onDragLeave={uploadMode === 'individual' ? () => setDragOver(false) : undefined}
            >
              {uploadMode === 'individual' ? (
                <>
                  <input
                    ref={inputRef}
                    type="file"
                    multiple
                    accept="application/pdf,.txt,.docx"
                    onChange={handleInputChange}
                    hidden
                  />

                  <div className="bul-drop-content">
                    <div className="bul-drop-icon">📄</div>
                    <p className="bul-drop-title">
                      Drop CV Files Here
                    </p>
                    <p className="bul-drop-subtitle">
                      PDF, TXT, DOCX files supported (max 500 files)
                    </p>
                    <button
                      className="bul-browse-btn"
                      onClick={handleBrowse}
                      disabled={processing}
                    >
                      Browse Files
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <input
                    ref={linkedinInputRef}
                    type="file"
                    accept=".zip"
                    onChange={handleLinkedinZipSelect}
                    hidden
                  />

                  <div className="bul-drop-content">
                    <div className="bul-drop-icon">💼</div>
                    <p className="bul-drop-title">
                      LinkedIn Export ZIP
                    </p>
                    <p className="bul-drop-subtitle">
                      Upload ZIP file from LinkedIn Sales Navigator export
                    </p>
                    <button
                      className="bul-browse-btn"
                      onClick={() => linkedinInputRef.current?.click()}
                      disabled={processing}
                    >
                      Select ZIP File
                    </button>
                  </div>
                </>
              )}
            </div>
                </p>
                <button
                  type="button"
                  className="bul-btn bul-btn-primary"
                  onClick={handleBrowse}
                  disabled={processing}
                >
                  Select Files
                </button>
              </div>
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="bul-file-list">
                <h4>
                  {uploadMode === 'linkedin'
                    ? 'LinkedIn Export File'
                    : `Selected Files (${files.length}/500)`
                  }
                </h4>
                <div className="bul-files">
                  {files.map((file, idx) => (
                    <motion.div
                      key={`${idx}-${file.name}`}
                      className="bul-file-item"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                    >
                      <span className="bul-file-icon">
                        {uploadMode === 'linkedin' ? '💼' : '📄'}
                      </span>
                      <div className="bul-file-info">
                        <span className="bul-file-name">
                          {file.name}
                        </span>
                        <span className="bul-file-size">
                          {(file.size / 1024 / 1024).toFixed(1)} MB
                        </span>
                      </div>
                      <button
                        type="button"
                        className="bul-file-remove"
                        onClick={() => removeFile(idx)}
                        disabled={processing}
                      >
                        ✕
                      </button>
                    </motion.div>
                  ))}
                </div>
                {uploadMode === 'linkedin' && (
                  <div className="bul-linkedin-info">
                    <p>
                      💡 LinkedIn exports typically contain 50-500 CVs.
                      The ZIP will be processed automatically.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Error Display */}
            {error && (
              <motion.div
                className="bul-error"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                {error}
              </motion.div>
            )}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      {!results && (
        <div className="bul-footer">
          <button
            className="bul-btn bul-btn-secondary"
            onClick={resetForm}
            disabled={processing}
          >
            Clear
          </button>
          <button
            className="bul-btn bul-btn-primary"
            onClick={handleProcess}
            disabled={
              files.length === 0 || !selectedJobId || processing || !apiKey
            }
          >
            {processing ? 'Processing...' : 'Process CVs'}
          </button>
        </div>
      )}
    </div>
  )
}

export default BatchUploadLocalMode
