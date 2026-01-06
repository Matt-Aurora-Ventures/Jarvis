import { useState, useEffect, useCallback } from 'react'
import { jarvisApi } from '../lib/api'
import { POLLING_INTERVALS } from '../lib/constants'

/**
 * usePosition - Hook for active position with auto-refresh
 */
export function usePosition(autoRefresh = true) {
  const [position, setPosition] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchPosition = useCallback(async () => {
    try {
      const data = await jarvisApi.getActivePosition()
      setPosition(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const exit = useCallback(async (reason = 'MANUAL_EXIT') => {
    try {
      await jarvisApi.exitPosition(reason)
      await fetchPosition()
    } catch (err) {
      setError(err.message)
      throw err
    }
  }, [fetchPosition])

  useEffect(() => {
    fetchPosition()
    
    if (autoRefresh) {
      const interval = setInterval(fetchPosition, POLLING_INTERVALS.POSITION)
      return () => clearInterval(interval)
    }
  }, [fetchPosition, autoRefresh])

  return {
    position,
    loading,
    error,
    refresh: fetchPosition,
    exit,
    // Derived values
    hasPosition: position?.has_position ?? false,
    symbol: position?.symbol ?? '',
    pnlPercent: position?.pnl_pct ?? 0,
    pnlUSD: position?.pnl_usd ?? 0,
    isProfit: (position?.pnl_pct ?? 0) >= 0,
  }
}

export default usePosition
