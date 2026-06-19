import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Hook for real-time WebSocket batch upload progress tracking
 * @param {string} taskId - Celery task ID
 * @param {string} baseUrl - API base URL (e.g., ws://localhost:8001)
 * @returns {Object} Progress state and handlers
 */
export const useWebSocketProgress = (taskId, baseUrl = null, authToken = null) => {
  const [progress, setProgress] = useState(null)
  const [status, setStatus] = useState('PENDING')
  const [error, setError] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)

  const url = baseUrl || window.location.origin.replace('http', 'ws')

  const connect = useCallback(() => {
    if (!taskId) {
      setError('No task ID provided')
      return
    }

    try {
      if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
        wsRef.current.close()
      }
      const params = authToken ? `?token=${encodeURIComponent(authToken)}` : ''
      const wsUrl = `${url}/api/v1/recruiter/ws/batch-upload/${taskId}${params}`
      console.log(`[WebSocket] Connecting to ${wsUrl}`)

      const websocket = new WebSocket(wsUrl)
      wsRef.current = websocket

      websocket.onopen = () => {
        console.log('[WebSocket] Connected')
        setIsConnected(true)
        setError(null)
      }

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[WebSocket] Received:', data)

          if (data.error) {
            setError(data.error)
          } else {
            setProgress({
              status: data.status,
              processed: data.processed || 0,
              total: data.total || 0,
              percent: data.percent || 0,
              currentFile: data.current_file || null,
            })
            setStatus(data.status)

            // Close when done
            if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
              websocket.close()
            }
          }
        } catch (e) {
          console.error('[WebSocket] Parse error:', e)
          setError(`Parse error: ${e.message}`)
        }
      }

      websocket.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        setError('WebSocket error occurred')
        setIsConnected(false)
      }

      websocket.onclose = () => {
        console.log('[WebSocket] Disconnected')
        if (wsRef.current === websocket) {
          wsRef.current = null
        }
        setIsConnected(false)
      }
    } catch (e) {
      console.error('[WebSocket] Connection error:', e)
      setError(e.message)
    }
  }, [taskId, url, authToken])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [taskId, connect, disconnect])

  return {
    progress,
    status,
    error,
    isConnected,
    disconnect,
    reconnect: connect,
  }
}

export default useWebSocketProgress
