import React, { useState, useMemo } from 'react'
import {
  PieChart,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Wallet,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Plus,
  Minus,
  RefreshCw,
  Settings,
  Eye,
  EyeOff,
  Clock,
  Target,
  AlertTriangle,
  ChevronRight,
  Layers,
  Activity
} from 'lucide-react'

export function PortfolioTracker() {
  const [viewMode, setViewMode] = useState('overview') // overview, holdings, performance, allocation
  const [showBalances, setShowBalances] = useState(true)
  const [timeRange, setTimeRange] = useState('24h')

  const timeRanges = ['24h', '7d', '30d', '90d', '1y', 'all']

  // Mock portfolio data
  const holdings = useMemo(() => [
    { token: 'SOL', amount: 125.5, avgCost: 98.50, currentPrice: 148.75, allocation: 35 },
    { token: 'BTC', amount: 0.85, avgCost: 42000, currentPrice: 67500, allocation: 25 },
    { token: 'ETH', amount: 12.3, avgCost: 1850, currentPrice: 2450, allocation: 15 },
    { token: 'JUP', amount: 15000, avgCost: 0.65, currentPrice: 0.95, allocation: 8 },
    { token: 'BONK', amount: 500000000, avgCost: 0.000012, currentPrice: 0.000025, allocation: 6 },
    { token: 'RNDR', amount: 500, avgCost: 5.50, currentPrice: 8.20, allocation: 5 },
    { token: 'WIF', amount: 2500, avgCost: 1.25, currentPrice: 2.85, allocation: 4 },
    { token: 'PYTH', amount: 10000, avgCost: 0.28, currentPrice: 0.42, allocation: 2 }
  ].map(h => {
    const value = h.amount * h.currentPrice
    const cost = h.amount * h.avgCost
    const pnl = value - cost
    const pnlPercent = (pnl / cost) * 100
    return { ...h, value, cost, pnl, pnlPercent }
  }), [])

  // Total portfolio stats
  const portfolioStats = useMemo(() => {
    const totalValue = holdings.reduce((sum, h) => sum + h.value, 0)
    const totalCost = holdings.reduce((sum, h) => sum + h.cost, 0)
    const totalPnl = totalValue - totalCost
    const totalPnlPercent = (totalPnl / totalCost) * 100

    // Performance by time period
    const performance = {
      '24h': { value: 1250, percent: 1.8 },
      '7d': { value: 8500, percent: 12.5 },
      '30d': { value: -2100, percent: -2.8 },
      '90d': { value: 25000, percent: 42.5 },
      '1y': { value: 45000, percent: 85.2 },
      'all': { value: 52000, percent: 102.5 }
    }

    return { totalValue, totalCost, totalPnl, totalPnlPercent, performance }
  }, [holdings])

  // Historical data for chart
  const historicalData = useMemo(() => {
    const data = []
    let value = portfolioStats.totalValue * 0.7
    for (let i = 30; i >= 0; i--) {
      value = value * (1 + (Math.random() - 0.45) * 0.05)
      data.push({
        day: i === 0 ? 'Today' : `-${i}d`,
        value,
        change: (Math.random() - 0.5) * 5
      })
    }
    return data
  }, [portfolioStats.totalValue])

  // Top performers / losers
  const sortedByPnl = [...holdings].sort((a, b) => b.pnlPercent - a.pnlPercent)
  const topPerformers = sortedByPnl.slice(0, 3)
  const worstPerformers = sortedByPnl.slice(-3).reverse()

  const formatValue = (value) => {
    if (!showBalances) return '****'
    if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
    if (value >= 1000) return `$${(value / 1000).toFixed(2)}K`
    return `$${value.toFixed(2)}`
  }

  const allocationColors = [
    'bg-blue-500', 'bg-purple-500', 'bg-green-500', 'bg-yellow-500',
    'bg-orange-500', 'bg-pink-500', 'bg-cyan-500', 'bg-red-500'
  ]

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Wallet className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Portfolio Tracker</h1>
            <p className="text-white/60 text-sm">Track holdings, P&L, and allocation</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Show/Hide Balances */}
          <button
            onClick={() => setShowBalances(!showBalances)}
            className="p-2 bg-white/5 rounded-lg hover:bg-white/10"
          >
            {showBalances ? (
              <Eye className="w-5 h-5 text-white/60" />
            ) : (
              <EyeOff className="w-5 h-5 text-white/60" />
            )}
          </button>

          {/* Time Range */}
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {timeRanges.map(range => (
              <option key={range} value={range}>{range}</option>
            ))}
          </select>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['overview', 'holdings', 'performance', 'allocation'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-blue-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Portfolio Value Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-blue-400" />
            <span className="text-white/60 text-sm">Total Value</span>
          </div>
          <p className="text-2xl font-bold">{formatValue(portfolioStats.totalValue)}</p>
          <p className={`text-sm mt-1 ${
            portfolioStats.performance[timeRange].percent >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {portfolioStats.performance[timeRange].percent >= 0 ? '+' : ''}
            {portfolioStats.performance[timeRange].percent.toFixed(2)}% ({timeRange})
          </p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">Total P&L</span>
          </div>
          <p className={`text-2xl font-bold ${portfolioStats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {portfolioStats.totalPnl >= 0 ? '+' : ''}{formatValue(Math.abs(portfolioStats.totalPnl))}
          </p>
          <p className={`text-sm mt-1 ${portfolioStats.totalPnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {portfolioStats.totalPnlPercent >= 0 ? '+' : ''}{portfolioStats.totalPnlPercent.toFixed(2)}%
          </p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Layers className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Holdings</span>
          </div>
          <p className="text-2xl font-bold">{holdings.length}</p>
          <p className="text-sm mt-1 text-white/60">Assets tracked</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">Best Performer</span>
          </div>
          <p className="text-2xl font-bold">{topPerformers[0]?.token}</p>
          <p className="text-sm mt-1 text-green-400">
            +{topPerformers[0]?.pnlPercent.toFixed(2)}%
          </p>
        </div>
      </div>

      {viewMode === 'overview' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Portfolio Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-400" />
              Portfolio Value
            </h2>

            <div className="h-64 flex items-end gap-1">
              {historicalData.map((d, idx) => {
                const maxVal = Math.max(...historicalData.map(h => h.value))
                const height = (d.value / maxVal) * 100

                return (
                  <div
                    key={idx}
                    className="flex-1 flex flex-col items-center justify-end"
                  >
                    <div
                      className={`w-full rounded-t ${d.change >= 0 ? 'bg-blue-500' : 'bg-blue-500/50'}`}
                      style={{ height: `${height}%` }}
                    />
                  </div>
                )
              })}
            </div>

            <div className="flex justify-between mt-2 text-xs text-white/40">
              <span>-30d</span>
              <span>Today</span>
            </div>
          </div>

          {/* Top/Worst Performers */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                Top Performers
              </h3>

              <div className="space-y-2">
                {topPerformers.map(h => (
                  <div key={h.token} className="flex items-center justify-between p-2 bg-green-500/10 rounded-lg">
                    <span className="font-medium">{h.token}</span>
                    <span className="text-green-400">+{h.pnlPercent.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-400" />
                Underperformers
              </h3>

              <div className="space-y-2">
                {worstPerformers.map(h => (
                  <div key={h.token} className="flex items-center justify-between p-2 bg-red-500/10 rounded-lg">
                    <span className="font-medium">{h.token}</span>
                    <span className={h.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {h.pnlPercent >= 0 ? '+' : ''}{h.pnlPercent.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'holdings' && (
        <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Asset</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Holdings</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Avg Cost</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Current Price</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Value</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">P&L</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">P&L %</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Allocation</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, idx) => (
                <tr key={h.token} className={`border-b border-white/5 hover:bg-white/5 ${idx % 2 === 0 ? 'bg-white/[0.02]' : ''}`}>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${allocationColors[idx % allocationColors.length]}`} />
                      <span className="font-medium">{h.token}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    {showBalances ? h.amount.toLocaleString() : '****'}
                  </td>
                  <td className="py-3 px-4 text-right text-white/60">
                    ${h.avgCost.toLocaleString()}
                  </td>
                  <td className="py-3 px-4 text-right font-medium">
                    ${h.currentPrice.toLocaleString()}
                  </td>
                  <td className="py-3 px-4 text-right font-medium">
                    {formatValue(h.value)}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={h.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {h.pnl >= 0 ? '+' : ''}{formatValue(Math.abs(h.pnl))}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-medium ${h.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {h.pnlPercent >= 0 ? '+' : ''}{h.pnlPercent.toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-16 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${allocationColors[idx % allocationColors.length]}`}
                          style={{ width: `${h.allocation}%` }}
                        />
                      </div>
                      <span className="text-xs text-white/60">{h.allocation}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-white/5">
                <td className="py-3 px-4 font-semibold" colSpan={4}>Total</td>
                <td className="py-3 px-4 text-right font-bold">{formatValue(portfolioStats.totalValue)}</td>
                <td className="py-3 px-4 text-right">
                  <span className={`font-bold ${portfolioStats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {portfolioStats.totalPnl >= 0 ? '+' : ''}{formatValue(Math.abs(portfolioStats.totalPnl))}
                  </span>
                </td>
                <td className="py-3 px-4 text-right">
                  <span className={`font-bold ${portfolioStats.totalPnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {portfolioStats.totalPnlPercent >= 0 ? '+' : ''}{portfolioStats.totalPnlPercent.toFixed(2)}%
                  </span>
                </td>
                <td className="py-3 px-4 text-center text-white/60">100%</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {viewMode === 'performance' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Performance by Time Period */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-purple-400" />
              Performance by Period
            </h2>

            <div className="grid grid-cols-3 gap-4">
              {Object.entries(portfolioStats.performance).map(([period, data]) => (
                <div
                  key={period}
                  className={`p-4 rounded-xl border ${
                    data.percent >= 0
                      ? 'bg-green-500/10 border-green-500/30'
                      : 'bg-red-500/10 border-red-500/30'
                  }`}
                >
                  <p className="text-white/60 text-sm mb-1">{period}</p>
                  <p className={`text-xl font-bold ${data.percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {data.percent >= 0 ? '+' : ''}{data.percent.toFixed(2)}%
                  </p>
                  <p className={`text-sm ${data.percent >= 0 ? 'text-green-400/60' : 'text-red-400/60'}`}>
                    {data.value >= 0 ? '+' : ''}${Math.abs(data.value).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>

            {/* Performance Chart */}
            <div className="mt-6 h-48 flex items-end gap-2">
              {Object.entries(portfolioStats.performance).map(([period, data], idx) => {
                const maxPercent = Math.max(...Object.values(portfolioStats.performance).map(p => Math.abs(p.percent)))
                const height = (Math.abs(data.percent) / maxPercent) * 100

                return (
                  <div key={period} className="flex-1 flex flex-col items-center">
                    <div
                      className={`w-full rounded-t ${
                        data.percent >= 0 ? 'bg-green-500' : 'bg-red-500'
                      }`}
                      style={{ height: `${height}%` }}
                    />
                    <span className="text-xs text-white/60 mt-2">{period}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Stats */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-yellow-400" />
                Key Metrics
              </h3>

              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-white/60">Total Invested</span>
                  <span className="font-medium">{formatValue(portfolioStats.totalCost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Current Value</span>
                  <span className="font-medium">{formatValue(portfolioStats.totalValue)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">All-Time P&L</span>
                  <span className={`font-medium ${portfolioStats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {portfolioStats.totalPnl >= 0 ? '+' : ''}{formatValue(Math.abs(portfolioStats.totalPnl))}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">ROI</span>
                  <span className={`font-medium ${portfolioStats.totalPnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {portfolioStats.totalPnlPercent >= 0 ? '+' : ''}{portfolioStats.totalPnlPercent.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-400" />
                Risk Metrics
              </h3>

              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-white/60">Max Drawdown</span>
                  <span className="text-red-400 font-medium">-18.5%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Volatility (30d)</span>
                  <span className="font-medium">24.3%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Sharpe Ratio</span>
                  <span className="font-medium">1.85</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Win Rate</span>
                  <span className="text-green-400 font-medium">68%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'allocation' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Pie Chart Visualization */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <PieChart className="w-5 h-5 text-blue-400" />
              Portfolio Allocation
            </h2>

            <div className="flex items-center gap-8">
              {/* Pie Chart */}
              <div className="relative w-64 h-64">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  {holdings.reduce((acc, h, idx) => {
                    const startAngle = acc.angle
                    const sweepAngle = (h.allocation / 100) * 360
                    const endAngle = startAngle + sweepAngle

                    const startX = 50 + 40 * Math.cos((startAngle * Math.PI) / 180)
                    const startY = 50 + 40 * Math.sin((startAngle * Math.PI) / 180)
                    const endX = 50 + 40 * Math.cos((endAngle * Math.PI) / 180)
                    const endY = 50 + 40 * Math.sin((endAngle * Math.PI) / 180)

                    const largeArc = sweepAngle > 180 ? 1 : 0

                    const colors = ['#3b82f6', '#8b5cf6', '#22c55e', '#eab308', '#f97316', '#ec4899', '#06b6d4', '#ef4444']

                    acc.paths.push(
                      <path
                        key={h.token}
                        d={`M 50 50 L ${startX} ${startY} A 40 40 0 ${largeArc} 1 ${endX} ${endY} Z`}
                        fill={colors[idx % colors.length]}
                        opacity={0.8}
                        className="hover:opacity-100 transition-opacity cursor-pointer"
                      />
                    )

                    return { angle: endAngle, paths: acc.paths }
                  }, { angle: 0, paths: [] }).paths}
                </svg>
                <div className="absolute inset-0 flex items-center justify-center flex-col">
                  <p className="text-2xl font-bold">{holdings.length}</p>
                  <p className="text-white/60 text-sm">Assets</p>
                </div>
              </div>

              {/* Legend */}
              <div className="flex-1 space-y-2">
                {holdings.map((h, idx) => (
                  <div key={h.token} className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${allocationColors[idx % allocationColors.length]}`} />
                    <span className="flex-1 font-medium">{h.token}</span>
                    <span className="text-white/60">{h.allocation}%</span>
                    <span className="text-white/40">{formatValue(h.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Allocation Recommendations */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Settings className="w-4 h-4 text-cyan-400" />
                Allocation Analysis
              </h3>

              <div className="space-y-3">
                <div className="p-3 bg-blue-500/10 rounded-lg">
                  <p className="text-blue-400 font-medium">SOL Heavy (35%)</p>
                  <p className="text-white/60 text-xs mt-1">Consider diversifying if risk-averse</p>
                </div>
                <div className="p-3 bg-green-500/10 rounded-lg">
                  <p className="text-green-400 font-medium">Good BTC Exposure (25%)</p>
                  <p className="text-white/60 text-xs mt-1">Solid foundation asset</p>
                </div>
                <div className="p-3 bg-yellow-500/10 rounded-lg">
                  <p className="text-yellow-400 font-medium">Meme Exposure (10%)</p>
                  <p className="text-white/60 text-xs mt-1">Appropriate speculative allocation</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-purple-400" />
                Rebalancing Suggestions
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Consider taking profits on BONK (+108%)</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>SOL position may need trimming</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Consider adding stablecoins for dry powder</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PortfolioTracker
