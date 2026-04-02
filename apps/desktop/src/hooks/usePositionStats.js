import { useState, useEffect, useCallback } from 'react'
import { jarvisApi } from '../lib/api'
import { POLLING_INTERVALS } from '../lib/constants'

/**
 * usePositionStats - Hook for position tracking statistics
 */
export function usePositionStats(autoRefresh = true) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/position/stats')
      const data = await response.json()
      if (data.success) {
        setStats(data.stats)
        setError(null)
      } else {
        setError(data.error || 'Failed to fetch stats')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()

    if (autoRefresh) {
      // Refresh stats every 30 seconds
      const interval = setInterval(fetchStats, 30000)
      return () => clearInterval(interval)
    }
  }, [fetchStats, autoRefresh])

  return {
    stats,
    loading,
    error,
    refresh: fetchStats,
    // Derived values
    totalTrades: stats?.total_positions ?? 0,
    winRate: stats?.win_rate ?? 0,
    totalPnl: stats?.total_pnl_usd ?? 0,
    avgHoldTime: stats?.avg_hold_duration_minutes ?? 0,
    currentStreak: stats?.current_streak ?? 0,
    bestTrade: stats?.best_trade_pnl_pct ?? 0,
    worstTrade: stats?.worst_trade_pnl_pct ?? 0,
  }
}

/**
 * usePositionHistory - Hook for position history
 */
export function usePositionHistory(limit = 50, autoRefresh = false) {
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchHistory = useCallback(async () => {
    try {
      const response = await fetch(`/api/position/history?limit=${limit}`)
      const data = await response.json()
      if (data.success) {
        setPositions(data.positions || [])
        setError(null)
      } else {
        setError(data.error || 'Failed to fetch history')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetchHistory()

    if (autoRefresh) {
      const interval = setInterval(fetchHistory, 60000) // Refresh every minute
      return () => clearInterval(interval)
    }
  }, [fetchHistory, autoRefresh])

  return {
    positions,
    loading,
    error,
    refresh: fetchHistory,
    count: positions.length,
  }
}

export default usePositionStats
