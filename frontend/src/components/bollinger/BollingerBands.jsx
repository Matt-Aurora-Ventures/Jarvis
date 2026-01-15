import React, { useState, useMemo, useEffect } from 'react'
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Settings,
  AlertTriangle,
  Target,
  Maximize2,
  Minimize2,
  BarChart3
} from 'lucide-react'

export function BollingerBands() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [period, setPeriod] = useState(20)
  const [stdDev, setStdDev] = useState(2)
  const [viewMode, setViewMode] = useState('bands') // bands, squeeze, signals
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w']

  // Generate mock Bollinger Bands data
  const bbData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Calculate SMA (mock)
    const sma = currentPrice * (0.98 + Math.random() * 0.04)

    // Calculate standard deviation (mock)
    const volatility = currentPrice * (0.02 + Math.random() * 0.02)

    // Bollinger Bands
    const upperBand = sma + (volatility * stdDev)
    const lowerBand = sma - (volatility * stdDev)
    const middleBand = sma

    // Band width (normalized)
    const bandWidth = ((upperBand - lowerBand) / middleBand) * 100

    // %B indicator
    const percentB = ((currentPrice - lowerBand) / (upperBand - lowerBand)) * 100

    // Price position
    const pricePosition =
      currentPrice >= upperBand ? 'above_upper' :
      currentPrice <= lowerBand ? 'below_lower' :
      currentPrice > middleBand ? 'upper_half' : 'lower_half'

    // Squeeze detection (when bands narrow)
    const avgBandWidth = 8 // mock average
    const squeezeRatio = bandWidth / avgBandWidth
    const isSqueezing = squeezeRatio < 0.8
    const isExpanding = squeezeRatio > 1.2

    // Historical data for visualization
    const history = Array.from({ length: 30 }, (_, i) => {
      const histPrice = currentPrice * (0.9 + Math.random() * 0.2)
      const histSma = histPrice * (0.98 + Math.random() * 0.04)
      const histVol = histPrice * (0.01 + Math.random() * 0.03)
      return {
        period: i + 1,
        price: histPrice,
        upper: histSma + histVol * stdDev,
        middle: histSma,
        lower: histSma - histVol * stdDev,
        bandwidth: ((histVol * stdDev * 2) / histSma) * 100
      }
    })

    // Signals
    const signals = []

    if (currentPrice >= upperBand) {
      signals.push({
        type: 'overbought',
        strength: 'strong',
        description: 'Price at or above upper band - potential reversal or strong momentum'
      })
    } else if (currentPrice <= lowerBand) {
      signals.push({
        type: 'oversold',
        strength: 'strong',
        description: 'Price at or below lower band - potential reversal or strong selling'
      })
    }

    if (isSqueezing) {
      signals.push({
        type: 'squeeze',
        strength: 'neutral',
        description: 'Bands are squeezing - expect volatility expansion soon'
      })
    }

    if (isExpanding) {
      signals.push({
        type: 'expansion',
        strength: 'neutral',
        description: 'Bands are expanding - trend in progress'
      })
    }

    // W-bottom / M-top patterns (simplified)
    const pattern = Math.random() > 0.7 ? (Math.random() > 0.5 ? 'w_bottom' : 'm_top') : null

    return {
      currentPrice,
      upperBand,
      middleBand,
      lowerBand,
      bandWidth,
      percentB,
      pricePosition,
      isSqueezing,
      isExpanding,
      squeezeRatio,
      history,
      signals,
      pattern,
      volatility
    }
  }, [selectedToken, timeframe, period, stdDev])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const getPositionColor = (position) => {
    switch(position) {
      case 'above_upper': return 'text-red-400'
      case 'below_lower': return 'text-green-400'
      case 'upper_half': return 'text-yellow-400'
      case 'lower_half': return 'text-cyan-400'
      default: return 'text-gray-400'
    }
  }

  const getPositionText = (position) => {
    switch(position) {
      case 'above_upper': return 'Above Upper Band'
      case 'below_lower': return 'Below Lower Band'
      case 'upper_half': return 'Upper Half'
      case 'lower_half': return 'Lower Half'
      default: return 'Unknown'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-pink-400" />
          <h2 className="text-xl font-bold text-white">Bollinger Bands</h2>
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
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
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
      <div className="flex items-center gap-4 mb-6 p-3 bg-white/5 rounded-lg border border-white/10">
        <Settings className="w-4 h-4 text-gray-400" />
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">Period:</span>
          <input
            type="number"
            value={period}
            onChange={(e) => setPeriod(parseInt(e.target.value) || 20)}
            className="w-16 bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">Std Dev:</span>
          <input
            type="number"
            step="0.5"
            value={stdDev}
            onChange={(e) => setStdDev(parseFloat(e.target.value) || 2)}
            className="w-16 bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm"
          />
        </div>
      </div>

      {/* Summary */}
      <div className={`rounded-lg p-4 mb-6 border ${
        bbData.pricePosition === 'above_upper' || bbData.pricePosition === 'upper_half'
          ? 'bg-red-500/10 border-red-500/20'
          : 'bg-green-500/10 border-green-500/20'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Price Position</div>
            <div className={`text-lg font-bold ${getPositionColor(bbData.pricePosition)}`}>
              {getPositionText(bbData.pricePosition)}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">%B</div>
            <div className={`text-lg font-bold ${
              bbData.percentB > 100 ? 'text-red-400' :
              bbData.percentB < 0 ? 'text-green-400' :
              bbData.percentB > 80 ? 'text-yellow-400' :
              bbData.percentB < 20 ? 'text-cyan-400' : 'text-white'
            }`}>
              {bbData.percentB.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Band Width</div>
            <div className="text-lg font-bold text-white">{bbData.bandWidth.toFixed(2)}%</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Volatility Status</div>
            <div className={`text-lg font-medium flex items-center gap-2 ${
              bbData.isSqueezing ? 'text-yellow-400' :
              bbData.isExpanding ? 'text-red-400' : 'text-gray-400'
            }`}>
              {bbData.isSqueezing ? <Minimize2 className="w-4 h-4" /> :
               bbData.isExpanding ? <Maximize2 className="w-4 h-4" /> :
               <Activity className="w-4 h-4" />}
              {bbData.isSqueezing ? 'Squeezing' :
               bbData.isExpanding ? 'Expanding' : 'Normal'}
            </div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'bands', label: 'Bands' },
          { id: 'squeeze', label: 'Squeeze' },
          { id: 'signals', label: 'Signals' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-pink-500/20 text-pink-400 border border-pink-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Bands View */}
      {viewMode === 'bands' && (
        <div className="space-y-4">
          {/* Band Levels */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <div className="text-gray-400 text-sm mb-1">Upper Band (+{stdDev}σ)</div>
              <div className="text-2xl font-bold text-red-400">${formatPrice(bbData.upperBand)}</div>
              <div className="text-gray-500 text-sm">
                {((bbData.upperBand - bbData.currentPrice) / bbData.currentPrice * 100).toFixed(2)}% away
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Middle Band (SMA {period})</div>
              <div className="text-2xl font-bold text-white">${formatPrice(bbData.middleBand)}</div>
              <div className="text-gray-500 text-sm">
                {((bbData.middleBand - bbData.currentPrice) / bbData.currentPrice * 100).toFixed(2)}% away
              </div>
            </div>
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <div className="text-gray-400 text-sm mb-1">Lower Band (-{stdDev}σ)</div>
              <div className="text-2xl font-bold text-green-400">${formatPrice(bbData.lowerBand)}</div>
              <div className="text-gray-500 text-sm">
                {((bbData.lowerBand - bbData.currentPrice) / bbData.currentPrice * 100).toFixed(2)}% away
              </div>
            </div>
          </div>

          {/* Visual Band Chart */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Band Visualization</h3>
            <div className="h-48 flex items-end gap-1">
              {bbData.history.map((point, i) => {
                const maxPrice = Math.max(...bbData.history.map(h => h.upper))
                const minPrice = Math.min(...bbData.history.map(h => h.lower))
                const range = maxPrice - minPrice

                const upperPos = ((maxPrice - point.upper) / range) * 100
                const lowerPos = ((maxPrice - point.lower) / range) * 100
                const pricePos = ((maxPrice - point.price) / range) * 100
                const middlePos = ((maxPrice - point.middle) / range) * 100

                return (
                  <div key={i} className="flex-1 relative h-full group">
                    {/* Band area */}
                    <div
                      className="absolute left-0 right-0 bg-pink-500/20"
                      style={{
                        top: `${upperPos}%`,
                        bottom: `${100 - lowerPos}%`
                      }}
                    />
                    {/* Middle line */}
                    <div
                      className="absolute left-0 right-0 h-0.5 bg-pink-500/50"
                      style={{ top: `${middlePos}%` }}
                    />
                    {/* Price */}
                    <div
                      className="absolute left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-white rounded-full"
                      style={{ top: `${pricePos}%` }}
                    />
                    <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black/90 p-2 rounded text-xs text-white whitespace-nowrap z-10 left-1/2 -translate-x-1/2">
                      <div>Price: ${formatPrice(point.price)}</div>
                      <div className="text-red-400">Upper: ${formatPrice(point.upper)}</div>
                      <div className="text-green-400">Lower: ${formatPrice(point.lower)}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Current Price */}
          <div className="bg-white/10 rounded-lg p-4 border border-white/20">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Current Price</span>
              <span className="text-xl font-bold text-white">${formatPrice(bbData.currentPrice)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Squeeze View */}
      {viewMode === 'squeeze' && (
        <div className="space-y-4">
          {/* Squeeze Status */}
          <div className={`rounded-lg p-6 border ${
            bbData.isSqueezing ? 'bg-yellow-500/10 border-yellow-500/20' :
            bbData.isExpanding ? 'bg-red-500/10 border-red-500/20' :
            'bg-white/5 border-white/10'
          }`}>
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-2">Squeeze Status</div>
              <div className={`text-4xl font-bold mb-2 ${
                bbData.isSqueezing ? 'text-yellow-400' :
                bbData.isExpanding ? 'text-red-400' : 'text-gray-400'
              }`}>
                {bbData.isSqueezing ? 'SQUEEZE' : bbData.isExpanding ? 'EXPANSION' : 'NORMAL'}
              </div>
              <div className="text-gray-500">
                Squeeze Ratio: {bbData.squeezeRatio.toFixed(2)}x
              </div>
            </div>
          </div>

          {/* Band Width History */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Band Width History</h3>
            <div className="h-32 flex items-end gap-1">
              {bbData.history.map((point, i) => {
                const maxBW = Math.max(...bbData.history.map(h => h.bandwidth))
                const height = (point.bandwidth / maxBW) * 100

                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-t ${
                      point.bandwidth < bbData.bandWidth * 0.8 ? 'bg-yellow-500' :
                      point.bandwidth > bbData.bandWidth * 1.2 ? 'bg-red-500' : 'bg-pink-500'
                    }`}
                    style={{ height: `${height}%` }}
                  />
                )
              })}
            </div>
            <div className="flex justify-center gap-4 mt-4 text-xs">
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-yellow-500 rounded" /> Squeeze</span>
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-pink-500 rounded" /> Normal</span>
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-red-500 rounded" /> Expansion</span>
            </div>
          </div>

          {/* Squeeze Trading Strategy */}
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <h3 className="text-blue-400 font-medium mb-2">Squeeze Trading</h3>
            <div className="text-gray-400 text-sm space-y-1">
              <p>Bollinger Band squeezes indicate low volatility periods that often precede significant moves.</p>
              <p><span className="text-yellow-400">Squeeze:</span> Wait for breakout direction, then enter</p>
              <p><span className="text-red-400">Expansion:</span> Trend is in progress, trade with momentum</p>
              <p><span className="text-green-400">Tip:</span> Combine with other indicators for breakout direction</p>
            </div>
          </div>
        </div>
      )}

      {/* Signals View */}
      {viewMode === 'signals' && (
        <div className="space-y-4">
          {/* Active Signals */}
          {bbData.signals.length > 0 ? (
            bbData.signals.map((signal, i) => (
              <div key={i} className={`rounded-lg p-4 border ${
                signal.type === 'overbought' ? 'bg-red-500/10 border-red-500/20' :
                signal.type === 'oversold' ? 'bg-green-500/10 border-green-500/20' :
                'bg-yellow-500/10 border-yellow-500/20'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {signal.type === 'overbought' ? <TrendingUp className="w-5 h-5 text-red-400" /> :
                     signal.type === 'oversold' ? <TrendingDown className="w-5 h-5 text-green-400" /> :
                     <AlertTriangle className="w-5 h-5 text-yellow-400" />}
                    <span className={`font-medium capitalize ${
                      signal.type === 'overbought' ? 'text-red-400' :
                      signal.type === 'oversold' ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {signal.type.replace('_', ' ')}
                    </span>
                  </div>
                  <span className="text-xs px-2 py-0.5 bg-white/10 text-gray-400 rounded capitalize">
                    {signal.strength}
                  </span>
                </div>
                <p className="text-gray-400 text-sm">{signal.description}</p>
              </div>
            ))
          ) : (
            <div className="bg-white/5 rounded-lg p-4 border border-white/10 text-center text-gray-500">
              No active signals
            </div>
          )}

          {/* Pattern Detection */}
          {bbData.pattern && (
            <div className={`rounded-lg p-4 border ${
              bbData.pattern === 'w_bottom' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Target className={`w-5 h-5 ${bbData.pattern === 'w_bottom' ? 'text-green-400' : 'text-red-400'}`} />
                <span className={`font-medium ${bbData.pattern === 'w_bottom' ? 'text-green-400' : 'text-red-400'}`}>
                  {bbData.pattern === 'w_bottom' ? 'W-Bottom Pattern' : 'M-Top Pattern'}
                </span>
              </div>
              <p className="text-gray-400 text-sm">
                {bbData.pattern === 'w_bottom'
                  ? 'Potential reversal pattern forming. Second low above lower band confirms bullish signal.'
                  : 'Potential reversal pattern forming. Second high below upper band confirms bearish signal.'}
              </p>
            </div>
          )}

          {/* %B Interpretation */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3">%B Interpretation</h3>
            <div className="relative h-8 bg-gradient-to-r from-green-500 via-white to-red-500 rounded-lg">
              <div
                className="absolute top-full mt-1 -translate-x-1/2"
                style={{ left: `${Math.min(100, Math.max(0, bbData.percentB))}%` }}
              >
                <div className="w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-white" />
                <span className="text-xs text-white">{bbData.percentB.toFixed(0)}%</span>
              </div>
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-6">
              <span>Oversold (0%)</span>
              <span>Neutral (50%)</span>
              <span>Overbought (100%)</span>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>BB = Bollinger Bands</span>
          <span>%B = Position within bands</span>
          <span>Squeeze = Low volatility</span>
          <span>σ = Standard Deviation</span>
        </div>
      </div>
    </div>
  )
}

export default BollingerBands
