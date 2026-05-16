import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import useWebSocketProgress from '../hooks/useWebSocketProgress'
import './BatchUploadProgress.css'

/**
 * Real-time batch upload progress tracker with WebSocket
 * Shows file processing, percentage, and current status
 */
export const BatchUploadProgress = ({ taskId, onComplete = null }) => {
  const { progress, status, error, isConnected, disconnect } =
    useWebSocketProgress(taskId)
  const [showDetails, setShowDetails] = useState(false)

  // Call onComplete when task finishes
  useEffect(() => {
    if (status === 'SUCCESS' || status === 'FAILURE') {
      if (onComplete) {
        onComplete(status, progress)
      }
    }
  }, [status, progress, onComplete])

  if (!taskId) {
    return (
      <div className="batch-upload-progress error">
        <p>No task ID provided</p>
      </div>
    )
  }

  return (
    <div className="batch-upload-progress">
      {/* Header */}
      <div className="bup-header">
        <div className="bup-title">
          <span className="bup-status-badge" data-status={status}>
            {status === 'PENDING' && '⏳'}
            {status === 'PROGRESS' && '🔄'}
            {status === 'SUCCESS' && '✅'}
            {status === 'FAILURE' && '❌'}
          </span>
          <h3>Batch Upload Progress</h3>
          {!isConnected && <span className="bup-warning">(Offline)</span>}
        </div>
        <button
          className="bup-toggle-details"
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? '▼' : '▶'} Details
        </button>
      </div>

      {/* Main Progress Bar */}
      {progress && (
        <div className="bup-progress-section">
          {/* Percentage */}
          <div className="bup-percentage">
            <motion.div
              className="bup-percentage-value"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5 }}
            >
              {Math.round(progress.percent)}%
            </motion.div>
          </div>

          {/* Progress Bar */}
          <div className="bup-progress-bar">
            <motion.div
              className="bup-progress-fill"
              initial={{ width: 0 }}
              animate={{ width: `${progress.percent}%` }}
              transition={{ duration: 0.3 }}
              data-status={status}
            />
          </div>

          {/* Stats */}
          <div className="bup-stats">
            <span>
              {progress.processed} / {progress.total} files processed
            </span>
            <span className="bup-status-text">{status}</span>
          </div>

          {/* Current File */}
          {progress.currentFile && (
            <div className="bup-current-file">
              <span className="bup-label">Processing:</span>
              <motion.span
                className="bup-filename"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                key={progress.currentFile}
              >
                {progress.currentFile}
              </motion.span>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <motion.div
          className="bup-error"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <strong>Error:</strong> {error}
        </motion.div>
      )}

      {/* Details Section */}
      <AnimatePresence>
        {showDetails && progress && (
          <motion.div
            className="bup-details"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <div className="bup-detail-row">
              <span className="bup-label">Status:</span>
              <code>{progress.status}</code>
            </div>
            <div className="bup-detail-row">
              <span className="bup-label">Processed:</span>
              <code>{progress.processed}</code>
            </div>
            <div className="bup-detail-row">
              <span className="bup-label">Total:</span>
              <code>{progress.total}</code>
            </div>
            <div className="bup-detail-row">
              <span className="bup-label">Percent:</span>
              <code>{progress.percent.toFixed(2)}%</code>
            </div>
            {progress.currentFile && (
              <div className="bup-detail-row">
                <span className="bup-label">Current File:</span>
                <code>{progress.currentFile}</code>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Action Buttons */}
      <div className="bup-actions">
        {(status === 'SUCCESS' || status === 'FAILURE') && (
          <button className="bup-btn bup-btn-primary" onClick={disconnect}>
            Close
          </button>
        )}
        {!isConnected && (
          <button className="bup-btn bup-btn-secondary">
            Connection Lost - Refresh to Reconnect
          </button>
        )}
      </div>
    </div>
  )
}

export default BatchUploadProgress
