import React, { useState, useMemo } from 'react'
import {
  Grid3X3,
  TrendingUp,
  TrendingDown,
  Zap,
  Activity,
  Target,
  ChevronDown,
  BarChart3,
  Layers,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react'

export function FootprintChart() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('footprint') // footprint, imbalance, delta
  const [timeframe, setTimeframe] = useState('5m')

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate footprint candle data
  const footprintCandles = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const priceStep = basePrice * 0.001

    return Array.from({ length: 20 }, (_, candleIdx) => {
      const open = basePrice + (Math.random() - 0.5) * basePrice * 0.02
      const close = open + (Math.random() - 0.5) * basePrice * 0.015
      const high = Math.max(open, close) + Math.random() * basePrice * 0.005
      const low = Math.min(open, close) - Math.random() * basePrice * 0.005

      const isBullish = close > open
      const levels = []

      // Generate price levels within candle
      const numLevels = Math.floor((high - low) / priceStep) + 1
      for (let i = 0; i < numLevels; i++) {
        const price = low + i * priceStep
        const bidVolume = Math.floor(Math.random() * 5000) + 100
        const askVolume = Math.floor(Math.random() * 5000) + 100
        const delta = askVolume - bidVolume

        // Detect imbalances (3:1 ratio)
        const bidImbalance = bidVolume > askVolume * 3
        const askImbalance = askVolume > bidVolume * 3

        levels.push({
          price,
          bidVolume,
          askVolume,
          delta,
          bidImbalance,
          askImbalance,
          isPOC: false
        })
      }

      // Mark POC (highest volume level)
      const maxVolIdx = levels.reduce((maxIdx, level, idx, arr) =>
        (level.bidVolume + level.askVolume) > (arr[maxIdx].bidVolume + arr[maxIdx].askVolume) ? idx : maxIdx, 0)
      if (levels[maxVolIdx]) levels[maxVolIdx].isPOC = true

      const totalBid = levels.reduce((sum, l) => sum + l.bidVolume, 0)
      const totalAsk = levels.reduce((sum, l) => sum + l.askVolume, 0)
      const totalDelta = totalAsk - totalBid

      return {
        time: new Date(Date.now() - (19 - candleIdx) * 5 * 60 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        open,
        high,
        low,
        close,
        isBullish,
        levels: levels.reverse(),
        totalBid,
        totalAsk,
        totalVolume: totalBid + totalAsk,
        totalDelta,
        deltaPct: ((totalDelta / (totalBid + totalAsk)) * 100).toFixed(1)
      }
    })
  }, [selectedToken])

  // Statistics
  const stats = useMemo(() => {
    const totalDelta = footprintCandles.reduce((sum, c) => sum + c.totalDelta, 0)
    const totalVolume = footprintCandles.reduce((sum, c) => sum + c.totalVolume, 0)
    const imbalanceCount = footprintCandles.reduce((sum, c) =>
      sum + c.levels.filter(l => l.bidImbalance || l.askImbalance).length, 0)

    const bullishCandles = footprintCandles.filter(c => c.isBullish).length
    const avgDelta = totalDelta / footprintCandles.length

    return {
      totalDelta,
      totalVolume,
      imbalanceCount,
      bullishCandles,
      bearishCandles: footprintCandles.length - bullishCandles,
      avgDelta,
      deltaBias: totalDelta > 0 ? 'Bullish' : 'Bearish'
    }
  }, [footprintCandles])

  const formatVolume = (vol) => {
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(1)}M`
    if (vol >= 1000) return `${(vol / 1000).toFixed(1)}K`
    return vol.toString()
  }

  const getHeatmapColor = (volume, maxVolume) => {
    const intensity = volume / maxVolume
    if (intensity > 0.8) return 'bg-purple-500/40'
    if (intensity > 0.6) return 'bg-purple-500/30'
    if (intensity > 0.4) return 'bg-purple-500/20'
    if (intensity > 0.2) return 'bg-purple-500/10'
    return 'bg-white/5'
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Grid3X3 className="w-5 h-5 text-orange-400" />
            <h2 className="text-lg font-semibold text-white">Footprint Chart</h2>
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

            {/* Timeframe */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['1m', '5m', '15m', '1h'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    timeframe === tf
                      ? 'bg-orange-500/30 text-orange-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'footprint', label: 'Footprint', icon: Grid3X3 },
            { id: 'imbalance', label: 'Imbalance', icon: Zap },
            { id: 'delta', label: 'Delta Profile', icon: Activity }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-orange-500/30 text-orange-400'
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
            <div className="text-xs text-gray-500 mb-1">Total Delta</div>
            <div className={`text-sm font-medium ${stats.totalDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.totalDelta >= 0 ? '+' : ''}{formatVolume(stats.totalDelta)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Total Volume</div>
            <div className="text-sm font-medium text-white">
              {formatVolume(stats.totalVolume)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Imbalances</div>
            <div className="text-sm font-medium text-yellow-400">
              {stats.imbalanceCount}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Bullish Candles</div>
            <div className="text-sm font-medium text-green-400">
              {stats.bullishCandles}/{footprintCandles.length}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Avg Delta</div>
            <div className={`text-sm font-medium ${stats.avgDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.avgDelta >= 0 ? '+' : ''}{formatVolume(Math.round(stats.avgDelta))}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Bias</div>
            <div className={`text-sm font-medium ${stats.deltaBias === 'Bullish' ? 'text-green-400' : 'text-red-400'}`}>
              {stats.deltaBias}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'footprint' && (
          <div className="space-y-4">
            {/* Footprint Grid */}
            <div className="overflow-x-auto">
              <div className="flex gap-1 min-w-max">
                {footprintCandles.slice(-10).map((candle, candleIdx) => {
                  const maxVol = Math.max(...candle.levels.map(l => l.bidVolume + l.askVolume))

                  return (
                    <div key={candleIdx} className="flex flex-col items-center">
                      {/* Time */}
                      <div className="text-[10px] text-gray-500 mb-1">{candle.time}</div>

                      {/* Candle Footprint */}
                      <div className={`border rounded ${candle.isBullish ? 'border-green-500/50' : 'border-red-500/50'}`}>
                        {candle.levels.slice(0, 8).map((level, levelIdx) => (
                          <div
                            key={levelIdx}
                            className={`flex items-center gap-0.5 px-1 py-0.5 text-[10px] font-mono ${
                              level.isPOC ? 'bg-yellow-500/20' : getHeatmapColor(level.bidVolume + level.askVolume, maxVol)
                            }`}
                          >
                            {/* Bid */}
                            <span className={`w-8 text-right ${level.bidImbalance ? 'text-red-400 font-bold' : 'text-red-400/70'}`}>
                              {level.bidVolume}
                            </span>

                            {/* Separator */}
                            <span className="text-gray-600">x</span>

                            {/* Ask */}
                            <span className={`w-8 text-left ${level.askImbalance ? 'text-green-400 font-bold' : 'text-green-400/70'}`}>
                              {level.askVolume}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Delta */}
                      <div className={`text-[10px] font-medium mt-1 ${candle.totalDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {candle.totalDelta >= 0 ? '+' : ''}{formatVolume(candle.totalDelta)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-6 text-xs">
              <span className="flex items-center gap-1">
                <div className="w-3 h-3 bg-yellow-500/20 border border-yellow-500/50 rounded"></div>
                POC (Point of Control)
              </span>
              <span className="flex items-center gap-1">
                <span className="text-red-400 font-bold">Bold Red</span>
                Bid Imbalance (3:1)
              </span>
              <span className="flex items-center gap-1">
                <span className="text-green-400 font-bold">Bold Green</span>
                Ask Imbalance (3:1)
              </span>
            </div>
          </div>
        )}

        {viewMode === 'imbalance' && (
          <div className="space-y-4">
            {/* Imbalance Scanner */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Imbalance Zones</h3>
              <div className="space-y-2">
                {footprintCandles.flatMap((candle, candleIdx) =>
                  candle.levels
                    .filter(l => l.bidImbalance || l.askImbalance)
                    .map((level, levelIdx) => (
                      <div
                        key={`${candleIdx}-${levelIdx}`}
                        className={`flex items-center justify-between p-2 rounded ${
                          level.askImbalance ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          {level.askImbalance ? (
                            <ArrowUpRight className="w-4 h-4 text-green-400" />
                          ) : (
                            <ArrowDownRight className="w-4 h-4 text-red-400" />
                          )}
                          <div>
                            <div className="text-sm text-white">${level.price.toFixed(2)}</div>
                            <div className="text-xs text-gray-400">{candle.time}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-sm font-medium ${level.askImbalance ? 'text-green-400' : 'text-red-400'}`}>
                            {level.askImbalance ? 'Buy' : 'Sell'} Imbalance
                          </div>
                          <div className="text-xs text-gray-400">
                            {level.bidVolume} x {level.askVolume}
                          </div>
                        </div>
                      </div>
                    ))
                ).slice(0, 10)}
              </div>
            </div>

            {/* Imbalance Stack */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-green-400 mb-3">Stacked Buy Imbalances</h3>
                <div className="space-y-2">
                  {footprintCandles.slice(-5).map((candle, idx) => {
                    const askImbalances = candle.levels.filter(l => l.askImbalance)
                    if (askImbalances.length === 0) return null
                    return (
                      <div key={idx} className="flex justify-between items-center">
                        <span className="text-xs text-gray-400">{candle.time}</span>
                        <div className="flex gap-1">
                          {askImbalances.slice(0, 3).map((_, i) => (
                            <div key={i} className="w-2 h-2 bg-green-400 rounded-full"></div>
                          ))}
                        </div>
                        <span className="text-xs text-green-400">{askImbalances.length} levels</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-red-400 mb-3">Stacked Sell Imbalances</h3>
                <div className="space-y-2">
                  {footprintCandles.slice(-5).map((candle, idx) => {
                    const bidImbalances = candle.levels.filter(l => l.bidImbalance)
                    if (bidImbalances.length === 0) return null
                    return (
                      <div key={idx} className="flex justify-between items-center">
                        <span className="text-xs text-gray-400">{candle.time}</span>
                        <div className="flex gap-1">
                          {bidImbalances.slice(0, 3).map((_, i) => (
                            <div key={i} className="w-2 h-2 bg-red-400 rounded-full"></div>
                          ))}
                        </div>
                        <span className="text-xs text-red-400">{bidImbalances.length} levels</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'delta' && (
          <div className="space-y-4">
            {/* Delta Profile */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Candle Delta Profile</h3>
              <div className="space-y-1">
                {footprintCandles.slice(-15).map((candle, idx) => {
                  const maxDelta = Math.max(...footprintCandles.map(c => Math.abs(c.totalDelta)))
                  const deltaWidth = (Math.abs(candle.totalDelta) / maxDelta) * 100

                  return (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">{candle.time}</span>

                      {/* Delta Bar */}
                      <div className="flex-1 h-5 flex items-center">
                        {candle.totalDelta >= 0 ? (
                          <>
                            <div className="w-1/2"></div>
                            <div
                              className="h-full bg-green-500/60 rounded-r"
                              style={{ width: `${deltaWidth / 2}%` }}
                            />
                          </>
                        ) : (
                          <>
                            <div className="w-1/2 flex justify-end">
                              <div
                                className="h-full bg-red-500/60 rounded-l"
                                style={{ width: `${deltaWidth}%` }}
                              />
                            </div>
                            <div className="w-1/2"></div>
                          </>
                        )}
                      </div>

                      <span className={`text-xs w-16 text-right ${candle.totalDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {candle.totalDelta >= 0 ? '+' : ''}{formatVolume(candle.totalDelta)}
                      </span>
                    </div>
                  )
                })}
              </div>

              {/* Center line label */}
              <div className="flex justify-center mt-2">
                <span className="text-xs text-gray-500">0</span>
              </div>
            </div>

            {/* Cumulative Delta */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Cumulative Delta</h3>
              <div className="h-32 flex items-end gap-1">
                {footprintCandles.slice(-20).reduce((acc, candle, idx) => {
                  const prevSum = idx > 0 ? acc[idx - 1].cumDelta : 0
                  acc.push({
                    ...candle,
                    cumDelta: prevSum + candle.totalDelta
                  })
                  return acc
                }, []).map((candle, idx, arr) => {
                  const maxCum = Math.max(...arr.map(c => Math.abs(c.cumDelta)))
                  const height = (Math.abs(candle.cumDelta) / maxCum) * 100

                  return (
                    <div
                      key={idx}
                      className={`flex-1 rounded-t ${candle.cumDelta >= 0 ? 'bg-green-500/60' : 'bg-red-500/60'}`}
                      style={{ height: `${Math.max(height, 5)}%` }}
                      title={`${candle.time}: ${formatVolume(candle.cumDelta)}`}
                    />
                  )
                })}
              </div>
              <div className="flex justify-between mt-2 text-xs text-gray-500">
                <span>{footprintCandles[0]?.time}</span>
                <span>{footprintCandles[footprintCandles.length - 1]?.time}</span>
              </div>
            </div>

            {/* Delta Analysis */}
            <div className="bg-gradient-to-r from-orange-500/10 to-yellow-500/10 rounded-lg p-4 border border-orange-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-medium text-white">Delta Analysis</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">Delta Trend</div>
                  <div className={`text-sm ${
                    footprintCandles.slice(-5).reduce((sum, c) => sum + c.totalDelta, 0) > 0
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}>
                    {footprintCandles.slice(-5).reduce((sum, c) => sum + c.totalDelta, 0) > 0
                      ? 'Buyers in control (last 5 candles)'
                      : 'Sellers in control (last 5 candles)'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">Delta vs Price</div>
                  <div className="text-sm text-blue-400">
                    {footprintCandles[footprintCandles.length - 1]?.isBullish &&
                     footprintCandles[footprintCandles.length - 1]?.totalDelta > 0
                      ? 'Confirmation (price & delta aligned)'
                      : 'Divergence detected'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default FootprintChart
