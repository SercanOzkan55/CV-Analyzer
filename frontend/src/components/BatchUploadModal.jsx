import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { recruiterSaaSBatchUpload } from '../api'
import BatchUploadProgress from './BatchUploadProgress'
import {
  validateFileUploads,
  formatErrorMessage,
} from '../utils/recruiterErrorHandling'
import './BatchUploadModal.css'

/**
 * Modal for bulk CV upload to recruiter
 * Supports multiple file selection and real-time progress tracking
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback when modal closes
 * @param {function} onSuccess - Callback when upload completes successfully
 * @param {array} jobs - Available recruiter jobs for selection
 */
export const BatchUploadModal = ({ isOpen, onClose, onSuccess = null, jobs = [], token = null }) => {
  const inputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)

    const dropped = Array.from(e.dataTransfer.files)
    const validation = validateFileUploads([...files, ...dropped], {
      maxFiles: 50,
      maxSizeMB: 10,
      allowedTypes: ['application/pdf'],
    })

    if (!validation.valid) {
      setUploadError(validation.error)
      return
    }

    setFiles(validation.validFiles)
    setUploadError(null)
  }

  const handleBrowse = () => {
    inputRef.current?.click()
  }

  const handleInputChange = (e) => {
    const selected = Array.from(e.target.files || [])
    const validation = validateFileUploads([...files, ...selected], {
      maxFiles: 50,
      maxSizeMB: 10,
      allowedTypes: ['application/pdf'],
    })

    if (!validation.valid) {
      setUploadError(validation.error)
      return
    }

    setFiles(validation.validFiles)
    setUploadError(null)
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setUploadError('Please select at least one file')
      return
    }

    if (!selectedJobId) {
      setUploadError('Please select a job position')
      return
    }

    const validation = validateFileUploads(files, {
      maxFiles: 50,
      maxSizeMB: 10,
      allowedTypes: ['application/pdf'],
    })

    if (!validation.valid) {
      setUploadError(validation.error)
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      const response = await recruiterSaaSBatchUpload(token, selectedJobId, files)

      if (response.task_id) {
        setTaskId(response.task_id)
      } else {
        throw new Error('No task ID received')
      }
    } catch (error) {
      console.error('Upload error:', error)
      const errorMsg = await formatErrorMessage(error, 'Upload failed')
      setUploadError(errorMsg)
      setUploading(false)
    }
  }

  const handleUploadComplete = (status, progress) => {
    if (status === 'SUCCESS') {
      if (onSuccess) {
        onSuccess(progress)
      }
      // Close modal after 2 seconds
      setTimeout(() => {
        handleClose()
      }, 2000)
    }
  }

  const handleClose = () => {
    setFiles([])
    setTaskId(null)
    setUploading(false)
    setUploadError(null)
    onClose()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="batch-upload-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
        >
          <motion.div
            className="batch-upload-modal"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bum-header">
              <h2>Bulk Upload CVs</h2>
              <button
                className="bum-close"
                onClick={handleClose}
                disabled={uploading && !taskId}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div className="bum-content">
              {taskId ? (
                /* Progress View */
                <BatchUploadProgress
                  taskId={taskId}
                  onComplete={handleUploadComplete}
                />
              ) : (
                /* File Selection View */
                <div className="bum-file-selection">
                  {/* Job Selection */}
                  {jobs && jobs.length > 0 && (
                    <div className="bum-job-selection">
                      <label htmlFor="job-select" className="bum-job-label">
                        Select Job Position
                      </label>
                      <select
                        id="job-select"
                        className="bum-job-select"
                        value={selectedJobId || ''}
                        onChange={(e) =>
                          setSelectedJobId(e.target.value ? parseInt(e.target.value) : null)
                        }
                        disabled={uploading}
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
                    className={`bum-drop-zone ${dragOver ? 'drag-over' : ''}`}
                    onDrop={handleDrop}
                    onDragOver={(e) => {
                      e.preventDefault()
                      setDragOver(true)
                    }}
                    onDragLeave={() => setDragOver(false)}
                  >
                    <input
                      ref={inputRef}
                      type="file"
                      multiple
                      accept="application/pdf"
                      onChange={handleInputChange}
                      hidden
                    />

                    <div className="bum-drop-content">
                      <div className="bum-drop-icon">📁</div>
                      <p className="bum-drop-title">
                        Drag PDFs here or click to browse
                      </p>
                      <p className="bum-drop-subtitle">
                        Max 100 files per batch, PDF format only
                      </p>
                      <button
                        type="button"
                        className="bum-btn bum-btn-primary"
                        onClick={handleBrowse}
                      >
                        Select Files
                      </button>
                    </div>
                  </div>

                  {/* File List */}
                  {files.length > 0 && (
                    <div className="bum-file-list">
                      <h4>
                        Selected Files ({files.length}/100)
                      </h4>
                      <div className="bum-files">
                        {files.map((file, idx) => (
                          <motion.div
                            key={`${idx}-${file.name}`}
                            className="bum-file-item"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                          >
                            <span className="bum-file-icon">📄</span>
                            <div className="bum-file-info">
                              <span className="bum-file-name">
                                {file.name}
                              </span>
                              <span className="bum-file-size">
                                {(file.size / 1024).toFixed(1)} KB
                              </span>
                            </div>
                            <button
                              type="button"
                              className="bum-file-remove"
                              onClick={() => removeFile(idx)}
                            >
                              ✕
                            </button>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Error Display */}
                  {uploadError && (
                    <motion.div
                      className="bum-error"
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      {uploadError}
                    </motion.div>
                  )}
                </div>
              )}
            </div>

            {/* Footer Actions */}
            {!taskId && (
              <div className="bum-footer">
                <button
                  className="bum-btn bum-btn-secondary"
                  onClick={handleClose}
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  className="bum-btn bum-btn-primary"
                  onClick={handleUpload}
                  disabled={
                    files.length === 0 || !selectedJobId || uploading || files.length > 50
                  }
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default BatchUploadModal
