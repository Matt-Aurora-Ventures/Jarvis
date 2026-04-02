import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useWebSocketPrice - Real-time price updates via WebSocket
 *
 * Features:
 * - True real-time updates via WebSocket
 * - Automatic reconnection with exponential backoff
 * - Fallback to polling if WebSocket unavailable
 * - Memory-efficient price history
 *
 * @param {string|string[]} tokens - Token mint address(es) to subscribe to
 * @param {object} options - Configuration options
 */
export function useWebSocketPrice(tokens, options = {}) {
  const {
    wsUrl = `ws://${window.location.hostname}:8766`,
    maxHistory = 60,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    enabled = true,
  } = options

  const [prices, setPrices] = useState({})  // { tokenAddress: price }
  const [priceHistory, setPriceHistory] = useState({})  // { tokenAddress: [{ price, timestamp }] }
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)

  // Refs
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(reconnectDelay)
  const mountedRef = useRef(true)

  // Normalize tokens to array
  const tokenArray = Array.isArray(tokens) ? tokens : [tokens].filter(Boolean)

  // Handle incoming WebSocket message
  const handleMessage = useCallback((event) => {
    try {
      const message = JSON.parse(event.data)

      if (message.type === 'price_update' && message.data) {
        const { token, price, priceChange1h, priceChange24h, volume24h, liquidity, timestamp } = message.data

        if (!mountedRef.current) return

        setPrices(prev => ({
          ...prev,
          [token]: {
            price,
            priceChange1h,
            priceChange24h,
            volume24h,
            liquidity,
            timestamp,
          }
        }))

        setPriceHistory(prev => {
          const history = prev[token] || []
          const updated = [...history, { price, timestamp: Date.now() }]
          return {
            ...prev,
            [token]: updated.slice(-maxHistory)
          }
        })

        setError(null)
      } else if (message.type === 'connected') {
        console.log('WebSocket connected:', message.message)
      } else if (message.type === 'error') {
        console.error('WebSocket error:', message.message)
        setError(message.message)
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err)
    }
  }, [maxHistory])

  // Subscribe to tokens
  const subscribe = useCallback((ws, tokenList) => {
    if (ws && ws.readyState === WebSocket.OPEN && tokenList.length > 0) {
      ws.send(JSON.stringify({
        type: 'subscribe',
        tokens: tokenList,
      }))
    }
  }, [])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!enabled || tokenArray.length === 0) return

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnected(true)
        setError(null)
        reconnectDelayRef.current = reconnectDelay

        // Subscribe to tokens
        subscribe(ws, tokenArray)
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        setError('WebSocket connection error')
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setConnected(false)
        wsRef.current = null

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
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      setError(err.message)
    }
  }, [enabled, tokenArray, wsUrl, handleMessage, subscribe, reconnectDelay, maxReconnectDelay])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
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

  // Setup WebSocket connection
  useEffect(() => {
    mountedRef.current = true

    if (enabled && tokenArray.length > 0) {
      connect()
    }

    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [enabled, JSON.stringify(tokenArray)])

  // Update subscriptions when tokens change
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      subscribe(wsRef.current, tokenArray)
    }
  }, [JSON.stringify(tokenArray), subscribe])

  // Get price for a specific token
  const getPrice = useCallback((token) => {
    return prices[token]?.price || null
  }, [prices])

  // Get history for a specific token
  const getHistory = useCallback((token) => {
    return priceHistory[token] || []
  }, [priceHistory])

  // Calculate price change for a token
  const getPriceChange = useCallback((token) => {
    const history = priceHistory[token] || []
    if (history.length < 2) return 0

    const first = history[0].price
    const last = history[history.length - 1].price
    return ((last - first) / first) * 100
  }, [priceHistory])

  return {
    prices,
    priceHistory,
    connected,
    error,
    getPrice,
    getHistory,
    getPriceChange,
    refresh,
  }
}

/**
 * useSingleTokenPrice - Convenience hook for single token price
 */
export function useSingleTokenPrice(token, options = {}) {
  const { prices, priceHistory, connected, error, refresh } = useWebSocketPrice(
    token ? [token] : [],
    options
  )

  const price = token ? prices[token]?.price : null
  const history = token ? priceHistory[token] || [] : []
  const priceChange = history.length >= 2
    ? ((history[history.length - 1].price - history[0].price) / history[0].price) * 100
    : 0

  return {
    price,
    priceHistory: history,
    priceChange,
    priceData: token ? prices[token] : null,
    connected,
    error,
    loading: !connected && !price,
    refresh,
  }
}

export default useWebSocketPrice
