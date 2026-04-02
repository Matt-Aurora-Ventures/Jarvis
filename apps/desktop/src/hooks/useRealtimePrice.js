import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useRealtimePrice - High-performance real-time price updates
 *
 * Features:
 * - Update batching (flushes every 100ms to prevent UI thrashing)
 * - Request deduplication
 * - Automatic reconnection
 * - Memory-efficient price history
 *
 * @param {string} mint - Token mint address
 * @param {object} options - Configuration options
 */
export function useRealtimePrice(mint, options = {}) {
  const {
    refreshInterval = 2000,    // Poll every 2s
    batchInterval = 100,       // Batch UI updates every 100ms
    maxHistory = 60,           // Keep last 60 price points
    enabled = true,
  } = options

  const [price, setPrice] = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Refs for batching
  const pendingUpdate = useRef(null)
  const batchTimeoutRef = useRef(null)
  const lastFetchRef = useRef(0)

  // Batch update function - prevents UI thrashing
  const scheduleUpdate = useCallback((newPrice) => {
    pendingUpdate.current = newPrice

    if (!batchTimeoutRef.current) {
      batchTimeoutRef.current = setTimeout(() => {
        if (pendingUpdate.current !== null) {
          setPrice(pendingUpdate.current)
          setPriceHistory(prev => {
            const updated = [...prev, {
              price: pendingUpdate.current,
              timestamp: Date.now()
            }]
            // Keep only last N entries
            return updated.slice(-maxHistory)
          })
        }
        batchTimeoutRef.current = null
        pendingUpdate.current = null
      }, batchInterval)
    }
  }, [batchInterval, maxHistory])

  // Fetch price with deduplication
  const fetchPrice = useCallback(async () => {
    if (!mint || !enabled) return

    // Deduplicate rapid requests
    const now = Date.now()
    if (now - lastFetchRef.current < 500) return
    lastFetchRef.current = now

    try {
      const response = await fetch(`/api/tools/token/${mint}`)
      if (!response.ok) throw new Error('Failed to fetch price')

      const data = await response.json()
      if (data.success && data.price) {
        scheduleUpdate(data.price)
        setError(null)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [mint, enabled, scheduleUpdate])

  // Setup polling
  useEffect(() => {
    if (!enabled) return

    fetchPrice()
    const interval = setInterval(fetchPrice, refreshInterval)

    return () => {
      clearInterval(interval)
      if (batchTimeoutRef.current) {
        clearTimeout(batchTimeoutRef.current)
      }
    }
  }, [fetchPrice, refreshInterval, enabled])

  // Derived values
  const priceChange = priceHistory.length >= 2
    ? ((priceHistory[priceHistory.length - 1].price - priceHistory[0].price) / priceHistory[0].price) * 100
    : 0

  return {
    price,
    priceHistory,
    priceChange,
    loading,
    error,
    refresh: fetchPrice,
  }
}

export default useRealtimePrice
