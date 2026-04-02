import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  PieChart, RefreshCw, Settings, ArrowRight, Plus, Minus, Check,
  AlertTriangle, TrendingUp, TrendingDown, Wallet, Target, Percent,
  DollarSign, ChevronDown, ChevronUp, Sliders, ArrowUpRight,
  ArrowDownRight, Clock, Zap, Shield, Info, BarChart3, Activity
} from 'lucide-react'

// Supported assets
const ASSETS = [
  { symbol: 'BTC', name: 'Bitcoin', color: '#F7931A' },
  { symbol: 'ETH', name: 'Ethereum', color: '#627EEA' },
  { symbol: 'SOL', name: 'Solana', color: '#00FFA3' },
  { symbol: 'AVAX', name: 'Avalanche', color: '#E84142' },
  { symbol: 'MATIC', name: 'Polygon', color: '#8247E5' },
  { symbol: 'ARB', name: 'Arbitrum', color: '#28A0F0' },
  { symbol: 'OP', name: 'Optimism', color: '#FF0420' },
  { symbol: 'LINK', name: 'Chainlink', color: '#2A5ADA' },
  { symbol: 'UNI', name: 'Uniswap', color: '#FF007A' },
  { symbol: 'AAVE', name: 'Aave', color: '#B6509E' },
  { symbol: 'USDC', name: 'USD Coin', color: '#2775CA' },
  { symbol: 'USDT', name: 'Tether', color: '#50AF95' }
]

// Rebalancing strategies
const STRATEGIES = {
  THRESHOLD: { name: 'Threshold', description: 'Rebalance when deviation exceeds threshold' },
  PERIODIC: { name: 'Periodic', description: 'Rebalance at fixed intervals' },
  SMART: { name: 'Smart DCA', description: 'Buy dips, sell peaks with DCA' },
  MOMENTUM: { name: 'Momentum', description: 'Follow market momentum with weights' }
}

// Model portfolios
const MODEL_PORTFOLIOS = {
  CONSERVATIVE: {
    name: 'Conservative',
    description: 'Low risk, stable coins focus',
    allocation: { BTC: 30, ETH: 20, USDC: 30, USDT: 20 }
  },
  BALANCED: {
    name: 'Balanced',
    description: 'Mix of majors and stables',
    allocation: { BTC: 35, ETH: 30, SOL: 15, USDC: 20 }
  },
  GROWTH: {
    name: 'Growth',
    description: 'Higher risk, higher reward',
    allocation: { BTC: 30, ETH: 25, SOL: 20, ARB: 10, OP: 10, LINK: 5 }
  },
  DEFI: {
    name: 'DeFi Focus',
    description: 'DeFi tokens allocation',
    allocation: { ETH: 30, UNI: 20, AAVE: 20, LINK: 15, ARB: 15 }
  },
  CUSTOM: {
    name: 'Custom',
    description: 'Build your own allocation',
    allocation: {}
  }
}

// Generate mock portfolio
const generatePortfolio = () => {
  const assets = ASSETS.slice(0, 6 + Math.floor(Math.random() * 4))
  const totalValue = 50000 + Math.random() * 200000

  return assets.map(asset => {
    const allocation = Math.random() * 30 + 5
    const value = totalValue * (allocation / 100)
    const price = asset.symbol === 'BTC' ? 65000 + Math.random() * 5000 :
                  asset.symbol === 'ETH' ? 3500 + Math.random() * 500 :
                  asset.symbol === 'SOL' ? 150 + Math.random() * 30 :
                  asset.symbol.includes('USD') ? 1 :
                  Math.random() * 100 + 1
    const amount = value / price
    const change24h = (Math.random() - 0.5) * 20

    return {
      ...asset,
      amount,
      price,
      value,
      allocation,
      change24h
    }
  })
}

// Generate rebalance trades
const generateRebalanceTrades = (current, target) => {
  const trades = []
  const currentMap = {}
  current.forEach(a => { currentMap[a.symbol] = a })

  Object.entries(target).forEach(([symbol, targetAlloc]) => {
    const currentAsset = currentMap[symbol]
    const currentAlloc = currentAsset?.allocation || 0
    const diff = targetAlloc - currentAlloc

    if (Math.abs(diff) > 0.5) {
      const asset = ASSETS.find(a => a.symbol === symbol)
      const totalValue = current.reduce((sum, a) => sum + a.value, 0)
      const tradeValue = Math.abs(diff) * totalValue / 100
      const price = currentAsset?.price || (symbol === 'BTC' ? 65000 : symbol === 'ETH' ? 3500 : 100)

      trades.push({
        symbol,
        name: asset?.name || symbol,
        color: asset?.color || '#888',
        type: diff > 0 ? 'BUY' : 'SELL',
        currentAlloc,
        targetAlloc,
        diff: Math.abs(diff),
        value: tradeValue,
        amount: tradeValue / price,
        price,
        impact: (Math.random() * 0.5).toFixed(2)
      })
    }
  })

  return trades.sort((a, b) => b.value - a.value)
}

export function PortfolioRebalancer() {
  const [portfolio, setPortfolio] = useState([])
  const [selectedStrategy, setSelectedStrategy] = useState('THRESHOLD')
  const [selectedModel, setSelectedModel] = useState('BALANCED')
  const [targetAllocation, setTargetAllocation] = useState({})
  const [threshold, setThreshold] = useState(5)
  const [showTrades, setShowTrades] = useState(false)
  const [isRebalancing, setIsRebalancing] = useState(false)
  const [expandedSection, setExpandedSection] = useState('allocation')
  const [rebalanceHistory, setRebalanceHistory] = useState([])

  useEffect(() => {
    const initialPortfolio = generatePortfolio()
    setPortfolio(initialPortfolio)
    setTargetAllocation(MODEL_PORTFOLIOS[selectedModel].allocation)

    // Mock rebalance history
    setRebalanceHistory(Array.from({ length: 5 }, (_, i) => ({
      date: new Date(Date.now() - (i + 1) * 7 * 24 * 60 * 60 * 1000),
      tradesCount: Math.floor(Math.random() * 5) + 2,
      totalValue: (Math.random() * 5000 + 1000).toFixed(2),
      gasCost: (Math.random() * 50 + 10).toFixed(2),
      strategy: Object.keys(STRATEGIES)[Math.floor(Math.random() * 4)]
    })))
  }, [])

  useEffect(() => {
    if (selectedModel !== 'CUSTOM') {
      setTargetAllocation(MODEL_PORTFOLIOS[selectedModel].allocation)
    }
  }, [selectedModel])

  const totalValue = useMemo(() =>
    portfolio.reduce((sum, asset) => sum + asset.value, 0),
    [portfolio]
  )

  const totalChange = useMemo(() => {
    if (portfolio.length === 0) return 0
    return portfolio.reduce((sum, asset) => sum + (asset.change24h * asset.allocation / 100), 0)
  }, [portfolio])

  const deviation = useMemo(() => {
    let maxDev = 0
    portfolio.forEach(asset => {
      const target = targetAllocation[asset.symbol] || 0
      const diff = Math.abs(asset.allocation - target)
      if (diff > maxDev) maxDev = diff
    })
    return maxDev
  }, [portfolio, targetAllocation])

  const needsRebalance = deviation > threshold

  const trades = useMemo(() =>
    generateRebalanceTrades(portfolio, targetAllocation),
    [portfolio, targetAllocation]
  )

  const handleRebalance = useCallback(() => {
    setIsRebalancing(true)
    setTimeout(() => {
      // Apply target allocation
      const newPortfolio = portfolio.map(asset => ({
        ...asset,
        allocation: targetAllocation[asset.symbol] || asset.allocation,
        value: totalValue * ((targetAllocation[asset.symbol] || asset.allocation) / 100)
      }))
      setPortfolio(newPortfolio)
      setIsRebalancing(false)
      setShowTrades(false)

      // Add to history
      setRebalanceHistory(prev => [{
        date: new Date(),
        tradesCount: trades.length,
        totalValue: trades.reduce((sum, t) => sum + t.value, 0).toFixed(2),
        gasCost: (Math.random() * 50 + 10).toFixed(2),
        strategy: selectedStrategy
      }, ...prev.slice(0, 9)])
    }, 2000)
  }, [portfolio, targetAllocation, totalValue, trades, selectedStrategy])

  const updateTargetAllocation = (symbol, value) => {
    setTargetAllocation(prev => ({
      ...prev,
      [symbol]: parseFloat(value) || 0
    }))
    setSelectedModel('CUSTOM')
  }

  const totalTargetAllocation = Object.values(targetAllocation).reduce((sum, v) => sum + v, 0)

  const formatCurrency = (value) => {
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'
    if (value >= 1e3) return '$' + (value / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <PieChart className="w-8 h-8 text-cyan-400" />
          Portfolio Rebalancer
        </h1>
        <p className="text-white/60">Automated portfolio rebalancing with smart strategies</p>
      </div>

      {/* Portfolio Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <DollarSign className="w-4 h-4" />
            Total Value
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalValue)}</div>
          <div className={`flex items-center gap-1 text-sm ${totalChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalChange >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {totalChange >= 0 ? '+' : ''}{totalChange.toFixed(2)}% (24h)
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            Max Deviation
          </div>
          <div className={`text-2xl font-bold ${needsRebalance ? 'text-orange-400' : 'text-green-400'}`}>
            {deviation.toFixed(1)}%
          </div>
          <div className="text-sm text-white/60">
            Threshold: {threshold}%
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Wallet className="w-4 h-4" />
            Assets
          </div>
          <div className="text-2xl font-bold">{portfolio.length}</div>
          <div className="text-sm text-white/60">
            {Object.keys(targetAllocation).length} in target
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Sliders className="w-4 h-4" />
            Strategy
          </div>
          <div className="text-lg font-bold">{STRATEGIES[selectedStrategy].name}</div>
          <div className="text-sm text-white/60 truncate">
            {STRATEGIES[selectedStrategy].description}
          </div>
        </div>
      </div>

      {/* Rebalance Alert */}
      {needsRebalance && (
        <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-6 h-6 text-orange-400" />
              <div>
                <div className="font-medium text-orange-400">Rebalance Recommended</div>
                <div className="text-sm text-white/60">
                  Portfolio deviation ({deviation.toFixed(1)}%) exceeds threshold ({threshold}%)
                </div>
              </div>
            </div>
            <button
              onClick={() => setShowTrades(true)}
              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg font-medium transition-colors"
            >
              View Trades
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Current Allocation */}
        <div className="lg:col-span-2 bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          <button
            onClick={() => setExpandedSection(expandedSection === 'allocation' ? '' : 'allocation')}
            className="w-full p-4 flex items-center justify-between border-b border-white/10 hover:bg-white/5"
          >
            <h2 className="font-semibold flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              Current vs Target Allocation
            </h2>
            {expandedSection === 'allocation' ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>

          {expandedSection === 'allocation' && (
            <div className="p-4">
              <div className="space-y-4">
                {portfolio.map((asset, idx) => {
                  const target = targetAllocation[asset.symbol] || 0
                  const diff = asset.allocation - target

                  return (
                    <div key={idx} className="bg-white/5 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold"
                            style={{ backgroundColor: asset.color + '30', color: asset.color }}
                          >
                            {asset.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <div className="font-medium">{asset.name}</div>
                            <div className="text-sm text-white/60">{asset.symbol}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-medium">{formatCurrency(asset.value)}</div>
                          <div className={`text-sm ${asset.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                          </div>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-white/60">Current: {asset.allocation.toFixed(1)}%</span>
                          <span className="text-white/60">Target: {target.toFixed(1)}%</span>
                          <span className={diff > 0 ? 'text-red-400' : diff < 0 ? 'text-green-400' : 'text-white/60'}>
                            {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                          </span>
                        </div>
                        <div className="relative h-3 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="absolute h-full rounded-full transition-all"
                            style={{
                              width: `${asset.allocation}%`,
                              backgroundColor: asset.color
                            }}
                          />
                          <div
                            className="absolute h-full w-1 bg-white"
                            style={{ left: `${target}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Settings Panel */}
        <div className="space-y-6">
          {/* Strategy Selection */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-cyan-400" />
              Rebalancing Strategy
            </h3>
            <div className="space-y-2">
              {Object.entries(STRATEGIES).map(([key, strategy]) => (
                <button
                  key={key}
                  onClick={() => setSelectedStrategy(key)}
                  className={`w-full p-3 rounded-lg text-left transition-colors ${
                    selectedStrategy === key
                      ? 'bg-cyan-500/20 border border-cyan-500/30'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <div className="font-medium">{strategy.name}</div>
                  <div className="text-sm text-white/60">{strategy.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Model Portfolio */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-cyan-400" />
              Model Portfolio
            </h3>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:border-cyan-500/50"
            >
              {Object.entries(MODEL_PORTFOLIOS).map(([key, model]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">
                  {model.name}
                </option>
              ))}
            </select>
            <p className="text-sm text-white/60">
              {MODEL_PORTFOLIOS[selectedModel].description}
            </p>
          </div>

          {/* Threshold Setting */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4 flex items-center gap-2">
              <Percent className="w-5 h-5 text-cyan-400" />
              Rebalance Threshold
            </h3>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="1"
                max="20"
                value={threshold}
                onChange={(e) => setThreshold(parseInt(e.target.value))}
                className="flex-1"
              />
              <span className="w-12 text-center font-bold">{threshold}%</span>
            </div>
            <p className="text-sm text-white/60 mt-2">
              Trigger rebalance when any asset deviates by this amount
            </p>
          </div>
        </div>
      </div>

      {/* Target Allocation Editor */}
      <div className="mt-6 bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'target' ? '' : 'target')}
          className="w-full p-4 flex items-center justify-between border-b border-white/10 hover:bg-white/5"
        >
          <h2 className="font-semibold flex items-center gap-2">
            <Target className="w-5 h-5 text-cyan-400" />
            Edit Target Allocation
            <span className={`ml-2 text-sm ${totalTargetAllocation === 100 ? 'text-green-400' : 'text-orange-400'}`}>
              ({totalTargetAllocation.toFixed(1)}%)
            </span>
          </h2>
          {expandedSection === 'target' ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>

        {expandedSection === 'target' && (
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {ASSETS.map((asset, idx) => (
                <div key={idx} className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                      style={{ backgroundColor: asset.color + '30', color: asset.color }}
                    >
                      {asset.symbol.slice(0, 2)}
                    </div>
                    <span className="font-medium text-sm">{asset.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={targetAllocation[asset.symbol] || 0}
                      onChange={(e) => updateTargetAllocation(asset.symbol, e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500/50"
                    />
                    <span className="text-white/60 text-sm">%</span>
                  </div>
                </div>
              ))}
            </div>

            {totalTargetAllocation !== 100 && (
              <div className="mt-4 p-3 bg-orange-500/10 border border-orange-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-orange-400 text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  Total allocation must equal 100% (currently {totalTargetAllocation.toFixed(1)}%)
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Rebalance History */}
      <div className="mt-6 bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <div className="p-4 border-b border-white/10">
          <h2 className="font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5 text-cyan-400" />
            Rebalance History
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-4 text-white/60 font-medium">Date</th>
                <th className="text-left p-4 text-white/60 font-medium">Strategy</th>
                <th className="text-left p-4 text-white/60 font-medium">Trades</th>
                <th className="text-left p-4 text-white/60 font-medium">Volume</th>
                <th className="text-left p-4 text-white/60 font-medium">Gas Cost</th>
              </tr>
            </thead>
            <tbody>
              {rebalanceHistory.map((entry, idx) => (
                <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-4">{entry.date.toLocaleDateString()}</td>
                  <td className="p-4">{STRATEGIES[entry.strategy]?.name || entry.strategy}</td>
                  <td className="p-4">{entry.tradesCount}</td>
                  <td className="p-4">${entry.totalValue}</td>
                  <td className="p-4">${entry.gasCost}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trade Preview Modal */}
      {showTrades && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <ArrowRight className="w-6 h-6 text-cyan-400" />
                Rebalance Preview
              </h2>
              <button
                onClick={() => setShowTrades(false)}
                className="text-white/60 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="p-4 max-h-[60vh] overflow-y-auto">
              {trades.length === 0 ? (
                <div className="text-center py-8 text-white/60">
                  <Check className="w-12 h-12 mx-auto mb-4 text-green-400" />
                  Portfolio is balanced. No trades needed.
                </div>
              ) : (
                <div className="space-y-3">
                  {trades.map((trade, idx) => (
                    <div key={idx} className="bg-white/5 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              trade.type === 'BUY' ? 'bg-green-500/20' : 'bg-red-500/20'
                            }`}
                          >
                            {trade.type === 'BUY' ? (
                              <ArrowUpRight className="w-5 h-5 text-green-400" />
                            ) : (
                              <ArrowDownRight className="w-5 h-5 text-red-400" />
                            )}
                          </div>
                          <div>
                            <div className="font-medium">
                              {trade.type} {trade.symbol}
                            </div>
                            <div className="text-sm text-white/60">{trade.name}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-medium">{formatCurrency(trade.value)}</div>
                          <div className="text-sm text-white/60">
                            {trade.amount.toFixed(4)} {trade.symbol}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-sm text-white/60">
                        <span>{trade.currentAlloc.toFixed(1)}% → {trade.targetAlloc.toFixed(1)}%</span>
                        <span>Est. slippage: {trade.impact}%</span>
                      </div>
                    </div>
                  ))}

                  <div className="bg-white/5 rounded-lg p-4 mt-4">
                    <div className="flex justify-between mb-2">
                      <span className="text-white/60">Total Trades</span>
                      <span>{trades.length}</span>
                    </div>
                    <div className="flex justify-between mb-2">
                      <span className="text-white/60">Total Volume</span>
                      <span>{formatCurrency(trades.reduce((sum, t) => sum + t.value, 0))}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Est. Gas</span>
                      <span>${(trades.length * 15).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-white/10 flex gap-3">
              <button
                onClick={() => setShowTrades(false)}
                className="flex-1 px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleRebalance}
                disabled={isRebalancing || trades.length === 0}
                className="flex-1 px-4 py-3 bg-cyan-500 hover:bg-cyan-600 disabled:bg-white/10 disabled:cursor-not-allowed rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
              >
                {isRebalancing ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Rebalancing...
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    Execute Rebalance
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Info Banner */}
      <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <div className="font-medium text-white mb-1">How Rebalancing Works</div>
            <p>
              Portfolio rebalancing automatically adjusts your holdings to maintain your target allocation.
              When asset prices change, your portfolio drifts from targets. Rebalancing sells overweight
              assets and buys underweight ones to restore balance and manage risk.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PortfolioRebalancer
