import React, { useState, useMemo, useEffect } from 'react'
import { TrendingUp, TrendingDown, Zap, Maximize2, Settings, Activity, Gauge, ArrowUpRight, ArrowDownRight, AlertTriangle, Target, BarChart3 } from 'lucide-react'

export function MomentumOscillator({
  symbol = 'BTC/USDT',
  priceData = [],
  period = 14,
  rsiPeriod = 14,
  stochPeriod = 14,
  onSignal,
  onDivergence
}) {
  const [selectedPeriod, setSelectedPeriod] = useState(period)
  const [showRSI, setShowRSI] = useState(true)
  const [showStoch, setShowStoch] = useState(true)
  const [showMomentum, setShowMomentum] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)

  // Generate sample price data if none provided
  const prices = useMemo(() => {
    if (priceData.length > 0) return priceData

    const data = []
    let price = 45000
    for (let i = 0; i < 100; i++) {
      const change = (Math.random() - 0.48) * 600
      price += change
      data.push({
        time: Date.now() - (100 - i) * 4 * 60 * 60 * 1000,
        open: price - Math.random() * 100,
        high: price + Math.random() * 200,
        low: price - Math.random() * 200,
        close: price,
        volume: Math.floor(Math.random() * 1000 + 500)
      })
    }
    return data
  }, [priceData])

  // Calculate Momentum (Rate of Change)
  const momentumData = useMemo(() => {
    const result = []
    for (let i = selectedPeriod; i < prices.length; i++) {
      const currentPrice = prices[i].close
      const pastPrice = prices[i - selectedPeriod].close
      const momentum = ((currentPrice - pastPrice) / pastPrice) * 100
      result.push({
        time: prices[i].time,
        value: momentum,
        price: currentPrice
      })
    }
    return result
  }, [prices, selectedPeriod])

  // Calculate RSI
  const rsiData = useMemo(() => {
    const result = []
    const gains = []
    const losses = []

    for (let i = 1; i < prices.length; i++) {
      const change = prices[i].close - prices[i - 1].close
      gains.push(change > 0 ? change : 0)
      losses.push(change < 0 ? Math.abs(change) : 0)

      if (i >= rsiPeriod) {
        const avgGain = gains.slice(i - rsiPeriod, i).reduce((a, b) => a + b, 0) / rsiPeriod
        const avgLoss = losses.slice(i - rsiPeriod, i).reduce((a, b) => a + b, 0) / rsiPeriod
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
        const rsi = 100 - (100 / (1 + rs))

        result.push({
          time: prices[i].time,
          value: rsi,
          price: prices[i].close,
          overbought: rsi > 70,
          oversold: rsi < 30
        })
      }
    }
    return result
  }, [prices, rsiPeriod])

  // Calculate Stochastic
  const stochData = useMemo(() => {
    const result = []

    for (let i = stochPeriod; i < prices.length; i++) {
      const slice = prices.slice(i - stochPeriod, i + 1)
      const highest = Math.max(...slice.map(p => p.high))
      const lowest = Math.min(...slice.map(p => p.low))
      const currentClose = prices[i].close

      const k = highest === lowest ? 50 : ((currentClose - lowest) / (highest - lowest)) * 100

      // Calculate %D (3-period SMA of %K)
      let d = k
      if (result.length >= 2) {
        d = (result[result.length - 1].k + result[result.length - 2].k + k) / 3
      }

      result.push({
        time: prices[i].time,
        k,
        d,
        price: currentClose,
        overbought: k > 80,
        oversold: k < 20
      })
    }
    return result
  }, [prices, stochPeriod])

  // Detect divergences
  const divergences = useMemo(() => {
    const result = []
    const lookback = 10

    if (rsiData.length < lookback * 2) return result

    for (let i = lookback; i < rsiData.length - 1; i++) {
      const currentRsi = rsiData[i].value
      const prevRsi = rsiData[i - lookback].value
      const currentPrice = rsiData[i].price
      const prevPrice = rsiData[i - lookback].price

      // Bullish divergence: price makes lower low, RSI makes higher low
      if (currentPrice < prevPrice && currentRsi > prevRsi && currentRsi < 40) {
        result.push({
          type: 'bullish',
          index: i,
          time: rsiData[i].time,
          indicator: 'RSI',
          price: currentPrice,
          rsi: currentRsi
        })
      }

      // Bearish divergence: price makes higher high, RSI makes lower high
      if (currentPrice > prevPrice && currentRsi < prevRsi && currentRsi > 60) {
        result.push({
          type: 'bearish',
          index: i,
          time: rsiData[i].time,
          indicator: 'RSI',
          price: currentPrice,
          rsi: currentRsi
        })
      }
    }

    return result.slice(-5)
  }, [rsiData])

  // Current readings
  const currentReadings = useMemo(() => {
    const latestMomentum = momentumData[momentumData.length - 1]
    const latestRSI = rsiData[rsiData.length - 1]
    const latestStoch = stochData[stochData.length - 1]

    // Composite signal
    let bullSignals = 0
    let bearSignals = 0

    if (latestMomentum?.value > 0) bullSignals++
    else bearSignals++

    if (latestRSI?.value > 50) bullSignals++
    else bearSignals++

    if (latestStoch?.k > 50) bullSignals++
    else bearSignals++

    const signal = bullSignals > bearSignals ? 'bullish' : bearSignals > bullSignals ? 'bearish' : 'neutral'
    const strength = Math.abs(bullSignals - bearSignals)

    return {
      momentum: latestMomentum,
      rsi: latestRSI,
      stoch: latestStoch,
      signal,
      strength
    }
  }, [momentumData, rsiData, stochData])

  // Render oscillator chart
  const renderOscillator = (data, key, color, levels = []) => {
    if (data.length < 2) return null

    const width = 400
    const height = 60
    const max = Math.max(...data.map(d => d[key] || d.value))
    const min = Math.min(...data.map(d => d[key] || d.value))
    const range = max - min || 1

    const points = data.slice(-50).map((d, i) => {
      const x = (i / 49) * width
      const y = height - ((( d[key] || d.value) - min) / range) * height
      return `${x},${y}`
    }).join(' ')

    return (
      <svg className="w-full h-[60px]" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {/* Level lines */}
        {levels.map((level, idx) => {
          const y = height - ((level - min) / range) * height
          return (
            <line
              key={idx}
              x1={0}
              y1={y}
              x2={width}
              y2={y}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="4,4"
            />
          )
        })}

        {/* Zero line for momentum */}
        {key === 'value' && min < 0 && max > 0 && (
          <line
            x1={0}
            y1={height - ((0 - min) / range) * height}
            x2={width}
            y2={height - ((0 - min) / range) * height}
            stroke="rgba(255,255,255,0.2)"
          />
        )}

        {/* Line */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth={2}
          points={points}
        />

        {/* Area fill */}
        <polygon
          fill={`url(#gradient-${color.replace('#', '')})`}
          points={`0,${height} ${points} ${width},${height}`}
          opacity={0.3}
        />

        <defs>
          <linearGradient id={`gradient-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.5} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
      </svg>
    )
  }

  const periods = [7, 10, 14, 21, 28]

  return (
    <div className={`bg-[#0a0e14] rounded-lg border border-white/10 ${isExpanded ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-violet-500/20 rounded-lg">
            <Zap className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">Momentum Oscillator</h3>
            <p className="text-xs text-white/50">{symbol} • Multi-Indicator Suite</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(Number(e.target.value))}
            className="bg-white/5 text-xs text-white rounded px-2 py-1 border border-white/10"
          >
            {periods.map(p => (
              <option key={p} value={p}>{p} Period</option>
            ))}
          </select>

          <button
            onClick={() => setShowMomentum(!showMomentum)}
            className={`p-1.5 rounded text-xs ${showMomentum ? 'bg-violet-500/20 text-violet-400' : 'bg-white/5 text-white/40'}`}
          >
            MOM
          </button>

          <button
            onClick={() => setShowRSI(!showRSI)}
            className={`p-1.5 rounded text-xs ${showRSI ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5 text-white/40'}`}
          >
            RSI
          </button>

          <button
            onClick={() => setShowStoch(!showStoch)}
            className={`p-1.5 rounded text-xs ${showStoch ? 'bg-cyan-500/20 text-cyan-400' : 'bg-white/5 text-white/40'}`}
          >
            STOCH
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 bg-white/5 rounded hover:bg-white/10"
          >
            <Maximize2 className="w-4 h-4 text-white/60" />
          </button>
        </div>
      </div>

      {/* Signal Summary */}
      <div className="grid grid-cols-4 gap-2 p-3 border-b border-white/10">
        <div className={`rounded-lg p-3 text-center ${
          currentReadings.signal === 'bullish' ? 'bg-emerald-500/10 border border-emerald-500/20' :
          currentReadings.signal === 'bearish' ? 'bg-red-500/10 border border-red-500/20' :
          'bg-white/5 border border-white/10'
        }`}>
          <div className={`text-lg font-bold flex items-center justify-center gap-1 ${
            currentReadings.signal === 'bullish' ? 'text-emerald-400' :
            currentReadings.signal === 'bearish' ? 'text-red-400' : 'text-white/60'
          }`}>
            {currentReadings.signal === 'bullish' ? (
              <ArrowUpRight className="w-5 h-5" />
            ) : currentReadings.signal === 'bearish' ? (
              <ArrowDownRight className="w-5 h-5" />
            ) : (
              <Activity className="w-5 h-5" />
            )}
            {currentReadings.signal.charAt(0).toUpperCase() + currentReadings.signal.slice(1)}
          </div>
          <div className="text-[10px] text-white/40">Composite Signal</div>
        </div>

        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className={`text-lg font-bold ${
            currentReadings.momentum?.value > 0 ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {currentReadings.momentum?.value?.toFixed(2) || '--'}%
          </div>
          <div className="text-[10px] text-white/40">Momentum</div>
        </div>

        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className={`text-lg font-bold ${
            currentReadings.rsi?.overbought ? 'text-red-400' :
            currentReadings.rsi?.oversold ? 'text-emerald-400' : 'text-white'
          }`}>
            {currentReadings.rsi?.value?.toFixed(1) || '--'}
          </div>
          <div className="text-[10px] text-white/40">RSI ({rsiPeriod})</div>
        </div>

        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className={`text-lg font-bold ${
            currentReadings.stoch?.overbought ? 'text-red-400' :
            currentReadings.stoch?.oversold ? 'text-emerald-400' : 'text-white'
          }`}>
            {currentReadings.stoch?.k?.toFixed(1) || '--'}
          </div>
          <div className="text-[10px] text-white/40">Stoch %K</div>
        </div>
      </div>

      {/* Oscillator Charts */}
      <div className="p-3 space-y-3">
        {/* Momentum */}
        {showMomentum && (
          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-white/60">Momentum (ROC)</span>
              <span className={`text-xs font-medium ${
                currentReadings.momentum?.value > 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {currentReadings.momentum?.value?.toFixed(2)}%
              </span>
            </div>
            {renderOscillator(momentumData, 'value', '#8b5cf6')}
          </div>
        )}

        {/* RSI */}
        {showRSI && (
          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-white/60">RSI ({rsiPeriod})</span>
              <div className="flex items-center gap-2">
                {currentReadings.rsi?.overbought && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded">Overbought</span>
                )}
                {currentReadings.rsi?.oversold && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 rounded">Oversold</span>
                )}
                <span className="text-xs font-medium text-white">
                  {currentReadings.rsi?.value?.toFixed(1)}
                </span>
              </div>
            </div>
            {renderOscillator(rsiData, 'value', '#10b981', [30, 50, 70])}
            <div className="flex justify-between text-[10px] text-white/30 mt-1">
              <span>Oversold (30)</span>
              <span>Overbought (70)</span>
            </div>
          </div>
        )}

        {/* Stochastic */}
        {showStoch && (
          <div className="bg-white/5 rounded-lg p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-white/60">Stochastic ({stochPeriod})</span>
              <div className="flex items-center gap-2">
                {currentReadings.stoch?.overbought && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded">Overbought</span>
                )}
                {currentReadings.stoch?.oversold && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 rounded">Oversold</span>
                )}
                <span className="text-xs font-medium text-cyan-400">%K: {currentReadings.stoch?.k?.toFixed(1)}</span>
                <span className="text-xs font-medium text-orange-400">%D: {currentReadings.stoch?.d?.toFixed(1)}</span>
              </div>
            </div>
            <div className="relative">
              {renderOscillator(stochData, 'k', '#06b6d4', [20, 50, 80])}
              <div className="absolute inset-0">
                {renderOscillator(stochData, 'd', '#f97316', [20, 50, 80])}
              </div>
            </div>
            <div className="flex justify-between text-[10px] text-white/30 mt-1">
              <span>Oversold (20)</span>
              <span>Overbought (80)</span>
            </div>
          </div>
        )}
      </div>

      {/* Divergences */}
      {divergences.length > 0 && (
        <div className="p-3 border-t border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium text-white">Divergences Detected</span>
          </div>
          <div className="space-y-1">
            {divergences.map((div, idx) => (
              <div
                key={idx}
                className={`flex items-center justify-between p-2 rounded ${
                  div.type === 'bullish' ? 'bg-emerald-500/10' : 'bg-red-500/10'
                }`}
              >
                <div className="flex items-center gap-2">
                  {div.type === 'bullish' ? (
                    <TrendingUp className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-400" />
                  )}
                  <span className="text-xs text-white/80">
                    {div.type.charAt(0).toUpperCase() + div.type.slice(1)} Divergence
                  </span>
                </div>
                <span className="text-xs text-white/50">
                  {div.indicator}: {div.rsi?.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Indicator Legend */}
      <div className="p-3 border-t border-white/10 flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-violet-500 rounded-full"></div>
            <span className="text-white/40">Momentum</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
            <span className="text-white/40">RSI</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-cyan-500 rounded-full"></div>
            <span className="text-white/40">Stoch %K</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
            <span className="text-white/40">Stoch %D</span>
          </div>
        </div>
        <div className="text-white/30">
          Signal Strength: {currentReadings.strength}/3
        </div>
      </div>
    </div>
  )
}

export default MomentumOscillator
