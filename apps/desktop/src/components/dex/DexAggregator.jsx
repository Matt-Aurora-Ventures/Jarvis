import React, { useState, useMemo, useEffect } from 'react'
import {
  Layers,
  ArrowDown,
  ArrowRight,
  Settings,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
  Clock,
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Search,
  Star,
  ExternalLink,
  Info,
  Wallet,
  Route,
  BarChart3,
  Shield
} from 'lucide-react'

export function DexAggregator() {
  const [fromToken, setFromToken] = useState('SOL')
  const [toToken, setToToken] = useState('USDC')
  const [amount, setAmount] = useState('1')
  const [slippage, setSlippage] = useState(0.5)
  const [showSettings, setShowSettings] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedRoute, setSelectedRoute] = useState(0)
  const [viewMode, setViewMode] = useState('swap') // swap, routes, analytics

  const tokens = [
    { symbol: 'SOL', name: 'Solana', price: 178.50, balance: 45.32 },
    { symbol: 'ETH', name: 'Ethereum', price: 3456.00, balance: 2.15 },
    { symbol: 'USDC', name: 'USD Coin', price: 1.00, balance: 5000.00 },
    { symbol: 'USDT', name: 'Tether', price: 1.00, balance: 2500.00 },
    { symbol: 'BONK', name: 'Bonk', price: 0.000025, balance: 15000000 },
    { symbol: 'WIF', name: 'dogwifhat', price: 2.85, balance: 500 },
    { symbol: 'JUP', name: 'Jupiter', price: 1.25, balance: 1000 },
    { symbol: 'RAY', name: 'Raydium', price: 4.50, balance: 200 },
    { symbol: 'ORCA', name: 'Orca', price: 3.20, balance: 150 },
    { symbol: 'PYTH', name: 'Pyth', price: 0.45, balance: 3000 }
  ]

  const dexes = [
    { id: 'jupiter', name: 'Jupiter', icon: '♃', color: 'text-green-400' },
    { id: 'raydium', name: 'Raydium', icon: '⚡', color: 'text-purple-400' },
    { id: 'orca', name: 'Orca', icon: '🐋', color: 'text-blue-400' },
    { id: 'meteora', name: 'Meteora', icon: '☄️', color: 'text-orange-400' },
    { id: 'phoenix', name: 'Phoenix', icon: '🔥', color: 'text-red-400' },
    { id: 'lifinity', name: 'Lifinity', icon: '∞', color: 'text-cyan-400' }
  ]

  const fromTokenData = tokens.find(t => t.symbol === fromToken) || tokens[0]
  const toTokenData = tokens.find(t => t.symbol === toToken) || tokens[2]

  // Generate mock routes
  const routes = useMemo(() => {
    const inputAmount = parseFloat(amount) || 0
    const inputValue = inputAmount * fromTokenData.price
    const baseOutput = inputValue / toTokenData.price

    return [
      {
        id: 1,
        name: 'Best Route',
        dexes: ['Jupiter'],
        hops: 1,
        outputAmount: baseOutput * 0.9995,
        priceImpact: 0.05 + Math.random() * 0.1,
        fee: inputValue * 0.003,
        estimatedGas: 0.00025,
        executionTime: '~5s',
        isBest: true
      },
      {
        id: 2,
        name: 'Split Route',
        dexes: ['Jupiter', 'Raydium'],
        hops: 2,
        outputAmount: baseOutput * 0.998,
        priceImpact: 0.08 + Math.random() * 0.1,
        fee: inputValue * 0.0035,
        estimatedGas: 0.00035,
        executionTime: '~8s',
        isBest: false
      },
      {
        id: 3,
        name: 'Raydium Direct',
        dexes: ['Raydium'],
        hops: 1,
        outputAmount: baseOutput * 0.996,
        priceImpact: 0.12 + Math.random() * 0.15,
        fee: inputValue * 0.0025,
        estimatedGas: 0.0002,
        executionTime: '~4s',
        isBest: false
      },
      {
        id: 4,
        name: 'Multi-Hop',
        dexes: ['Orca', 'Meteora'],
        hops: 3,
        outputAmount: baseOutput * 0.994,
        priceImpact: 0.15 + Math.random() * 0.2,
        fee: inputValue * 0.004,
        estimatedGas: 0.00045,
        executionTime: '~12s',
        isBest: false
      }
    ].map(route => ({
      ...route,
      outputValue: route.outputAmount * toTokenData.price,
      savings: (route.outputAmount - baseOutput * 0.99) * toTokenData.price
    }))
  }, [amount, fromToken, toToken, fromTokenData, toTokenData])

  // Analytics data
  const analyticsData = useMemo(() => ({
    totalVolume24h: 125000000 + Math.random() * 50000000,
    totalTrades24h: 45000 + Math.floor(Math.random() * 10000),
    avgSavings: 0.15 + Math.random() * 0.1,
    topPairs: [
      { pair: 'SOL/USDC', volume: 45000000, trades: 15000 },
      { pair: 'ETH/USDC', volume: 32000000, trades: 8000 },
      { pair: 'BONK/SOL', volume: 18000000, trades: 12000 },
      { pair: 'JUP/SOL', volume: 12000000, trades: 5000 },
      { pair: 'WIF/SOL', volume: 8000000, trades: 4000 }
    ],
    dexVolume: dexes.map(dex => ({
      name: dex.name,
      volume: Math.random() * 50000000,
      marketShare: Math.random() * 30
    })).sort((a, b) => b.volume - a.volume)
  }), [])

  const handleSwap = () => {
    setIsLoading(true)
    setTimeout(() => {
      setIsLoading(false)
      // Would execute swap
    }, 2000)
  }

  const handleSwapTokens = () => {
    const temp = fromToken
    setFromToken(toToken)
    setToToken(temp)
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(4)
  }

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Layers className="w-6 h-6 text-green-400" />
          <h2 className="text-xl font-bold text-white">DEX Aggregator</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg transition-colors ${showSettings ? 'bg-white/10' : 'bg-white/5 hover:bg-white/10'}`}
          >
            <Settings className="w-5 h-5 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'swap', label: 'Swap' },
          { id: 'routes', label: 'Routes' },
          { id: 'analytics', label: 'Analytics' }
        ].map(m => (
          <button
            key={m.id}
            onClick={() => setViewMode(m.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === m.id
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="mb-6 p-4 bg-white/5 rounded-lg border border-white/10">
          <h3 className="text-white font-medium mb-4">Swap Settings</h3>
          <div className="space-y-4">
            <div>
              <label className="text-gray-400 text-sm block mb-2">Slippage Tolerance</label>
              <div className="flex gap-2">
                {[0.1, 0.5, 1.0, 3.0].map(s => (
                  <button
                    key={s}
                    onClick={() => setSlippage(s)}
                    className={`px-3 py-1.5 rounded text-sm ${
                      slippage === s
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-white/5 text-gray-400 hover:bg-white/10'
                    }`}
                  >
                    {s}%
                  </button>
                ))}
                <input
                  type="number"
                  value={slippage}
                  onChange={(e) => setSlippage(Number(e.target.value))}
                  className="w-20 bg-white/5 border border-white/10 rounded px-2 py-1.5 text-white text-sm"
                  step={0.1}
                />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-gray-400 text-sm">
                <input type="checkbox" className="rounded bg-white/10" defaultChecked />
                Auto-route optimization
              </label>
              <label className="flex items-center gap-2 text-gray-400 text-sm">
                <input type="checkbox" className="rounded bg-white/10" defaultChecked />
                MEV protection
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Swap Mode */}
      {viewMode === 'swap' && (
        <div className="space-y-4">
          {/* From Token */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="flex justify-between mb-2">
              <span className="text-gray-400 text-sm">From</span>
              <span className="text-gray-400 text-sm">
                Balance: {formatNumber(fromTokenData.balance)} {fromToken}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="flex-1 bg-transparent text-2xl font-medium text-white outline-none"
                placeholder="0.0"
              />
              <select
                value={fromToken}
                onChange={(e) => setFromToken(e.target.value)}
                className="bg-white/10 border border-white/10 rounded-lg px-4 py-2 text-white font-medium"
              >
                {tokens.map(t => (
                  <option key={t.symbol} value={t.symbol}>{t.symbol}</option>
                ))}
              </select>
            </div>
            <div className="text-gray-500 text-sm mt-1">
              ~{formatCurrency(parseFloat(amount || 0) * fromTokenData.price)}
            </div>
          </div>

          {/* Swap Button */}
          <div className="flex justify-center -my-2 z-10 relative">
            <button
              onClick={handleSwapTokens}
              className="p-2 bg-white/10 rounded-full border border-white/10 hover:bg-white/20 transition-colors"
            >
              <ArrowDown className="w-5 h-5 text-white" />
            </button>
          </div>

          {/* To Token */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="flex justify-between mb-2">
              <span className="text-gray-400 text-sm">To</span>
              <span className="text-gray-400 text-sm">
                Balance: {formatNumber(toTokenData.balance)} {toToken}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="text-2xl font-medium text-white">
                  {routes[selectedRoute]?.outputAmount.toFixed(4) || '0.0'}
                </div>
              </div>
              <select
                value={toToken}
                onChange={(e) => setToToken(e.target.value)}
                className="bg-white/10 border border-white/10 rounded-lg px-4 py-2 text-white font-medium"
              >
                {tokens.map(t => (
                  <option key={t.symbol} value={t.symbol}>{t.symbol}</option>
                ))}
              </select>
            </div>
            <div className="text-gray-500 text-sm mt-1">
              ~{formatCurrency(routes[selectedRoute]?.outputValue || 0)}
            </div>
          </div>

          {/* Route Info */}
          {routes[selectedRoute] && parseFloat(amount) > 0 && (
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center justify-between mb-3">
                <span className="text-gray-400 text-sm">Best Route</span>
                <button
                  onClick={() => setViewMode('routes')}
                  className="text-green-400 text-sm hover:underline"
                >
                  View all routes
                </button>
              </div>
              <div className="flex items-center gap-2 mb-3">
                {routes[selectedRoute].dexes.map((dex, i) => (
                  <React.Fragment key={dex}>
                    <span className="px-2 py-1 bg-white/10 rounded text-sm text-white">{dex}</span>
                    {i < routes[selectedRoute].dexes.length - 1 && (
                      <ArrowRight className="w-4 h-4 text-gray-500" />
                    )}
                  </React.Fragment>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-gray-400">Price Impact</div>
                  <div className={routes[selectedRoute].priceImpact > 1 ? 'text-red-400' : 'text-green-400'}>
                    {routes[selectedRoute].priceImpact.toFixed(2)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Fees</div>
                  <div className="text-white">{formatCurrency(routes[selectedRoute].fee)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Est. Time</div>
                  <div className="text-white">{routes[selectedRoute].executionTime}</div>
                </div>
              </div>
            </div>
          )}

          {/* Rate Info */}
          {parseFloat(amount) > 0 && (
            <div className="flex justify-between text-sm text-gray-400 px-2">
              <span>Rate</span>
              <span>1 {fromToken} = {(toTokenData.price ? fromTokenData.price / toTokenData.price : 0).toFixed(4)} {toToken}</span>
            </div>
          )}

          {/* Swap Button */}
          <button
            onClick={handleSwap}
            disabled={!amount || parseFloat(amount) <= 0 || isLoading}
            className={`w-full py-4 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
              !amount || parseFloat(amount) <= 0
                ? 'bg-white/5 text-gray-500 cursor-not-allowed'
                : isLoading
                ? 'bg-green-500/50 text-white'
                : 'bg-green-500 hover:bg-green-600 text-white'
            }`}
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                Swapping...
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                Swap
              </>
            )}
          </button>
        </div>
      )}

      {/* Routes Mode */}
      {viewMode === 'routes' && (
        <div className="space-y-4">
          {/* Input Summary */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10 flex items-center justify-between">
            <div>
              <span className="text-gray-400 text-sm">Swapping</span>
              <div className="text-white font-medium">
                {amount || '0'} {fromToken} → {toToken}
              </div>
            </div>
            <button
              onClick={() => setViewMode('swap')}
              className="px-3 py-1.5 bg-white/5 text-gray-400 rounded-lg text-sm hover:bg-white/10"
            >
              Edit
            </button>
          </div>

          {/* Routes List */}
          <div className="space-y-3">
            {routes.map((route, i) => (
              <div
                key={route.id}
                onClick={() => setSelectedRoute(i)}
                className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                  selectedRoute === i
                    ? 'bg-green-500/10 border-green-500/30'
                    : 'bg-white/5 border-white/10 hover:bg-white/10'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {route.isBest && (
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                        BEST
                      </span>
                    )}
                    <span className="text-white font-medium">{route.name}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-white font-medium">{formatNumber(route.outputAmount)} {toToken}</div>
                    <div className="text-gray-500 text-xs">{formatCurrency(route.outputValue)}</div>
                  </div>
                </div>

                {/* Route Path */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm text-gray-400">{fromToken}</span>
                  {route.dexes.map((dex, j) => (
                    <React.Fragment key={j}>
                      <ArrowRight className="w-3 h-3 text-gray-600" />
                      <span className="px-2 py-1 bg-white/10 rounded text-xs text-white">{dex}</span>
                    </React.Fragment>
                  ))}
                  <ArrowRight className="w-3 h-3 text-gray-600" />
                  <span className="text-sm text-gray-400">{toToken}</span>
                </div>

                {/* Route Details */}
                <div className="grid grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="text-gray-500">Impact</div>
                    <div className={route.priceImpact > 1 ? 'text-red-400' : 'text-white'}>
                      {route.priceImpact.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Fees</div>
                    <div className="text-white">${route.fee.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Gas</div>
                    <div className="text-white">{route.estimatedGas} SOL</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Time</div>
                    <div className="text-white">{route.executionTime}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Execute Button */}
          <button
            onClick={handleSwap}
            className="w-full py-4 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
          >
            <Zap className="w-5 h-5" />
            Execute via {routes[selectedRoute]?.name || 'Best Route'}
          </button>
        </div>
      )}

      {/* Analytics Mode */}
      {viewMode === 'analytics' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">24h Volume</div>
              <div className="text-2xl font-bold text-white">${formatNumber(analyticsData.totalVolume24h)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">24h Trades</div>
              <div className="text-2xl font-bold text-white">{formatNumber(analyticsData.totalTrades24h)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Avg Savings</div>
              <div className="text-2xl font-bold text-green-400">{analyticsData.avgSavings.toFixed(2)}%</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">DEXes</div>
              <div className="text-2xl font-bold text-white">{dexes.length}</div>
            </div>
          </div>

          {/* Top Pairs */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Top Trading Pairs (24h)</h3>
            <div className="space-y-3">
              {analyticsData.topPairs.map((pair, i) => (
                <div key={pair.pair} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500 w-6">{i + 1}.</span>
                    <span className="text-white font-medium">{pair.pair}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-white">${formatNumber(pair.volume)}</div>
                    <div className="text-gray-500 text-xs">{formatNumber(pair.trades)} trades</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* DEX Market Share */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">DEX Volume Distribution</h3>
            <div className="space-y-3">
              {analyticsData.dexVolume.map((dex, i) => (
                <div key={dex.name}>
                  <div className="flex justify-between mb-1">
                    <span className="text-white">{dex.name}</span>
                    <span className="text-gray-400">${formatNumber(dex.volume)}</span>
                  </div>
                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full"
                      style={{ width: `${dex.marketShare}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Supported DEXes */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Supported DEXes</h3>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {dexes.map(dex => (
                <div key={dex.id} className="p-3 bg-white/5 rounded-lg text-center">
                  <div className="text-2xl mb-1">{dex.icon}</div>
                  <div className={`text-sm font-medium ${dex.color}`}>{dex.name}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DexAggregator
