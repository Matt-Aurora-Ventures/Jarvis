import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

/**
 * Market Data Stream Types
 */
export const StreamType = {
  PRICE: 'price',
  TRADES: 'trades',
  ORDERBOOK: 'orderbook',
  CANDLES: 'candles',
  LIQUIDATIONS: 'liquidations',
}

/**
 * Connection states
 */
export const ConnectionState = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error',
}

/**
 * useMarketDataStream - Comprehensive real-time market data
 *
 * Features:
 * - Multi-token subscriptions
 * - Multiple data types (price, trades, orderbook)
 * - Connection state management
 * - Automatic reconnection with backoff
 * - Data aggregation and caching
 * - Memory-efficient circular buffers
 */
export function useMarketDataStream(options = {}) {
  const {
    wsUrl = `ws://${window.location.hostname}:8766`,
    maxTradeHistory = 100,
    maxCandleHistory = 300,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    maxReconnectAttempts = 20,
    enabled = true,
  } = options

  // State
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED)
  const [subscriptions, setSubscriptions] = useState(new Set())
  const [prices, setPrices] = useState({})
  const [trades, setTrades] = useState({})
  const [orderBooks, setOrderBooks] = useState({})
  const [candles, setCandles] = useState({})
  const [stats, setStats] = useState({
    messagesReceived: 0,
    lastMessageTime: null,
    reconnectCount: 0,
    uptime: 0,
  })
  const [error, setError] = useState(null)

  // Refs
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(reconnectDelay)
  const reconnectCountRef = useRef(0)
  const mountedRef = useRef(true)
  const startTimeRef = useRef(null)
  const uptimeIntervalRef = useRef(null)

  // Handle incoming message
  const handleMessage = useCallback((event) => {
    try {
      const message = JSON.parse(event.data)
      if (!mountedRef.current) return

      setStats(prev => ({
        ...prev,
        messagesReceived: prev.messagesReceived + 1,
        lastMessageTime: new Date().toISOString(),
      }))

      switch (message.type) {
        case 'price_update':
          handlePriceUpdate(message.data)
          break
        case 'trade':
          handleTradeUpdate(message.data)
          break
        case 'orderbook':
          handleOrderBookUpdate(message.data)
          break
        case 'candle':
          handleCandleUpdate(message.data)
          break
        case 'connected':
          console.log('[MarketData] Connected:', message.message)
          break
        case 'subscribed':
          console.log('[MarketData] Subscribed to:', message.tokens)
          break
        case 'error':
          console.error('[MarketData] Error:', message.message)
          setError(message.message)
          break
        default:
          console.debug('[MarketData] Unknown message type:', message.type)
      }
    } catch (err) {
      console.error('[MarketData] Parse error:', err)
    }
  }, [])

  // Price update handler
  const handlePriceUpdate = useCallback((data) => {
    if (!data || !data.token) return

    setPrices(prev => ({
      ...prev,
      [data.token]: {
        price: data.price,
        priceChange1h: data.priceChange1h,
        priceChange24h: data.priceChange24h,
        volume24h: data.volume24h,
        liquidity: data.liquidity,
        marketCap: data.marketCap,
        timestamp: data.timestamp || new Date().toISOString(),
        high24h: data.high24h,
        low24h: data.low24h,
      }
    }))
  }, [])

  // Trade update handler (circular buffer)
  const handleTradeUpdate = useCallback((data) => {
    if (!data || !data.token) return

    setTrades(prev => {
      const tokenTrades = prev[data.token] || []
      const newTrade = {
        id: data.id || Date.now(),
        price: data.price,
        amount: data.amount,
        side: data.side, // 'buy' or 'sell'
        timestamp: data.timestamp || new Date().toISOString(),
        value: data.price * data.amount,
      }

      // Circular buffer - keep max history
      const updated = [...tokenTrades, newTrade].slice(-maxTradeHistory)

      return {
        ...prev,
        [data.token]: updated,
      }
    })
  }, [maxTradeHistory])

  // Order book update handler
  const handleOrderBookUpdate = useCallback((data) => {
    if (!data || !data.token) return

    setOrderBooks(prev => ({
      ...prev,
      [data.token]: {
        bids: data.bids || [], // [[price, amount], ...]
        asks: data.asks || [],
        spread: data.spread,
        midPrice: data.midPrice,
        timestamp: data.timestamp || new Date().toISOString(),
      }
    }))
  }, [])

  // Candle update handler (circular buffer)
  const handleCandleUpdate = useCallback((data) => {
    if (!data || !data.token) return

    setCandles(prev => {
      const tokenCandles = prev[data.token] || {}
      const interval = data.interval || '1m'
      const candleList = tokenCandles[interval] || []

      const newCandle = {
        time: data.time,
        open: data.open,
        high: data.high,
        low: data.low,
        close: data.close,
        volume: data.volume,
      }

      // Update last candle or append new one
      const lastCandle = candleList[candleList.length - 1]
      let updated

      if (lastCandle && lastCandle.time === newCandle.time) {
        // Update existing candle
        updated = [...candleList.slice(0, -1), newCandle]
      } else {
        // Append new candle (circular buffer)
        updated = [...candleList, newCandle].slice(-maxCandleHistory)
      }

      return {
        ...prev,
        [data.token]: {
          ...tokenCandles,
          [interval]: updated,
        }
      }
    })
  }, [maxCandleHistory])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!enabled) return

    setConnectionState(ConnectionState.CONNECTING)

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[MarketData] WebSocket connected')
        setConnectionState(ConnectionState.CONNECTED)
        setError(null)
        reconnectDelayRef.current = reconnectDelay
        reconnectCountRef.current = 0
        startTimeRef.current = Date.now()

        // Start uptime counter
        uptimeIntervalRef.current = setInterval(() => {
          if (startTimeRef.current) {
            setStats(prev => ({
              ...prev,
              uptime: Math.floor((Date.now() - startTimeRef.current) / 1000),
            }))
          }
        }, 1000)

        // Re-subscribe to all tokens
        if (subscriptions.size > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            tokens: Array.from(subscriptions),
          }))
        }
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        console.error('[MarketData] WebSocket error:', event)
        setError('WebSocket connection error')
        setConnectionState(ConnectionState.ERROR)
      }

      ws.onclose = () => {
        console.log('[MarketData] WebSocket disconnected')
        setConnectionState(ConnectionState.DISCONNECTED)
        wsRef.current = null

        // Clear uptime counter
        if (uptimeIntervalRef.current) {
          clearInterval(uptimeIntervalRef.current)
        }

        // Schedule reconnection
        if (mountedRef.current && enabled && reconnectCountRef.current < maxReconnectAttempts) {
          setConnectionState(ConnectionState.RECONNECTING)
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
    } catch (err) {
      console.error('[MarketData] Connection failed:', err)
      setError(err.message)
      setConnectionState(ConnectionState.ERROR)
    }
  }, [enabled, wsUrl, handleMessage, subscriptions, reconnectDelay, maxReconnectDelay, maxReconnectAttempts])

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (uptimeIntervalRef.current) {
      clearInterval(uptimeIntervalRef.current)
      uptimeIntervalRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setConnectionState(ConnectionState.DISCONNECTED)
  }, [])

  // Subscribe to tokens
  const subscribe = useCallback((tokens) => {
    const tokenArray = Array.isArray(tokens) ? tokens : [tokens]

    setSubscriptions(prev => {
      const updated = new Set(prev)
      tokenArray.forEach(t => updated.add(t))
      return updated
    })

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

    setSubscriptions(prev => {
      const updated = new Set(prev)
      tokenArray.forEach(t => updated.delete(t))
      return updated
    })

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

  // Manual refresh
  const refresh = useCallback(() => {
    disconnect()
    reconnectDelayRef.current = reconnectDelay
    reconnectCountRef.current = 0
    setTimeout(connect, 100)
  }, [disconnect, connect, reconnectDelay])

  // Mount/unmount
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

  // Computed values
  const isConnected = connectionState === ConnectionState.CONNECTED
  const isReconnecting = connectionState === ConnectionState.RECONNECTING

  return {
    // Connection
    connectionState,
    isConnected,
    isReconnecting,
    error,
    stats,

    // Data
    prices,
    trades,
    orderBooks,
    candles,

    // Actions
    subscribe,
    unsubscribe,
    send,
    refresh,
    disconnect,
    connect,

    // Subscriptions
    subscriptions: Array.from(subscriptions),
  }
}

/**
 * useTokenStream - Single token convenience hook
 */
export function useTokenStream(token, options = {}) {
  const stream = useMarketDataStream(options)

  // Auto-subscribe to token
  useEffect(() => {
    if (token && stream.isConnected) {
      stream.subscribe(token)
    }
    return () => {
      if (token) {
        stream.unsubscribe(token)
      }
    }
  }, [token, stream.isConnected])

  const price = token ? stream.prices[token] : null
  const tokenTrades = token ? stream.trades[token] || [] : []
  const orderBook = token ? stream.orderBooks[token] : null
  const tokenCandles = token ? stream.candles[token] : {}

  // Calculate derived metrics
  const metrics = useMemo(() => {
    if (!price) return null

    const recentTrades = tokenTrades.slice(-10)
    const buyVolume = recentTrades.filter(t => t.side === 'buy').reduce((sum, t) => sum + t.value, 0)
    const sellVolume = recentTrades.filter(t => t.side === 'sell').reduce((sum, t) => sum + t.value, 0)

    return {
      lastPrice: price.price,
      change1h: price.priceChange1h,
      change24h: price.priceChange24h,
      volume24h: price.volume24h,
      liquidity: price.liquidity,
      buyPressure: buyVolume > 0 ? buyVolume / (buyVolume + sellVolume) * 100 : 50,
      sellPressure: sellVolume > 0 ? sellVolume / (buyVolume + sellVolume) * 100 : 50,
      tradeCount: tokenTrades.length,
      spread: orderBook?.spread || 0,
    }
  }, [price, tokenTrades, orderBook])

  return {
    // Connection
    isConnected: stream.isConnected,
    connectionState: stream.connectionState,
    error: stream.error,

    // Data
    price,
    trades: tokenTrades,
    orderBook,
    candles: tokenCandles,
    metrics,

    // Actions
    refresh: stream.refresh,
  }
}

/**
 * useMultiTokenStream - Multiple tokens convenience hook
 */
export function useMultiTokenStream(tokens = [], options = {}) {
  const stream = useMarketDataStream(options)

  // Auto-subscribe to tokens
  useEffect(() => {
    if (tokens.length > 0 && stream.isConnected) {
      stream.subscribe(tokens)
    }
    return () => {
      if (tokens.length > 0) {
        stream.unsubscribe(tokens)
      }
    }
  }, [JSON.stringify(tokens), stream.isConnected])

  // Get prices for all tokens
  const tokenPrices = useMemo(() => {
    return tokens.reduce((acc, token) => {
      acc[token] = stream.prices[token] || null
      return acc
    }, {})
  }, [tokens, stream.prices])

  // Sort tokens by various criteria
  const sortedByChange = useMemo(() => {
    return [...tokens].sort((a, b) => {
      const changeA = stream.prices[a]?.priceChange24h || 0
      const changeB = stream.prices[b]?.priceChange24h || 0
      return changeB - changeA
    })
  }, [tokens, stream.prices])

  const sortedByVolume = useMemo(() => {
    return [...tokens].sort((a, b) => {
      const volA = stream.prices[a]?.volume24h || 0
      const volB = stream.prices[b]?.volume24h || 0
      return volB - volA
    })
  }, [tokens, stream.prices])

  // Aggregate stats
  const aggregateStats = useMemo(() => {
    let totalVolume = 0
    let gainers = 0
    let losers = 0
    let unchanged = 0

    tokens.forEach(token => {
      const price = stream.prices[token]
      if (price) {
        totalVolume += price.volume24h || 0
        const change = price.priceChange24h || 0
        if (change > 0) gainers++
        else if (change < 0) losers++
        else unchanged++
      }
    })

    return {
      totalVolume,
      gainers,
      losers,
      unchanged,
      totalTokens: tokens.length,
      connectedTokens: Object.keys(stream.prices).length,
    }
  }, [tokens, stream.prices])

  return {
    // Connection
    isConnected: stream.isConnected,
    connectionState: stream.connectionState,
    error: stream.error,
    stats: stream.stats,

    // Data
    prices: tokenPrices,
    allPrices: stream.prices,

    // Sorted views
    sortedByChange,
    sortedByVolume,

    // Aggregate
    aggregateStats,

    // Actions
    subscribe: stream.subscribe,
    unsubscribe: stream.unsubscribe,
    refresh: stream.refresh,
  }
}

export default useMarketDataStream
