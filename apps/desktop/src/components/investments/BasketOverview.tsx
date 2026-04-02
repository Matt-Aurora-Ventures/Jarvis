import React from 'react'
import type { BasketData } from './useInvestmentData'

// ---------------------------------------------------------------------------
// Color palette for tokens (cycles if > 10 tokens)
// ---------------------------------------------------------------------------
const TOKEN_COLORS = [
  '#8B5CF6', // violet
  '#3B82F6', // blue
  '#10B981', // emerald
  '#F59E0B', // amber
  '#EF4444', // red
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
  '#84CC16', // lime
  '#6366F1', // indigo
]

function colorFor(index: number): string {
  return TOKEN_COLORS[index % TOKEN_COLORS.length]
}

// ---------------------------------------------------------------------------
// SVG Donut Chart
// ---------------------------------------------------------------------------
interface DonutProps {
  slices: { weight: number; color: string }[]
  size?: number
}

function DonutChart({ slices, size = 180 }: DonutProps) {
  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 10
  const circumference = 2 * Math.PI * radius

  let accumulated = 0
  const paths = slices.map((s, i) => {
    const offset = circumference * (1 - accumulated / 100)
    const length = circumference * (s.weight / 100)
    accumulated += s.weight
    return (
      <circle
        key={i}
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke={s.color}
        strokeWidth={20}
        strokeDasharray={`${length} ${circumference - length}`}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${cx} ${cy})`}
        className="transition-all duration-500"
      />
    )
  })

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Background ring */}
      <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#1F2937" strokeWidth={20} />
      {paths}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  return `$${val.toFixed(2)}`
}

function formatPct(val: number): string {
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface BasketOverviewProps {
  basket: BasketData | null
  loading: boolean
}

export function BasketOverview({ basket, loading }: BasketOverviewProps) {
  if (loading && !basket) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-40 mb-6" />
        <div className="flex items-center justify-center h-44">
          <div className="w-44 h-44 rounded-full bg-gray-800" />
        </div>
      </div>
    )
  }

  if (!basket) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 text-gray-400 text-sm">
        Basket data unavailable.
      </div>
    )
  }

  const slices = basket.tokens.map((t, i) => ({
    weight: t.weight,
    color: colorFor(i),
  }))

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Basket Overview</h2>
        <span className="text-xs text-gray-500">
          NAV/share: {formatUSD(basket.nav_per_share)}
        </span>
      </div>

      {/* NAV Banner */}
      <div className="text-center mb-6">
        <span className="text-xs uppercase tracking-wider text-gray-500">Total NAV</span>
        <div className="text-3xl font-bold text-white mt-1">{formatUSD(basket.total_nav)}</div>
      </div>

      {/* Donut + Legend */}
      <div className="flex flex-col md:flex-row items-center gap-6">
        {/* Chart */}
        <div className="flex-shrink-0">
          <DonutChart slices={slices} size={180} />
        </div>

        {/* Token list */}
        <div className="flex-1 w-full space-y-2">
          {basket.tokens.map((token, idx) => (
            <div
              key={token.symbol}
              className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-gray-800/50 hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: colorFor(idx) }}
                />
                <span className="font-medium text-white">{token.symbol}</span>
                <span className="text-gray-500">{token.weight.toFixed(1)}%</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-gray-300">{formatUSD(token.usd_value)}</span>
                <span
                  className={`text-xs font-medium ${
                    token.change_24h >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPct(token.change_24h)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rebalance info */}
      <div className="mt-5 flex items-center justify-between text-xs text-gray-500 border-t border-gray-800 pt-3">
        <span>
          Last rebalance:{' '}
          {basket.last_rebalance
            ? new Date(basket.last_rebalance).toLocaleString()
            : 'Never'}
        </span>
        <span>
          Next:{' '}
          {basket.next_rebalance
            ? new Date(basket.next_rebalance).toLocaleString()
            : 'TBD'}
        </span>
      </div>
    </div>
  )
}

export default BasketOverview
