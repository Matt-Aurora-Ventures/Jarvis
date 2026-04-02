import React, { useMemo } from 'react'
import type { PerpsCandle, PerpsMarket } from './usePerpsData'

interface Props {
  market: PerpsMarket
  resolution: string
  candles: PerpsCandle[]
  loading: boolean
  error: string | null
  onMarketChange: (market: PerpsMarket) => void
  onResolutionChange: (resolution: string) => void
}

const MARKETS: PerpsMarket[] = ['SOL-USD', 'BTC-USD', 'ETH-USD']
const RESOLUTIONS = [
  { value: '1', label: '1m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '60', label: '1h' },
]

const WIDTH = 880
const HEIGHT = 280
const PAD_X = 24
const PAD_Y = 16

function fmt(v: number): string {
  if (!Number.isFinite(v)) return '--'
  if (v >= 1000) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  return `$${v.toFixed(4)}`
}

export function PerpsPriceChart({
  market,
  resolution,
  candles,
  loading,
  error,
  onMarketChange,
  onResolutionChange,
}: Props) {
  const model = useMemo(() => {
    if (candles.length === 0) return null

    const lows = candles.map((c) => c.low)
    const highs = candles.map((c) => c.high)
    const rawMin = Math.min(...lows)
    const rawMax = Math.max(...highs)
    const span = Math.max(rawMax - rawMin, 1e-6)
    const pad = span * 0.06
    const min = rawMin - pad
    const max = rawMax + pad

    const plotWidth = WIDTH - PAD_X * 2
    const plotHeight = HEIGHT - PAD_Y * 2
    const step = plotWidth / Math.max(candles.length - 1, 1)
    const bodyWidth = Math.max(Math.min(step * 0.7, 10), 2)

    const toX = (idx: number) => PAD_X + idx * step
    const toY = (price: number) => PAD_Y + ((max - price) / (max - min)) * plotHeight

    return {
      min,
      max,
      bodyWidth,
      toX,
      toY,
    }
  }, [candles])

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-sm font-semibold text-white">Perps Candles</h3>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1.5">
            {MARKETS.map((m) => (
              <button
                key={m}
                onClick={() => onMarketChange(m)}
                className={`px-2.5 py-1 text-xs rounded border transition-colors ${
                  market === m
                    ? 'bg-blue-600/30 border-blue-500 text-blue-200'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {m.split('-')[0]}
              </button>
            ))}
          </div>

          <div className="flex gap-1.5">
            {RESOLUTIONS.map((r) => (
              <button
                key={r.value}
                onClick={() => onResolutionChange(r.value)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  resolution === r.value
                    ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-gray-950 border border-gray-800 rounded-lg p-2 min-h-[320px] flex items-center justify-center">
        {loading && candles.length === 0 && (
          <p className="text-xs text-gray-500">Loading candle data...</p>
        )}

        {!loading && candles.length === 0 && (
          <p className="text-xs text-amber-400 text-center">
            {error || 'No candle data available for this market/resolution yet.'}
          </p>
        )}

        {model && (
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-[300px]">
            <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="transparent" />

            {[0, 1, 2, 3].map((tick) => {
              const y = PAD_Y + ((HEIGHT - PAD_Y * 2) * tick) / 3
              const price = model.max - ((model.max - model.min) * tick) / 3
              return (
                <g key={tick}>
                  <line
                    x1={PAD_X}
                    x2={WIDTH - PAD_X}
                    y1={y}
                    y2={y}
                    stroke="rgba(75,85,99,0.45)"
                    strokeWidth={1}
                  />
                  <text
                    x={WIDTH - 2}
                    y={y + 3}
                    fontSize={10}
                    fill="rgba(156,163,175,0.9)"
                    textAnchor="end"
                  >
                    {fmt(price)}
                  </text>
                </g>
              )
            })}

            {candles.map((c, idx) => {
              const x = model.toX(idx)
              const yHigh = model.toY(c.high)
              const yLow = model.toY(c.low)
              const yOpen = model.toY(c.open)
              const yClose = model.toY(c.close)
              const up = c.close >= c.open
              const color = up ? '#22c55e' : '#ef4444'
              const bodyY = Math.min(yOpen, yClose)
              const bodyH = Math.max(Math.abs(yClose - yOpen), 1)

              return (
                <g key={`${c.time}-${idx}`}>
                  <line x1={x} x2={x} y1={yHigh} y2={yLow} stroke={color} strokeWidth={1} />
                  <rect
                    x={x - model.bodyWidth / 2}
                    y={bodyY}
                    width={model.bodyWidth}
                    height={bodyH}
                    fill={color}
                    opacity={0.85}
                    rx={1}
                  />
                </g>
              )
            })}
          </svg>
        )}
      </div>

      {error && candles.length > 0 && (
        <p className="text-[11px] text-amber-400">
          Last fetch note: {error}
        </p>
      )}
    </div>
  )
}

export default PerpsPriceChart
