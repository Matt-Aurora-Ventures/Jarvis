import React, { useState, useMemo } from 'react'
import {
  LayoutGrid,
  TrendingUp,
  TrendingDown,
  Activity,
  ChevronDown,
  Settings,
  Zap,
  Target
} from 'lucide-react'

export function RenkoChart() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [boxSize, setBoxSize] = useState('auto') // auto, 0.1, 0.25, 0.5, 1.0
  const [viewMode, setViewMode] = useState('chart') // chart, analysis, signals

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate Renko bricks
  const renkoData = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000

    // Calculate box size based on price
    let brickSize
    if (boxSize === 'auto') {
      brickSize = basePrice * 0.005 // 0.5% of price
    } else {
      brickSize = parseFloat(boxSize)
    }

    const bricks = []
    let currentPrice = basePrice
    let direction = Math.random() > 0.5 ? 'up' : 'down'

    // Generate 60 bricks
    for (let i = 0; i < 60; i++) {
      // Randomly change direction sometimes
      if (Math.random() < 0.3) {
        direction = direction === 'up' ? 'down' : 'up'
      }

      const newPrice = direction === 'up'
        ? currentPrice + brickSize
        : currentPrice - brickSize

      bricks.push({
        id: i,
        open: currentPrice,
        close: newPrice,
        high: Math.max(currentPrice, newPrice),
        low: Math.min(currentPrice, newPrice),
        direction,
        boxSize: brickSize
      })

      currentPrice = newPrice
    }

    // Calculate trends
    let currentTrend = { direction: bricks[0]?.direction, start: 0, length: 0 }
    const trends = []

    bricks.forEach((brick, idx) => {
      if (brick.direction === currentTrend.direction) {
        currentTrend.length++
      } else {
        trends.push({ ...currentTrend })
        currentTrend = { direction: brick.direction, start: idx, length: 1 }
      }
    })
    trends.push(currentTrend)

    const longestTrend = Math.max(...trends.map(t => t.length))
    const avgTrend = trends.reduce((sum, t) => sum + t.length, 0) / trends.length

    return {
      bricks,
      brickSize,
      trends,
      longestTrend,
      avgTrend,
      upBricks: bricks.filter(b => b.direction === 'up').length,
      downBricks: bricks.filter(b => b.direction === 'down').length,
      currentTrend: trends[trends.length - 1],
      priceRange: {
        high: Math.max(...bricks.map(b => b.high)),
        low: Math.min(...bricks.map(b => b.low))
      }
    }
  }, [selectedToken, boxSize])

  // Chart rendering calculations
  const chartConfig = useMemo(() => {
    const chartWidth = 100
    const chartHeight = 200
    const brickWidth = chartWidth / renkoData.bricks.length

    const priceHigh = renkoData.priceRange.high
    const priceLow = renkoData.priceRange.low
    const priceRange = priceHigh - priceLow

    const priceToY = (price) => {
      return chartHeight - ((price - priceLow) / priceRange) * chartHeight
    }

    return { chartWidth, chartHeight, brickWidth, priceToY, priceRange }
  }, [renkoData])

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(0)
    if (selectedToken === 'ETH') return price.toFixed(0)
    return price.toFixed(2)
  }

  const formatBoxSize = (size) => {
    if (size >= 1) return `$${size.toFixed(2)}`
    return `$${size.toFixed(4)}`
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <LayoutGrid className="w-5 h-5 text-lime-400" />
            <h2 className="text-lg font-semibold text-white">Renko Chart</h2>
          </div>

          <div className="flex items-center gap-2">
            {/* Token Selector */}
            <div className="relative">
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm appearance-none pr-8 cursor-pointer"
              >
                {tokens.map(token => (
                  <option key={token} value={token}>{token}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Box Size */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['auto', '0.1', '0.25', '0.5', '1.0'].map((size) => (
                <button
                  key={size}
                  onClick={() => setBoxSize(size)}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    boxSize === size
                      ? 'bg-lime-500/30 text-lime-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {size === 'auto' ? 'Auto' : `$${size}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'chart', label: 'Renko Chart', icon: LayoutGrid },
            { id: 'analysis', label: 'Analysis', icon: Activity },
            { id: 'signals', label: 'Signals', icon: Target }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-lime-500/30 text-lime-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Box Size</div>
            <div className="text-sm font-medium text-lime-400">
              {formatBoxSize(renkoData.brickSize)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Up Bricks</div>
            <div className="text-sm font-medium text-green-400">
              {renkoData.upBricks} ({((renkoData.upBricks / renkoData.bricks.length) * 100).toFixed(0)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Down Bricks</div>
            <div className="text-sm font-medium text-red-400">
              {renkoData.downBricks} ({((renkoData.downBricks / renkoData.bricks.length) * 100).toFixed(0)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Longest Trend</div>
            <div className="text-sm font-medium text-white">
              {renkoData.longestTrend} bricks
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Avg Trend</div>
            <div className="text-sm font-medium text-white">
              {renkoData.avgTrend.toFixed(1)} bricks
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Current Trend</div>
            <div className={`text-sm font-medium ${renkoData.currentTrend.direction === 'up' ? 'text-green-400' : 'text-red-400'}`}>
              {renkoData.currentTrend.length} {renkoData.currentTrend.direction === 'up' ? 'Up' : 'Down'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'chart' && (
          <div className="space-y-4">
            {/* Renko Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <svg width="100%" height={chartConfig.chartHeight} className="overflow-visible">
                {renkoData.bricks.map((brick, idx) => {
                  const x = idx * chartConfig.brickWidth
                  const yTop = chartConfig.priceToY(brick.high)
                  const yBottom = chartConfig.priceToY(brick.low)
                  const height = yBottom - yTop

                  return (
                    <rect
                      key={brick.id}
                      x={`${x}%`}
                      y={yTop}
                      width={`${chartConfig.brickWidth * 0.9}%`}
                      height={height}
                      fill={brick.direction === 'up' ? '#22c55e' : '#ef4444'}
                      stroke={brick.direction === 'up' ? '#16a34a' : '#dc2626'}
                      strokeWidth="1"
                      rx="2"
                    />
                  )
                })}
              </svg>

              {/* Price axis */}
              <div className="flex justify-between mt-2 text-xs text-gray-500">
                <span>${formatPrice(renkoData.priceRange.low)}</span>
                <span>${formatPrice((renkoData.priceRange.high + renkoData.priceRange.low) / 2)}</span>
                <span>${formatPrice(renkoData.priceRange.high)}</span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 text-xs">
              <span className="flex items-center gap-1">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                Up Brick (Bull)
              </span>
              <span className="flex items-center gap-1">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                Down Brick (Bear)
              </span>
              <span className="text-gray-400">
                Each brick = {formatBoxSize(renkoData.brickSize)} move
              </span>
            </div>
          </div>
        )}

        {viewMode === 'analysis' && (
          <div className="space-y-4">
            {/* Trend Distribution */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
                <h3 className="text-sm font-medium text-green-400 mb-3">Bullish Trends</h3>
                <div className="space-y-2">
                  {renkoData.trends.filter(t => t.direction === 'up').slice(0, 5).map((trend, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">Trend {idx + 1}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-2 bg-green-500/60 rounded" style={{ width: `${trend.length * 10}px` }} />
                        <span className="text-sm text-green-400">{trend.length} bricks</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
                <h3 className="text-sm font-medium text-red-400 mb-3">Bearish Trends</h3>
                <div className="space-y-2">
                  {renkoData.trends.filter(t => t.direction === 'down').slice(0, 5).map((trend, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">Trend {idx + 1}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-2 bg-red-500/60 rounded" style={{ width: `${trend.length * 10}px` }} />
                        <span className="text-sm text-red-400">{trend.length} bricks</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Trend Statistics */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Trend Statistics</h3>
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">
                    {renkoData.trends.length}
                  </div>
                  <div className="text-xs text-gray-400">Total Trends</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-lime-400">
                    {renkoData.longestTrend}
                  </div>
                  <div className="text-xs text-gray-400">Longest</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">
                    {renkoData.avgTrend.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-400">Average</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-400">
                    {renkoData.trends.filter(t => t.direction === 'up').length}:{renkoData.trends.filter(t => t.direction === 'down').length}
                  </div>
                  <div className="text-xs text-gray-400">Up:Down Ratio</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'signals' && (
          <div className="space-y-4">
            {/* Current Signal */}
            <div className={`rounded-lg p-4 border ${
              renkoData.currentTrend.direction === 'up'
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-red-500/10 border-red-500/20'
            }`}>
              <div className="flex items-center gap-2 mb-3">
                {renkoData.currentTrend.direction === 'up' ? (
                  <TrendingUp className="w-5 h-5 text-green-400" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-red-400" />
                )}
                <h3 className="text-lg font-medium text-white">
                  {renkoData.currentTrend.direction === 'up' ? 'Bullish' : 'Bearish'} Trend Active
                </h3>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">Duration</div>
                  <div className={`text-lg font-medium ${
                    renkoData.currentTrend.direction === 'up' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {renkoData.currentTrend.length} bricks
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">Strength</div>
                  <div className="text-lg font-medium text-white">
                    {renkoData.currentTrend.length >= renkoData.avgTrend ? 'Strong' : 'Weak'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">Move</div>
                  <div className="text-lg font-medium text-white">
                    {formatBoxSize(renkoData.currentTrend.length * renkoData.brickSize)}
                  </div>
                </div>
              </div>
            </div>

            {/* Reversal Signals */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Reversal Watch</h3>
              <p className="text-sm text-gray-300 mb-4">
                Renko reversal requires price to move {formatBoxSize(renkoData.brickSize * 2)} in the opposite direction
                (2 box sizes).
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-green-500/10 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Bullish Reversal Level</div>
                  <div className="text-lg font-medium text-green-400">
                    ${formatPrice(renkoData.bricks[renkoData.bricks.length - 1]?.close + renkoData.brickSize * 2)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    If currently bearish
                  </div>
                </div>
                <div className="bg-red-500/10 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Bearish Reversal Level</div>
                  <div className="text-lg font-medium text-red-400">
                    ${formatPrice(renkoData.bricks[renkoData.bricks.length - 1]?.close - renkoData.brickSize * 2)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    If currently bullish
                  </div>
                </div>
              </div>
            </div>

            {/* Trading Strategy */}
            <div className="bg-gradient-to-r from-lime-500/10 to-green-500/10 rounded-lg p-4 border border-lime-500/20">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-lime-400" />
                <h3 className="text-sm font-medium text-white">Renko Strategy</h3>
              </div>
              <p className="text-sm text-gray-300">
                {renkoData.currentTrend.length >= renkoData.avgTrend
                  ? `Strong ${renkoData.currentTrend.direction === 'up' ? 'bullish' : 'bearish'} trend - consider ${renkoData.currentTrend.direction === 'up' ? 'long' : 'short'} positions with trend`
                  : `Trend developing - wait for ${renkoData.avgTrend.toFixed(0)}+ bricks to confirm strength`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default RenkoChart
