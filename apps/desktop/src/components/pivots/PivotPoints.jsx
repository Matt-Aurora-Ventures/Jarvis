import React, { useState, useMemo, useEffect } from 'react'
import {
  Crosshair,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Settings,
  Target,
  ArrowUp,
  ArrowDown,
  Calendar,
  ChevronUp,
  ChevronDown
} from 'lucide-react'

export function PivotPoints() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [pivotType, setPivotType] = useState('standard') // standard, fibonacci, camarilla, woodie, demark
  const [timeframe, setTimeframe] = useState('daily') // daily, weekly, monthly
  const [viewMode, setViewMode] = useState('levels') // levels, chart, analysis
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const pivotTypes = ['standard', 'fibonacci', 'camarilla', 'woodie', 'demark']
  const timeframes = ['daily', 'weekly', 'monthly']

  // Generate mock OHLC data and calculate pivots
  const pivotData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Previous period OHLC
    const high = currentPrice * (1.02 + Math.random() * 0.03)
    const low = currentPrice * (0.95 + Math.random() * 0.03)
    const close = currentPrice * (0.98 + Math.random() * 0.04)
    const open = currentPrice * (0.97 + Math.random() * 0.04)

    let pivots = {}

    // Standard Pivot Points
    const standardPP = (high + low + close) / 3
    const standardR1 = (2 * standardPP) - low
    const standardR2 = standardPP + (high - low)
    const standardR3 = high + 2 * (standardPP - low)
    const standardS1 = (2 * standardPP) - high
    const standardS2 = standardPP - (high - low)
    const standardS3 = low - 2 * (high - standardPP)

    if (pivotType === 'standard') {
      pivots = {
        name: 'Standard',
        pp: standardPP,
        r1: standardR1,
        r2: standardR2,
        r3: standardR3,
        s1: standardS1,
        s2: standardS2,
        s3: standardS3
      }
    }

    // Fibonacci Pivot Points
    else if (pivotType === 'fibonacci') {
      const range = high - low
      pivots = {
        name: 'Fibonacci',
        pp: standardPP,
        r1: standardPP + (range * 0.382),
        r2: standardPP + (range * 0.618),
        r3: standardPP + range,
        s1: standardPP - (range * 0.382),
        s2: standardPP - (range * 0.618),
        s3: standardPP - range
      }
    }

    // Camarilla Pivot Points
    else if (pivotType === 'camarilla') {
      const range = high - low
      pivots = {
        name: 'Camarilla',
        pp: standardPP,
        r1: close + (range * 1.1 / 12),
        r2: close + (range * 1.1 / 6),
        r3: close + (range * 1.1 / 4),
        r4: close + (range * 1.1 / 2),
        s1: close - (range * 1.1 / 12),
        s2: close - (range * 1.1 / 6),
        s3: close - (range * 1.1 / 4),
        s4: close - (range * 1.1 / 2)
      }
    }

    // Woodie Pivot Points
    else if (pivotType === 'woodie') {
      const woodiePP = (high + low + (2 * close)) / 4
      pivots = {
        name: 'Woodie',
        pp: woodiePP,
        r1: (2 * woodiePP) - low,
        r2: woodiePP + high - low,
        s1: (2 * woodiePP) - high,
        s2: woodiePP - high + low
      }
    }

    // DeMark Pivot Points
    else if (pivotType === 'demark') {
      let x
      if (close < open) {
        x = high + (2 * low) + close
      } else if (close > open) {
        x = (2 * high) + low + close
      } else {
        x = high + low + (2 * close)
      }
      pivots = {
        name: 'DeMark',
        pp: x / 4,
        r1: x / 2 - low,
        s1: x / 2 - high
      }
    }

    // Determine price position
    let pricePosition = 'at_pivot'
    const sortedLevels = Object.entries(pivots)
      .filter(([key]) => key !== 'name' && key !== 'pp')
      .sort(([, a], [, b]) => b - a)

    for (const [key, value] of sortedLevels) {
      if (currentPrice > value) {
        pricePosition = key.startsWith('r') ? `above_${key}` : `above_${key}`
        break
      }
    }

    // Distance to nearest levels
    const aboveLevels = Object.entries(pivots)
      .filter(([key, val]) => key !== 'name' && val > currentPrice)
      .sort(([, a], [, b]) => a - b)

    const belowLevels = Object.entries(pivots)
      .filter(([key, val]) => key !== 'name' && val < currentPrice)
      .sort(([, a], [, b]) => b - a)

    const nearestResistance = aboveLevels[0]
    const nearestSupport = belowLevels[0]

    // Trading bias based on pivot
    const tradingBias = currentPrice > pivots.pp ? 'bullish' : currentPrice < pivots.pp ? 'bearish' : 'neutral'

    return {
      currentPrice,
      high,
      low,
      close,
      open,
      pivots,
      pricePosition,
      nearestResistance,
      nearestSupport,
      tradingBias,
      distanceToResistance: nearestResistance ? ((nearestResistance[1] - currentPrice) / currentPrice * 100) : null,
      distanceToSupport: nearestSupport ? ((currentPrice - nearestSupport[1]) / currentPrice * 100) : null
    }
  }, [selectedToken, pivotType, timeframe])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const getLevelName = (key) => {
    const names = {
      pp: 'Pivot Point',
      r1: 'Resistance 1',
      r2: 'Resistance 2',
      r3: 'Resistance 3',
      r4: 'Resistance 4',
      s1: 'Support 1',
      s2: 'Support 2',
      s3: 'Support 3',
      s4: 'Support 4'
    }
    return names[key] || key.toUpperCase()
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Crosshair className="w-6 h-6 text-violet-400" />
          <h2 className="text-xl font-bold text-white">Pivot Points</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {tokens.map(token => (
              <option key={token} value={token}>{token}</option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Settings */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-3 bg-white/5 rounded-lg border border-white/10">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-gray-400" />
          <span className="text-gray-400 text-sm">Type:</span>
          <select
            value={pivotType}
            onChange={(e) => setPivotType(e.target.value)}
            className="bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm capitalize"
          >
            {pivotTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-400" />
          <span className="text-gray-400 text-sm">Period:</span>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm capitalize"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Status Summary */}
      <div className={`rounded-lg p-4 mb-6 border ${
        pivotData.tradingBias === 'bullish' ? 'bg-green-500/10 border-green-500/20' :
        pivotData.tradingBias === 'bearish' ? 'bg-red-500/10 border-red-500/20' :
        'bg-yellow-500/10 border-yellow-500/20'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Pivot Point</div>
            <div className="text-xl font-bold text-violet-400">${formatPrice(pivotData.pivots.pp)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Trading Bias</div>
            <div className={`text-lg font-bold capitalize flex items-center gap-2 ${
              pivotData.tradingBias === 'bullish' ? 'text-green-400' :
              pivotData.tradingBias === 'bearish' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {pivotData.tradingBias === 'bullish' ? <TrendingUp className="w-4 h-4" /> :
               pivotData.tradingBias === 'bearish' ? <TrendingDown className="w-4 h-4" /> : null}
              {pivotData.tradingBias}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Nearest Resistance</div>
            {pivotData.nearestResistance ? (
              <div>
                <span className="text-red-400 font-medium">${formatPrice(pivotData.nearestResistance[1])}</span>
                <span className="text-gray-500 text-sm ml-2">({pivotData.distanceToResistance?.toFixed(2)}%)</span>
              </div>
            ) : <span className="text-gray-500">-</span>}
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Nearest Support</div>
            {pivotData.nearestSupport ? (
              <div>
                <span className="text-green-400 font-medium">${formatPrice(pivotData.nearestSupport[1])}</span>
                <span className="text-gray-500 text-sm ml-2">({pivotData.distanceToSupport?.toFixed(2)}%)</span>
              </div>
            ) : <span className="text-gray-500">-</span>}
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'levels', label: 'Levels' },
          { id: 'chart', label: 'Chart' },
          { id: 'analysis', label: 'Analysis' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Levels View */}
      {viewMode === 'levels' && (
        <div className="space-y-2">
          {/* Resistance Levels */}
          {Object.entries(pivotData.pivots)
            .filter(([key]) => key.startsWith('r'))
            .sort(([a], [b]) => {
              const numA = parseInt(a.slice(1))
              const numB = parseInt(b.slice(1))
              return numB - numA
            })
            .map(([key, value]) => (
              <div key={key} className={`flex items-center justify-between p-3 rounded-lg border ${
                pivotData.currentPrice > value ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
              }`}>
                <div className="flex items-center gap-3">
                  <ChevronUp className="w-4 h-4 text-red-400" />
                  <span className="text-white font-medium">{getLevelName(key)}</span>
                </div>
                <div className="text-right">
                  <span className="text-white font-bold">${formatPrice(value)}</span>
                  <span className="text-gray-500 text-sm ml-2">
                    ({((value - pivotData.currentPrice) / pivotData.currentPrice * 100).toFixed(2)}%)
                  </span>
                </div>
              </div>
            ))}

          {/* Pivot Point */}
          <div className="flex items-center justify-between p-3 rounded-lg border bg-violet-500/10 border-violet-500/20">
            <div className="flex items-center gap-3">
              <Crosshair className="w-4 h-4 text-violet-400" />
              <span className="text-white font-medium">Pivot Point</span>
            </div>
            <div className="text-right">
              <span className="text-violet-400 font-bold">${formatPrice(pivotData.pivots.pp)}</span>
              <span className="text-gray-500 text-sm ml-2">
                ({((pivotData.pivots.pp - pivotData.currentPrice) / pivotData.currentPrice * 100).toFixed(2)}%)
              </span>
            </div>
          </div>

          {/* Support Levels */}
          {Object.entries(pivotData.pivots)
            .filter(([key]) => key.startsWith('s'))
            .sort(([a], [b]) => {
              const numA = parseInt(a.slice(1))
              const numB = parseInt(b.slice(1))
              return numA - numB
            })
            .map(([key, value]) => (
              <div key={key} className={`flex items-center justify-between p-3 rounded-lg border ${
                pivotData.currentPrice < value ? 'bg-red-500/10 border-red-500/20' : 'bg-green-500/10 border-green-500/20'
              }`}>
                <div className="flex items-center gap-3">
                  <ChevronDown className="w-4 h-4 text-green-400" />
                  <span className="text-white font-medium">{getLevelName(key)}</span>
                </div>
                <div className="text-right">
                  <span className="text-white font-bold">${formatPrice(value)}</span>
                  <span className="text-gray-500 text-sm ml-2">
                    ({((value - pivotData.currentPrice) / pivotData.currentPrice * 100).toFixed(2)}%)
                  </span>
                </div>
              </div>
            ))}

          {/* Current Price */}
          <div className="flex items-center justify-between p-3 rounded-lg border bg-white/10 border-white/20 mt-4">
            <span className="text-gray-400">Current Price</span>
            <span className="text-white font-bold">${formatPrice(pivotData.currentPrice)}</span>
          </div>
        </div>
      )}

      {/* Chart View */}
      {viewMode === 'chart' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">Pivot Levels Visualization</h3>
          <div className="relative h-80">
            {/* Create visual representation */}
            {(() => {
              const allLevels = Object.entries(pivotData.pivots)
                .filter(([key]) => key !== 'name')
                .map(([key, value]) => ({ key, value }))

              const maxPrice = Math.max(...allLevels.map(l => l.value), pivotData.currentPrice) * 1.02
              const minPrice = Math.min(...allLevels.map(l => l.value), pivotData.currentPrice) * 0.98

              return allLevels.map((level, i) => {
                const position = ((maxPrice - level.value) / (maxPrice - minPrice)) * 100

                return (
                  <div
                    key={level.key}
                    className={`absolute left-0 right-0 h-0.5 ${
                      level.key === 'pp' ? 'bg-violet-400' :
                      level.key.startsWith('r') ? 'bg-red-400' : 'bg-green-400'
                    }`}
                    style={{ top: `${position}%` }}
                  >
                    <span className={`absolute left-2 -top-5 text-xs px-2 py-0.5 rounded ${
                      level.key === 'pp' ? 'text-violet-400 bg-violet-500/20' :
                      level.key.startsWith('r') ? 'text-red-400 bg-red-500/20' : 'text-green-400 bg-green-500/20'
                    }`}>
                      {level.key.toUpperCase()}: ${formatPrice(level.value)}
                    </span>
                  </div>
                )
              })
            })()}

            {/* Current price marker */}
            <div
              className="absolute left-0 right-0 h-1 bg-white"
              style={{
                top: `${((Math.max(...Object.values(pivotData.pivots).filter(v => typeof v === 'number')) * 1.02 - pivotData.currentPrice) /
                       (Math.max(...Object.values(pivotData.pivots).filter(v => typeof v === 'number')) * 1.02 -
                        Math.min(...Object.values(pivotData.pivots).filter(v => typeof v === 'number')) * 0.98)) * 100}%`
              }}
            >
              <span className="absolute right-2 -top-5 text-xs text-white bg-white/20 px-2 py-0.5 rounded">
                Price: ${formatPrice(pivotData.currentPrice)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Analysis View */}
      {viewMode === 'analysis' && (
        <div className="space-y-4">
          {/* Previous Period Data */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3">Previous {timeframe.charAt(0).toUpperCase() + timeframe.slice(1)} Data</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-gray-400 text-sm">Open</div>
                <div className="text-white font-medium">${formatPrice(pivotData.open)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">High</div>
                <div className="text-green-400 font-medium">${formatPrice(pivotData.high)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Low</div>
                <div className="text-red-400 font-medium">${formatPrice(pivotData.low)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Close</div>
                <div className="text-white font-medium">${formatPrice(pivotData.close)}</div>
              </div>
            </div>
          </div>

          {/* Trading Strategy */}
          <div className={`rounded-lg p-4 border ${
            pivotData.tradingBias === 'bullish' ? 'bg-green-500/10 border-green-500/20' :
            pivotData.tradingBias === 'bearish' ? 'bg-red-500/10 border-red-500/20' :
            'bg-yellow-500/10 border-yellow-500/20'
          }`}>
            <h3 className="text-white font-medium mb-2">Trading Strategy</h3>
            <div className="text-gray-400 text-sm space-y-2">
              {pivotData.tradingBias === 'bullish' ? (
                <>
                  <p>Price is above the pivot point, indicating bullish bias.</p>
                  <p><span className="text-green-400">Entry:</span> Look for long entries on pullbacks to PP or S1</p>
                  <p><span className="text-red-400">Target:</span> {pivotData.nearestResistance ? `R${pivotData.nearestResistance[0].slice(1)} at $${formatPrice(pivotData.nearestResistance[1])}` : 'Next resistance'}</p>
                  <p><span className="text-yellow-400">Stop:</span> Below {pivotData.nearestSupport ? `S${pivotData.nearestSupport[0].slice(1)}` : 'nearest support'}</p>
                </>
              ) : pivotData.tradingBias === 'bearish' ? (
                <>
                  <p>Price is below the pivot point, indicating bearish bias.</p>
                  <p><span className="text-red-400">Entry:</span> Look for short entries on rallies to PP or R1</p>
                  <p><span className="text-green-400">Target:</span> {pivotData.nearestSupport ? `S${pivotData.nearestSupport[0].slice(1)} at $${formatPrice(pivotData.nearestSupport[1])}` : 'Next support'}</p>
                  <p><span className="text-yellow-400">Stop:</span> Above {pivotData.nearestResistance ? `R${pivotData.nearestResistance[0].slice(1)}` : 'nearest resistance'}</p>
                </>
              ) : (
                <p>Price is near the pivot point. Wait for a clear break above or below for directional bias.</p>
              )}
            </div>
          </div>

          {/* Pivot Type Info */}
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <h3 className="text-blue-400 font-medium mb-2">{pivotData.pivots.name} Pivot Points</h3>
            <p className="text-gray-400 text-sm">
              {pivotType === 'standard' && 'Classic pivot points calculated from (H+L+C)/3. Most widely used method.'}
              {pivotType === 'fibonacci' && 'Uses Fibonacci ratios (38.2%, 61.8%) to calculate support and resistance levels.'}
              {pivotType === 'camarilla' && 'Developed for intraday trading. Includes 4 support and 4 resistance levels.'}
              {pivotType === 'woodie' && 'Gives more weight to the closing price. Good for trend following.'}
              {pivotType === 'demark' && 'Conditional calculation based on open vs close relationship.'}
            </p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>PP = Pivot Point</span>
          <span>R1/R2/R3 = Resistance</span>
          <span>S1/S2/S3 = Support</span>
          <span>Based on {timeframe} OHLC</span>
        </div>
      </div>
    </div>
  )
}

export default PivotPoints
