import React, { useState, useMemo, useCallback } from 'react'
import type { PerformancePoint } from './useInvestmentData'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Timeframe = '24h' | '7d' | '30d' | '90d' | 'ALL'

const TIMEFRAME_HOURS: Record<Timeframe, number> = {
  '24h': 24,
  '7d': 168,
  '30d': 720,
  '90d': 2160,
  ALL: 0, // 0 means "all available data"
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  return `$${val.toFixed(2)}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface PerformanceChartProps {
  performance: PerformancePoint[]
  loading: boolean
  onTimeframeChange?: (hours: number) => void
}

export function PerformanceChart({
  performance,
  loading,
  onTimeframeChange,
}: PerformanceChartProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>('7d')
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  const handleTimeframeChange = useCallback(
    (tf: Timeframe) => {
      setTimeframe(tf)
      const hours = TIMEFRAME_HOURS[tf]
      if (onTimeframeChange && hours > 0) {
        onTimeframeChange(hours)
      }
    },
    [onTimeframeChange],
  )

  // Filter data points to the selected timeframe
  const filteredData = useMemo(() => {
    if (!performance || performance.length === 0) return []
    if (timeframe === 'ALL') return performance

    const hours = TIMEFRAME_HOURS[timeframe]
    const cutoff = Date.now() - hours * 3600_000
    const filtered = performance.filter(p => new Date(p.timestamp).getTime() >= cutoff)
    // If the filter yields nothing (stale data), show all
    return filtered.length > 0 ? filtered : performance
  }, [performance, timeframe])

  // Compute chart geometry
  const chartWidth = 600
  const chartHeight = 200
  const padX = 0
  const padY = 10

  const { polylinePoints, navMin, navMax, changeUSD, changePct, isPositive, areaPath } =
    useMemo(() => {
      if (filteredData.length === 0) {
        return {
          polylinePoints: '',
          navMin: 0,
          navMax: 0,
          changeUSD: 0,
          changePct: 0,
          isPositive: true,
          areaPath: '',
        }
      }

      const navs = filteredData.map(p => p.nav)
      const min = Math.min(...navs)
      const max = Math.max(...navs)
      const range = max - min || 1

      const points = filteredData.map((p, i) => {
        const x = padX + (i / (filteredData.length - 1 || 1)) * (chartWidth - 2 * padX)
        const y = padY + (1 - (p.nav - min) / range) * (chartHeight - 2 * padY)
        return { x, y }
      })

      const polyline = points.map(pt => `${pt.x},${pt.y}`).join(' ')

      // Area fill path (under the polyline)
      const area =
        `M ${points[0].x},${chartHeight} ` +
        points.map(pt => `L ${pt.x},${pt.y}`).join(' ') +
        ` L ${points[points.length - 1].x},${chartHeight} Z`

      const first = navs[0]
      const last = navs[navs.length - 1]
      const change = last - first
      const pct = first !== 0 ? (change / first) * 100 : 0

      return {
        polylinePoints: polyline,
        navMin: min,
        navMax: max,
        changeUSD: change,
        changePct: pct,
        isPositive: change >= 0,
        areaPath: area,
      }
    }, [filteredData])

  // Hovered point for tooltip
  const hoveredPoint = hoveredIdx !== null ? filteredData[hoveredIdx] : null

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (filteredData.length === 0) return
      const svg = e.currentTarget
      const rect = svg.getBoundingClientRect()
      const relX = e.clientX - rect.left
      const ratio = relX / rect.width
      const idx = Math.round(ratio * (filteredData.length - 1))
      setHoveredIdx(Math.max(0, Math.min(idx, filteredData.length - 1)))
    },
    [filteredData],
  )

  // Loading
  if (loading && performance.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-48 mb-4" />
        <div className="h-52 bg-gray-800 rounded" />
      </div>
    )
  }

  const lineColor = isPositive ? '#10B981' : '#EF4444'
  const fillColor = isPositive ? 'rgba(16,185,129,0.10)' : 'rgba(239,68,68,0.10)'

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white">NAV Performance</h2>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`text-2xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
              {changePct >= 0 ? '+' : ''}
              {changePct.toFixed(2)}%
            </span>
            <span className="text-sm text-gray-400">
              ({changeUSD >= 0 ? '+' : ''}
              {formatUSD(Math.abs(changeUSD))})
            </span>
          </div>
        </div>

        {/* Timeframe selector */}
        <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
          {(Object.keys(TIMEFRAME_HOURS) as Timeframe[]).map(tf => (
            <button
              key={tf}
              onClick={() => handleTimeframeChange(tf)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                timeframe === tf
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      {filteredData.length === 0 ? (
        <div className="flex items-center justify-center h-52 text-gray-500 text-sm">
          No performance data available.
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            className="w-full h-52"
            preserveAspectRatio="none"
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setHoveredIdx(null)}
          >
            {/* Grid lines */}
            {[0.25, 0.5, 0.75].map(frac => {
              const y = padY + frac * (chartHeight - 2 * padY)
              return (
                <line
                  key={frac}
                  x1={0}
                  y1={y}
                  x2={chartWidth}
                  y2={y}
                  stroke="#1F2937"
                  strokeWidth={1}
                />
              )
            })}

            {/* Area fill */}
            <path d={areaPath} fill={fillColor} />

            {/* Line */}
            <polyline
              points={polylinePoints}
              fill="none"
              stroke={lineColor}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />

            {/* Hover marker */}
            {hoveredIdx !== null && filteredData.length > 0 && (() => {
              const navs = filteredData.map(p => p.nav)
              const min = Math.min(...navs)
              const max = Math.max(...navs)
              const range = max - min || 1
              const x =
                padX +
                (hoveredIdx / (filteredData.length - 1 || 1)) * (chartWidth - 2 * padX)
              const y =
                padY +
                (1 - (filteredData[hoveredIdx].nav - min) / range) *
                  (chartHeight - 2 * padY)
              return (
                <>
                  <line
                    x1={x}
                    y1={0}
                    x2={x}
                    y2={chartHeight}
                    stroke="#4B5563"
                    strokeWidth={1}
                    strokeDasharray="4 2"
                  />
                  <circle cx={x} cy={y} r={4} fill={lineColor} stroke="#111827" strokeWidth={2} />
                </>
              )
            })()}
          </svg>

          {/* Tooltip */}
          {hoveredPoint && (
            <div className="absolute top-2 left-2 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs pointer-events-none">
              <div className="text-gray-400">
                {new Date(hoveredPoint.timestamp).toLocaleString()}
              </div>
              <div className="text-white font-semibold mt-0.5">
                NAV: {formatUSD(hoveredPoint.nav)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Y-axis labels */}
      {filteredData.length > 0 && (
        <div className="flex justify-between text-xs text-gray-600 mt-1 px-1">
          <span>{formatUSD(navMin)}</span>
          <span>{formatUSD((navMin + navMax) / 2)}</span>
          <span>{formatUSD(navMax)}</span>
        </div>
      )}
    </div>
  )
}

export default PerformanceChart
