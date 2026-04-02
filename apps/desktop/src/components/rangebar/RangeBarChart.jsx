import React, { useState, useMemo, useEffect } from 'react'
import { TrendingUp, TrendingDown, Ruler, Maximize2, Settings, BarChart3, Target, Activity, Gauge, Clock, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export function RangeBarChart({
  symbol = 'BTC/USDT',
  tickData = [],
  rangeSize = 50,
  onBarComplete,
  onTrendChange
}) {
  const [selectedRange, setSelectedRange] = useState(rangeSize)
  const [showVolume, setShowVolume] = useState(true)
  const [showStats, setShowStats] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)

  // Generate range bars from tick data
  const rangeBars = useMemo(() => {
    const bars = []
    let currentBar = null
    let barVolume = 0

    // Generate sample tick data if none provided
    let ticks = tickData.length > 0 ? tickData : []
    if (ticks.length === 0) {
      let price = 45000
      for (let i = 0; i < 2000; i++) {
        const change = (Math.random() - 0.49) * 30
        price += change
        ticks.push({
          price,
          volume: Math.floor(Math.random() * 10 + 1),
          time: Date.now() - (2000 - i) * 1000
        })
      }
    }

    for (const tick of ticks) {
      barVolume += tick.volume || 1

      if (!currentBar) {
        currentBar = {
          open: tick.price,
          high: tick.price,
          low: tick.price,
          close: tick.price,
          startTime: tick.time,
          endTime: tick.time,
          volume: barVolume,
          tickCount: 1
        }
      } else {
        currentBar.high = Math.max(currentBar.high, tick.price)
        currentBar.low = Math.min(currentBar.low, tick.price)
        currentBar.close = tick.price
        currentBar.endTime = tick.time
        currentBar.volume = barVolume
        currentBar.tickCount++

        // Check if range is complete
        const range = currentBar.high - currentBar.low
        if (range >= selectedRange) {
          currentBar.isBullish = currentBar.close > currentBar.open
          currentBar.range = range
          currentBar.duration = currentBar.endTime - currentBar.startTime
          bars.push({ ...currentBar })

          // Start new bar
          currentBar = {
            open: tick.price,
            high: tick.price,
            low: tick.price,
            close: tick.price,
            startTime: tick.time,
            endTime: tick.time,
            volume: 0,
            tickCount: 0
          }
          barVolume = 0
        }
      }
    }

    // Add incomplete bar
    if (currentBar && currentBar.tickCount > 0) {
      currentBar.isBullish = currentBar.close > currentBar.open
      currentBar.range = currentBar.high - currentBar.low
      currentBar.duration = currentBar.endTime - currentBar.startTime
      currentBar.isIncomplete = true
      bars.push(currentBar)
    }

    return bars
  }, [tickData, selectedRange])

  // Calculate statistics
  const stats = useMemo(() => {
    if (rangeBars.length < 2) return null

    const completeBars = rangeBars.filter(b => !b.isIncomplete)
    const bullishBars = completeBars.filter(b => b.isBullish)
    const bearishBars = completeBars.filter(b => !b.isBullish)

    // Average duration per bar
    const avgDuration = completeBars.reduce((sum, b) => sum + b.duration, 0) / completeBars.length
    const avgVolume = completeBars.reduce((sum, b) => sum + b.volume, 0) / completeBars.length
    const avgTicksPerBar = completeBars.reduce((sum, b) => sum + b.tickCount, 0) / completeBars.length

    // Trend analysis
    const recent10 = completeBars.slice(-10)
    const recentBullish = recent10.filter(b => b.isBullish).length
    const trend = recentBullish > 6 ? 'bullish' : recentBullish < 4 ? 'bearish' : 'neutral'

    // Velocity (bars per minute)
    const totalTime = completeBars.length > 1
      ? completeBars[completeBars.length - 1].endTime - completeBars[0].startTime
      : 0
    const velocity = totalTime > 0 ? (completeBars.length / (totalTime / 60000)).toFixed(2) : 0

    // Consecutive count
    let consecutiveCount = 1
    for (let i = completeBars.length - 2; i >= 0; i--) {
      if (completeBars[i].isBullish === completeBars[completeBars.length - 1].isBullish) {
        consecutiveCount++
      } else {
        break
      }
    }

    return {
      totalBars: completeBars.length,
      bullishBars: bullishBars.length,
      bearishBars: bearishBars.length,
      bullishPercent: ((bullishBars.length / completeBars.length) * 100).toFixed(1),
      avgDuration: avgDuration / 1000, // seconds
      avgVolume: avgVolume.toFixed(0),
      avgTicksPerBar: avgTicksPerBar.toFixed(0),
      trend,
      velocity,
      consecutiveCount,
      lastBarDirection: completeBars[completeBars.length - 1]?.isBullish ? 'bullish' : 'bearish'
    }
  }, [rangeBars])

  // Render range bars
  const renderBars = () => {
    const visibleBars = rangeBars.slice(-50)
    const maxPrice = Math.max(...visibleBars.map(b => b.high))
    const minPrice = Math.min(...visibleBars.map(b => b.low))
    const priceRange = maxPrice - minPrice
    const chartHeight = 180
    const maxVolume = Math.max(...visibleBars.map(b => b.volume))

    const priceToY = (price) => {
      return chartHeight - ((price - minPrice) / priceRange) * chartHeight
    }

    return (
      <svg className="w-full h-[220px]" viewBox={`0 0 ${visibleBars.length * 14} 220`}>
        {/* Price chart area */}
        <g>
          {/* Grid */}
          {[0.25, 0.5, 0.75].map(pct => (
            <line
              key={pct}
              x1={0}
              y1={chartHeight * pct}
              x2={visibleBars.length * 14}
              y2={chartHeight * pct}
              stroke="rgba(255,255,255,0.05)"
              strokeDasharray="2,2"
            />
          ))}

          {/* Bars */}
          {visibleBars.map((bar, idx) => {
            const x = idx * 14 + 7
            const color = bar.isBullish ? '#10b981' : '#ef4444'
            const opacity = bar.isIncomplete ? 0.5 : 1

            return (
              <g key={idx}>
                {/* Wick */}
                <line
                  x1={x}
                  y1={priceToY(bar.high)}
                  x2={x}
                  y2={priceToY(bar.low)}
                  stroke={color}
                  strokeWidth={1}
                  opacity={opacity}
                />
                {/* Body */}
                <rect
                  x={x - 5}
                  y={priceToY(Math.max(bar.open, bar.close))}
                  width={10}
                  height={Math.max(2, Math.abs(priceToY(bar.open) - priceToY(bar.close)))}
                  fill={color}
                  opacity={opacity}
                  rx={1}
                />
                {/* Incomplete marker */}
                {bar.isIncomplete && (
                  <circle cx={x} cy={priceToY(bar.close) - 8} r={2} fill="#fbbf24" />
                )}
              </g>
            )
          })}
        </g>

        {/* Volume bars */}
        {showVolume && (
          <g transform={`translate(0, ${chartHeight + 10})`}>
            {visibleBars.map((bar, idx) => {
              const x = idx * 14 + 2
              const volHeight = (bar.volume / maxVolume) * 25
              return (
                <rect
                  key={idx}
                  x={x}
                  y={25 - volHeight}
                  width={10}
                  height={volHeight}
                  fill={bar.isBullish ? '#10b981' : '#ef4444'}
                  opacity={bar.isIncomplete ? 0.3 : 0.5}
                  rx={1}
                />
              )
            })}
          </g>
        )}
      </svg>
    )
  }

  const rangeSizes = [25, 50, 100, 200, 500, 1000]

  return (
    <div className={`bg-[#0a0e14] rounded-lg border border-white/10 ${isExpanded ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg">
            <Ruler className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">Range Bar Chart</h3>
            <p className="text-xs text-white/50">{symbol} • ${selectedRange} Range • Time Independent</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={selectedRange}
            onChange={(e) => setSelectedRange(Number(e.target.value))}
            className="bg-white/5 text-xs text-white rounded px-2 py-1 border border-white/10"
          >
            {rangeSizes.map(size => (
              <option key={size} value={size}>${size}</option>
            ))}
          </select>

          <button
            onClick={() => setShowVolume(!showVolume)}
            className={`p-1.5 rounded ${showVolume ? 'bg-cyan-500/20 text-cyan-400' : 'bg-white/5 text-white/40'}`}
          >
            <BarChart3 className="w-4 h-4" />
          </button>

          <button
            onClick={() => setShowStats(!showStats)}
            className={`p-1.5 rounded ${showStats ? 'bg-cyan-500/20 text-cyan-400' : 'bg-white/5 text-white/40'}`}
          >
            <Activity className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 bg-white/5 rounded hover:bg-white/10"
          >
            <Maximize2 className="w-4 h-4 text-white/60" />
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && showStats && (
        <div className="grid grid-cols-6 gap-2 p-3 border-b border-white/10">
          <div className="text-center">
            <div className="text-lg font-bold text-white">{stats.totalBars}</div>
            <div className="text-[10px] text-white/40">Total Bars</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-emerald-400">{stats.bullishBars}</div>
            <div className="text-[10px] text-white/40">Bullish</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-red-400">{stats.bearishBars}</div>
            <div className="text-[10px] text-white/40">Bearish</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-cyan-400">{stats.velocity}</div>
            <div className="text-[10px] text-white/40">Bars/min</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-white">{stats.avgTicksPerBar}</div>
            <div className="text-[10px] text-white/40">Ticks/Bar</div>
          </div>
          <div className="text-center">
            <div className={`text-lg font-bold ${
              stats.trend === 'bullish' ? 'text-emerald-400' :
              stats.trend === 'bearish' ? 'text-red-400' : 'text-white/60'
            }`}>
              {stats.trend === 'bullish' ? '↑' : stats.trend === 'bearish' ? '↓' : '→'}
            </div>
            <div className="text-[10px] text-white/40">Trend</div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="p-3 border-b border-white/10">
        {renderBars()}
      </div>

      {/* Detailed Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3 p-3 border-b border-white/10">
          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center gap-2 mb-1">
              <Gauge className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] text-white/40">Bull/Bear Ratio</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-white/10 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${stats.bullishPercent}%` }}
                />
              </div>
              <span className="text-xs text-white">{stats.bullishPercent}%</span>
            </div>
          </div>

          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] text-white/40">Avg Duration</span>
            </div>
            <div className="text-sm font-bold text-white">
              {stats.avgDuration < 60
                ? `${stats.avgDuration.toFixed(1)}s`
                : `${(stats.avgDuration / 60).toFixed(1)}m`
              }
            </div>
          </div>

          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center gap-2 mb-1">
              <BarChart3 className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] text-white/40">Avg Volume</span>
            </div>
            <div className="text-sm font-bold text-white">{stats.avgVolume}</div>
          </div>

          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center gap-2 mb-1">
              <Activity className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] text-white/40">Consecutive</span>
            </div>
            <div className={`text-sm font-bold flex items-center gap-1 ${
              stats.lastBarDirection === 'bullish' ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {stats.lastBarDirection === 'bullish' ? (
                <ArrowUpRight className="w-3 h-3" />
              ) : (
                <ArrowDownRight className="w-3 h-3" />
              )}
              {stats.consecutiveCount}
            </div>
          </div>
        </div>
      )}

      {/* Current Bar Progress */}
      {rangeBars.length > 0 && rangeBars[rangeBars.length - 1].isIncomplete && (
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-white/60">Current Bar Progress</span>
            <span className="text-xs text-yellow-400">Building...</span>
          </div>
          <div className="bg-white/10 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-cyan-500 transition-all duration-300"
              style={{
                width: `${Math.min(100, (rangeBars[rangeBars.length - 1].range / selectedRange) * 100)}%`
              }}
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-white/40">
            <span>${rangeBars[rangeBars.length - 1].range.toFixed(2)}</span>
            <span>${selectedRange}</span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="p-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-emerald-500 rounded-sm"></div>
            <span className="text-white/40">Bullish</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
            <span className="text-white/40">Bearish</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
            <span className="text-white/40">Building</span>
          </div>
        </div>
        <div className="text-white/30">
          Pure Price Action • No Time Dependency
        </div>
      </div>
    </div>
  )
}

export default RangeBarChart
