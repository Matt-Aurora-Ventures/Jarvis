import React from 'react'
import { Target, Zap, RefreshCw, Clock, XCircle } from 'lucide-react'
import { formatCryptoPrice, formatUSD, formatPercent, formatDuration } from '../../lib/format'

/**
 * PositionCard - Display active trading position
 */
function PositionCard({ position, onExit, onRefresh }) {
  if (!position?.has_position) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Target className="card-title-icon" size={20} />
            Active Position
          </div>
        </div>
        <div className="card-body text-center">
          <Zap size={32} style={{ color: 'var(--text-tertiary)', margin: '2rem auto' }} />
          <p style={{ color: 'var(--text-secondary)' }}>No active position</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
            Waiting for entry signal...
          </p>
        </div>
      </div>
    )
  }

  const {
    symbol,
    entry_price,
    current_price,
    tp_price,
    sl_price,
    pnl_pct,
    pnl_usd,
    time_held_minutes,
    is_paper,
  } = position

  const isProfit = pnl_pct >= 0
  const priceRange = tp_price - sl_price
  const currentProgress = priceRange > 0 
    ? ((current_price - sl_price) / priceRange) * 100 
    : 50

  return (
    <div className={`card position-card ${isProfit ? 'profit' : 'loss'}`}>
      <div className="card-header">
        <div className="card-title">
          <Target className="card-title-icon" size={20} />
          Active Position
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {is_paper && <span className="badge badge-warning">PAPER</span>}
          <button onClick={onRefresh} className="btn btn-ghost btn-sm">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="card-body">
        <div className="position-header">
          <span className="position-symbol">{symbol}</span>
          <span className={`position-pnl ${isProfit ? 'positive' : 'negative'}`}>
            {formatPercent(pnl_pct)}
          </span>
        </div>

        <div className="position-metrics">
          <MetricItem label="Entry" value={formatCryptoPrice(entry_price)} />
          <MetricItem label="Current" value={formatCryptoPrice(current_price)} />
          <MetricItem 
            label="P&L" 
            value={formatUSD(pnl_usd)} 
            className={isProfit ? 'positive' : 'negative'} 
          />
        </div>

        <TPSLProgress 
          slPrice={sl_price} 
          tpPrice={tp_price} 
          progress={currentProgress} 
        />

        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginTop: '1rem' 
        }}>
          <span style={{ 
            fontSize: '0.875rem', 
            color: 'var(--text-secondary)', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '4px' 
          }}>
            <Clock size={14} />
            {formatDuration(time_held_minutes)} held
          </span>
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={() => onExit('MANUAL_EXIT')}
          >
            <XCircle size={14} />
            Exit Position
          </button>
        </div>
      </div>
    </div>
  )
}

function MetricItem({ label, value, className = '' }) {
  return (
    <div className="metric-item">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${className}`}>{value}</div>
    </div>
  )
}

function TPSLProgress({ slPrice, tpPrice, progress }) {
  const clampedProgress = Math.min(Math.max(progress, 0), 100)
  
  return (
    <div className="tpsl-progress">
      <div className="tpsl-labels">
        <span>SL: {formatCryptoPrice(slPrice)}</span>
        <span>TP: {formatCryptoPrice(tpPrice)}</span>
      </div>
      <div className="tpsl-bar">
        <div className="tpsl-fill" style={{ width: `${clampedProgress}%` }} />
        <div className="tpsl-marker" style={{ left: `${clampedProgress}%` }} />
      </div>
    </div>
  )
}

export default PositionCard
