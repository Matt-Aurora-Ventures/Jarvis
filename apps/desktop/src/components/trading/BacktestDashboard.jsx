import React, { useState, useEffect, useMemo } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Calendar,
  DollarSign,
  Percent,
  Clock,
  Target,
  Shield,
  Zap,
  RefreshCw,
  Play,
  Pause,
  Settings,
  Download,
  ChevronDown,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'

/**
 * Backtest Result Card
 */
function MetricCard({ label, value, subValue, icon: Icon, trend, color = 'cyan' }) {
  const colorClasses = {
    cyan: 'text-cyan-400',
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  }

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-400 mb-1">{label}</p>
          <p className={`text-2xl font-bold ${colorClasses[color]}`}>{value}</p>
          {subValue && (
            <p className="text-xs text-gray-500 mt-1">{subValue}</p>
          )}
        </div>
        {Icon && (
          <div className={`p-2 rounded-lg bg-gray-700/50 ${colorClasses[color]}`}>
            <Icon size={18} />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${
          trend >= 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {trend >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {Math.abs(trend).toFixed(2)}%
        </div>
      )}
    </div>
  )
}

/**
 * Equity Curve Chart
 */
function EquityCurve({ data, height = 200 }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <span className="text-gray-500">No data</span>
      </div>
    )
  }

  const width = 800
  const padding = { top: 20, right: 20, bottom: 30, left: 60 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const values = data.map(d => d.equity)
  const minEquity = Math.min(...values) * 0.95
  const maxEquity = Math.max(...values) * 1.05

  const xScale = (i) => padding.left + (i / (data.length - 1)) * chartWidth
  const yScale = (v) => padding.top + (1 - (v - minEquity) / (maxEquity - minEquity)) * chartHeight

  const linePath = data.map((d, i) =>
    `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(d.equity)}`
  ).join(' ')

  const areaPath = linePath +
    ` L ${xScale(data.length - 1)} ${padding.top + chartHeight}` +
    ` L ${padding.left} ${padding.top + chartHeight} Z`

  const startEquity = data[0]?.equity || 0
  const endEquity = data[data.length - 1]?.equity || 0
  const isPositive = endEquity >= startEquity

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
        const y = padding.top + chartHeight * pct
        const value = maxEquity - (maxEquity - minEquity) * pct
        return (
          <g key={i}>
            <line
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="#374151"
              strokeDasharray="4,4"
            />
            <text
              x={padding.left - 8}
              y={y + 4}
              fill="#6b7280"
              fontSize={10}
              textAnchor="end"
            >
              ${value.toFixed(0)}
            </text>
          </g>
        )
      })}

      {/* Area fill */}
      <path
        d={areaPath}
        fill={isPositive ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)'}
      />

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={isPositive ? '#22c55e' : '#ef4444'}
        strokeWidth={2}
      />

      {/* Start/End markers */}
      <circle
        cx={xScale(0)}
        cy={yScale(startEquity)}
        r={4}
        fill="#1f2937"
        stroke={isPositive ? '#22c55e' : '#ef4444'}
        strokeWidth={2}
      />
      <circle
        cx={xScale(data.length - 1)}
        cy={yScale(endEquity)}
        r={4}
        fill={isPositive ? '#22c55e' : '#ef4444'}
      />
    </svg>
  )
}

/**
 * Drawdown Chart
 */
function DrawdownChart({ data, height = 100 }) {
  if (!data || data.length === 0) return null

  const width = 800
  const padding = { top: 10, right: 20, bottom: 20, left: 60 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const drawdowns = data.map(d => d.drawdown || 0)
  const maxDrawdown = Math.min(...drawdowns)

  const xScale = (i) => padding.left + (i / (data.length - 1)) * chartWidth
  const yScale = (v) => padding.top + (v / maxDrawdown) * chartHeight

  const barWidth = Math.max(1, chartWidth / data.length - 1)

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {/* Zero line */}
      <line
        x1={padding.left}
        y1={padding.top}
        x2={width - padding.right}
        y2={padding.top}
        stroke="#374151"
      />

      {/* Bars */}
      {data.map((d, i) => {
        if (!d.drawdown || d.drawdown === 0) return null
        const barHeight = yScale(d.drawdown) - padding.top
        return (
          <rect
            key={i}
            x={xScale(i) - barWidth / 2}
            y={padding.top}
            width={barWidth}
            height={barHeight}
            fill="rgba(239, 68, 68, 0.5)"
          />
        )
      })}

      {/* Max drawdown label */}
      <text
        x={padding.left - 8}
        y={padding.top + chartHeight}
        fill="#ef4444"
        fontSize={10}
        textAnchor="end"
      >
        {(maxDrawdown * 100).toFixed(1)}%
      </text>
    </svg>
  )
}

/**
 * Trade Distribution Chart
 */
function TradeDistribution({ trades }) {
  if (!trades || trades.length === 0) return null

  const wins = trades.filter(t => t.pnl > 0)
  const losses = trades.filter(t => t.pnl < 0)

  const winPnls = wins.map(t => t.pnl)
  const lossPnls = losses.map(t => Math.abs(t.pnl))

  const avgWin = winPnls.length > 0 ? winPnls.reduce((a, b) => a + b, 0) / winPnls.length : 0
  const avgLoss = lossPnls.length > 0 ? lossPnls.reduce((a, b) => a + b, 0) / lossPnls.length : 0

  const winRate = trades.length > 0 ? (wins.length / trades.length) * 100 : 0

  return (
    <div className="space-y-4">
      {/* Win/Loss Bar */}
      <div>
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-green-400">{wins.length} Wins</span>
          <span className="text-gray-400">{winRate.toFixed(1)}%</span>
          <span className="text-red-400">{losses.length} Losses</span>
        </div>
        <div className="h-4 rounded-full overflow-hidden flex bg-gray-700">
          <div
            className="bg-green-500 h-full"
            style={{ width: `${winRate}%` }}
          />
          <div
            className="bg-red-500 h-full"
            style={{ width: `${100 - winRate}%` }}
          />
        </div>
      </div>

      {/* Average Win/Loss */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/30">
          <p className="text-gray-400 text-xs mb-1">Avg Win</p>
          <p className="text-green-400 font-bold">${avgWin.toFixed(2)}</p>
        </div>
        <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/30">
          <p className="text-gray-400 text-xs mb-1">Avg Loss</p>
          <p className="text-red-400 font-bold">${avgLoss.toFixed(2)}</p>
        </div>
      </div>

      {/* Profit Factor */}
      <div className="text-center">
        <p className="text-gray-400 text-xs mb-1">Profit Factor</p>
        <p className={`text-xl font-bold ${
          avgWin * wins.length > avgLoss * losses.length ? 'text-green-400' : 'text-red-400'
        }`}>
          {avgLoss > 0 ? ((avgWin * wins.length) / (avgLoss * losses.length)).toFixed(2) : '-'}
        </p>
      </div>
    </div>
  )
}

/**
 * Trade List
 */
function TradeList({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No trades to display
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Date</th>
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Symbol</th>
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Side</th>
            <th className="text-right py-2 px-3 text-gray-400 font-medium">Entry</th>
            <th className="text-right py-2 px-3 text-gray-400 font-medium">Exit</th>
            <th className="text-right py-2 px-3 text-gray-400 font-medium">P&L</th>
            <th className="text-right py-2 px-3 text-gray-400 font-medium">%</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {trades.slice(0, 20).map((trade, i) => {
            const isWin = trade.pnl > 0
            return (
              <tr key={i} className="hover:bg-gray-800/50">
                <td className="py-2 px-3 text-gray-300">
                  {new Date(trade.date).toLocaleDateString()}
                </td>
                <td className="py-2 px-3 text-white font-medium">${trade.symbol}</td>
                <td className="py-2 px-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    trade.side === 'buy'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trade.side.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 px-3 text-right text-gray-300 font-mono">
                  ${trade.entryPrice?.toFixed(6)}
                </td>
                <td className="py-2 px-3 text-right text-gray-300 font-mono">
                  ${trade.exitPrice?.toFixed(6)}
                </td>
                <td className={`py-2 px-3 text-right font-mono ${
                  isWin ? 'text-green-400' : 'text-red-400'
                }`}>
                  {isWin ? '+' : ''}{trade.pnl?.toFixed(2)}
                </td>
                <td className={`py-2 px-3 text-right ${
                  isWin ? 'text-green-400' : 'text-red-400'
                }`}>
                  {trade.pnlPct > 0 ? '+' : ''}{trade.pnlPct?.toFixed(2)}%
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {trades.length > 20 && (
        <p className="text-center text-gray-500 text-xs mt-2">
          Showing 20 of {trades.length} trades
        </p>
      )}
    </div>
  )
}

/**
 * Backtest Dashboard Component
 */
export default function BacktestDashboard({
  strategyId,
  strategyName = 'Strategy',
  onRunBacktest,
  onExport,
}) {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  // Backtest parameters
  const [params, setParams] = useState({
    startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
    initialCapital: 10000,
    positionSize: 10, // % of capital
  })

  // Fetch existing results
  useEffect(() => {
    if (strategyId) {
      fetchResults()
    }
  }, [strategyId])

  const fetchResults = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/trading/backtests?strategy=${strategyId}`)
      if (!response.ok) throw new Error('Failed to fetch backtest results')

      const data = await response.json()
      if (data.results) {
        setResults(data.results)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRunBacktest = async () => {
    if (onRunBacktest) {
      setLoading(true)
      setError(null)

      try {
        const result = await onRunBacktest(params)
        setResults(result)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
  }

  // Calculate summary metrics
  const metrics = useMemo(() => {
    if (!results) return null

    const trades = results.trades || []
    const equityCurve = results.equityCurve || []

    const wins = trades.filter(t => t.pnl > 0)
    const losses = trades.filter(t => t.pnl < 0)

    const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0)
    const winRate = trades.length > 0 ? (wins.length / trades.length) * 100 : 0

    const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0
    const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0)) / losses.length : 0

    const profitFactor = avgLoss > 0 && losses.length > 0
      ? (avgWin * wins.length) / (avgLoss * losses.length)
      : 0

    const maxDrawdown = equityCurve.length > 0
      ? Math.min(...equityCurve.map(d => d.drawdown || 0)) * 100
      : 0

    const startEquity = equityCurve[0]?.equity || params.initialCapital
    const endEquity = equityCurve[equityCurve.length - 1]?.equity || startEquity
    const totalReturn = ((endEquity - startEquity) / startEquity) * 100

    return {
      totalPnl,
      totalReturn,
      winRate,
      profitFactor,
      maxDrawdown,
      avgWin,
      avgLoss,
      totalTrades: trades.length,
      wins: wins.length,
      losses: losses.length,
    }
  }, [results, params.initialCapital])

  if (loading && !results) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="animate-spin text-cyan-400" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="text-cyan-400" />
            Backtest: {strategyName}
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            {params.startDate} to {params.endDate}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunBacktest}
            disabled={loading}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            Run Backtest
          </button>
          {results && onExport && (
            <button
              onClick={() => onExport(results)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <Download size={16} />
              Export
            </button>
          )}
        </div>
      </div>

      {/* Parameters */}
      <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Start Date</label>
            <input
              type="date"
              value={params.startDate}
              onChange={(e) => setParams({ ...params, startDate: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">End Date</label>
            <input
              type="date"
              value={params.endDate}
              onChange={(e) => setParams({ ...params, endDate: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Initial Capital ($)</label>
            <input
              type="number"
              value={params.initialCapital}
              onChange={(e) => setParams({ ...params, initialCapital: parseFloat(e.target.value) })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Position Size (%)</label>
            <input
              type="number"
              value={params.positionSize}
              onChange={(e) => setParams({ ...params, positionSize: parseFloat(e.target.value) })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 flex items-center gap-2">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {metrics && (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Total P&L"
              value={`$${metrics.totalPnl.toFixed(2)}`}
              subValue={`${metrics.totalReturn >= 0 ? '+' : ''}${metrics.totalReturn.toFixed(2)}%`}
              icon={DollarSign}
              color={metrics.totalPnl >= 0 ? 'green' : 'red'}
            />
            <MetricCard
              label="Win Rate"
              value={`${metrics.winRate.toFixed(1)}%`}
              subValue={`${metrics.wins}W / ${metrics.losses}L`}
              icon={Target}
              color={metrics.winRate >= 50 ? 'green' : 'yellow'}
            />
            <MetricCard
              label="Profit Factor"
              value={metrics.profitFactor.toFixed(2)}
              icon={BarChart3}
              color={metrics.profitFactor >= 1.5 ? 'green' : metrics.profitFactor >= 1 ? 'yellow' : 'red'}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${metrics.maxDrawdown.toFixed(1)}%`}
              icon={Shield}
              color={metrics.maxDrawdown > -15 ? 'green' : metrics.maxDrawdown > -30 ? 'yellow' : 'red'}
            />
          </div>

          {/* Tabs */}
          <div className="flex gap-2 border-b border-gray-700 pb-2">
            {['overview', 'trades', 'analysis'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-t-lg transition-colors capitalize ${
                  activeTab === tab
                    ? 'bg-gray-800 text-cyan-400 border-b-2 border-cyan-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Equity Curve */}
              <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Activity className="text-cyan-400" />
                  Equity Curve
                </h3>
                <EquityCurve data={results.equityCurve} height={250} />
              </div>

              {/* Drawdown */}
              <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
                  <TrendingDown className="text-red-400" />
                  Drawdown
                </h3>
                <DrawdownChart data={results.equityCurve} height={80} />
              </div>

              {/* Trade Distribution */}
              <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <BarChart3 className="text-purple-400" />
                  Trade Distribution
                </h3>
                <TradeDistribution trades={results.trades} />
              </div>
            </div>
          )}

          {activeTab === 'trades' && (
            <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
              <h3 className="text-lg font-semibold text-white mb-4">Trade History</h3>
              <TradeList trades={results.trades} />
            </div>
          )}

          {activeTab === 'analysis' && (
            <div className="grid md:grid-cols-2 gap-6">
              {/* Additional Metrics */}
              <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-lg font-semibold text-white mb-4">Performance Metrics</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Trades</span>
                    <span className="text-white">{metrics.totalTrades}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Average Win</span>
                    <span className="text-green-400">${metrics.avgWin.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Average Loss</span>
                    <span className="text-red-400">${metrics.avgLoss.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Expectancy</span>
                    <span className={metrics.totalPnl / metrics.totalTrades >= 0 ? 'text-green-400' : 'text-red-400'}>
                      ${(metrics.totalPnl / metrics.totalTrades).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Risk Metrics */}
              <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <h3 className="text-lg font-semibold text-white mb-4">Risk Metrics</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Max Drawdown</span>
                    <span className="text-red-400">{metrics.maxDrawdown.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk/Reward</span>
                    <span className="text-white">
                      1:{(metrics.avgWin / metrics.avgLoss).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Profit Factor</span>
                    <span className={metrics.profitFactor >= 1 ? 'text-green-400' : 'text-red-400'}>
                      {metrics.profitFactor.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {!results && !loading && (
        <div className="text-center py-16 text-gray-400">
          <BarChart3 size={48} className="mx-auto mb-4 opacity-50" />
          <p>No backtest results yet</p>
          <p className="text-sm text-gray-500 mt-1">Configure parameters and run a backtest</p>
        </div>
      )}
    </div>
  )
}
