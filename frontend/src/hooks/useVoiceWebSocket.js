import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useVoiceWebSocket - Real-time voice status updates via WebSocket
 *
 * Features:
 * - Real-time voice status (listening, speaking, processing)
 * - Live transcription display
 * - Automatic reconnection
 * - Voice capability detection
 *
 * @param {object} options - Configuration options
 */
export function useVoiceWebSocket(options = {}) {
  const {
    wsUrl = `ws://${window.location.hostname}:8766/ws/voice`,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    enabled = true,
  } = options

  const [status, setStatus] = useState({
    enabled: false,
    listening: false,
    speaking: false,
    processing: false,
    tts_available: false,
    stt_available: false,
    microphone_available: false,
    wake_word_enabled: false,
  })
  const [transcript, setTranscript] = useState('')
  const [transcriptHistory, setTranscriptHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)

  // Refs
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(reconnectDelay)
  const mountedRef = useRef(true)

  // Handle incoming WebSocket message
  const handleMessage = useCallback((event) => {
    try {
      const message = JSON.parse(event.data)

      if (!mountedRef.current) return

      switch (message.type) {
        case 'voice_status':
          setStatus(prev => ({ ...prev, ...message.data }))
          setError(null)
          break

        case 'voice_transcript':
          const { text, is_final } = message.data
          setTranscript(text)
          if (is_final && text) {
            setTranscriptHistory(prev => [...prev.slice(-19), {
              text,
              timestamp: Date.now(),
            }])
          }
          break

        case 'voice_response':
          // Jarvis is speaking
          setStatus(prev => ({ ...prev, speaking: true }))
          break

        case 'voice_response_end':
          setStatus(prev => ({ ...prev, speaking: false }))
          break

        case 'pong':
          // Heartbeat response
          break

        case 'error':
          console.error('Voice WebSocket error:', message.data)
          setError(message.data?.message || 'Voice error')
          break

        default:
          console.log('Unknown voice message type:', message.type)
      }
    } catch (err) {
      console.error('Failed to parse voice WebSocket message:', err)
    }
  }, [])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!enabled) return

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('Voice WebSocket connected')
        setConnected(true)
        setError(null)
        reconnectDelayRef.current = reconnectDelay

        // Request initial status
        ws.send('status')
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        console.error('Voice WebSocket error:', event)
        setError('Voice connection error')
      }

      ws.onclose = () => {
        console.log('Voice WebSocket disconnected')
        setConnected(false)
        wsRef.current = null

        // Reset status on disconnect
        setStatus(prev => ({
          ...prev,
          listening: false,
          speaking: false,
          processing: false,
        }))

        // Schedule reconnection
        if (mountedRef.current && enabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(
              reconnectDelayRef.current * 2,
              maxReconnectDelay
            )
            connect()
          }, reconnectDelayRef.current)
        }
      }

      wsRef.current = ws

      // Setup heartbeat
      const heartbeat = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)

      ws._heartbeat = heartbeat
    } catch (err) {
      console.error('Failed to create Voice WebSocket:', err)
      setError(err.message)
    }
  }, [enabled, wsUrl, handleMessage, reconnectDelay, maxReconnectDelay])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      if (wsRef.current._heartbeat) {
        clearInterval(wsRef.current._heartbeat)
      }
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  // Manual refresh (force reconnect)
  const refresh = useCallback(() => {
    disconnect()
    reconnectDelayRef.current = reconnectDelay
    connect()
  }, [disconnect, connect, reconnectDelay])

  // Request status update
  const requestStatus = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send('status')
    }
  }, [])

  // Setup WebSocket connection
  useEffect(() => {
    mountedRef.current = true

    if (enabled) {
      connect()
    }

    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [enabled])

  return {
    // Status
    status,
    isListening: status.listening,
    isSpeaking: status.speaking,
    isProcessing: status.processing,
    isEnabled: status.enabled,

    // Capabilities
    hasTTS: status.tts_available,
    hasSTT: status.stt_available,
    hasMicrophone: status.microphone_available,
    hasWakeWord: status.wake_word_enabled,

    // Transcription
    transcript,
    transcriptHistory,

    // Connection
    connected,
    error,

    // Actions
    refresh,
    requestStatus,
  }
}

/**
 * useVoiceStatus - Simplified hook just for voice status
 */
export function useVoiceStatus(options = {}) {
  const { status, connected, error, isListening, isSpeaking, isProcessing } = useVoiceWebSocket(options)

  return {
    ...status,
    connected,
    error,
    isActive: isListening || isSpeaking || isProcessing,
  }
}

export default useVoiceWebSocket
