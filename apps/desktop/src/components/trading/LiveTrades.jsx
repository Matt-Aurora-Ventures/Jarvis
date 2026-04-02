import React, { useMemo, useState, useEffect, useRef } from 'react'
import { TrendingUp, TrendingDown, Activity, Clock, Zap, ArrowUpRight, ArrowDownRight, Pause, Play } from 'lucide-react'

/**
 * LiveTrades - Real-time trade feed with animations
 *
 * Features:
 * - Animated new trade highlights
 * - Buy/Sell side coloring
 * - Trade aggregation stats
 * - Pause/Resume functionality
 * - Large trade alerts
 */
export function LiveTrades({
  trades = [],
  maxDisplay = 50,
  largeTradeThreshold = 1000, // USD
  showAggregates = true,
  autoScroll = true,
  compact = false,
  className = '',
}) {
  const [isPaused, setIsPaused] = useState(false)
  const [highlightedTrade, setHighlightedTrade] = useState(null)
  const listRef = useRef(null)
  const previousTradesLengthRef = useRef(trades.length)

  // Auto-scroll on new trades
  useEffect(() => {
    if (autoScroll && !isPaused && trades.length > previousTradesLengthRef.current) {
      if (listRef.current) {
        listRef.current.scrollTop = 0
      }
    }
    previousTradesLengthRef.current = trades.length
  }, [trades.length, autoScroll, isPaused])

  // Highlight new trades
  useEffect(() => {
    if (trades.length > 0) {
      const lastTrade = trades[trades.length - 1]
      setHighlightedTrade(lastTrade.id)
      const timer = setTimeout(() => setHighlightedTrade(null), 1000)
      return () => clearTimeout(timer)
    }
  }, [trades.length])

  // Calculate aggregate stats
  const stats = useMemo(() => {
    if (trades.length === 0) return null

    const buyTrades = trades.filter(t => t.side === 'buy')
    const sellTrades = trades.filter(t => t.side === 'sell')

    const buyVolume = buyTrades.reduce((sum, t) => sum + (t.value || t.price * t.amount), 0)
    const sellVolume = sellTrades.reduce((sum, t) => sum + (t.value || t.price * t.amount), 0)

    const largeTrades = trades.filter(t => (t.value || t.price * t.amount) >= largeTradeThreshold)

    const avgTradeSize = trades.reduce((sum, t) => sum + (t.value || t.price * t.amount), 0) / trades.length

    // Price trend
    const prices = trades.map(t => t.price)
    const recentPrices = prices.slice(-10)
    const priceDirection = recentPrices.length > 1
      ? recentPrices[recentPrices.length - 1] > recentPrices[0] ? 'up' : 'down'
      : 'neutral'

    return {
      totalTrades: trades.length,
      buyCount: buyTrades.length,
      sellCount: sellTrades.length,
      buyVolume,
      sellVolume,
      buyPressure: buyVolume / (buyVolume + sellVolume) * 100,
      largeTrades: largeTrades.length,
      avgTradeSize,
      priceDirection,
    }
  }, [trades, largeTradeThreshold])

  // Format helpers
  const formatPrice = (price) => {
    if (!price) return '-'
    if (price >= 1) return `$${price.toFixed(4)}`
    if (price >= 0.01) return `$${price.toFixed(6)}`
    return `$${price.toFixed(8)}`
  }

  const formatAmount = (amount) => {
    if (amount >= 1000000) return `${(amount / 1000000).toFixed(2)}M`
    if (amount >= 1000) return `${(amount / 1000).toFixed(2)}K`
    return amount.toFixed(2)
  }

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const formatTimeAgo = (timestamp) => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    return `${Math.floor(seconds / 3600)}h`
  }

  // Display trades (reversed for newest first)
  const displayTrades = useMemo(() => {
    const sorted = [...trades].reverse()
    return isPaused ? sorted : sorted.slice(0, maxDisplay)
  }, [trades, maxDisplay, isPaused])

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 flex flex-col ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-white">Live Trades</span>
          {trades.length > 0 && (
            <span className="text-xs text-gray-400">({trades.length})</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="p-1.5 rounded hover:bg-gray-800 transition-colors"
            title={isPaused ? 'Resume' : 'Pause'}
          >
            {isPaused ? (
              <Play className="w-4 h-4 text-green-400" />
            ) : (
              <Pause className="w-4 h-4 text-gray-400" />
            )}
          </button>
        </div>
      </div>

      {/* Aggregate Stats */}
      {showAggregates && stats && (
        <div className="grid grid-cols-4 gap-2 px-4 py-2 border-b border-gray-800 text-xs">
          <div className="text-center">
            <div className="text-gray-400">Buys</div>
            <div className="text-green-400 font-medium">{stats.buyCount}</div>
          </div>
          <div className="text-center">
            <div className="text-gray-400">Sells</div>
            <div className="text-red-400 font-medium">{stats.sellCount}</div>
          </div>
          <div className="text-center">
            <div className="text-gray-400">Buy Vol</div>
            <div className="text-green-400 font-medium">${formatAmount(stats.buyVolume)}</div>
          </div>
          <div className="text-center">
            <div className="text-gray-400">Sell Vol</div>
            <div className="text-red-400 font-medium">${formatAmount(stats.sellVolume)}</div>
          </div>
        </div>
      )}

      {/* Buy/Sell Pressure Bar */}
      {stats && (
        <div className="px-4 py-1.5 border-b border-gray-800">
          <div className="h-1 bg-gray-800 rounded-full overflow-hidden flex">
            <div
              className="bg-green-500 transition-all duration-300"
              style={{ width: `${stats.buyPressure}%` }}
            />
          </div>
        </div>
      )}

      {/* Trade List */}
      <div
        ref={listRef}
        className={`flex-1 overflow-y-auto ${compact ? 'max-h-48' : 'max-h-80'}`}
      >
        {displayTrades.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            <Clock className="w-4 h-4 mr-2" />
            Waiting for trades...
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {displayTrades.map((trade, idx) => {
              const isBuy = trade.side === 'buy'
              const isLarge = (trade.value || trade.price * trade.amount) >= largeTradeThreshold
              const isHighlighted = trade.id === highlightedTrade

              return (
                <div
                  key={trade.id || idx}
                  className={`
                    flex items-center px-4 py-2 transition-all duration-300
                    ${isHighlighted ? 'bg-white/5' : ''}
                    ${isLarge ? 'bg-yellow-500/5' : ''}
                    hover:bg-gray-800/50
                  `}
                >
                  {/* Side indicator */}
                  <div className={`
                    w-1 h-8 rounded-full mr-3
                    ${isBuy ? 'bg-green-500' : 'bg-red-500'}
                    ${isHighlighted ? 'animate-pulse' : ''}
                  `} />

                  {/* Trade icon */}
                  <div className={`
                    p-1.5 rounded mr-3
                    ${isBuy ? 'bg-green-500/10' : 'bg-red-500/10'}
                  `}>
                    {isBuy ? (
                      <ArrowUpRight className="w-3.5 h-3.5 text-green-400" />
                    ) : (
                      <ArrowDownRight className="w-3.5 h-3.5 text-red-400" />
                    )}
                  </div>

                  {/* Trade details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${isBuy ? 'text-green-400' : 'text-red-400'}`}>
                        {isBuy ? 'BUY' : 'SELL'}
                      </span>
                      {isLarge && (
                        <Zap className="w-3 h-3 text-yellow-400" title="Large trade" />
                      )}
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatAmount(trade.amount)} @ {formatPrice(trade.price)}
                    </div>
                  </div>

                  {/* Value & Time */}
                  <div className="text-right">
                    <div className={`text-sm font-mono ${isLarge ? 'text-yellow-400' : 'text-gray-300'}`}>
                      ${formatAmount(trade.value || trade.price * trade.amount)}
                    </div>
                    <div className="text-xs text-gray-500" title={formatTime(trade.timestamp)}>
                      {formatTimeAgo(trade.timestamp)} ago
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Footer stats */}
      {stats && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-gray-800 text-xs">
          <div className="flex items-center gap-1 text-gray-400">
            <Activity className="w-3 h-3" />
            <span>Avg: ${formatAmount(stats.avgTradeSize)}</span>
          </div>
          {stats.largeTrades > 0 && (
            <div className="flex items-center gap-1 text-yellow-400">
              <Zap className="w-3 h-3" />
              <span>{stats.largeTrades} large trades</span>
            </div>
          )}
          <div className={`flex items-center gap-1 ${
            stats.priceDirection === 'up' ? 'text-green-400' :
            stats.priceDirection === 'down' ? 'text-red-400' : 'text-gray-400'
          }`}>
            {stats.priceDirection === 'up' ? (
              <TrendingUp className="w-3 h-3" />
            ) : stats.priceDirection === 'down' ? (
              <TrendingDown className="w-3 h-3" />
            ) : null}
            <span>Trend</span>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * TradeAlert - Large trade notification component
 */
export function TradeAlert({ trade, onDismiss, threshold = 5000 }) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false)
      onDismiss?.()
    }, 5000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  if (!trade || !isVisible) return null

  const isBuy = trade.side === 'buy'
  const value = trade.value || trade.price * trade.amount

  if (value < threshold) return null

  return (
    <div className={`
      fixed bottom-4 right-4 z-50
      bg-gray-900 border rounded-lg p-4 shadow-xl
      animate-slide-in
      ${isBuy ? 'border-green-500/50' : 'border-red-500/50'}
    `}>
      <div className="flex items-center gap-3">
        <div className={`
          p-2 rounded-full
          ${isBuy ? 'bg-green-500/20' : 'bg-red-500/20'}
        `}>
          <Zap className={`w-5 h-5 ${isBuy ? 'text-green-400' : 'text-red-400'}`} />
        </div>

        <div>
          <div className="font-medium text-white">
            Large {isBuy ? 'Buy' : 'Sell'} Detected!
          </div>
          <div className="text-sm text-gray-400">
            ${value.toLocaleString()} trade
          </div>
        </div>

        <button
          onClick={() => {
            setIsVisible(false)
            onDismiss?.()
          }}
          className="ml-4 text-gray-500 hover:text-gray-300"
        >
          &times;
        </button>
      </div>
    </div>
  )
}

/**
 * TradeHeatmap - Visual trade activity heatmap
 */
export function TradeHeatmap({
  trades = [],
  buckets = 20,
  className = '',
}) {
  const heatmapData = useMemo(() => {
    if (trades.length === 0) return []

    const now = Date.now()
    const timeWindow = 60 * 1000 // 1 minute

    // Create time buckets
    const bucketSize = timeWindow / buckets
    const data = new Array(buckets).fill(0).map((_, i) => ({
      buyVolume: 0,
      sellVolume: 0,
      time: now - (buckets - i - 1) * bucketSize,
    }))

    // Fill buckets
    trades.forEach(trade => {
      const tradeTime = new Date(trade.timestamp).getTime()
      const bucketIndex = Math.floor((tradeTime - (now - timeWindow)) / bucketSize)

      if (bucketIndex >= 0 && bucketIndex < buckets) {
        const value = trade.value || trade.price * trade.amount
        if (trade.side === 'buy') {
          data[bucketIndex].buyVolume += value
        } else {
          data[bucketIndex].sellVolume += value
        }
      }
    })

    // Find max for scaling
    const maxVolume = Math.max(
      ...data.map(d => d.buyVolume),
      ...data.map(d => d.sellVolume)
    )

    return data.map(d => ({
      ...d,
      buyIntensity: maxVolume > 0 ? d.buyVolume / maxVolume : 0,
      sellIntensity: maxVolume > 0 ? d.sellVolume / maxVolume : 0,
    }))
  }, [trades, buckets])

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-white">Trade Activity</span>
        <span className="text-xs text-gray-400">Last 60s</span>
      </div>

      <div className="flex gap-0.5">
        {heatmapData.map((bucket, i) => (
          <div key={i} className="flex-1 flex flex-col gap-0.5">
            {/* Buy heat */}
            <div
              className="h-4 rounded-sm transition-all duration-150"
              style={{
                backgroundColor: `rgba(34, 197, 94, ${bucket.buyIntensity * 0.8 + 0.1})`,
              }}
              title={`Buy: $${bucket.buyVolume.toFixed(2)}`}
            />
            {/* Sell heat */}
            <div
              className="h-4 rounded-sm transition-all duration-150"
              style={{
                backgroundColor: `rgba(239, 68, 68, ${bucket.sellIntensity * 0.8 + 0.1})`,
              }}
              title={`Sell: $${bucket.sellVolume.toFixed(2)}`}
            />
          </div>
        ))}
      </div>

      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>-60s</span>
        <span>Now</span>
      </div>
    </div>
  )
}

export default LiveTrades
