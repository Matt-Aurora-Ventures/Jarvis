import { useState, useEffect, useCallback } from 'react'
import { jarvisApi } from '../lib/api'
import { POLLING_INTERVALS } from '../lib/constants'

/**
 * useWallet - Hook for wallet data with auto-refresh
 */
export function useWallet(autoRefresh = true) {
  const [wallet, setWallet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchWallet = useCallback(async () => {
    try {
      const data = await jarvisApi.getWalletStatus()
      setWallet(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWallet()
    
    if (autoRefresh) {
      const interval = setInterval(fetchWallet, POLLING_INTERVALS.WALLET)
      return () => clearInterval(interval)
    }
  }, [fetchWallet, autoRefresh])

  return { 
    wallet, 
    loading, 
    error, 
    refresh: fetchWallet,
    // Derived values
    balanceSOL: wallet?.balance_sol ?? 0,
    balanceUSD: wallet?.balance_usd ?? 0,
    solPrice: wallet?.sol_price ?? 0,
  }
}

export default useWallet
