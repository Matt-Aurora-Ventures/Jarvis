import React, { useMemo, useState } from 'react'
import { TrendingUp, TrendingDown, Activity, Zap, BarChart3, Layers } from 'lucide-react'

/**
 * MarketDepth - Real-time order book visualization
 *
 * Features:
 * - Bid/Ask visualization with depth bars
 * - Spread calculation
 * - Cumulative depth display
 * - Buy/Sell pressure indicators
 * - Price impact calculator
 */
export function MarketDepth({
  bids = [],
  asks = [],
  midPrice = 0,
  spread = 0,
  lastPrice = 0,
  maxLevels = 15,
  showCumulative = true,
  compact = false,
  className = '',
}) {
  const [hoverLevel, setHoverLevel] = useState(null)

  // Process order book data
  const { processedBids, processedAsks, maxVolume, totalBidVolume, totalAskVolume } = useMemo(() => {
    // Limit to maxLevels
    const limitedBids = bids.slice(0, maxLevels)
    const limitedAsks = asks.slice(0, maxLevels)

    // Calculate volumes
    let bidCumulative = 0
    let askCumulative = 0

    const processedBids = limitedBids.map(([price, amount]) => {
      bidCumulative += amount
      return { price, amount, cumulative: bidCumulative }
    })

    const processedAsks = limitedAsks.map(([price, amount]) => {
      askCumulative += amount
      return { price, amount, cumulative: askCumulative }
    })

    // Find max volume for bar scaling
    const maxBidVol = Math.max(...processedBids.map(b => showCumulative ? b.cumulative : b.amount), 0)
    const maxAskVol = Math.max(...processedAsks.map(a => showCumulative ? a.cumulative : a.amount), 0)
    const maxVolume = Math.max(maxBidVol, maxAskVol)

    return {
      processedBids,
      processedAsks,
      maxVolume,
      totalBidVolume: bidCumulative,
      totalAskVolume: askCumulative,
    }
  }, [bids, asks, maxLevels, showCumulative])

  // Calculate buy/sell pressure
  const buyPressure = useMemo(() => {
    if (totalBidVolume + totalAskVolume === 0) return 50
    return (totalBidVolume / (totalBidVolume + totalAskVolume)) * 100
  }, [totalBidVolume, totalAskVolume])

  // Format price
  const formatPrice = (price) => {
    if (price >= 1) return price.toFixed(4)
    if (price >= 0.01) return price.toFixed(6)
    return price.toFixed(8)
  }

  // Format volume
  const formatVolume = (vol) => {
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(2)}M`
    if (vol >= 1000) return `${(vol / 1000).toFixed(2)}K`
    return vol.toFixed(2)
  }

  // Calculate spread percentage
  const spreadPercent = midPrice > 0 ? (spread / midPrice) * 100 : 0

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Order Book</span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Spread</span>
            <span className="text-yellow-400 font-mono">{spreadPercent.toFixed(3)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Mid</span>
            <span className="text-white font-mono">${formatPrice(midPrice)}</span>
          </div>
        </div>
      </div>

      {/* Pressure bar */}
      <div className="px-4 py-2 border-b border-gray-800">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-green-400">Buy {buyPressure.toFixed(1)}%</span>
          <div className="flex-1" />
          <span className="text-xs text-red-400">Sell {(100 - buyPressure).toFixed(1)}%</span>
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden flex">
          <div
            className="bg-gradient-to-r from-green-500 to-green-400 transition-all duration-300"
            style={{ width: `${buyPressure}%` }}
          />
          <div
            className="bg-gradient-to-r from-red-400 to-red-500 transition-all duration-300"
            style={{ width: `${100 - buyPressure}%` }}
          />
        </div>
      </div>

      {/* Order book */}
      <div className={`grid grid-cols-2 gap-0.5 ${compact ? 'max-h-64' : 'max-h-96'} overflow-hidden`}>
        {/* Bids (Buy orders) */}
        <div className="flex flex-col-reverse">
          {/* Column header */}
          <div className="grid grid-cols-3 gap-1 px-2 py-1 text-xs text-gray-500 bg-gray-900/50 sticky bottom-0">
            <span>Price</span>
            <span className="text-right">Amount</span>
            <span className="text-right">{showCumulative ? 'Total' : 'Value'}</span>
          </div>

          {/* Bid levels */}
          {processedBids.map((bid, idx) => {
            const barWidth = maxVolume > 0
              ? ((showCumulative ? bid.cumulative : bid.amount) / maxVolume) * 100
              : 0

            return (
              <div
                key={`bid-${idx}`}
                className="relative group"
                onMouseEnter={() => setHoverLevel({ type: 'bid', idx, ...bid })}
                onMouseLeave={() => setHoverLevel(null)}
              >
                {/* Volume bar */}
                <div
                  className="absolute inset-0 bg-green-500/20 transition-all duration-150"
                  style={{ width: `${barWidth}%` }}
                />

                {/* Content */}
                <div className="relative grid grid-cols-3 gap-1 px-2 py-0.5 text-xs hover:bg-green-500/10">
                  <span className="text-green-400 font-mono">{formatPrice(bid.price)}</span>
                  <span className="text-right text-gray-300 font-mono">{formatVolume(bid.amount)}</span>
                  <span className="text-right text-gray-400 font-mono">
                    {showCumulative ? formatVolume(bid.cumulative) : formatVolume(bid.price * bid.amount)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Asks (Sell orders) */}
        <div className="flex flex-col">
          {/* Column header */}
          <div className="grid grid-cols-3 gap-1 px-2 py-1 text-xs text-gray-500 bg-gray-900/50 sticky top-0">
            <span>Price</span>
            <span className="text-right">Amount</span>
            <span className="text-right">{showCumulative ? 'Total' : 'Value'}</span>
          </div>

          {/* Ask levels */}
          {processedAsks.map((ask, idx) => {
            const barWidth = maxVolume > 0
              ? ((showCumulative ? ask.cumulative : ask.amount) / maxVolume) * 100
              : 0

            return (
              <div
                key={`ask-${idx}`}
                className="relative group"
                onMouseEnter={() => setHoverLevel({ type: 'ask', idx, ...ask })}
                onMouseLeave={() => setHoverLevel(null)}
              >
                {/* Volume bar (right-aligned) */}
                <div
                  className="absolute inset-0 bg-red-500/20 transition-all duration-150"
                  style={{
                    width: `${barWidth}%`,
                    left: 'auto',
                    right: 0,
                  }}
                />

                {/* Content */}
                <div className="relative grid grid-cols-3 gap-1 px-2 py-0.5 text-xs hover:bg-red-500/10">
                  <span className="text-red-400 font-mono">{formatPrice(ask.price)}</span>
                  <span className="text-right text-gray-300 font-mono">{formatVolume(ask.amount)}</span>
                  <span className="text-right text-gray-400 font-mono">
                    {showCumulative ? formatVolume(ask.cumulative) : formatVolume(ask.price * ask.amount)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Hover tooltip */}
      {hoverLevel && (
        <div className="absolute z-10 bg-gray-800 border border-gray-700 rounded-lg p-2 text-xs shadow-lg pointer-events-none">
          <div className={`font-medium mb-1 ${hoverLevel.type === 'bid' ? 'text-green-400' : 'text-red-400'}`}>
            {hoverLevel.type === 'bid' ? 'Buy Order' : 'Sell Order'}
          </div>
          <div className="text-gray-300">
            Price: ${formatPrice(hoverLevel.price)}
          </div>
          <div className="text-gray-300">
            Amount: {formatVolume(hoverLevel.amount)}
          </div>
          <div className="text-gray-300">
            Total: {formatVolume(hoverLevel.cumulative)}
          </div>
          <div className="text-gray-400 mt-1">
            Value: ${formatVolume(hoverLevel.price * hoverLevel.amount)}
          </div>
        </div>
      )}

      {/* Summary footer */}
      <div className="grid grid-cols-2 gap-4 px-4 py-2 bg-gray-900/50 border-t border-gray-800 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Bid Depth</span>
          <span className="text-green-400 font-mono">{formatVolume(totalBidVolume)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Ask Depth</span>
          <span className="text-red-400 font-mono">{formatVolume(totalAskVolume)}</span>
        </div>
      </div>
    </div>
  )
}

/**
 * DepthChart - Visual depth chart representation
 */
export function DepthChart({
  bids = [],
  asks = [],
  midPrice = 0,
  height = 200,
  className = '',
}) {
  // Process data for chart
  const chartData = useMemo(() => {
    let bidCumulative = 0
    let askCumulative = 0

    const bidPoints = bids.map(([price, amount]) => {
      bidCumulative += amount
      return { price, cumulative: bidCumulative }
    }).reverse()

    const askPoints = asks.map(([price, amount]) => {
      askCumulative += amount
      return { price, cumulative: askCumulative }
    })

    const maxCumulative = Math.max(bidCumulative, askCumulative)
    const allPrices = [...bidPoints.map(p => p.price), ...askPoints.map(p => p.price)]
    const minPrice = Math.min(...allPrices)
    const maxPrice = Math.max(...allPrices)
    const priceRange = maxPrice - minPrice

    return {
      bidPoints,
      askPoints,
      maxCumulative,
      minPrice,
      maxPrice,
      priceRange,
    }
  }, [bids, asks])

  // Convert to SVG coordinates
  const width = 400
  const padding = 10

  const scaleX = (price) => {
    if (chartData.priceRange === 0) return width / 2
    return padding + ((price - chartData.minPrice) / chartData.priceRange) * (width - 2 * padding)
  }

  const scaleY = (cumulative) => {
    if (chartData.maxCumulative === 0) return height - padding
    return height - padding - (cumulative / chartData.maxCumulative) * (height - 2 * padding)
  }

  // Generate path for bid area
  const bidPath = useMemo(() => {
    if (chartData.bidPoints.length === 0) return ''

    const points = chartData.bidPoints.map(p => `${scaleX(p.price)},${scaleY(p.cumulative)}`)
    const startX = scaleX(chartData.bidPoints[0].price)
    const endX = scaleX(chartData.bidPoints[chartData.bidPoints.length - 1].price)

    return `M${startX},${height - padding} L${points.join(' L')} L${endX},${height - padding} Z`
  }, [chartData.bidPoints, height])

  // Generate path for ask area
  const askPath = useMemo(() => {
    if (chartData.askPoints.length === 0) return ''

    const points = chartData.askPoints.map(p => `${scaleX(p.price)},${scaleY(p.cumulative)}`)
    const startX = scaleX(chartData.askPoints[0].price)
    const endX = scaleX(chartData.askPoints[chartData.askPoints.length - 1].price)

    return `M${startX},${height - padding} L${points.join(' L')} L${endX},${height - padding} Z`
  }, [chartData.askPoints, height])

  // Mid price line
  const midPriceX = scaleX(midPrice)

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Depth Chart</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-green-500/50 rounded" />
            <span className="text-gray-400">Bids</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500/50 rounded" />
            <span className="text-gray-400">Asks</span>
          </div>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
      >
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map(ratio => (
          <line
            key={ratio}
            x1={padding}
            y1={scaleY(chartData.maxCumulative * ratio)}
            x2={width - padding}
            y2={scaleY(chartData.maxCumulative * ratio)}
            stroke="#374151"
            strokeDasharray="4,4"
          />
        ))}

        {/* Bid area */}
        <path
          d={bidPath}
          fill="rgba(34, 197, 94, 0.3)"
          stroke="rgb(34, 197, 94)"
          strokeWidth="2"
        />

        {/* Ask area */}
        <path
          d={askPath}
          fill="rgba(239, 68, 68, 0.3)"
          stroke="rgb(239, 68, 68)"
          strokeWidth="2"
        />

        {/* Mid price line */}
        {midPrice > 0 && (
          <line
            x1={midPriceX}
            y1={padding}
            x2={midPriceX}
            y2={height - padding}
            stroke="#fbbf24"
            strokeWidth="1"
            strokeDasharray="4,4"
          />
        )}
      </svg>
    </div>
  )
}

export default MarketDepth
