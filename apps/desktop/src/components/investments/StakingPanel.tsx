import React from 'react'
import type { StakingPool } from './useInvestmentData'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  return `$${val.toFixed(2)}`
}

function formatNumber(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`
  return val.toLocaleString()
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StakingPanelProps {
  pool: StakingPool | null
  loading: boolean
}

export function StakingPanel({ pool, loading }: StakingPanelProps) {
  if (loading && !pool) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-36 mb-4" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (!pool) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 text-sm text-gray-500">
        Staking pool data unavailable.
      </div>
    )
  }

  // Default tier info if the backend doesn't provide it
  const tiers = pool.tiers && pool.tiers.length > 0
    ? pool.tiers
    : [
        { name: 'Base', multiplier: 1.0, min_days: 0, max_days: 29, stakers: 0 },
        { name: 'Silver', multiplier: 1.25, min_days: 30, max_days: 89, stakers: 0 },
        { name: 'Gold', multiplier: 1.5, min_days: 90, max_days: 999, stakers: 0 },
      ]

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Staking Pool</h2>

      {/* Key stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* TVL */}
        <div className="bg-gray-800/50 rounded-lg p-4 text-center">
          <span className="text-xs uppercase tracking-wider text-gray-500 block mb-1">TVL</span>
          <span className="text-xl font-bold text-white">{formatUSD(pool.tvl_usd)}</span>
        </div>

        {/* APY */}
        <div className="bg-gray-800/50 rounded-lg p-4 text-center">
          <span className="text-xs uppercase tracking-wider text-gray-500 block mb-1">APY</span>
          <span className="text-xl font-bold text-green-400">{pool.apy_pct.toFixed(1)}%</span>
        </div>

        {/* Total stakers */}
        <div className="bg-gray-800/50 rounded-lg p-4 text-center">
          <span className="text-xs uppercase tracking-wider text-gray-500 block mb-1">Stakers</span>
          <span className="text-xl font-bold text-white">{formatNumber(pool.total_stakers)}</span>
        </div>
      </div>

      {/* Tier breakdown */}
      <div>
        <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Lock-up Tiers</h3>
        <div className="space-y-2">
          {tiers.map(tier => {
            const multiplierColor =
              tier.multiplier >= 1.5
                ? 'text-yellow-400'
                : tier.multiplier >= 1.25
                ? 'text-blue-400'
                : 'text-gray-400'

            return (
              <div
                key={tier.name}
                className="flex items-center justify-between bg-gray-800/40 rounded-lg px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  {/* Multiplier badge */}
                  <span
                    className={`text-sm font-bold ${multiplierColor}`}
                  >
                    {tier.multiplier}x
                  </span>
                  <div>
                    <span className="text-sm font-medium text-white">{tier.name}</span>
                    <span className="text-xs text-gray-500 ml-2">
                      {tier.min_days}-{tier.max_days >= 999 ? '...' : tier.max_days}d
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Visual bar showing proportion of stakers */}
                  {pool.total_stakers > 0 && (
                    <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-violet-500"
                        style={{
                          width: `${Math.max(3, (tier.stakers / pool.total_stakers) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                  <span className="text-xs text-gray-500 w-12 text-right">
                    {formatNumber(tier.stakers)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default StakingPanel
