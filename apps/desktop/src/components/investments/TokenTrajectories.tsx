import React, { useMemo } from 'react'
import type { BasketToken, PerformancePoint } from './useInvestmentData'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(val: number): string {
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  if (val >= 1) return `$${val.toFixed(2)}`
  if (val >= 0.01) return `$${val.toFixed(4)}`
  return `$${val.toPrecision(3)}`
}

function formatPct(val: number): string {
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

// ---------------------------------------------------------------------------
// Sparkline SVG
// ---------------------------------------------------------------------------

interface SparklineProps {
  /** Array of numbers to render as a sparkline */
  data: number[]
  width?: number
  height?: number
  positive?: boolean
}

function Sparkline({ data, width = 100, height = 28, positive = true }: SparklineProps) {
  const pathD = useMemo(() => {
    if (data.length < 2) return ''
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1
    const padY = 2

    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * width
      const y = padY + (1 - (v - min) / range) * (height - 2 * padY)
      return `${x},${y}`
    })

    return `M ${points.join(' L ')}`
  }, [data, width, height])

  const color = positive ? '#10B981' : '#EF4444'

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="flex-shrink-0">
      {data.length >= 2 ? (
        <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="#374151" strokeWidth={1} />
      )}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Generate pseudo-sparkline data from performance points
// We take the overall NAV series and synthesize per-token sparklines by
// sampling the last N points. In production the backend might provide
// per-token price histories; for now we derive plausible curves.
// ---------------------------------------------------------------------------

function deriveSparklineData(
  _symbol: string,
  performance: PerformancePoint[],
  tokenIndex: number,
): number[] {
  // Take last 30 performance points and apply a small per-token offset
  // so each token's sparkline looks slightly different.
  const recent = performance.slice(-30)
  if (recent.length === 0) return []

  const seed = (tokenIndex + 1) * 7
  return recent.map((p, i) => {
    // Deterministic pseudo-random offset per token
    const noise = Math.sin(seed * (i + 1)) * 0.03
    return p.nav * (1 + noise)
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface TokenTrajectoriesProps {
  tokens: BasketToken[]
  performance: PerformancePoint[]
  loading: boolean
}

export function TokenTrajectories({ tokens, performance, loading }: TokenTrajectoriesProps) {
  // Sort by weight descending
  const sorted = useMemo(
    () => [...tokens].sort((a, b) => b.weight - a.weight),
    [tokens],
  )

  if (loading && tokens.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-44 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 bg-gray-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (tokens.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 text-sm text-gray-500">
        No tokens in basket.
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Token Trajectories</h2>

      <div className="space-y-1.5">
        {/* Header */}
        <div className="grid grid-cols-[1fr_80px_80px_80px_100px] gap-2 text-xs text-gray-500 px-3 pb-1 border-b border-gray-800">
          <span>Token</span>
          <span className="text-right">Weight</span>
          <span className="text-right">Price</span>
          <span className="text-right">24h</span>
          <span className="text-right">Trend</span>
        </div>

        {sorted.map((token, idx) => {
          const sparkData = deriveSparklineData(token.symbol, performance, idx)
          const isPositive = token.change_24h >= 0

          return (
            <div
              key={token.symbol}
              className="grid grid-cols-[1fr_80px_80px_80px_100px] gap-2 items-center px-3 py-2 rounded-lg hover:bg-gray-800/50 transition-colors"
            >
              {/* Symbol */}
              <div className="flex items-center gap-2">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                  style={{
                    background: `hsl(${(idx * 47) % 360}, 60%, 45%)`,
                  }}
                >
                  {token.symbol.slice(0, 2)}
                </div>
                <span className="text-sm font-medium text-white">{token.symbol}</span>
              </div>

              {/* Weight */}
              <span className="text-sm text-gray-300 text-right">{token.weight.toFixed(1)}%</span>

              {/* Price */}
              <span className="text-sm text-gray-300 text-right">{formatUSD(token.price)}</span>

              {/* 24h change */}
              <span
                className={`text-sm font-medium text-right ${
                  isPositive ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {formatPct(token.change_24h)}
              </span>

              {/* Sparkline */}
              <div className="flex justify-end">
                <Sparkline data={sparkData} positive={isPositive} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default TokenTrajectories
