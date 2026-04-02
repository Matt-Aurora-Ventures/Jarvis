import React, { useState, useEffect, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  PieChart,
  BarChart3,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Target,
  Percent,
  Wallet,
  RefreshCw,
  ChevronDown
} from 'lucide-react'

// Time range options
const TIME_RANGES = [
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: 'all', label: 'All Time' },
]

export default function PortfolioAnalytics() {
  const [timeRange, setTimeRange] = useState('7d')
  const [loading, setLoading] = useState(true)
  const [portfolioData, setPortfolioData] = useState(null)
  const [trades, setTrades] = useState([])
  const [holdings, setHoldings] = useState([])

  useEffect(() => {
    fetchPortfolioData()
    fetchTrades()
    fetchHoldings()
  }, [timeRange])

  const fetchPortfolioData = async () => {
    try {
      const response = await fetch(`/api/portfolio/stats?range=${timeRange}`)
      if (response.ok) {
        const data = await response.json()
        setPortfolioData(data)
      }
    } catch (err) {
      console.error('Failed to fetch portfolio data:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchTrades = async () => {
    try {
      const response = await fetch(`/api/scan/history?limit=100`)
      if (response.ok) {
        const data = await response.json()
        setTrades(data.trades || [])
      }
    } catch (err) {
      console.error('Failed to fetch trades:', err)
    }
  }

  const fetchHoldings = async () => {
    try {
      const response = await fetch('/api/wallet/status')
      if (response.ok) {
        const data = await response.json()
        setHoldings(data.tokens || [])
      }
    } catch (err) {
      console.error('Failed to fetch holdings:', err)
    }
  }

  // Calculate metrics from trades
  const metrics = useMemo(() => {
    if (!trades.length) {
      return {
        totalPnL: 0,
        winRate: 0,
        avgWin: 0,
        avgLoss: 0,
        profitFactor: 0,
        maxDrawdown: 0,
        sharpeRatio: 0,
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        bestTrade: 0,
        worstTrade: 0,
      }
    }

    const wins = trades.filter(t => (t.pnl_pct || 0) > 0)
    const losses = trades.filter(t => (t.pnl_pct || 0) < 0)
    const pnls = trades.map(t => t.pnl_pct || 0)

    const totalWins = wins.reduce((sum, t) => sum + (t.pnl_pct || 0), 0)
    const totalLosses = Math.abs(losses.reduce((sum, t) => sum + (t.pnl_pct || 0), 0))

    return {
      totalPnL: pnls.reduce((sum, pnl) => sum + pnl, 0),
      winRate: (wins.length / trades.length) * 100,
      avgWin: wins.length ? totalWins / wins.length : 0,
      avgLoss: losses.length ? totalLosses / losses.length : 0,
      profitFactor: totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0,
      maxDrawdown: calculateMaxDrawdown(pnls),
      sharpeRatio: calculateSharpeRatio(pnls),
      totalTrades: trades.length,
      winningTrades: wins.length,
      losingTrades: losses.length,
      bestTrade: Math.max(...pnls),
      worstTrade: Math.min(...pnls),
    }
  }, [trades])

  // Holdings breakdown
  const holdingsBreakdown = useMemo(() => {
    if (!holdings.length) return []

    const totalValue = holdings.reduce((sum, h) => sum + (h.value_usd || 0), 0)

    return holdings.map(h => ({
      ...h,
      percentage: totalValue > 0 ? (h.value_usd / totalValue) * 100 : 0,
    })).sort((a, b) => b.value_usd - a.value_usd)
  }, [holdings])

  // PnL distribution for chart
  const pnlDistribution = useMemo(() => {
    const buckets = {
      'Loss > 20%': 0,
      'Loss 10-20%': 0,
      'Loss 5-10%': 0,
      'Loss 0-5%': 0,
      'Gain 0-5%': 0,
      'Gain 5-10%': 0,
      'Gain 10-20%': 0,
      'Gain > 20%': 0,
    }

    trades.forEach(t => {
      const pnl = t.pnl_pct || 0
      if (pnl < -20) buckets['Loss > 20%']++
      else if (pnl < -10) buckets['Loss 10-20%']++
      else if (pnl < -5) buckets['Loss 5-10%']++
      else if (pnl < 0) buckets['Loss 0-5%']++
      else if (pnl < 5) buckets['Gain 0-5%']++
      else if (pnl < 10) buckets['Gain 5-10%']++
      else if (pnl < 20) buckets['Gain 10-20%']++
      else buckets['Gain > 20%']++
    })

    return Object.entries(buckets).map(([label, count]) => ({ label, count }))
  }, [trades])

  if (loading) {
    return (
      <div className="portfolio-analytics loading">
        <RefreshCw size={24} className="animate-spin" />
        <span>Loading analytics...</span>
      </div>
    )
  }

  return (
    <div className="portfolio-analytics">
      {/* Header */}
      <div className="analytics-header">
        <div>
          <h1>Portfolio Analytics</h1>
          <p>Track your trading performance and portfolio allocation</p>
        </div>
        <div className="time-range-selector">
          <Calendar size={18} />
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
          >
            {TIME_RANGES.map(range => (
              <option key={range.value} value={range.value}>{range.label}</option>
            ))}
          </select>
          <ChevronDown size={16} />
        </div>
      </div>

      {/* Key Metrics */}
      <div className="metrics-grid">
        <MetricCard
          icon={<DollarSign />}
          label="Total P&L"
          value={`${metrics.totalPnL >= 0 ? '+' : ''}${metrics.totalPnL.toFixed(2)}%`}
          trend={metrics.totalPnL >= 0 ? 'up' : 'down'}
          color={metrics.totalPnL >= 0 ? 'success' : 'error'}
        />
        <MetricCard
          icon={<Target />}
          label="Win Rate"
          value={`${metrics.winRate.toFixed(1)}%`}
          subtext={`${metrics.winningTrades}W / ${metrics.losingTrades}L`}
          color={metrics.winRate >= 50 ? 'success' : 'warning'}
        />
        <MetricCard
          icon={<Activity />}
          label="Profit Factor"
          value={metrics.profitFactor === Infinity ? '∞' : metrics.profitFactor.toFixed(2)}
          subtext="Gains / Losses"
          color={metrics.profitFactor >= 1.5 ? 'success' : metrics.profitFactor >= 1 ? 'warning' : 'error'}
        />
        <MetricCard
          icon={<BarChart3 />}
          label="Total Trades"
          value={metrics.totalTrades.toString()}
          subtext={`${timeRange} period`}
        />
      </div>

      {/* Performance Details */}
      <div className="analytics-sections">
        <div className="section performance-section">
          <h2>
            <Activity size={20} />
            Performance Metrics
          </h2>

          <div className="perf-grid">
            <div className="perf-item">
              <span className="perf-label">Average Win</span>
              <span className="perf-value success">+{metrics.avgWin.toFixed(2)}%</span>
            </div>
            <div className="perf-item">
              <span className="perf-label">Average Loss</span>
              <span className="perf-value error">-{metrics.avgLoss.toFixed(2)}%</span>
            </div>
            <div className="perf-item">
              <span className="perf-label">Best Trade</span>
              <span className="perf-value success">+{metrics.bestTrade.toFixed(2)}%</span>
            </div>
            <div className="perf-item">
              <span className="perf-label">Worst Trade</span>
              <span className="perf-value error">{metrics.worstTrade.toFixed(2)}%</span>
            </div>
            <div className="perf-item">
              <span className="perf-label">Max Drawdown</span>
              <span className="perf-value warning">{metrics.maxDrawdown.toFixed(2)}%</span>
            </div>
            <div className="perf-item">
              <span className="perf-label">Sharpe Ratio</span>
              <span className={`perf-value ${metrics.sharpeRatio >= 1 ? 'success' : 'warning'}`}>
                {metrics.sharpeRatio.toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        {/* P&L Distribution */}
        <div className="section distribution-section">
          <h2>
            <BarChart3 size={20} />
            P&L Distribution
          </h2>

          <div className="distribution-chart">
            {pnlDistribution.map((bucket, i) => {
              const maxCount = Math.max(...pnlDistribution.map(b => b.count))
              const width = maxCount > 0 ? (bucket.count / maxCount) * 100 : 0
              const isLoss = bucket.label.includes('Loss')

              return (
                <div key={i} className="distribution-bar">
                  <span className="bar-label">{bucket.label}</span>
                  <div className="bar-track">
                    <div
                      className={`bar-fill ${isLoss ? 'loss' : 'gain'}`}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <span className="bar-count">{bucket.count}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Holdings Breakdown */}
      <div className="section holdings-section">
        <h2>
          <Wallet size={20} />
          Current Holdings
        </h2>

        {holdingsBreakdown.length === 0 ? (
          <div className="empty-holdings">
            <PieChart size={48} style={{ opacity: 0.3 }} />
            <p>No token holdings found</p>
          </div>
        ) : (
          <div className="holdings-grid">
            <div className="holdings-chart">
              <div className="pie-chart">
                {holdingsBreakdown.slice(0, 6).map((holding, i) => {
                  const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
                  return (
                    <div
                      key={i}
                      className="pie-segment"
                      style={{
                        '--color': colors[i % colors.length],
                        '--percentage': holding.percentage,
                        '--offset': holdingsBreakdown.slice(0, i).reduce((sum, h) => sum + h.percentage, 0),
                      }}
                    />
                  )
                })}
              </div>
            </div>

            <div className="holdings-list">
              {holdingsBreakdown.slice(0, 10).map((holding, i) => (
                <div key={i} className="holding-item">
                  <div className="holding-info">
                    <span className="holding-symbol">{holding.symbol}</span>
                    <span className="holding-amount">{holding.amount?.toFixed(4)}</span>
                  </div>
                  <div className="holding-value">
                    <span className="value-usd">${holding.value_usd?.toFixed(2)}</span>
                    <span className="value-pct">{holding.percentage?.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recent Trades */}
      <div className="section trades-section">
        <h2>
          <TrendingUp size={20} />
          Recent Trades
        </h2>

        <div className="trades-table">
          <div className="table-header">
            <span>Token</span>
            <span>Entry</span>
            <span>Exit</span>
            <span>P&L</span>
            <span>Status</span>
          </div>

          {trades.slice(0, 10).map((trade, i) => (
            <div key={i} className="table-row">
              <span className="token">{trade.symbol || 'Unknown'}</span>
              <span className="price">${trade.entry_price?.toFixed(8) || '-'}</span>
              <span className="price">${trade.exit_price?.toFixed(8) || '-'}</span>
              <span className={`pnl ${(trade.pnl_pct || 0) >= 0 ? 'positive' : 'negative'}`}>
                {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{trade.pnl_pct?.toFixed(2) || '0.00'}%
              </span>
              <span className={`status ${trade.is_paper ? 'paper' : 'live'}`}>
                {trade.is_paper ? 'Paper' : 'Live'}
              </span>
            </div>
          ))}

          {trades.length === 0 && (
            <div className="no-trades">
              <p>No trades in selected period</p>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .portfolio-analytics {
          padding: var(--space-xl);
          max-width: 1400px;
          margin: 0 auto;
        }

        .portfolio-analytics.loading {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-md);
          min-height: 400px;
          color: var(--text-secondary);
        }

        .analytics-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: var(--space-xl);
        }

        .analytics-header h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 var(--space-xs) 0;
        }

        .analytics-header p {
          color: var(--text-secondary);
          font-size: 0.875rem;
          margin: 0;
        }

        .time-range-selector {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-sm) var(--space-md);
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          border-radius: var(--radius-md);
          color: var(--text-secondary);
        }

        .time-range-selector select {
          background: transparent;
          border: none;
          color: var(--text-primary);
          font-size: 0.875rem;
          cursor: pointer;
          padding-right: var(--space-lg);
          appearance: none;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--space-lg);
          margin-bottom: var(--space-xl);
        }

        .analytics-sections {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-lg);
          margin-bottom: var(--space-xl);
        }

        .section {
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: var(--radius-lg);
          padding: var(--space-xl);
        }

        .section h2 {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          font-size: 1.125rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 var(--space-lg) 0;
        }

        .perf-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--space-md);
        }

        .perf-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-md);
          background: var(--bg-tertiary);
          border-radius: var(--radius-md);
        }

        .perf-label {
          font-size: 0.813rem;
          color: var(--text-secondary);
        }

        .perf-value {
          font-size: 1rem;
          font-weight: 600;
        }

        .perf-value.success { color: var(--success); }
        .perf-value.error { color: var(--error); }
        .perf-value.warning { color: var(--warning); }

        .distribution-chart {
          display: flex;
          flex-direction: column;
          gap: var(--space-sm);
        }

        .distribution-bar {
          display: grid;
          grid-template-columns: 100px 1fr 40px;
          align-items: center;
          gap: var(--space-md);
        }

        .bar-label {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .bar-track {
          height: 20px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          overflow: hidden;
        }

        .bar-fill {
          height: 100%;
          transition: width 0.3s ease;
        }

        .bar-fill.loss { background: var(--error); }
        .bar-fill.gain { background: var(--success); }

        .bar-count {
          font-size: 0.813rem;
          font-weight: 500;
          color: var(--text-primary);
          text-align: right;
        }

        .holdings-section {
          margin-bottom: var(--space-xl);
        }

        .empty-holdings {
          text-align: center;
          padding: var(--space-3xl);
          color: var(--text-secondary);
        }

        .holdings-grid {
          display: grid;
          grid-template-columns: 200px 1fr;
          gap: var(--space-xl);
        }

        .pie-chart {
          width: 180px;
          height: 180px;
          border-radius: 50%;
          background: conic-gradient(from 0deg, var(--bg-tertiary) 0deg 360deg);
          position: relative;
          overflow: hidden;
        }

        .holdings-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-sm);
        }

        .holding-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-md);
          background: var(--bg-tertiary);
          border-radius: var(--radius-md);
        }

        .holding-symbol {
          font-weight: 600;
          color: var(--text-primary);
        }

        .holding-amount {
          font-size: 0.813rem;
          color: var(--text-tertiary);
          margin-left: var(--space-sm);
        }

        .holding-value {
          text-align: right;
        }

        .value-usd {
          display: block;
          font-weight: 500;
          color: var(--text-primary);
        }

        .value-pct {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .trades-table {
          display: flex;
          flex-direction: column;
        }

        .table-header, .table-row {
          display: grid;
          grid-template-columns: 1.5fr 1fr 1fr 1fr 0.8fr;
          padding: var(--space-md);
          align-items: center;
        }

        .table-header {
          background: var(--bg-tertiary);
          border-radius: var(--radius-md) var(--radius-md) 0 0;
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-secondary);
          text-transform: uppercase;
        }

        .table-row {
          border-bottom: 1px solid var(--border-secondary);
        }

        .table-row:last-child {
          border-bottom: none;
        }

        .token {
          font-weight: 500;
          color: var(--text-primary);
        }

        .price {
          font-family: monospace;
          font-size: 0.813rem;
          color: var(--text-secondary);
        }

        .pnl {
          font-weight: 600;
        }

        .pnl.positive { color: var(--success); }
        .pnl.negative { color: var(--error); }

        .status {
          font-size: 0.75rem;
          padding: 4px 8px;
          border-radius: 12px;
          text-align: center;
        }

        .status.paper {
          background: rgba(var(--warning-rgb), 0.1);
          color: var(--warning);
        }

        .status.live {
          background: rgba(var(--success-rgb), 0.1);
          color: var(--success);
        }

        .no-trades {
          text-align: center;
          padding: var(--space-xl);
          color: var(--text-tertiary);
        }

        @media (max-width: 1024px) {
          .metrics-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .analytics-sections {
            grid-template-columns: 1fr;
          }

          .holdings-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 640px) {
          .metrics-grid {
            grid-template-columns: 1fr;
          }

          .analytics-header {
            flex-direction: column;
            gap: var(--space-md);
          }

          .table-header, .table-row {
            grid-template-columns: 1fr 1fr 1fr;
          }

          .table-header span:nth-child(3),
          .table-header span:nth-child(4),
          .table-row span:nth-child(3),
          .table-row span:nth-child(4) {
            display: none;
          }
        }
      `}</style>
    </div>
  )
}

// Helper Components
function MetricCard({ icon, label, value, subtext, trend, color = 'default' }) {
  const colorClasses = {
    success: 'var(--success)',
    error: 'var(--error)',
    warning: 'var(--warning)',
    default: 'var(--text-primary)',
  }

  return (
    <div className="metric-card">
      <div className="metric-icon" style={{ color: colorClasses[color] }}>
        {icon}
      </div>
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: colorClasses[color] }}>
        {value}
        {trend && (
          trend === 'up' ?
            <ArrowUpRight size={20} style={{ marginLeft: 4 }} /> :
            <ArrowDownRight size={20} style={{ marginLeft: 4 }} />
        )}
      </div>
      {subtext && <div className="metric-subtext">{subtext}</div>}

      <style jsx>{`
        .metric-card {
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
        }

        .metric-icon {
          margin-bottom: var(--space-sm);
          opacity: 0.8;
        }

        .metric-label {
          font-size: 0.813rem;
          color: var(--text-secondary);
          margin-bottom: var(--space-xs);
        }

        .metric-value {
          font-size: 1.75rem;
          font-weight: 700;
          display: flex;
          align-items: center;
        }

        .metric-subtext {
          font-size: 0.75rem;
          color: var(--text-tertiary);
          margin-top: var(--space-xs);
        }
      `}</style>
    </div>
  )
}

// Helper functions
function calculateMaxDrawdown(pnls) {
  if (!pnls.length) return 0

  let peak = 0
  let maxDrawdown = 0
  let cumulative = 0

  for (const pnl of pnls) {
    cumulative += pnl
    if (cumulative > peak) peak = cumulative
    const drawdown = peak - cumulative
    if (drawdown > maxDrawdown) maxDrawdown = drawdown
  }

  return maxDrawdown
}

function calculateSharpeRatio(pnls) {
  if (pnls.length < 2) return 0

  const mean = pnls.reduce((sum, pnl) => sum + pnl, 0) / pnls.length
  const variance = pnls.reduce((sum, pnl) => sum + Math.pow(pnl - mean, 2), 0) / pnls.length
  const stdDev = Math.sqrt(variance)

  if (stdDev === 0) return 0

  // Annualized assuming daily returns, risk-free rate = 0
  return (mean * Math.sqrt(252)) / (stdDev * Math.sqrt(252))
}
