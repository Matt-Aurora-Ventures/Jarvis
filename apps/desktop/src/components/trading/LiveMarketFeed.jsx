import React, { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Activity, RefreshCw, Zap, ArrowRight } from 'lucide-react'

/**
 * LiveMarketFeed - Real-time market data component
 * Shows SOL price, trending tokens, and market activity
 */
export default function LiveMarketFeed({ onTokenSelect }) {
  const [solPrice, setSolPrice] = useState(null)
  const [btcPrice, setBtcPrice] = useState(null)
  const [trending, setTrending] = useState([])
  const [gainers, setGainers] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [error, setError] = useState(null)

  const fetchMarketData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch data from multiple endpoints in parallel
      const [priceRes, trendingRes, gainersRes] = await Promise.allSettled([
        fetch('/api/price/sol').then(r => r.json()),
        fetch('/api/trending?limit=5').then(r => r.json()),
        fetch('/api/gainers?limit=5').then(r => r.json()),
      ])

      // Process results
      if (priceRes.status === 'fulfilled' && priceRes.value.price) {
        setSolPrice(priceRes.value.price)
      }

      if (trendingRes.status === 'fulfilled' && trendingRes.value.tokens) {
        setTrending(trendingRes.value.tokens.slice(0, 5))
      }

      if (gainersRes.status === 'fulfilled' && gainersRes.value.tokens) {
        setGainers(gainersRes.value.tokens.slice(0, 5))
      }

      setLastUpdate(new Date())
    } catch (err) {
      console.error('Market data fetch error:', err)
      setError('Failed to load market data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMarketData()

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchMarketData, 30000)
    return () => clearInterval(interval)
  }, [fetchMarketData])

  const formatPrice = (price) => {
    if (!price) return '---'
    if (price < 0.01) return `$${price.toFixed(6)}`
    if (price < 1) return `$${price.toFixed(4)}`
    if (price < 100) return `$${price.toFixed(2)}`
    return `$${price.toFixed(0)}`
  }

  const formatChange = (change) => {
    if (!change && change !== 0) return '---'
    const prefix = change >= 0 ? '+' : ''
    return `${prefix}${change.toFixed(1)}%`
  }

  const formatVolume = (vol) => {
    if (!vol) return '---'
    if (vol >= 1e9) return `$${(vol / 1e9).toFixed(1)}B`
    if (vol >= 1e6) return `$${(vol / 1e6).toFixed(1)}M`
    if (vol >= 1e3) return `$${(vol / 1e3).toFixed(1)}K`
    return `$${vol.toFixed(0)}`
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-green-400" />
          <span className="font-medium text-white">Live Market</span>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdate && (
            <span className="text-xs text-gray-500">
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchMarketData}
            disabled={loading}
            className="p-1 hover:bg-gray-800 rounded transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error ? (
        <div className="p-4 text-center text-red-400 text-sm">{error}</div>
      ) : (
        <>
          {/* Major Prices */}
          <div className="grid grid-cols-2 gap-4 p-4 border-b border-gray-800">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-gray-500">SOL</span>
                <div className="text-xl font-bold text-white">
                  {formatPrice(solPrice)}
                </div>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                <span className="text-white font-bold text-sm">SOL</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-gray-500">BTC</span>
                <div className="text-xl font-bold text-white">
                  {formatPrice(btcPrice)}
                </div>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-yellow-500 flex items-center justify-center">
                <span className="text-white font-bold text-sm">BTC</span>
              </div>
            </div>
          </div>

          {/* Trending Section */}
          <div className="p-4 border-b border-gray-800">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="text-sm font-medium text-gray-300">Trending</span>
            </div>
            <div className="space-y-2">
              {trending.length === 0 ? (
                <div className="text-center text-gray-500 text-sm py-2">
                  {loading ? 'Loading...' : 'No trending tokens'}
                </div>
              ) : (
                trending.map((token, i) => (
                  <div
                    key={token.address || i}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-800 cursor-pointer transition-colors"
                    onClick={() => onTokenSelect?.(token)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-4">{i + 1}</span>
                      <span className="font-medium text-white text-sm">${token.symbol}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-300">{formatPrice(token.price)}</span>
                      <span className={`text-xs ${token.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatChange(token.change)}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Gainers Section */}
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-gray-300">Top Gainers</span>
            </div>
            <div className="space-y-2">
              {gainers.length === 0 ? (
                <div className="text-center text-gray-500 text-sm py-2">
                  {loading ? 'Loading...' : 'No data available'}
                </div>
              ) : (
                gainers.map((token, i) => (
                  <div
                    key={token.address || i}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-800 cursor-pointer transition-colors"
                    onClick={() => onTokenSelect?.(token)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white text-sm">${token.symbol}</span>
                      <span className="text-xs text-gray-500">{formatVolume(token.volume)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-green-400 font-medium">
                        {formatChange(token.change)}
                      </span>
                      <ArrowRight className="w-3 h-3 text-gray-500" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
