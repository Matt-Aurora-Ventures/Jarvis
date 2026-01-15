import React, { useState, useMemo, useEffect } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Activity,
  ChevronDown,
  Pause,
  Play,
  Settings,
  Zap
} from 'lucide-react'

export function TickChart() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [tickSize, setTickSize] = useState(100) // Number of trades per bar
  const [isPlaying, setIsPlaying] = useState(true)
  const [viewMode, setViewMode] = useState('chart') // chart, stats, volume
  const [bars, setBars] = useState([])

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate initial tick bars
  useEffect(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const initialBars = []

    for (let i = 0; i < 50; i++) {
      const open = basePrice + (Math.random() - 0.5) * basePrice * 0.005
      const close = open + (Math.random() - 0.5) * basePrice * 0.003
      const high = Math.max(open, close) + Math.random() * basePrice * 0.001
      const low = Math.min(open, close) - Math.random() * basePrice * 0.001
      const volume = Math.floor(Math.random() * 50000) + 5000
      const trades = tickSize
      const buyVolume = volume * (0.4 + Math.random() * 0.2)
      const sellVolume = volume - buyVolume
      const delta = buyVolume - sellVolume

      initialBars.push({
        id: Date.now() + i,
        open,
        high,
        low,
        close,
        volume,
        trades,
        buyVolume,
        sellVolume,
        delta,
        isBullish: close > open,
        time: new Date(Date.now() - (49 - i) * 30000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      })
    }

    setBars(initialBars)
  }, [selectedToken, tickSize])

  // Add new bars
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      setBars(prev => {
        if (prev.length === 0) return prev

        const lastBar = prev[prev.length - 1]
        const basePrice = lastBar.close
        const open = basePrice
        const close = open + (Math.random() - 0.5) * basePrice * 0.003
        const high = Math.max(open, close) + Math.random() * basePrice * 0.001
        const low = Math.min(open, close) - Math.random() * basePrice * 0.001
        const volume = Math.floor(Math.random() * 50000) + 5000
        const buyVolume = volume * (0.4 + Math.random() * 0.2)
        const sellVolume = volume - buyVolume

        const newBar = {
          id: Date.now(),
          open,
          high,
          low,
          close,
          volume,
          trades: tickSize,
          buyVolume,
          sellVolume,
          delta: buyVolume - sellVolume,
          isBullish: close > open,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }

        return [...prev.slice(-49), newBar]
      })
    }, 3000)

    return () => clearInterval(interval)
  }, [isPlaying, tickSize])

  // Statistics
  const stats = useMemo(() => {
    if (bars.length === 0) return null

    const bullishBars = bars.filter(b => b.isBullish).length
    const bearishBars = bars.length - bullishBars
    const totalVolume = bars.reduce((sum, b) => sum + b.volume, 0)
    const totalDelta = bars.reduce((sum, b) => sum + b.delta, 0)
    const avgVolume = totalVolume / bars.length
    const avgRange = bars.reduce((sum, b) => sum + (b.high - b.low), 0) / bars.length

    const priceChange = bars.length > 1 ? bars[bars.length - 1].close - bars[0].open : 0
    const priceChangePct = bars.length > 1 ? (priceChange / bars[0].open) * 100 : 0

    return {
      bullishBars,
      bearishBars,
      bullishPct: (bullishBars / bars.length) * 100,
      totalVolume,
      totalDelta,
      avgVolume,
      avgRange,
      priceChange,
      priceChangePct,
      currentPrice: bars[bars.length - 1]?.close || 0
    }
  }, [bars])

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(2)
    if (selectedToken === 'ETH') return price.toFixed(2)
    return price.toFixed(4)
  }

  const formatVolume = (vol) => {
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(1)}M`
    if (vol >= 1000) return `${(vol / 1000).toFixed(0)}K`
    return vol.toString()
  }

  // Calculate chart dimensions
  const chartHeight = 200
  const prices = bars.flatMap(b => [b.high, b.low])
  const minPrice = Math.min(...prices) * 0.9999
  const maxPrice = Math.max(...prices) * 1.0001
  const priceRange = maxPrice - minPrice

  const maxVolume = Math.max(...bars.map(b => b.volume))

  const priceToY = (price) => {
    return chartHeight - ((price - minPrice) / priceRange) * chartHeight
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-violet-400" />
            <h2 className="text-lg font-semibold text-white">Tick Chart</h2>
            <div className="flex items-center gap-1 ml-2">
              {isPlaying ? (
                <>
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-xs text-gray-400">Live</span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                  <span className="text-xs text-gray-400">Paused</span>
                </>
              )}
            </div>
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

            {/* Tick Size */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {[50, 100, 200, 500].map((size) => (
                <button
                  key={size}
                  onClick={() => setTickSize(size)}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    tickSize === size
                      ? 'bg-violet-500/30 text-violet-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {size}T
                </button>
              ))}
            </div>

            {/* Play/Pause */}
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`p-1.5 rounded-lg transition-colors ${
                isPlaying ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
              }`}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'chart', label: 'Tick Chart', icon: BarChart3 },
            { id: 'stats', label: 'Statistics', icon: Activity },
            { id: 'volume', label: 'Volume Profile', icon: TrendingUp }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-violet-500/30 text-violet-400'
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
      {stats && (
        <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Current</div>
              <div className="text-sm font-medium text-white">
                ${formatPrice(stats.currentPrice)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Change</div>
              <div className={`text-sm font-medium ${stats.priceChangePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.priceChangePct >= 0 ? '+' : ''}{stats.priceChangePct.toFixed(3)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Bullish Bars</div>
              <div className="text-sm font-medium text-green-400">
                {stats.bullishBars} ({stats.bullishPct.toFixed(0)}%)
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Total Volume</div>
              <div className="text-sm font-medium text-white">
                {formatVolume(stats.totalVolume)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Net Delta</div>
              <div className={`text-sm font-medium ${stats.totalDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.totalDelta >= 0 ? '+' : ''}{formatVolume(stats.totalDelta)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Tick Size</div>
              <div className="text-sm font-medium text-violet-400">
                {tickSize} trades/bar
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'chart' && (
          <div className="space-y-4">
            {/* Candlestick Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <svg width="100%" height={chartHeight} className="overflow-visible">
                {bars.map((bar, idx) => {
                  const barWidth = 100 / bars.length
                  const x = idx * barWidth + barWidth / 2

                  const yOpen = priceToY(bar.open)
                  const yClose = priceToY(bar.close)
                  const yHigh = priceToY(bar.high)
                  const yLow = priceToY(bar.low)

                  const bodyTop = Math.min(yOpen, yClose)
                  const bodyHeight = Math.abs(yOpen - yClose) || 1

                  return (
                    <g key={bar.id}>
                      {/* Wick */}
                      <line
                        x1={`${x}%`}
                        y1={yHigh}
                        x2={`${x}%`}
                        y2={yLow}
                        stroke={bar.isBullish ? '#22c55e' : '#ef4444'}
                        strokeWidth="1"
                      />
                      {/* Body */}
                      <rect
                        x={`${x - barWidth * 0.3}%`}
                        y={bodyTop}
                        width={`${barWidth * 0.6}%`}
                        height={bodyHeight}
                        fill={bar.isBullish ? '#22c55e' : '#ef4444'}
                        opacity="0.8"
                      />
                    </g>
                  )
                })}
              </svg>

              {/* X-axis time labels */}
              <div className="flex justify-between mt-2 text-xs text-gray-500">
                {bars.filter((_, i) => i % 10 === 0).map((bar, idx) => (
                  <span key={idx}>{bar.time}</span>
                ))}
              </div>
            </div>

            {/* Volume Bars */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-2">Volume per Tick</h3>
              <div className="h-16 flex items-end gap-0.5">
                {bars.map((bar, idx) => (
                  <div
                    key={bar.id}
                    className={`flex-1 rounded-t ${bar.isBullish ? 'bg-green-500/60' : 'bg-red-500/60'}`}
                    style={{ height: `${(bar.volume / maxVolume) * 100}%` }}
                    title={`${formatVolume(bar.volume)}`}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {viewMode === 'stats' && stats && (
          <div className="space-y-4">
            {/* Bar Statistics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-green-500/10 rounded-lg p-4 text-center border border-green-500/20">
                <div className="text-3xl font-bold text-green-400">
                  {stats.bullishBars}
                </div>
                <div className="text-xs text-gray-400 mt-1">Bullish Bars</div>
                <div className="text-xs text-green-400 mt-1">
                  {stats.bullishPct.toFixed(1)}%
                </div>
              </div>
              <div className="bg-red-500/10 rounded-lg p-4 text-center border border-red-500/20">
                <div className="text-3xl font-bold text-red-400">
                  {stats.bearishBars}
                </div>
                <div className="text-xs text-gray-400 mt-1">Bearish Bars</div>
                <div className="text-xs text-red-400 mt-1">
                  {(100 - stats.bullishPct).toFixed(1)}%
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-white">
                  {formatVolume(stats.avgVolume)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Avg Volume/Bar</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-violet-400">
                  ${stats.avgRange.toFixed(4)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Avg Range</div>
              </div>
            </div>

            {/* Trading Insight */}
            <div className={`rounded-lg p-4 border ${
              stats.bullishPct > 60 ? 'bg-green-500/10 border-green-500/20' :
              stats.bullishPct < 40 ? 'bg-red-500/10 border-red-500/20' :
              'bg-white/5 border-white/10'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className={`w-4 h-4 ${
                  stats.bullishPct > 60 ? 'text-green-400' :
                  stats.bullishPct < 40 ? 'text-red-400' :
                  'text-gray-400'
                }`} />
                <h3 className="text-sm font-medium text-white">Tick Analysis</h3>
              </div>
              <p className="text-sm text-gray-300">
                {stats.bullishPct > 60
                  ? `Strong bullish tick bias (${stats.bullishPct.toFixed(0)}%) - buyers dominating short-term action`
                  : stats.bullishPct < 40
                  ? `Strong bearish tick bias (${(100 - stats.bullishPct).toFixed(0)}%) - sellers dominating short-term action`
                  : `Balanced tick distribution (${stats.bullishPct.toFixed(0)}% bullish) - no clear short-term bias`}
              </p>
            </div>
          </div>
        )}

        {viewMode === 'volume' && (
          <div className="space-y-4">
            {/* Delta Profile */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Cumulative Delta</h3>
              <div className="h-32 flex items-end gap-1">
                {bars.reduce((acc, bar, idx) => {
                  const prevDelta = idx > 0 ? acc[idx - 1].cumDelta : 0
                  acc.push({
                    ...bar,
                    cumDelta: prevDelta + bar.delta
                  })
                  return acc
                }, []).map((bar, idx, arr) => {
                  const maxCum = Math.max(...arr.map(b => Math.abs(b.cumDelta)))
                  const height = Math.abs(bar.cumDelta) / maxCum * 100

                  return (
                    <div
                      key={bar.id}
                      className={`flex-1 rounded-t transition-all ${
                        bar.cumDelta >= 0 ? 'bg-green-500/60' : 'bg-red-500/60'
                      }`}
                      style={{ height: `${Math.max(height, 5)}%` }}
                      title={`Delta: ${formatVolume(bar.cumDelta)}`}
                    />
                  )
                })}
              </div>
            </div>

            {/* Buy/Sell Volume Split */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
                <h3 className="text-sm font-medium text-green-400 mb-2">Buy Volume</h3>
                <div className="text-2xl font-bold text-green-400">
                  {formatVolume(bars.reduce((sum, b) => sum + b.buyVolume, 0))}
                </div>
                <div className="h-20 flex items-end gap-0.5 mt-3">
                  {bars.slice(-20).map((bar) => (
                    <div
                      key={bar.id}
                      className="flex-1 bg-green-500/60 rounded-t"
                      style={{ height: `${(bar.buyVolume / Math.max(...bars.map(b => b.buyVolume))) * 100}%` }}
                    />
                  ))}
                </div>
              </div>
              <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
                <h3 className="text-sm font-medium text-red-400 mb-2">Sell Volume</h3>
                <div className="text-2xl font-bold text-red-400">
                  {formatVolume(bars.reduce((sum, b) => sum + b.sellVolume, 0))}
                </div>
                <div className="h-20 flex items-end gap-0.5 mt-3">
                  {bars.slice(-20).map((bar) => (
                    <div
                      key={bar.id}
                      className="flex-1 bg-red-500/60 rounded-t"
                      style={{ height: `${(bar.sellVolume / Math.max(...bars.map(b => b.sellVolume))) * 100}%` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TickChart
