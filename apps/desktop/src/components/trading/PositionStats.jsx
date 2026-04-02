import React from 'react'
import { TrendingUp, TrendingDown, Award, Clock, Target, RefreshCw, Flame } from 'lucide-react'
import { formatPercent, formatUSD, formatDuration } from '../../lib/format'
import { usePositionStats } from '../../hooks/usePositionStats'

/**
 * PositionStats - Display trading performance statistics
 */
function PositionStats() {
  const {
    stats,
    loading,
    error,
    refresh,
    totalTrades,
    winRate,
    totalPnl,
    avgHoldTime,
    currentStreak,
    bestTrade,
    worstTrade,
  } = usePositionStats()

  if (loading) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Award className="card-title-icon" size={20} />
            Performance Stats
          </div>
        </div>
        <div className="card-body text-center">
          <div className="animate-pulse">Loading stats...</div>
        </div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Award className="card-title-icon" size={20} />
            Performance Stats
          </div>
        </div>
        <div className="card-body text-center">
          <p style={{ color: 'var(--text-secondary)' }}>No trading history yet</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
            Stats will appear after your first trade
          </p>
        </div>
      </div>
    )
  }

  const isPositive = totalPnl >= 0
  const isWinning = currentStreak > 0

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Award className="card-title-icon" size={20} />
          Performance Stats
        </div>
        <button onClick={refresh} className="btn btn-ghost btn-sm">
          <RefreshCw size={14} />
        </button>
      </div>

      <div className="card-body">
        {/* Main Stats Grid */}
        <div className="stats-grid">
          <StatCard
            icon={<Target size={16} />}
            label="Total Trades"
            value={totalTrades}
          />
          <StatCard
            icon={<TrendingUp size={16} />}
            label="Win Rate"
            value={`${winRate.toFixed(1)}%`}
            className={winRate >= 50 ? 'positive' : 'negative'}
          />
          <StatCard
            icon={isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
            label="Total P&L"
            value={formatUSD(totalPnl)}
            className={isPositive ? 'positive' : 'negative'}
          />
          <StatCard
            icon={<Clock size={16} />}
            label="Avg Hold"
            value={formatDuration(avgHoldTime)}
          />
        </div>

        {/* Best/Worst Trades */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '1rem',
          padding: '0.75rem',
          background: 'var(--bg-tertiary)',
          borderRadius: '8px',
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Best Trade</div>
            <div className="positive" style={{ fontWeight: 600 }}>
              {formatPercent(bestTrade)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Worst Trade</div>
            <div className="negative" style={{ fontWeight: 600 }}>
              {formatPercent(worstTrade)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Current Streak</div>
            <div style={{
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: isWinning ? 'var(--success)' : currentStreak < 0 ? 'var(--danger)' : 'inherit'
            }}>
              {currentStreak > 0 && <Flame size={14} style={{ color: 'var(--warning)' }} />}
              {Math.abs(currentStreak)} {isWinning ? 'wins' : currentStreak < 0 ? 'losses' : ''}
            </div>
          </div>
        </div>

        {/* Win/Loss Breakdown */}
        {totalTrades > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <WinLossBar
              wins={stats.winning_positions || 0}
              losses={stats.losing_positions || 0}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, className = '' }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <div className="stat-label">{label}</div>
        <div className={`stat-value ${className}`}>{value}</div>
      </div>
    </div>
  )
}

function WinLossBar({ wins, losses }) {
  const total = wins + losses
  const winPct = total > 0 ? (wins / total) * 100 : 50

  return (
    <div className="win-loss-bar">
      <div className="win-loss-labels">
        <span className="positive">{wins} Wins</span>
        <span className="negative">{losses} Losses</span>
      </div>
      <div className="win-loss-track">
        <div
          className="win-loss-fill positive-bg"
          style={{ width: `${winPct}%` }}
        />
      </div>
    </div>
  )
}

export default PositionStats
