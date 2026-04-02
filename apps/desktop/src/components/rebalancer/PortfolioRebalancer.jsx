import React, { useState, useMemo, useEffect } from 'react'
import {
  Scale,
  RefreshCw,
  Settings,
  TrendingUp,
  TrendingDown,
  DollarSign,
  PieChart,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  Plus,
  Minus,
  Target,
  Zap,
  Clock,
  BarChart3,
  Wallet,
  ArrowLeftRight,
  ChevronDown,
  ChevronUp,
  Edit3,
  Save,
  Trash2
} from 'lucide-react'

export function PortfolioRebalancer() {
  const [mode, setMode] = useState('overview') // overview, configure, preview, history
  const [rebalanceStrategy, setRebalanceStrategy] = useState('threshold')
  const [isEditing, setIsEditing] = useState(false)
  const [driftThreshold, setDriftThreshold] = useState(5)
  const [minTradeSize, setMinTradeSize] = useState(50)

  const strategies = [
    { id: 'threshold', name: 'Threshold', description: 'Rebalance when drift exceeds threshold' },
    { id: 'calendar', name: 'Calendar', description: 'Rebalance on fixed schedule' },
    { id: 'constant_mix', name: 'Constant Mix', description: 'Maintain exact target weights' },
    { id: 'tactical', name: 'Tactical', description: 'Adjust based on market conditions' }
  ]

  // Generate mock portfolio holdings
  const [holdings, setHoldings] = useState([
    { symbol: 'SOL', target: 30, icon: '◎' },
    { symbol: 'ETH', target: 25, icon: 'Ξ' },
    { symbol: 'BTC', target: 20, icon: '₿' },
    { symbol: 'BONK', target: 10, icon: '🦴' },
    { symbol: 'JUP', target: 8, icon: '♃' },
    { symbol: 'USDC', target: 7, icon: '$' }
  ])

  // Calculate current weights with drift
  const portfolioData = useMemo(() => {
    const totalValue = 50000 + Math.random() * 10000

    return holdings.map(holding => {
      const drift = (Math.random() - 0.5) * 10
      const current = Math.max(0, holding.target + drift)
      const value = totalValue * (current / 100)
      const price = Math.random() * 200 + 10
      const amount = value / price
      const change24h = (Math.random() - 0.5) * 20

      return {
        ...holding,
        current: current,
        value,
        price,
        amount,
        change24h,
        drift: current - holding.target,
        needsRebalance: Math.abs(current - holding.target) > driftThreshold
      }
    })
  }, [holdings, driftThreshold])

  const totalValue = portfolioData.reduce((sum, h) => sum + h.value, 0)
  const totalDrift = portfolioData.reduce((sum, h) => sum + Math.abs(h.drift), 0)
  const needsRebalance = portfolioData.some(h => h.needsRebalance)

  // Generate rebalance trades
  const rebalanceTrades = useMemo(() => {
    return portfolioData
      .filter(h => Math.abs(h.drift) > 1)
      .map(holding => {
        const targetValue = totalValue * (holding.target / 100)
        const tradeValue = targetValue - holding.value
        const tradeAmount = Math.abs(tradeValue / holding.price)

        return {
          symbol: holding.symbol,
          action: tradeValue > 0 ? 'buy' : 'sell',
          amount: tradeAmount,
          value: Math.abs(tradeValue),
          price: holding.price,
          fromWeight: holding.current.toFixed(2),
          toWeight: holding.target.toFixed(2),
          slippage: (Math.random() * 0.5).toFixed(2),
          fee: (Math.abs(tradeValue) * 0.001).toFixed(2)
        }
      })
      .filter(t => t.value > minTradeSize)
      .sort((a, b) => b.value - a.value)
  }, [portfolioData, totalValue, minTradeSize])

  // Rebalance history
  const rebalanceHistory = useMemo(() => {
    return Array.from({ length: 10 }, (_, i) => {
      const trades = Math.floor(Math.random() * 5) + 2
      const totalVolume = Math.floor(Math.random() * 5000) + 500
      const improvement = (Math.random() * 5 + 1).toFixed(2)

      return {
        id: i + 1,
        date: new Date(Date.now() - i * 7 * 24 * 60 * 60 * 1000).toLocaleDateString(),
        trades,
        totalVolume,
        improvement,
        trigger: ['Threshold', 'Calendar', 'Manual'][Math.floor(Math.random() * 3)],
        status: 'completed',
        gasCost: (Math.random() * 5 + 0.5).toFixed(2)
      }
    })
  }, [])

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  const formatNumber = (num) => {
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const handleTargetChange = (symbol, newTarget) => {
    setHoldings(holdings.map(h =>
      h.symbol === symbol ? { ...h, target: Math.max(0, Math.min(100, newTarget)) } : h
    ))
  }

  const totalTargetWeight = holdings.reduce((sum, h) => sum + h.target, 0)

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Scale className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold text-white">Portfolio Rebalancer</h2>
        </div>
        <div className="flex items-center gap-2">
          {needsRebalance && (
            <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 text-sm rounded-lg flex items-center gap-1">
              <AlertTriangle className="w-4 h-4" />
              Rebalance Needed
            </span>
          )}
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'configure', label: 'Configure' },
          { id: 'preview', label: 'Preview Trades' },
          { id: 'history', label: 'History' }
        ].map(m => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              mode === m.id
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Overview Mode */}
      {mode === 'overview' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Portfolio Value</div>
              <div className="text-2xl font-bold text-white">{formatCurrency(totalValue)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Total Drift</div>
              <div className={`text-2xl font-bold ${totalDrift > 10 ? 'text-yellow-400' : 'text-green-400'}`}>
                {totalDrift.toFixed(1)}%
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Assets</div>
              <div className="text-2xl font-bold text-white">{holdings.length}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Last Rebalance</div>
              <div className="text-xl font-bold text-white">3d ago</div>
            </div>
          </div>

          {/* Current Allocation */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <PieChart className="w-4 h-4 text-purple-400" />
              Current Allocation
            </h3>

            {/* Visual Bar */}
            <div className="h-8 rounded-lg overflow-hidden flex mb-4">
              {portfolioData.map((holding, i) => {
                const colors = ['bg-purple-500', 'bg-blue-500', 'bg-orange-500', 'bg-green-500', 'bg-pink-500', 'bg-cyan-500']
                return (
                  <div
                    key={holding.symbol}
                    className={`${colors[i % colors.length]} h-full relative group`}
                    style={{ width: `${holding.current}%` }}
                  >
                    <div className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white opacity-0 group-hover:opacity-100 transition-opacity">
                      {holding.symbol}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Holdings Table */}
            <div className="space-y-2">
              {portfolioData.map((holding, i) => {
                const colors = ['text-purple-400', 'text-blue-400', 'text-orange-400', 'text-green-400', 'text-pink-400', 'text-cyan-400']
                return (
                  <div key={holding.symbol} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-3">
                      <span className={`text-lg ${colors[i % colors.length]}`}>{holding.icon}</span>
                      <div>
                        <div className="text-white font-medium">{holding.symbol}</div>
                        <div className="text-xs text-gray-500">{formatNumber(holding.amount)} tokens</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white">{formatCurrency(holding.value)}</div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-gray-400">{holding.current.toFixed(1)}%</span>
                        <ArrowRight className="w-3 h-3 text-gray-600" />
                        <span className="text-gray-400">{holding.target}%</span>
                        <span className={Math.abs(holding.drift) > driftThreshold ? 'text-yellow-400' : 'text-green-400'}>
                          ({holding.drift >= 0 ? '+' : ''}{holding.drift.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => setMode('preview')}
              className="flex-1 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
            >
              <ArrowLeftRight className="w-5 h-5" />
              Preview Rebalance
            </button>
            <button
              onClick={() => setMode('configure')}
              className="px-6 py-3 bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 rounded-lg flex items-center gap-2 transition-colors"
            >
              <Settings className="w-5 h-5" />
              Configure
            </button>
          </div>
        </div>
      )}

      {/* Configure Mode */}
      {mode === 'configure' && (
        <div className="space-y-6">
          {/* Strategy Selection */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              Rebalance Strategy
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {strategies.map(strat => (
                <button
                  key={strat.id}
                  onClick={() => setRebalanceStrategy(strat.id)}
                  className={`p-3 rounded-lg text-left transition-colors ${
                    rebalanceStrategy === strat.id
                      ? 'bg-blue-500/20 border border-blue-500/30'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <div className={`font-medium text-sm ${rebalanceStrategy === strat.id ? 'text-blue-400' : 'text-white'}`}>
                    {strat.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{strat.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Settings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4">Thresholds</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Drift Threshold (%)</label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={driftThreshold}
                    onChange={(e) => setDriftThreshold(Number(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>1%</span>
                    <span className="text-white">{driftThreshold}%</span>
                    <span>20%</span>
                  </div>
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Min Trade Size ($)</label>
                  <input
                    type="number"
                    value={minTradeSize}
                    onChange={(e) => setMinTradeSize(Number(e.target.value))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
            </div>

            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4">Schedule</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Auto-Rebalance</label>
                  <select className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white">
                    <option value="manual">Manual Only</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Max Slippage (%)</label>
                  <input
                    type="number"
                    defaultValue={1}
                    step={0.1}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Target Weights */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-medium flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-green-400" />
                Target Weights
              </h3>
              <div className="flex items-center gap-2">
                <span className={`text-sm ${totalTargetWeight === 100 ? 'text-green-400' : 'text-yellow-400'}`}>
                  Total: {totalTargetWeight}%
                </span>
                <button
                  onClick={() => setIsEditing(!isEditing)}
                  className="p-2 bg-white/5 rounded-lg hover:bg-white/10"
                >
                  {isEditing ? <Save className="w-4 h-4 text-green-400" /> : <Edit3 className="w-4 h-4 text-gray-400" />}
                </button>
              </div>
            </div>
            <div className="space-y-3">
              {holdings.map((holding, i) => (
                <div key={holding.symbol} className="flex items-center gap-4">
                  <div className="w-20 text-white font-medium">{holding.symbol}</div>
                  <div className="flex-1">
                    <input
                      type="range"
                      min="0"
                      max="50"
                      value={holding.target}
                      onChange={(e) => handleTargetChange(holding.symbol, Number(e.target.value))}
                      disabled={!isEditing}
                      className="w-full"
                    />
                  </div>
                  <div className="w-16 text-right">
                    {isEditing ? (
                      <input
                        type="number"
                        value={holding.target}
                        onChange={(e) => handleTargetChange(holding.symbol, Number(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-white text-sm text-right"
                      />
                    ) : (
                      <span className="text-white">{holding.target}%</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {totalTargetWeight !== 100 && (
              <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-yellow-400 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Target weights must sum to 100%
              </div>
            )}
          </div>
        </div>
      )}

      {/* Preview Mode */}
      {mode === 'preview' && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Trades Required</div>
              <div className="text-2xl font-bold text-white">{rebalanceTrades.length}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Total Volume</div>
              <div className="text-2xl font-bold text-white">
                {formatCurrency(rebalanceTrades.reduce((sum, t) => sum + t.value, 0))}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Est. Fees</div>
              <div className="text-2xl font-bold text-white">
                ${rebalanceTrades.reduce((sum, t) => sum + parseFloat(t.fee), 0).toFixed(2)}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Drift Reduction</div>
              <div className="text-2xl font-bold text-green-400">-{totalDrift.toFixed(1)}%</div>
            </div>
          </div>

          {/* Trade List */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Proposed Trades</h3>
            <div className="space-y-3">
              {rebalanceTrades.length > 0 ? (
                rebalanceTrades.map((trade, i) => (
                  <div key={i} className="flex items-center justify-between p-4 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${trade.action === 'buy' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                        {trade.action === 'buy' ? (
                          <Plus className="w-5 h-5 text-green-400" />
                        ) : (
                          <Minus className="w-5 h-5 text-red-400" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${trade.action === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                            {trade.action.toUpperCase()}
                          </span>
                          <span className="text-white">{trade.symbol}</span>
                        </div>
                        <div className="text-sm text-gray-400">
                          {formatNumber(trade.amount)} @ ${trade.price.toFixed(2)}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white font-medium">{formatCurrency(trade.value)}</div>
                      <div className="text-xs text-gray-500">
                        {trade.fromWeight}% → {trade.toWeight}%
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-400" />
                  <div className="text-white font-medium">Portfolio is balanced</div>
                  <div className="text-sm">No trades needed at current threshold</div>
                </div>
              )}
            </div>
          </div>

          {/* Execute Button */}
          {rebalanceTrades.length > 0 && (
            <button className="w-full py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
              <Zap className="w-5 h-5" />
              Execute Rebalance
            </button>
          )}
        </div>
      )}

      {/* History Mode */}
      {mode === 'history' && (
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-gray-400 text-sm border-b border-white/10">
                  <th className="pb-3 pr-4">Date</th>
                  <th className="pb-3 pr-4">Trigger</th>
                  <th className="pb-3 pr-4">Trades</th>
                  <th className="pb-3 pr-4 text-right">Volume</th>
                  <th className="pb-3 pr-4 text-right">Gas</th>
                  <th className="pb-3 text-right">Improvement</th>
                </tr>
              </thead>
              <tbody>
                {rebalanceHistory.map(record => (
                  <tr key={record.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-3 pr-4 text-white">{record.date}</td>
                    <td className="py-3 pr-4">
                      <span className="px-2 py-1 bg-white/10 rounded text-xs text-gray-300">
                        {record.trigger}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-white">{record.trades}</td>
                    <td className="py-3 pr-4 text-right text-white">{formatCurrency(record.totalVolume)}</td>
                    <td className="py-3 pr-4 text-right text-gray-400">${record.gasCost}</td>
                    <td className="py-3 text-right text-green-400">-{record.improvement}% drift</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default PortfolioRebalancer
