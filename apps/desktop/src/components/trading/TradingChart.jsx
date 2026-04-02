import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Settings,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronDown,
  Layers
} from 'lucide-react'

/**
 * Timeframe options
 */
const TIMEFRAMES = [
  { label: '5m', value: '5m', minutes: 5 },
  { label: '15m', value: '15m', minutes: 15 },
  { label: '1H', value: '1h', minutes: 60 },
  { label: '4H', value: '4h', minutes: 240 },
  { label: '1D', value: '1d', minutes: 1440 },
]

/**
 * Chart types
 */
const CHART_TYPES = [
  { label: 'Candles', value: 'candlestick', icon: BarChart3 },
  { label: 'Line', value: 'line', icon: Activity },
]

/**
 * Technical indicators
 */
const INDICATORS = [
  { id: 'sma20', label: 'SMA 20', color: '#3b82f6', enabled: true },
  { id: 'sma50', label: 'SMA 50', color: '#f59e0b', enabled: false },
  { id: 'ema12', label: 'EMA 12', color: '#10b981', enabled: false },
  { id: 'ema26', label: 'EMA 26', color: '#ef4444', enabled: false },
  { id: 'bollinger', label: 'Bollinger', color: '#8b5cf6', enabled: false },
]

/**
 * Calculate Simple Moving Average
 */
function calculateSMA(data, period) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0)
      result.push(sum / period)
    }
  }
  return result
}

/**
 * Calculate Exponential Moving Average
 */
function calculateEMA(data, period) {
  const result = []
  const multiplier = 2 / (period + 1)

  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      result.push(data[i].close)
    } else if (i < period - 1) {
      // Use SMA for first period-1 values
      const sum = data.slice(0, i + 1).reduce((acc, d) => acc + d.close, 0)
      result.push(sum / (i + 1))
    } else {
      const ema = (data[i].close - result[i - 1]) * multiplier + result[i - 1]
      result.push(ema)
    }
  }
  return result
}

/**
 * Calculate Bollinger Bands
 */
function calculateBollinger(data, period = 20, stdDev = 2) {
  const sma = calculateSMA(data, period)
  const upper = []
  const lower = []

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      upper.push(null)
      lower.push(null)
    } else {
      const slice = data.slice(i - period + 1, i + 1).map(d => d.close)
      const mean = sma[i]
      const variance = slice.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / period
      const std = Math.sqrt(variance)
      upper.push(mean + stdDev * std)
      lower.push(mean - stdDev * std)
    }
  }

  return { middle: sma, upper, lower }
}

/**
 * Candlestick component
 */
function Candle({ x, open, high, low, close, width, yScale, height }) {
  const isGreen = close >= open
  const color = isGreen ? '#22c55e' : '#ef4444'

  const bodyTop = yScale(Math.max(open, close))
  const bodyBottom = yScale(Math.min(open, close))
  const bodyHeight = Math.max(1, bodyBottom - bodyTop)

  const wickTop = yScale(high)
  const wickBottom = yScale(low)

  return (
    <g>
      {/* Wick */}
      <line
        x1={x + width / 2}
        y1={wickTop}
        x2={x + width / 2}
        y2={wickBottom}
        stroke={color}
        strokeWidth={1}
      />
      {/* Body */}
      <rect
        x={x + 1}
        y={bodyTop}
        width={Math.max(1, width - 2)}
        height={bodyHeight}
        fill={isGreen ? color : 'none'}
        stroke={color}
        strokeWidth={1}
      />
    </g>
  )
}

/**
 * Price tooltip
 */
function PriceTooltip({ candle, x, y }) {
  if (!candle) return null

  const isGreen = candle.close >= candle.open
  const change = ((candle.close - candle.open) / candle.open) * 100

  return (
    <div
      className="absolute z-50 bg-gray-800 border border-gray-700 rounded-lg p-2 text-xs shadow-lg pointer-events-none"
      style={{ left: x + 10, top: y - 60 }}
    >
      <div className="text-gray-400 mb-1">
        {new Date(candle.timestamp * 1000).toLocaleString()}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-gray-500">O:</span>
        <span className="text-white font-mono">${candle.open.toFixed(6)}</span>
        <span className="text-gray-500">H:</span>
        <span className="text-white font-mono">${candle.high.toFixed(6)}</span>
        <span className="text-gray-500">L:</span>
        <span className="text-white font-mono">${candle.low.toFixed(6)}</span>
        <span className="text-gray-500">C:</span>
        <span className={`font-mono ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
          ${candle.close.toFixed(6)}
        </span>
      </div>
      <div className={`mt-1 pt-1 border-t border-gray-700 ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
        {change >= 0 ? '+' : ''}{change.toFixed(2)}%
      </div>
    </div>
  )
}

/**
 * Volume bar chart
 */
function VolumeChart({ data, width, height, candleWidth }) {
  const maxVolume = Math.max(...data.map(d => d.volume || 0))

  return (
    <svg width={width} height={height} className="overflow-visible">
      {data.map((candle, i) => {
        const x = i * candleWidth
        const barHeight = ((candle.volume || 0) / maxVolume) * height * 0.8
        const isGreen = candle.close >= candle.open

        return (
          <rect
            key={i}
            x={x + 1}
            y={height - barHeight}
            width={Math.max(1, candleWidth - 2)}
            height={barHeight}
            fill={isGreen ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'}
          />
        )
      })}
    </svg>
  )
}

/**
 * Trading Chart Component
 */
export default function TradingChart({
  mint,
  symbol = 'TOKEN',
  initialTimeframe = '15m',
  height = 400,
  showVolume = true,
  showIndicators = true,
  onPriceUpdate,
}) {
  const [candles, setCandles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [timeframe, setTimeframe] = useState(initialTimeframe)
  const [chartType, setChartType] = useState('candlestick')
  const [indicators, setIndicators] = useState(INDICATORS)
  const [hoveredCandle, setHoveredCandle] = useState(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [showIndicatorMenu, setShowIndicatorMenu] = useState(false)

  const chartRef = useRef(null)
  const containerRef = useRef(null)

  // Chart dimensions
  const [dimensions, setDimensions] = useState({ width: 800, height })
  const volumeHeight = showVolume ? 60 : 0
  const chartHeight = dimensions.height - volumeHeight - 30 // 30 for x-axis labels
  const candleWidth = Math.max(4, Math.min(20, (dimensions.width - 60) / Math.max(1, candles.length)))

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: height
        })
      }
    })

    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [height])

  // Fetch candle data
  const fetchCandles = async () => {
    if (!mint) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/chart/${mint}?timeframe=${timeframe}&limit=100`)
      if (!response.ok) throw new Error('Failed to fetch chart data')

      const data = await response.json()
      if (data.success && data.candles) {
        setCandles(data.candles)
        if (data.candles.length > 0 && onPriceUpdate) {
          const latest = data.candles[data.candles.length - 1]
          onPriceUpdate(latest.close)
        }
      } else {
        setError(data.error || 'No chart data')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCandles()
    const interval = setInterval(fetchCandles, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [mint, timeframe])

  // Calculate price scale
  const priceRange = useMemo(() => {
    if (candles.length === 0) return { min: 0, max: 1 }

    const prices = candles.flatMap(c => [c.high, c.low])
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const padding = (max - min) * 0.1

    return { min: min - padding, max: max + padding }
  }, [candles])

  // Y scale function
  const yScale = (price) => {
    const { min, max } = priceRange
    return chartHeight - ((price - min) / (max - min)) * chartHeight
  }

  // Calculate indicator data
  const indicatorData = useMemo(() => {
    if (candles.length === 0) return {}

    const data = {}

    indicators.forEach(ind => {
      if (!ind.enabled) return

      switch (ind.id) {
        case 'sma20':
          data.sma20 = calculateSMA(candles, 20)
          break
        case 'sma50':
          data.sma50 = calculateSMA(candles, 50)
          break
        case 'ema12':
          data.ema12 = calculateEMA(candles, 12)
          break
        case 'ema26':
          data.ema26 = calculateEMA(candles, 26)
          break
        case 'bollinger':
          data.bollinger = calculateBollinger(candles, 20, 2)
          break
      }
    })

    return data
  }, [candles, indicators])

  // Toggle indicator
  const toggleIndicator = (id) => {
    setIndicators(prev =>
      prev.map(ind =>
        ind.id === id ? { ...ind, enabled: !ind.enabled } : ind
      )
    )
  }

  // Handle mouse move
  const handleMouseMove = (e) => {
    if (!chartRef.current || candles.length === 0) return

    const rect = chartRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const candleIndex = Math.floor(x / candleWidth)
    if (candleIndex >= 0 && candleIndex < candles.length) {
      setHoveredCandle(candles[candleIndex])
      setMousePos({ x: e.clientX - containerRef.current.getBoundingClientRect().left, y })
    } else {
      setHoveredCandle(null)
    }
  }

  // Render indicator line
  const renderIndicatorLine = (data, color, dashed = false) => {
    if (!data || data.length === 0) return null

    const points = data
      .map((val, i) => {
        if (val === null) return null
        return `${i * candleWidth + candleWidth / 2},${yScale(val)}`
      })
      .filter(p => p !== null)
      .join(' ')

    return (
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeDasharray={dashed ? '4,4' : undefined}
        opacity={0.8}
      />
    )
  }

  if (loading && candles.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <RefreshCw className="animate-spin text-cyan-400" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center text-gray-400" style={{ height }}>
        <Activity size={32} className="mb-2 opacity-50" />
        <p>{error}</p>
        <button
          onClick={fetchCandles}
          className="mt-2 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          Retry
        </button>
      </div>
    )
  }

  const latestCandle = candles[candles.length - 1]
  const firstCandle = candles[0]
  const priceChange = latestCandle && firstCandle
    ? ((latestCandle.close - firstCandle.open) / firstCandle.open) * 100
    : 0

  return (
    <div ref={containerRef} className="relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-white">${symbol}</span>
              {latestCandle && (
                <span className="text-lg font-mono text-white">
                  ${latestCandle.close.toFixed(6)}
                </span>
              )}
            </div>
            {latestCandle && (
              <div className={`text-sm ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
                <span className="text-gray-500 ml-2">
                  {TIMEFRAMES.find(t => t.value === timeframe)?.label}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Timeframe selector */}
          <div className="flex bg-gray-800 rounded-lg p-0.5">
            {TIMEFRAMES.map(tf => (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  timeframe === tf.value
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>

          {/* Chart type */}
          <div className="flex bg-gray-800 rounded-lg p-0.5">
            {CHART_TYPES.map(type => (
              <button
                key={type.value}
                onClick={() => setChartType(type.value)}
                className={`p-1.5 rounded transition-colors ${
                  chartType === type.value
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <type.icon size={16} />
              </button>
            ))}
          </div>

          {/* Indicators */}
          {showIndicators && (
            <div className="relative">
              <button
                onClick={() => setShowIndicatorMenu(!showIndicatorMenu)}
                className="p-1.5 bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors flex items-center gap-1"
              >
                <Layers size={16} />
                <ChevronDown size={12} />
              </button>

              {showIndicatorMenu && (
                <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-10 min-w-[150px]">
                  {indicators.map(ind => (
                    <button
                      key={ind.id}
                      onClick={() => toggleIndicator(ind.id)}
                      className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-700 text-sm transition-colors"
                    >
                      <div
                        className={`w-3 h-3 rounded border ${
                          ind.enabled ? 'bg-current' : 'bg-transparent'
                        }`}
                        style={{ borderColor: ind.color, color: ind.color }}
                      />
                      <span className="text-gray-300">{ind.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Refresh */}
          <button
            onClick={fetchCandles}
            className="p-1.5 bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Chart */}
      <div
        ref={chartRef}
        className="relative bg-gray-900/50 rounded-lg overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredCandle(null)}
      >
        <svg
          width={dimensions.width}
          height={chartHeight}
          className="overflow-visible"
        >
          {/* Grid lines */}
          <g className="text-gray-700">
            {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
              const y = chartHeight * pct
              return (
                <line
                  key={i}
                  x1={0}
                  y1={y}
                  x2={dimensions.width}
                  y2={y}
                  stroke="currentColor"
                  strokeDasharray="4,4"
                  opacity={0.3}
                />
              )
            })}
          </g>

          {/* Bollinger Bands (if enabled) */}
          {indicatorData.bollinger && (
            <>
              {renderIndicatorLine(indicatorData.bollinger.upper, '#8b5cf6', true)}
              {renderIndicatorLine(indicatorData.bollinger.middle, '#8b5cf6')}
              {renderIndicatorLine(indicatorData.bollinger.lower, '#8b5cf6', true)}
            </>
          )}

          {/* Indicator lines */}
          {indicatorData.sma20 && renderIndicatorLine(indicatorData.sma20, '#3b82f6')}
          {indicatorData.sma50 && renderIndicatorLine(indicatorData.sma50, '#f59e0b')}
          {indicatorData.ema12 && renderIndicatorLine(indicatorData.ema12, '#10b981')}
          {indicatorData.ema26 && renderIndicatorLine(indicatorData.ema26, '#ef4444')}

          {/* Candles or Line */}
          {chartType === 'candlestick' ? (
            candles.map((candle, i) => (
              <Candle
                key={i}
                x={i * candleWidth}
                open={candle.open}
                high={candle.high}
                low={candle.low}
                close={candle.close}
                width={candleWidth}
                yScale={yScale}
                height={chartHeight}
              />
            ))
          ) : (
            <polyline
              points={candles.map((c, i) =>
                `${i * candleWidth + candleWidth / 2},${yScale(c.close)}`
              ).join(' ')}
              fill="none"
              stroke="#06b6d4"
              strokeWidth={2}
            />
          )}

          {/* Crosshair */}
          {hoveredCandle && (
            <>
              <line
                x1={0}
                y1={yScale(hoveredCandle.close)}
                x2={dimensions.width}
                y2={yScale(hoveredCandle.close)}
                stroke="#94a3b8"
                strokeDasharray="2,2"
                opacity={0.5}
              />
            </>
          )}
        </svg>

        {/* Y-axis labels */}
        <div className="absolute right-0 top-0 bottom-0 w-14 flex flex-col justify-between text-xs text-gray-500 pointer-events-none">
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const price = priceRange.max - (priceRange.max - priceRange.min) * pct
            return (
              <span key={i} className="text-right pr-1">
                ${price.toFixed(6)}
              </span>
            )
          })}
        </div>

        {/* Tooltip */}
        {hoveredCandle && (
          <PriceTooltip
            candle={hoveredCandle}
            x={mousePos.x}
            y={mousePos.y}
          />
        )}
      </div>

      {/* Volume */}
      {showVolume && candles.length > 0 && (
        <div className="mt-1">
          <VolumeChart
            data={candles}
            width={dimensions.width}
            height={volumeHeight}
            candleWidth={candleWidth}
          />
        </div>
      )}

      {/* Legend */}
      {showIndicators && indicators.some(i => i.enabled) && (
        <div className="flex items-center gap-4 mt-2 text-xs">
          {indicators.filter(i => i.enabled).map(ind => (
            <div key={ind.id} className="flex items-center gap-1">
              <div className="w-3 h-0.5" style={{ backgroundColor: ind.color }} />
              <span className="text-gray-400">{ind.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
