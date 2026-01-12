import React from 'react'
import { ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { formatUSD, formatPercent } from '../../lib/format'

/**
 * StatsGrid - Display key metrics in a grid
 */
function StatsGrid({ walletData, sniperData, loading = false }) {
  // Show skeleton loading state
  if (loading) {
    return (
      <div className="stats-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="stat-card fade-in">
            <div className="skeleton skeleton-text" style={{ width: '60%', height: '14px', marginBottom: '8px' }} />
            <div className="skeleton skeleton-text" style={{ width: '80%', height: '24px', marginBottom: '8px' }} />
            <div className="skeleton skeleton-text" style={{ width: '40%', height: '14px' }} />
          </div>
        ))}
        <style jsx>{`
          .skeleton {
            background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--bg-tertiary) 50%, var(--bg-secondary) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
          }
          @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        `}</style>
      </div>
    )
  }

  const stats = [
    {
      label: 'Portfolio Value',
      value: formatUSD(walletData?.balance_usd),
      change: '+0.00%',
      positive: true,
    },
    {
      label: 'Win Rate',
      value: sniperData?.win_rate || '0%',
      change: sniperData?.win_rate || '0%',
      positive: parseFloat(sniperData?.win_rate) >= 50,
    },
    {
      label: 'Total Trades',
      value: sniperData?.total_trades || 0,
      change: 'All time',
      positive: true,
    },
    {
      label: 'Total P&L',
      value: formatUSD(sniperData?.state?.total_pnl_usd),
      change: sniperData?.state?.total_pnl_usd >= 0 ? '+' : '',
      positive: sniperData?.state?.total_pnl_usd >= 0,
    },
  ]

  return (
    <div className="stats-grid">
      {stats.map((stat, i) => (
        <StatCard key={i} {...stat} />
      ))}
    </div>
  )
}

function StatCard({ label, value, change, positive }) {
  return (
    <div className="stat-card fade-in">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className={`stat-change ${positive ? 'positive' : 'negative'}`}>
        {positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        {change}
      </div>
    </div>
  )
}

export default StatsGrid
