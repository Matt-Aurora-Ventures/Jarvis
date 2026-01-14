import React, { createContext, useContext, useCallback, useEffect, useState, useRef } from 'react'

/**
 * WebSocket Context - Global WebSocket state management
 *
 * Provides:
 * - Centralized connection management
 * - Subscription sharing across components
 * - Connection state broadcasting
 * - Automatic reconnection
 * - Price and market data caching
 */

// Connection states
export const WS_STATE = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error',
}

// Create context
const WebSocketContext = createContext(null)

// Default WebSocket URL
const DEFAULT_WS_URL = `ws://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8766`

/**
 * WebSocket Provider Component
 */
export function WebSocketProvider({
  children,
  wsUrl = DEFAULT_WS_URL,
  autoConnect = true,
  reconnectDelay = 1000,
  maxReconnectDelay = 30000,
  maxReconnectAttempts = 20,
}) {
  // Connection state
  const [connectionState, setConnectionState] = useState(WS_STATE.DISCONNECTED)
  const [error, setError] = useState(null)

  // Data state (shared across all subscribers)
  const [prices, setPrices] = useState({})
  const [trades, setTrades] = useState({})
  const [orderBooks, setOrderBooks] = useState({})

  // Statistics
  const [stats, setStats] = useState({
    messagesReceived: 0,
    lastMessageTime: null,
    reconnectCount: 0,
    connectedAt: null,
    subscriptions: [],
  })

  // Refs
  const wsRef = useRef(null)
  const subscriptionsRef = useRef(new Set())
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(reconnectDelay)
  const reconnectCountRef = useRef(0)
  const mountedRef = useRef(true)
  const listenersRef = useRef(new Map()) // Component-specific listeners

  // Handle incoming messages
  const handleMessage = useCallback((event) => {
    try {
      const message = JSON.parse(event.data)
      if (!mountedRef.current) return

      // Update stats
      setStats(prev => ({
        ...prev,
        messagesReceived: prev.messagesReceived + 1,
        lastMessageTime: new Date().toISOString(),
      }))

      // Route message to appropriate handler
      switch (message.type) {
        case 'price_update':
          if (message.data?.token) {
            setPrices(prev => ({
              ...prev,
              [message.data.token]: message.data,
            }))
          }
          break

        case 'trade':
          if (message.data?.token) {
            setTrades(prev => {
              const tokenTrades = prev[message.data.token] || []
              return {
                ...prev,
                [message.data.token]: [...tokenTrades, message.data].slice(-100),
              }
            })
          }
          break

        case 'orderbook':
          if (message.data?.token) {
            setOrderBooks(prev => ({
              ...prev,
              [message.data.token]: message.data,
            }))
          }
          break

        case 'connected':
          console.log('[WebSocket] Server connected:', message.message)
          break

        case 'subscribed':
          console.log('[WebSocket] Subscribed:', message.tokens)
          setStats(prev => ({
            ...prev,
            subscriptions: message.tokens,
          }))
          break

        case 'error':
          console.error('[WebSocket] Server error:', message.message)
          setError(message.message)
          break
      }

      // Notify component-specific listeners
      listenersRef.current.forEach((callback, id) => {
        try {
          callback(message)
        } catch (err) {
          console.error(`[WebSocket] Listener ${id} error:`, err)
        }
      })

    } catch (err) {
      console.error('[WebSocket] Parse error:', err)
    }
  }, [])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return true
    }

    setConnectionState(WS_STATE.CONNECTING)

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setConnectionState(WS_STATE.CONNECTED)
        setError(null)
        reconnectDelayRef.current = reconnectDelay
        reconnectCountRef.current = 0

        setStats(prev => ({
          ...prev,
          connectedAt: new Date().toISOString(),
          reconnectCount: 0,
        }))

        // Re-subscribe to all tokens
        if (subscriptionsRef.current.size > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            tokens: Array.from(subscriptionsRef.current),
          }))
        }
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        setError('Connection error')
        setConnectionState(WS_STATE.ERROR)
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setConnectionState(WS_STATE.DISCONNECTED)
        wsRef.current = null

        // Schedule reconnection
        if (mountedRef.current && reconnectCountRef.current < maxReconnectAttempts) {
          setConnectionState(WS_STATE.RECONNECTING)
          reconnectCountRef.current++

          setStats(prev => ({
            ...prev,
            reconnectCount: reconnectCountRef.current,
          }))

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(
              reconnectDelayRef.current * 1.5,
              maxReconnectDelay
            )
            connect()
          }, reconnectDelayRef.current)
        }
      }

      wsRef.current = ws
      return true
    } catch (err) {
      console.error('[WebSocket] Connection failed:', err)
      setError(err.message)
      setConnectionState(WS_STATE.ERROR)
      return false
    }
  }, [wsUrl, handleMessage, reconnectDelay, maxReconnectDelay, maxReconnectAttempts])

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setConnectionState(WS_STATE.DISCONNECTED)
  }, [])

  // Subscribe to tokens
  const subscribe = useCallback((tokens) => {
    const tokenArray = Array.isArray(tokens) ? tokens : [tokens]
    tokenArray.forEach(t => subscriptionsRef.current.add(t))

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        tokens: tokenArray,
      }))
    }
  }, [])

  // Unsubscribe from tokens
  const unsubscribe = useCallback((tokens) => {
    const tokenArray = Array.isArray(tokens) ? tokens : [tokens]
    tokenArray.forEach(t => subscriptionsRef.current.delete(t))

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'unsubscribe',
        tokens: tokenArray,
      }))
    }
  }, [])

  // Send raw message
  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof message === 'string' ? message : JSON.stringify(message))
      return true
    }
    return false
  }, [])

  // Add message listener (for components that need raw messages)
  const addListener = useCallback((id, callback) => {
    listenersRef.current.set(id, callback)
    return () => listenersRef.current.delete(id)
  }, [])

  // Remove listener
  const removeListener = useCallback((id) => {
    listenersRef.current.delete(id)
  }, [])

  // Manual refresh
  const refresh = useCallback(() => {
    disconnect()
    reconnectDelayRef.current = reconnectDelay
    reconnectCountRef.current = 0
    setTimeout(connect, 100)
  }, [disconnect, connect, reconnectDelay])

  // Auto-connect on mount
  useEffect(() => {
    mountedRef.current = true
    if (autoConnect) {
      connect()
    }
    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [autoConnect])

  // Context value
  const value = {
    // Connection state
    connectionState,
    isConnected: connectionState === WS_STATE.CONNECTED,
    isReconnecting: connectionState === WS_STATE.RECONNECTING,
    error,
    stats,

    // Data (cached)
    prices,
    trades,
    orderBooks,

    // Actions
    connect,
    disconnect,
    refresh,
    subscribe,
    unsubscribe,
    send,

    // Listeners
    addListener,
    removeListener,

    // Current subscriptions
    subscriptions: Array.from(subscriptionsRef.current),
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

/**
 * useWebSocket - Hook to access WebSocket context
 */
export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

/**
 * useTokenPrice - Hook to subscribe and get price for a token
 */
export function useTokenPrice(token) {
  const { prices, subscribe, unsubscribe, isConnected } = useWebSocket()

  useEffect(() => {
    if (token && isConnected) {
      subscribe(token)
    }
    return () => {
      if (token) {
        unsubscribe(token)
      }
    }
  }, [token, isConnected, subscribe, unsubscribe])

  return prices[token] || null
}

/**
 * useMultipleTokenPrices - Hook to subscribe to multiple tokens
 */
export function useMultipleTokenPrices(tokens = []) {
  const { prices, subscribe, unsubscribe, isConnected } = useWebSocket()

  useEffect(() => {
    if (tokens.length > 0 && isConnected) {
      subscribe(tokens)
    }
    return () => {
      if (tokens.length > 0) {
        unsubscribe(tokens)
      }
    }
  }, [JSON.stringify(tokens), isConnected, subscribe, unsubscribe])

  return tokens.reduce((acc, token) => {
    acc[token] = prices[token] || null
    return acc
  }, {})
}

/**
 * WebSocket Status Component
 */
export function WebSocketStatus({ showDetails = false, className = '' }) {
  const { connectionState, stats, error } = useWebSocket()

  const statusColors = {
    [WS_STATE.CONNECTED]: 'bg-green-500',
    [WS_STATE.CONNECTING]: 'bg-yellow-500 animate-pulse',
    [WS_STATE.RECONNECTING]: 'bg-yellow-500 animate-pulse',
    [WS_STATE.DISCONNECTED]: 'bg-gray-500',
    [WS_STATE.ERROR]: 'bg-red-500',
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`w-2 h-2 rounded-full ${statusColors[connectionState]}`} />

      {showDetails && (
        <div className="text-xs text-gray-400">
          <span className="capitalize">{connectionState}</span>
          {stats.messagesReceived > 0 && (
            <span className="ml-2">({stats.messagesReceived} msgs)</span>
          )}
          {error && (
            <span className="ml-2 text-red-400">({error})</span>
          )}
        </div>
      )}
    </div>
  )
}

export default WebSocketContext
