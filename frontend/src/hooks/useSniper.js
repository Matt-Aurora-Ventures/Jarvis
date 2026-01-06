import { useState, useEffect, useCallback } from 'react'
import { jarvisApi } from '../lib/api'
import { POLLING_INTERVALS } from '../lib/constants'

/**
 * useSniper - Hook for sniper status with auto-refresh
 */
export function useSniper(autoRefresh = true) {
  const [sniper, setSniper] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchSniper = useCallback(async () => {
    try {
      const data = await jarvisApi.getSniperStatus()
      setSniper(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const start = useCallback(async () => {
    try {
      await jarvisApi.startSniper()
      await fetchSniper()
    } catch (err) {
      setError(err.message)
      throw err
    }
  }, [fetchSniper])

  const stop = useCallback(async () => {
    try {
      await jarvisApi.stopSniper()
      await fetchSniper()
    } catch (err) {
      setError(err.message)
      throw err
    }
  }, [fetchSniper])

  useEffect(() => {
    fetchSniper()
    
    if (autoRefresh) {
      const interval = setInterval(fetchSniper, POLLING_INTERVALS.SNIPER)
      return () => clearInterval(interval)
    }
  }, [fetchSniper, autoRefresh])

  return {
    sniper,
    loading,
    error,
    refresh: fetchSniper,
    start,
    stop,
    // Derived values
    isRunning: sniper?.is_running ?? false,
    winRate: sniper?.win_rate ?? '0%',
    totalTrades: sniper?.total_trades ?? 0,
    totalPnl: sniper?.state?.total_pnl_usd ?? 0,
  }
}

export default useSniper
