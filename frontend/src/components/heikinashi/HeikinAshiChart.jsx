import React, { useState, useMemo, useEffect } from 'react'
import { TrendingUp, TrendingDown, Activity, Maximize2, Settings, BarChart3, Flame, Target, ArrowUpRight, ArrowDownRight, Zap } from 'lucide-react'

export function HeikinAshiChart({
  symbol = 'BTC/USDT',
  ohlcData = [],
  timeframe = '4H',
  onTrendChange,
  onSignal
}) {
  const [selectedTimeframe, setSelectedTimeframe] = useState(timeframe)
  const [showSignals, setShowSignals] = useState(true)
  const [showTrendStrength, setShowTrendStrength] = useState(true)
  const [smoothingPeriod, setSmoothingPeriod] = useState(1)
  const [isExpanded, setIsExpanded] = useState(false)

  // Generate Heikin Ashi data
  const haData = useMemo(() => {
    // Sample OHLC if none provided
    let candles = ohlcData.length > 0 ? ohlcData : []

    if (candles.length === 0) {
      let price = 45000
      for (let i = 0; i < 50; i++) {
        const change = (Math.random() - 0.48) * 800
        const open = price
        const close = price + change
        const high = Math.max(open, close) + Math.random() * 200
        const low = Math.min(open, close) - Math.random() * 200
        candles.push({
          time: Date.now() - (50 - i) * 4 * 60 * 60 * 1000,
          open,
          high,
          low,
          close,
          volume: Math.floor(Math.random() * 1000 + 500)
        })
        price = close
      }
    }

    // Convert to Heikin Ashi
    const ha = []
    for (let i = 0; i < candles.length; i++) {
      const curr = candles[i]
      const prev = i > 0 ? ha[i - 1] : null

      const haClose = (curr.open + curr.high + curr.low + curr.close) / 4
      const haOpen = prev ? (prev.open + prev.close) / 2 : (curr.open + curr.close) / 2
      const haHigh = Math.max(curr.high, haOpen, haClose)
      const haLow = Math.min(curr.low, haOpen, haClose)

      const isBullish = haClose > haOpen
      const hasShadow = isBullish ? haLow < haOpen : haHigh > haOpen
      const bodySize = Math.abs(haClose - haOpen)
      const totalRange = haHigh - haLow
      const bodyPercent = totalRange > 0 ? (bodySize / totalRange) * 100 : 0

      ha.push({
        time: curr.time,
        open: haOpen,
        high: haHigh,
        low: haLow,
        close: haClose,
        volume: curr.volume,
        isBullish,
        hasShadow,
        bodyPercent,
        // Trend strength: no shadow + large body = strong trend
        trendStrength: !hasShadow && bodyPercent > 60 ? 'strong' : hasShadow ? 'weak' : 'moderate'
      })
    }

    return ha
  }, [ohlcData])

  // Analyze trend
  const trendAnalysis = useMemo(() => {
    if (haData.length < 10) return null

    const recent = haData.slice(-20)
    const bullishCount = recent.filter(c => c.isBullish).length
    const bearishCount = recent.length - bullishCount

    // Count consecutive same-direction candles
    let consecutiveCount = 1
    for (let i = recent.length - 2; i >= 0; i--) {
      if (recent[i].isBullish === recent[recent.length - 1].isBullish) {
        consecutiveCount++
      } else {
        break
      }
    }

    // Strong candles (no opposing shadow, large body)
    const strongBullish = recent.filter(c => c.isBullish && c.trendStrength === 'strong').length
    const strongBearish = recent.filter(c => !c.isBullish && c.trendStrength === 'strong').length

    // Doji detection (small body, both shadows)
    const dojiCount = recent.filter(c => c.bodyPercent < 20).length

    // Trend determination
    let trend = 'neutral'
    let strength = 'weak'

    if (bullishCount > 14) {
      trend = 'bullish'
      strength = strongBullish > 5 ? 'strong' : strongBullish > 2 ? 'moderate' : 'weak'
    } else if (bearishCount > 14) {
      trend = 'bearish'
      strength = strongBearish > 5 ? 'strong' : strongBearish > 2 ? 'moderate' : 'weak'
    } else if (bullishCount > 12) {
      trend = 'bullish'
      strength = 'weak'
    } else if (bearishCount > 12) {
      trend = 'bearish'
      strength = 'weak'
    }

    // Reversal detection
    const lastFive = recent.slice(-5)
    const prevFive = recent.slice(-10, -5)
    const lastBullish = lastFive.filter(c => c.isBullish).length
    const prevBullish = prevFive.filter(c => c.isBullish).length
    const potentialReversal = Math.abs(lastBullish - prevBullish) >= 3

    return {
      trend,
      strength,
      bullishCount,
      bearishCount,
      consecutiveCount,
      strongBullish,
      strongBearish,
      dojiCount,
      potentialReversal,
      reversalDirection: potentialReversal
        ? (lastBullish > prevBullish ? 'bullish' : 'bearish')
        : null
    }
  }, [haData])

  // Generate trading signals
  const signals = useMemo(() => {
    const result = []
    if (haData.length < 3) return result

    for (let i = 2; i < haData.length; i++) {
      const curr = haData[i]
      const prev = haData[i - 1]
      const prev2 = haData[i - 2]

      // Bullish reversal: 2+ bearish followed by bullish with no lower shadow
      if (!prev.isBullish && !prev2.isBullish && curr.isBullish && curr.trendStrength !== 'weak') {
        result.push({
          index: i,
          time: curr.time,
          type: 'bullish_reversal',
          price: curr.close,
          strength: curr.trendStrength
        })
      }

      // Bearish reversal
      if (prev.isBullish && prev2.isBullish && !curr.isBullish && curr.trendStrength !== 'weak') {
        result.push({
          index: i,
          time: curr.time,
          type: 'bearish_reversal',
          price: curr.close,
          strength: curr.trendStrength
        })
      }

      // Strong continuation
      if (curr.trendStrength === 'strong' && prev.trendStrength === 'strong' && curr.isBullish === prev.isBullish) {
        result.push({
          index: i,
          time: curr.time,
          type: curr.isBullish ? 'strong_bull_continuation' : 'strong_bear_continuation',
          price: curr.close,
          strength: 'strong'
        })
      }

      // Indecision (doji after trend)
      if (curr.bodyPercent < 15 && (prev.trendStrength === 'strong' || prev.trendStrength === 'moderate')) {
        result.push({
          index: i,
          time: curr.time,
          type: 'indecision',
          price: curr.close,
          strength: 'weak'
        })
      }
    }

    return result.slice(-10) // Keep recent signals
  }, [haData])

  // Render candles
  const renderCandles = () => {
    const visibleCandles = haData.slice(-40)
    const maxPrice = Math.max(...visibleCandles.map(c => c.high))
    const minPrice = Math.min(...visibleCandles.map(c => c.low))
    const priceRange = maxPrice - minPrice
    const chartHeight = 200

    const priceToY = (price) => {
      return chartHeight - ((price - minPrice) / priceRange) * chartHeight
    }

    return (
      <svg className="w-full h-[200px]" viewBox={`0 0 ${visibleCandles.length * 12} ${chartHeight}`}>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map(pct => (
          <line
            key={pct}
            x1={0}
            y1={chartHeight * pct}
            x2={visibleCandles.length * 12}
            y2={chartHeight * pct}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="2,2"
          />
        ))}

        {/* Candles */}
        {visibleCandles.map((candle, idx) => {
          const x = idx * 12 + 6
          const candleColor = candle.isBullish ? '#10b981' : '#ef4444'
          const opacity = candle.trendStrength === 'strong' ? 1 : candle.trendStrength === 'moderate' ? 0.8 : 0.5

          return (
            <g key={idx}>
              {/* Wick */}
              <line
                x1={x}
                y1={priceToY(candle.high)}
                x2={x}
                y2={priceToY(candle.low)}
                stroke={candleColor}
                strokeWidth={1}
                opacity={opacity}
              />
              {/* Body */}
              <rect
                x={x - 4}
                y={priceToY(Math.max(candle.open, candle.close))}
                width={8}
                height={Math.max(2, Math.abs(priceToY(candle.open) - priceToY(candle.close)))}
                fill={candleColor}
                opacity={opacity}
                rx={1}
              />
              {/* Signal marker */}
              {showSignals && signals.find(s => s.index === haData.indexOf(candle)) && (
                <circle
                  cx={x}
                  cy={candle.isBullish ? priceToY(candle.low) + 10 : priceToY(candle.high) - 10}
                  r={4}
                  fill={candle.isBullish ? '#10b981' : '#ef4444'}
                  stroke="white"
                  strokeWidth={1}
                />
              )}
            </g>
          )
        })}
      </svg>
    )
  }

  const timeframes = ['1M', '5M', '15M', '1H', '4H', '1D']

  return (
    <div className={`bg-[#0a0e14] rounded-lg border border-white/10 ${isExpanded ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-orange-500/20 rounded-lg">
            <Flame className="w-4 h-4 text-orange-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">Heikin Ashi Chart</h3>
            <p className="text-xs text-white/50">{symbol} • {selectedTimeframe} • Smoothed Candlesticks</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded overflow-hidden">
            {timeframes.map(tf => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-2 py-1 text-xs ${
                  selectedTimeframe === tf
                    ? 'bg-orange-500/30 text-orange-300'
                    : 'text-white/50 hover:text-white/80'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowSignals(!showSignals)}
            className={`p-1.5 rounded ${showSignals ? 'bg-orange-500/20 text-orange-400' : 'bg-white/5 text-white/40'}`}
          >
            <Zap className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 bg-white/5 rounded hover:bg-white/10"
          >
            <Maximize2 className="w-4 h-4 text-white/60" />
          </button>
        </div>
      </div>

      {/* Trend Summary */}
      {trendAnalysis && (
        <div className="grid grid-cols-4 gap-2 p-3 border-b border-white/10">
          <div className="bg-white/5 rounded-lg p-2 text-center">
            <div className={`text-lg font-bold flex items-center justify-center gap-1 ${
              trendAnalysis.trend === 'bullish' ? 'text-emerald-400' :
              trendAnalysis.trend === 'bearish' ? 'text-red-400' : 'text-white/60'
            }`}>
              {trendAnalysis.trend === 'bullish' ? <TrendingUp className="w-4 h-4" /> :
               trendAnalysis.trend === 'bearish' ? <TrendingDown className="w-4 h-4" /> :
               <Activity className="w-4 h-4" />}
              {trendAnalysis.trend.charAt(0).toUpperCase() + trendAnalysis.trend.slice(1)}
            </div>
            <div className="text-[10px] text-white/40">Trend</div>
          </div>
          <div className="bg-white/5 rounded-lg p-2 text-center">
            <div className={`text-lg font-bold ${
              trendAnalysis.strength === 'strong' ? 'text-yellow-400' :
              trendAnalysis.strength === 'moderate' ? 'text-orange-400' : 'text-white/60'
            }`}>
              {trendAnalysis.strength.charAt(0).toUpperCase() + trendAnalysis.strength.slice(1)}
            </div>
            <div className="text-[10px] text-white/40">Strength</div>
          </div>
          <div className="bg-white/5 rounded-lg p-2 text-center">
            <div className="text-lg font-bold text-white">{trendAnalysis.consecutiveCount}</div>
            <div className="text-[10px] text-white/40">Consecutive</div>
          </div>
          <div className="bg-white/5 rounded-lg p-2 text-center">
            <div className={`text-lg font-bold ${trendAnalysis.potentialReversal ? 'text-yellow-400' : 'text-white/40'}`}>
              {trendAnalysis.potentialReversal ? '⚠️ Yes' : 'No'}
            </div>
            <div className="text-[10px] text-white/40">Reversal Signal</div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="p-3 border-b border-white/10">
        {renderCandles()}
      </div>

      {/* Candle Stats */}
      {trendAnalysis && (
        <div className="grid grid-cols-6 gap-2 p-3 border-b border-white/10">
          <div className="text-center">
            <div className="text-sm font-bold text-emerald-400">{trendAnalysis.bullishCount}</div>
            <div className="text-[10px] text-white/40">Bullish</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-red-400">{trendAnalysis.bearishCount}</div>
            <div className="text-[10px] text-white/40">Bearish</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-emerald-400">{trendAnalysis.strongBullish}</div>
            <div className="text-[10px] text-white/40">Strong Bull</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-red-400">{trendAnalysis.strongBearish}</div>
            <div className="text-[10px] text-white/40">Strong Bear</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-white/60">{trendAnalysis.dojiCount}</div>
            <div className="text-[10px] text-white/40">Indecision</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-white">{haData.length}</div>
            <div className="text-[10px] text-white/40">Total</div>
          </div>
        </div>
      )}

      {/* Recent Signals */}
      {showSignals && signals.length > 0 && (
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-medium text-white">Recent Signals</span>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {signals.slice(-5).reverse().map((signal, idx) => (
              <div
                key={idx}
                className={`flex items-center justify-between p-2 rounded ${
                  signal.type.includes('bull') ? 'bg-emerald-500/10' :
                  signal.type.includes('bear') ? 'bg-red-500/10' : 'bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  {signal.type.includes('bull') ? (
                    <ArrowUpRight className="w-3 h-3 text-emerald-400" />
                  ) : signal.type.includes('bear') ? (
                    <ArrowDownRight className="w-3 h-3 text-red-400" />
                  ) : (
                    <Activity className="w-3 h-3 text-white/40" />
                  )}
                  <span className="text-xs text-white/80">
                    {signal.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/50">${(signal.price / 1000).toFixed(2)}k</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    signal.strength === 'strong' ? 'bg-yellow-500/20 text-yellow-400' :
                    signal.strength === 'moderate' ? 'bg-orange-500/20 text-orange-400' :
                    'bg-white/10 text-white/50'
                  }`}>
                    {signal.strength}
                  </span>
                </div>
              </div>
            ))}
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
            <div className="w-3 h-3 bg-white/30 rounded-sm"></div>
            <span className="text-white/40">Weak/Indecision</span>
          </div>
        </div>
        <div className="text-white/30">
          HA = (O+H+L+C)/4
        </div>
      </div>
    </div>
  )
}

export default HeikinAshiChart
