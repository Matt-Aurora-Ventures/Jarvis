import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Layers,
  BarChart3,
  Settings,
  Zap,
  Eye,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  Grid3X3,
  Ruler,
  Circle,
  Calculator,
  Clock
} from 'lucide-react'

// Standard Fibonacci levels
const FIB_RETRACEMENT_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
const FIB_EXTENSION_LEVELS = [0, 0.618, 1, 1.272, 1.618, 2, 2.618, 3.618, 4.236]

export function FibonacciTool() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('retracement') // retracement, extension, clusters
  const [timeframe, setTimeframe] = useState('4h')
  const [autoDetect, setAutoDetect] = useState(true)

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']
  const timeframes = ['15m', '1h', '4h', '1d', '1w']

  // Generate swing data for each token
  const swingData = useMemo(() => {
    return tokens.map(token => {
      const currentPrice = 50 + Math.random() * 150
      const swingHigh = currentPrice * (1.1 + Math.random() * 0.2)
      const swingLow = currentPrice * (0.7 + Math.random() * 0.2)
      const range = swingHigh - swingLow

      // Calculate retracement levels
      const retracementLevels = FIB_RETRACEMENT_LEVELS.map(level => ({
        level,
        label: `${(level * 100).toFixed(1)}%`,
        price: swingHigh - (range * level),
        isKey: level === 0.382 || level === 0.5 || level === 0.618
      }))

      // Calculate extension levels
      const extensionLevels = FIB_EXTENSION_LEVELS.map(level => ({
        level,
        label: `${(level * 100).toFixed(1)}%`,
        price: swingLow + (range * level),
        isKey: level === 1 || level === 1.618 || level === 2.618
      }))

      // Determine current position
      let nearestLevel = null
      let nearestDistance = Infinity

      for (const rl of retracementLevels) {
        const distance = Math.abs(currentPrice - rl.price)
        if (distance < nearestDistance) {
          nearestDistance = distance
          nearestLevel = rl
        }
      }

      const distancePercent = (nearestDistance / currentPrice * 100)

      // Trend direction
      const trend = currentPrice > (swingHigh + swingLow) / 2 ? 'bullish' : 'bearish'

      // Confluence zones (multiple fibs align)
      const confluenceZones = [
        { price: swingLow + range * 0.618, strength: 3, label: 'Strong Support' },
        { price: swingLow + range * 0.382, strength: 2, label: 'Minor Support' },
        { price: swingHigh - range * 0.382, strength: 2, label: 'Minor Resistance' }
      ]

      return {
        token,
        currentPrice,
        swingHigh,
        swingLow,
        range,
        retracementLevels,
        extensionLevels,
        nearestLevel,
        distancePercent,
        trend,
        confluenceZones,
        swingAge: Math.floor(Math.random() * 30) + 1
      }
    })
  }, [])

  // Fibonacci clusters across all tokens
  const fibClusters = useMemo(() => {
    const clusters = []
    swingData.forEach(data => {
      data.retracementLevels.filter(l => l.isKey).forEach(level => {
        clusters.push({
          token: data.token,
          price: level.price,
          level: level.label,
          type: 'retracement',
          trend: data.trend
        })
      })
    })
    return clusters.sort((a, b) => b.price - a.price)
  }, [swingData])

  const selectedData = swingData.find(d => d.token === selectedToken)

  const getLevelColor = (level) => {
    if (level === 0 || level === 1) return 'text-white/60'
    if (level === 0.236 || level === 0.786) return 'text-blue-400'
    if (level === 0.382) return 'text-cyan-400'
    if (level === 0.5) return 'text-yellow-400'
    if (level === 0.618) return 'text-orange-400'
    return 'text-purple-400'
  }

  const getLevelBg = (level) => {
    if (level === 0.382) return 'bg-cyan-500/10'
    if (level === 0.5) return 'bg-yellow-500/10'
    if (level === 0.618) return 'bg-orange-500/10'
    return 'bg-white/5'
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-500/20 rounded-lg">
            <Ruler className="w-6 h-6 text-yellow-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Fibonacci Tool</h1>
            <p className="text-white/60 text-sm">Retracements, extensions, and confluence zones</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto Detect Toggle */}
          <button
            onClick={() => setAutoDetect(!autoDetect)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
              autoDetect ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-white/60'
            }`}
          >
            <Zap className="w-4 h-4" />
            <span className="text-sm">Auto Detect</span>
          </button>

          {/* Timeframe */}
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['retracement', 'extension', 'clusters'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-yellow-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Token Selector */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
        {tokens.map(token => {
          const data = swingData.find(d => d.token === token)
          return (
            <button
              key={token}
              onClick={() => setSelectedToken(token)}
              className={`px-4 py-2 rounded-lg whitespace-nowrap ${
                selectedToken === token
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'bg-white/5 text-white/60 hover:text-white'
              }`}
            >
              <span className="font-medium">{token}</span>
              <span className={`ml-2 text-xs ${
                data.trend === 'bullish' ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.trend === 'bullish' ? '+' : '-'}{((data.currentPrice - data.swingLow) / data.swingLow * 100).toFixed(1)}%
              </span>
            </button>
          )
        })}
      </div>

      {viewMode === 'retracement' && selectedData && (
        <div className="grid grid-cols-3 gap-6">
          {/* Retracement Levels Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-yellow-400" />
                {selectedToken} Fibonacci Retracement
              </h2>
              <div className="flex items-center gap-2 text-sm text-white/60">
                <Clock className="w-4 h-4" />
                <span>Swing age: {selectedData.swingAge} candles</span>
              </div>
            </div>

            {/* Visual Fib Levels */}
            <div className="relative h-80 border border-white/10 rounded-lg bg-white/[0.02]">
              {/* Current Price Line */}
              {(() => {
                const priceRange = selectedData.swingHigh - selectedData.swingLow
                const priceY = ((selectedData.swingHigh - selectedData.currentPrice) / priceRange) * 100

                return (
                  <div
                    className="absolute left-0 right-0 border-t-2 border-dashed border-white/60 z-10"
                    style={{ top: `${Math.min(Math.max(priceY, 0), 100)}%` }}
                  >
                    <span className="absolute right-2 -top-3 text-xs bg-white/10 px-2 py-0.5 rounded font-medium">
                      ${selectedData.currentPrice.toFixed(2)}
                    </span>
                  </div>
                )
              })()}

              {/* Fib Levels */}
              {selectedData.retracementLevels.map((level, idx) => {
                const priceRange = selectedData.swingHigh - selectedData.swingLow
                const y = (level.level) * 100

                return (
                  <div
                    key={idx}
                    className={`absolute left-0 right-0 border-t ${
                      level.isKey ? 'border-solid' : 'border-dashed'
                    } ${getLevelColor(level.level).replace('text-', 'border-')}`}
                    style={{ top: `${y}%` }}
                  >
                    <div className="flex justify-between px-2 -translate-y-3">
                      <span className={`text-xs ${getLevelColor(level.level)}`}>
                        {level.label}
                      </span>
                      <span className="text-xs text-white/60">
                        ${level.price.toFixed(2)}
                      </span>
                    </div>
                  </div>
                )
              })}

              {/* Labels */}
              <div className="absolute top-2 left-2 text-xs">
                <p className="text-green-400">High: ${selectedData.swingHigh.toFixed(2)}</p>
              </div>
              <div className="absolute bottom-2 left-2 text-xs">
                <p className="text-red-400">Low: ${selectedData.swingLow.toFixed(2)}</p>
              </div>
            </div>

            {/* Key Levels Table */}
            <div className="mt-4 grid grid-cols-3 gap-2">
              {selectedData.retracementLevels.filter(l => l.isKey || l.level === 0 || l.level === 1).map((level, idx) => (
                <div
                  key={idx}
                  className={`p-2 rounded-lg ${getLevelBg(level.level)}`}
                >
                  <div className="flex justify-between items-center">
                    <span className={`text-sm font-medium ${getLevelColor(level.level)}`}>
                      {level.label}
                    </span>
                    <span className="text-sm">${level.price.toFixed(2)}</span>
                  </div>
                  <div className="text-xs text-white/40 mt-1">
                    {((level.price - selectedData.currentPrice) / selectedData.currentPrice * 100).toFixed(2)}% away
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Analysis Panel */}
          <div className="space-y-4">
            {/* Current Position */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-yellow-400" />
                Current Position
              </h3>

              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-white/60">Current Price</span>
                  <span className="font-bold">${selectedData.currentPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Nearest Level</span>
                  <span className={`font-medium ${getLevelColor(selectedData.nearestLevel?.level || 0)}`}>
                    {selectedData.nearestLevel?.label}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Distance</span>
                  <span className="font-medium">{selectedData.distancePercent.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Trend Bias</span>
                  <span className={`font-medium ${
                    selectedData.trend === 'bullish' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {selectedData.trend}
                  </span>
                </div>
              </div>
            </div>

            {/* Key Targets */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                Key Targets
              </h3>

              <div className="space-y-2">
                {selectedData.trend === 'bullish' ? (
                  <>
                    <div className="p-2 bg-green-500/10 rounded-lg">
                      <p className="text-green-400 text-sm font-medium">Upside Target (0.382)</p>
                      <p className="text-white/60 text-xs">
                        ${selectedData.retracementLevels.find(l => l.level === 0.382)?.price.toFixed(2)}
                      </p>
                    </div>
                    <div className="p-2 bg-yellow-500/10 rounded-lg">
                      <p className="text-yellow-400 text-sm font-medium">Major Target (0%)</p>
                      <p className="text-white/60 text-xs">${selectedData.swingHigh.toFixed(2)}</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="p-2 bg-red-500/10 rounded-lg">
                      <p className="text-red-400 text-sm font-medium">Downside Support (0.618)</p>
                      <p className="text-white/60 text-xs">
                        ${selectedData.retracementLevels.find(l => l.level === 0.618)?.price.toFixed(2)}
                      </p>
                    </div>
                    <div className="p-2 bg-orange-500/10 rounded-lg">
                      <p className="text-orange-400 text-sm font-medium">Major Support (100%)</p>
                      <p className="text-white/60 text-xs">${selectedData.swingLow.toFixed(2)}</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Golden Ratio Reminder */}
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-orange-400 flex items-center gap-2">
                <Circle className="w-4 h-4" />
                Golden Ratio (0.618)
              </h3>
              <p className="text-sm text-white/60">
                Price: ${selectedData.retracementLevels.find(l => l.level === 0.618)?.price.toFixed(2)}
              </p>
              <p className="text-xs text-white/40 mt-2">
                The 61.8% level is considered the most significant Fibonacci level for trend reversals.
              </p>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'extension' && selectedData && (
        <div className="grid grid-cols-3 gap-6">
          {/* Extension Levels */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-400" />
              {selectedToken} Fibonacci Extensions
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left py-2 px-3 text-white/60 text-sm font-medium">Level</th>
                    <th className="text-right py-2 px-3 text-white/60 text-sm font-medium">Price</th>
                    <th className="text-right py-2 px-3 text-white/60 text-sm font-medium">Distance</th>
                    <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedData.extensionLevels.map((level, idx) => {
                    const distance = ((level.price - selectedData.currentPrice) / selectedData.currentPrice * 100)
                    const isReached = selectedData.currentPrice >= level.price

                    return (
                      <tr
                        key={idx}
                        className={`border-b border-white/5 ${level.isKey ? 'bg-white/5' : ''}`}
                      >
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className={`font-medium ${
                              level.level === 1.618 ? 'text-yellow-400' :
                              level.level === 2.618 ? 'text-orange-400' :
                              'text-white/60'
                            }`}>
                              {level.label}
                            </span>
                            {level.isKey && (
                              <span className="px-1.5 py-0.5 rounded text-xs bg-yellow-500/20 text-yellow-400">
                                KEY
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-3 text-right font-medium">
                          ${level.price.toFixed(2)}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className={distance >= 0 ? 'text-green-400' : 'text-red-400'}>
                            {distance >= 0 ? '+' : ''}{distance.toFixed(2)}%
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center">
                          {isReached ? (
                            <span className="px-2 py-1 rounded text-xs bg-green-500/10 text-green-400">
                              Reached
                            </span>
                          ) : (
                            <span className="px-2 py-1 rounded text-xs bg-white/5 text-white/40">
                              Pending
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Extension Visual */}
            <div className="mt-4 p-4 bg-white/5 rounded-lg">
              <h3 className="text-sm font-medium mb-3">Extension Targets from Swing Low</h3>
              <div className="flex items-center gap-2">
                <div className="text-red-400 text-xs">${selectedData.swingLow.toFixed(2)}</div>
                <div className="flex-1 h-2 bg-white/10 rounded-full relative">
                  {selectedData.extensionLevels.slice(0, 5).map((level, idx) => (
                    <div
                      key={idx}
                      className={`absolute top-0 w-0.5 h-full ${
                        level.isKey ? 'bg-yellow-400' : 'bg-white/40'
                      }`}
                      style={{ left: `${Math.min((level.level / 3) * 100, 100)}%` }}
                      title={level.label}
                    />
                  ))}
                  {/* Current Price Marker */}
                  <div
                    className="absolute top-0 w-2 h-2 bg-white rounded-full -translate-y-0"
                    style={{
                      left: `${Math.min(((selectedData.currentPrice - selectedData.swingLow) / (selectedData.range * 3)) * 100, 100)}%`
                    }}
                  />
                </div>
                <div className="text-green-400 text-xs">${(selectedData.swingLow + selectedData.range * 3).toFixed(2)}</div>
              </div>
            </div>
          </div>

          {/* Extension Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Calculator className="w-4 h-4 text-purple-400" />
                Extension Formula
              </h3>

              <div className="space-y-2 text-sm">
                <div className="p-2 bg-white/5 rounded">
                  <p className="text-white/60">Range</p>
                  <p className="font-medium">${selectedData.range.toFixed(2)}</p>
                </div>
                <div className="p-2 bg-white/5 rounded">
                  <p className="text-white/60">Swing Low + (Range x Level)</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                Key Extension Levels
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-2 bg-yellow-500/10 rounded-lg">
                  <p className="text-yellow-400 font-medium">161.8% (Golden)</p>
                  <p className="text-white/60 text-xs">Primary profit target in trending markets</p>
                </div>
                <div className="p-2 bg-orange-500/10 rounded-lg">
                  <p className="text-orange-400 font-medium">261.8%</p>
                  <p className="text-white/60 text-xs">Secondary target for strong trends</p>
                </div>
                <div className="p-2 bg-purple-500/10 rounded-lg">
                  <p className="text-purple-400 font-medium">423.6%</p>
                  <p className="text-white/60 text-xs">Extended target for parabolic moves</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'clusters' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Cluster Map */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Grid3X3 className="w-5 h-5 text-purple-400" />
              Fibonacci Confluence Zones
            </h2>

            <p className="text-white/60 text-sm mb-4">
              Price zones where multiple Fibonacci levels align across different tokens
            </p>

            <div className="space-y-3">
              {swingData.map(data => (
                <div key={data.token} className="p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{data.token}</span>
                    <span className="text-white/60 text-sm">
                      ${data.currentPrice.toFixed(2)}
                    </span>
                  </div>

                  {/* Confluence Zones Bar */}
                  <div className="relative h-8 bg-white/5 rounded overflow-hidden">
                    {/* Price Position */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-white z-10"
                      style={{
                        left: `${((data.currentPrice - data.swingLow) / data.range) * 100}%`
                      }}
                    />

                    {/* Key Fib Levels */}
                    {[0.382, 0.5, 0.618].map(level => {
                      const price = data.swingHigh - (data.range * level)
                      const position = ((price - data.swingLow) / data.range) * 100

                      return (
                        <div
                          key={level}
                          className={`absolute top-0 bottom-0 w-4 ${
                            level === 0.618 ? 'bg-orange-500/30' :
                            level === 0.5 ? 'bg-yellow-500/30' :
                            'bg-cyan-500/30'
                          }`}
                          style={{ left: `${Math.max(0, position - 2)}%` }}
                          title={`${(level * 100)}% - $${price.toFixed(2)}`}
                        />
                      )
                    })}
                  </div>

                  <div className="flex justify-between mt-1 text-xs text-white/40">
                    <span>Low: ${data.swingLow.toFixed(2)}</span>
                    <span>High: ${data.swingHigh.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cluster Analysis */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                Strong Confluence Areas
              </h3>

              <div className="space-y-2">
                {swingData.slice(0, 5).map(data => {
                  const goldenLevel = data.retracementLevels.find(l => l.level === 0.618)
                  return (
                    <div key={data.token} className="p-2 bg-orange-500/10 rounded-lg">
                      <div className="flex justify-between">
                        <span className="text-orange-400 font-medium">{data.token}</span>
                        <span className="text-white/60 text-sm">
                          ${goldenLevel?.price.toFixed(2)}
                        </span>
                      </div>
                      <p className="text-xs text-white/40">61.8% golden ratio</p>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-green-400" />
                Trading Strategy
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Look for price reactions at 61.8% level</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Confluence zones = higher probability trades</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Use extensions for profit targets</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Combine with volume and momentum</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default FibonacciTool
