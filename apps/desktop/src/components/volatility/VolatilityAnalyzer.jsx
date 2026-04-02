import React, { useState, useMemo, useEffect } from 'react'
import {
  Activity, TrendingUp, TrendingDown, BarChart3, LineChart,
  AlertTriangle, Zap, Clock, ArrowUpRight, ArrowDownRight,
  Filter, RefreshCw, Download, ChevronDown, Info, Target,
  Percent, Calendar, Award, Scale, Bell, Flame, Snowflake
} from 'lucide-react'

const TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 95420, vol24h: 2.8, vol7d: 4.2, vol30d: 12.5, atr: 1850, regime: 'medium' },
  { symbol: 'ETH', name: 'Ethereum', price: 3280, vol24h: 3.5, vol7d: 5.8, vol30d: 15.2, atr: 95, regime: 'medium' },
  { symbol: 'SOL', name: 'Solana', price: 185, vol24h: 5.2, vol7d: 8.4, vol30d: 22.8, atr: 8.5, regime: 'high' },
  { symbol: 'BNB', name: 'BNB', price: 680, vol24h: 2.1, vol7d: 3.5, vol30d: 9.8, atr: 18, regime: 'low' },
  { symbol: 'XRP', name: 'Ripple', price: 2.45, vol24h: 4.8, vol7d: 7.2, vol30d: 18.5, atr: 0.12, regime: 'high' },
  { symbol: 'ADA', name: 'Cardano', price: 0.95, vol24h: 3.8, vol7d: 6.1, vol30d: 16.2, atr: 0.045, regime: 'medium' },
  { symbol: 'AVAX', name: 'Avalanche', price: 38.50, vol24h: 4.5, vol7d: 7.8, vol30d: 19.5, atr: 2.2, regime: 'high' },
  { symbol: 'DOGE', name: 'Dogecoin', price: 0.38, vol24h: 6.2, vol7d: 9.5, vol30d: 25.8, atr: 0.028, regime: 'high' },
  { symbol: 'DOT', name: 'Polkadot', price: 7.85, vol24h: 3.2, vol7d: 5.4, vol30d: 14.5, atr: 0.35, regime: 'medium' },
  { symbol: 'LINK', name: 'Chainlink', price: 22.40, vol24h: 4.1, vol7d: 6.8, vol30d: 17.2, atr: 1.1, regime: 'medium' },
  { symbol: 'MATIC', name: 'Polygon', price: 0.52, vol24h: 4.8, vol7d: 7.5, vol30d: 19.8, atr: 0.032, regime: 'high' },
  { symbol: 'UNI', name: 'Uniswap', price: 13.20, vol24h: 3.9, vol7d: 6.2, vol30d: 15.8, atr: 0.65, regime: 'medium' },
  { symbol: 'ATOM', name: 'Cosmos', price: 9.45, vol24h: 3.5, vol7d: 5.8, vol30d: 14.2, atr: 0.42, regime: 'medium' },
  { symbol: 'LTC', name: 'Litecoin', price: 108, vol24h: 2.5, vol7d: 4.1, vol30d: 11.5, atr: 3.8, regime: 'low' },
  { symbol: 'NEAR', name: 'NEAR', price: 5.85, vol24h: 5.8, vol7d: 9.2, vol30d: 24.5, atr: 0.42, regime: 'high' }
]

const VOLATILITY_REGIMES = {
  low: { label: 'Low Volatility', color: 'text-blue-400', bg: 'bg-blue-500/20', border: 'border-blue-500/30', icon: Snowflake },
  medium: { label: 'Medium Volatility', color: 'text-yellow-400', bg: 'bg-yellow-500/20', border: 'border-yellow-500/30', icon: Activity },
  high: { label: 'High Volatility', color: 'text-red-400', bg: 'bg-red-500/20', border: 'border-red-500/30', icon: Flame }
}

const TIME_PERIODS = [
  { id: '24h', label: '24 Hour', key: 'vol24h' },
  { id: '7d', label: '7 Day', key: 'vol7d' },
  { id: '30d', label: '30 Day', key: 'vol30d' }
]

export function VolatilityAnalyzer() {
  const [mode, setMode] = useState('overview') // overview, ranking, alerts, calculator
  const [selectedPeriod, setSelectedPeriod] = useState('7d')
  const [selectedToken, setSelectedToken] = useState('BTC')
  const [sortBy, setSortBy] = useState('volatility') // volatility, name, regime
  const [sortOrder, setSortOrder] = useState('desc')
  const [regimeFilter, setRegimeFilter] = useState('all')
  const [alertThreshold, setAlertThreshold] = useState(5)

  // Simulated volatility updates
  const [volatilityData, setVolatilityData] = useState(TOKENS)

  useEffect(() => {
    const interval = setInterval(() => {
      setVolatilityData(prev => prev.map(token => ({
        ...token,
        vol24h: Math.max(0.5, token.vol24h + (Math.random() - 0.5) * 0.3),
        price: token.price * (1 + (Math.random() - 0.5) * 0.002)
      })))
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  // Get volatility key based on selected period
  const volKey = TIME_PERIODS.find(p => p.id === selectedPeriod)?.key || 'vol7d'

  // Sort and filter tokens
  const sortedTokens = useMemo(() => {
    let filtered = volatilityData

    if (regimeFilter !== 'all') {
      filtered = filtered.filter(t => t.regime === regimeFilter)
    }

    return filtered.sort((a, b) => {
      let comparison = 0
      if (sortBy === 'volatility') {
        comparison = a[volKey] - b[volKey]
      } else if (sortBy === 'name') {
        comparison = a.symbol.localeCompare(b.symbol)
      } else if (sortBy === 'regime') {
        const order = { high: 3, medium: 2, low: 1 }
        comparison = order[a.regime] - order[b.regime]
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })
  }, [volatilityData, sortBy, sortOrder, regimeFilter, volKey])

  // Market overview stats
  const marketStats = useMemo(() => {
    const avgVol = volatilityData.reduce((sum, t) => sum + t[volKey], 0) / volatilityData.length
    const highVolCount = volatilityData.filter(t => t.regime === 'high').length
    const lowVolCount = volatilityData.filter(t => t.regime === 'low').length
    const medVolCount = volatilityData.filter(t => t.regime === 'medium').length
    const maxVol = Math.max(...volatilityData.map(t => t[volKey]))
    const minVol = Math.min(...volatilityData.map(t => t[volKey]))
    const maxVolToken = volatilityData.find(t => t[volKey] === maxVol)
    const minVolToken = volatilityData.find(t => t[volKey] === minVol)

    // Market regime
    let marketRegime = 'medium'
    if (avgVol < 5) marketRegime = 'low'
    else if (avgVol > 8) marketRegime = 'high'

    return {
      avgVol,
      highVolCount,
      lowVolCount,
      medVolCount,
      maxVol,
      minVol,
      maxVolToken,
      minVolToken,
      marketRegime
    }
  }, [volatilityData, volKey])

  // Selected token data
  const tokenData = volatilityData.find(t => t.symbol === selectedToken)

  // Volatility alerts
  const alerts = useMemo(() => {
    return volatilityData
      .filter(t => t[volKey] > alertThreshold)
      .map(t => ({
        token: t.symbol,
        volatility: t[volKey],
        regime: t.regime,
        message: `${t.symbol} volatility at ${t[volKey].toFixed(1)}% (${selectedPeriod})`
      }))
      .sort((a, b) => b.volatility - a.volatility)
  }, [volatilityData, alertThreshold, volKey, selectedPeriod])

  // Bollinger Band width calculation (mock)
  const calculateBBWidth = (vol) => {
    return (vol * 2 / 100 * 2).toFixed(4)
  }

  // Historical volatility chart data (mock)
  const [historicalData] = useState(() => {
    const data = []
    for (let i = 30; i >= 0; i--) {
      data.push({
        date: new Date(Date.now() - i * 86400000).toLocaleDateString(),
        btc: 2 + Math.random() * 3,
        eth: 3 + Math.random() * 4,
        sol: 4 + Math.random() * 5
      })
    }
    return data
  })

  const RegimeIcon = VOLATILITY_REGIMES[marketStats.marketRegime].icon

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Activity className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Volatility Analyzer</h1>
            <p className="text-sm text-gray-400">Track and analyze market volatility</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['overview', 'ranking', 'alerts', 'calculator'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-purple-500 text-white' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Period Selector */}
      <div className="flex items-center gap-4 mb-6">
        <span className="text-sm text-gray-400">Period:</span>
        <div className="flex gap-2">
          {TIME_PERIODS.map(period => (
            <button
              key={period.id}
              onClick={() => setSelectedPeriod(period.id)}
              className={`px-3 py-1.5 rounded text-sm ${
                selectedPeriod === period.id
                  ? 'bg-purple-500 text-white'
                  : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              {period.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Live updates
        </div>
      </div>

      {/* Overview Mode */}
      {mode === 'overview' && (
        <div className="space-y-6">
          {/* Market Regime Banner */}
          <div className={`rounded-xl p-6 border ${VOLATILITY_REGIMES[marketStats.marketRegime].bg} ${VOLATILITY_REGIMES[marketStats.marketRegime].border}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${VOLATILITY_REGIMES[marketStats.marketRegime].bg}`}>
                  <RegimeIcon className={`w-8 h-8 ${VOLATILITY_REGIMES[marketStats.marketRegime].color}`} />
                </div>
                <div>
                  <div className="text-sm text-gray-400">Current Market Regime</div>
                  <div className={`text-2xl font-bold ${VOLATILITY_REGIMES[marketStats.marketRegime].color}`}>
                    {VOLATILITY_REGIMES[marketStats.marketRegime].label}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-gray-400">Avg Volatility ({selectedPeriod})</div>
                <div className="text-3xl font-bold text-white">{marketStats.avgVol.toFixed(2)}%</div>
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Flame className="w-5 h-5 text-red-400" />
                <span className="text-sm text-gray-400">High Volatility</span>
              </div>
              <div className="text-2xl font-bold text-red-400">{marketStats.highVolCount}</div>
              <div className="text-xs text-gray-500">tokens</div>
            </div>
            <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-yellow-400" />
                <span className="text-sm text-gray-400">Medium Volatility</span>
              </div>
              <div className="text-2xl font-bold text-yellow-400">{marketStats.medVolCount}</div>
              <div className="text-xs text-gray-500">tokens</div>
            </div>
            <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Snowflake className="w-5 h-5 text-blue-400" />
                <span className="text-sm text-gray-400">Low Volatility</span>
              </div>
              <div className="text-2xl font-bold text-blue-400">{marketStats.lowVolCount}</div>
              <div className="text-xs text-gray-500">tokens</div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Scale className="w-5 h-5 text-purple-400" />
                <span className="text-sm text-gray-400">Vol Spread</span>
              </div>
              <div className="text-2xl font-bold text-purple-400">
                {(marketStats.maxVol - marketStats.minVol).toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500">max - min</div>
            </div>
          </div>

          {/* Extremes */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="flex items-center gap-2 mb-4">
                <ArrowUpRight className="w-5 h-5 text-red-400" />
                <h3 className="font-semibold text-white">Most Volatile</h3>
              </div>
              {marketStats.maxVolToken && (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xl font-bold text-white">{marketStats.maxVolToken.symbol}</div>
                    <div className="text-sm text-gray-400">{marketStats.maxVolToken.name}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-red-400">{marketStats.maxVol.toFixed(2)}%</div>
                    <div className="text-sm text-gray-500">{selectedPeriod} volatility</div>
                  </div>
                </div>
              )}
            </div>
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="flex items-center gap-2 mb-4">
                <ArrowDownRight className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white">Least Volatile</h3>
              </div>
              {marketStats.minVolToken && (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xl font-bold text-white">{marketStats.minVolToken.symbol}</div>
                    <div className="text-sm text-gray-400">{marketStats.minVolToken.name}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-blue-400">{marketStats.minVol.toFixed(2)}%</div>
                    <div className="text-sm text-gray-500">{selectedPeriod} volatility</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Token Selection Detail */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white">Token Detail</h3>
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white"
              >
                {volatilityData.map(t => (
                  <option key={t.symbol} value={t.symbol}>{t.symbol} - {t.name}</option>
                ))}
              </select>
            </div>

            {tokenData && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">Current Price</div>
                  <div className="text-xl font-bold text-white">
                    ${tokenData.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">24h Volatility</div>
                  <div className={`text-xl font-bold ${
                    tokenData.vol24h > 5 ? 'text-red-400' : tokenData.vol24h > 3 ? 'text-yellow-400' : 'text-blue-400'
                  }`}>
                    {tokenData.vol24h.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">7d Volatility</div>
                  <div className={`text-xl font-bold ${
                    tokenData.vol7d > 8 ? 'text-red-400' : tokenData.vol7d > 5 ? 'text-yellow-400' : 'text-blue-400'
                  }`}>
                    {tokenData.vol7d.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">30d Volatility</div>
                  <div className={`text-xl font-bold ${
                    tokenData.vol30d > 20 ? 'text-red-400' : tokenData.vol30d > 12 ? 'text-yellow-400' : 'text-blue-400'
                  }`}>
                    {tokenData.vol30d.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">ATR (14)</div>
                  <div className="text-xl font-bold text-white">
                    ${tokenData.atr.toLocaleString()}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">ATR %</div>
                  <div className="text-xl font-bold text-white">
                    {((tokenData.atr / tokenData.price) * 100).toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-1">BB Width</div>
                  <div className="text-xl font-bold text-white">
                    {calculateBBWidth(tokenData[volKey])}
                  </div>
                </div>
                <div className={`rounded-lg p-4 ${VOLATILITY_REGIMES[tokenData.regime].bg} ${VOLATILITY_REGIMES[tokenData.regime].border}`}>
                  <div className="text-sm text-gray-400 mb-1">Regime</div>
                  <div className={`text-xl font-bold ${VOLATILITY_REGIMES[tokenData.regime].color}`}>
                    {VOLATILITY_REGIMES[tokenData.regime].label.split(' ')[0]}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Ranking Mode */}
      {mode === 'ranking' && (
        <div className="space-y-6">
          {/* Controls */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Filter:</span>
              <select
                value={regimeFilter}
                onChange={(e) => setRegimeFilter(e.target.value)}
                className="bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white text-sm"
              >
                <option value="all">All Regimes</option>
                <option value="high">High Volatility</option>
                <option value="medium">Medium Volatility</option>
                <option value="low">Low Volatility</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white text-sm"
              >
                <option value="volatility">Volatility</option>
                <option value="name">Name</option>
                <option value="regime">Regime</option>
              </select>
              <button
                onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
                className="p-1.5 bg-white/10 rounded text-gray-400 hover:bg-white/20"
              >
                {sortOrder === 'desc' ? <ArrowDownRight className="w-4 h-4" /> : <ArrowUpRight className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Ranking Table */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-white/10 bg-white/5">
                  <th className="p-4">Rank</th>
                  <th className="p-4">Token</th>
                  <th className="p-4">Price</th>
                  <th className="p-4">24h Vol</th>
                  <th className="p-4">7d Vol</th>
                  <th className="p-4">30d Vol</th>
                  <th className="p-4">ATR</th>
                  <th className="p-4">Regime</th>
                </tr>
              </thead>
              <tbody>
                {sortedTokens.map((token, idx) => {
                  const regime = VOLATILITY_REGIMES[token.regime]
                  const Icon = regime.icon
                  return (
                    <tr key={token.symbol} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-4">
                        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                          idx === 0 ? 'bg-red-500 text-white' :
                          idx === 1 ? 'bg-orange-500 text-white' :
                          idx === 2 ? 'bg-yellow-500 text-black' :
                          'bg-white/10 text-gray-400'
                        }`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div>
                            <div className="font-semibold text-white">{token.symbol}</div>
                            <div className="text-xs text-gray-500">{token.name}</div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-white font-mono">
                        ${token.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="p-4">
                        <span className={`font-semibold ${
                          token.vol24h > 5 ? 'text-red-400' : token.vol24h > 3 ? 'text-yellow-400' : 'text-blue-400'
                        }`}>
                          {token.vol24h.toFixed(2)}%
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`font-semibold ${
                          token.vol7d > 8 ? 'text-red-400' : token.vol7d > 5 ? 'text-yellow-400' : 'text-blue-400'
                        }`}>
                          {token.vol7d.toFixed(2)}%
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`font-semibold ${
                          token.vol30d > 20 ? 'text-red-400' : token.vol30d > 12 ? 'text-yellow-400' : 'text-blue-400'
                        }`}>
                          {token.vol30d.toFixed(2)}%
                        </span>
                      </td>
                      <td className="p-4 text-gray-300 font-mono">
                        ${token.atr}
                      </td>
                      <td className="p-4">
                        <span className={`flex items-center gap-1.5 px-2 py-1 rounded ${regime.bg} ${regime.color} text-xs`}>
                          <Icon className="w-3 h-3" />
                          {token.regime.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Alerts Mode */}
      {mode === 'alerts' && (
        <div className="space-y-6">
          {/* Alert Threshold */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-yellow-400" />
                <h3 className="font-semibold text-white">Volatility Alert Threshold</h3>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={alertThreshold}
                  onChange={(e) => setAlertThreshold(Number(e.target.value))}
                  className="w-32"
                />
                <span className="text-white font-semibold w-12">{alertThreshold}%</span>
              </div>
            </div>
            <p className="text-sm text-gray-400">
              Alert when {selectedPeriod} volatility exceeds {alertThreshold}%
            </p>
          </div>

          {/* Active Alerts */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                Active Alerts ({alerts.length})
              </h3>
              <span className="text-sm text-gray-400">{selectedPeriod} volatility &gt; {alertThreshold}%</span>
            </div>

            {alerts.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No tokens currently exceed the alert threshold</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {alerts.map((alert, idx) => {
                  const regime = VOLATILITY_REGIMES[alert.regime]
                  return (
                    <div key={idx} className="p-4 flex items-center justify-between hover:bg-white/5">
                      <div className="flex items-center gap-4">
                        <span className={`p-2 rounded-lg ${regime.bg}`}>
                          <AlertTriangle className={`w-5 h-5 ${regime.color}`} />
                        </span>
                        <div>
                          <div className="font-semibold text-white">{alert.token}</div>
                          <div className="text-sm text-gray-400">{alert.message}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-xl font-bold ${regime.color}`}>
                          {alert.volatility.toFixed(2)}%
                        </div>
                        <div className={`text-xs ${regime.color}`}>{regime.label}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Alert History (Mock) */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4">Recent Alert History</h3>
            <div className="space-y-2">
              {[
                { token: 'DOGE', vol: 8.5, time: '2 hours ago', status: 'resolved' },
                { token: 'SOL', vol: 7.2, time: '5 hours ago', status: 'resolved' },
                { token: 'XRP', vol: 6.8, time: '1 day ago', status: 'resolved' },
                { token: 'AVAX', vol: 9.1, time: '1 day ago', status: 'resolved' }
              ].map((h, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="text-white font-medium">{h.token}</span>
                    <span className="text-yellow-400">{h.vol}%</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500 text-sm">{h.time}</span>
                    <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
                      {h.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Calculator Mode */}
      {mode === 'calculator' && (
        <div className="space-y-6">
          {/* Position Size Calculator based on Volatility */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-green-400" />
              Volatility-Adjusted Position Size
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="text-xs text-gray-400 block mb-2">Account Size ($)</label>
                <input
                  type="number"
                  defaultValue={10000}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-2">Risk per Trade (%)</label>
                <input
                  type="number"
                  defaultValue={2}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-2">Token</label>
                <select className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white">
                  {volatilityData.map(t => (
                    <option key={t.symbol} value={t.symbol}>{t.symbol}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-2">Volatility Multiple</label>
                <select className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white">
                  <option value="1">1x ATR</option>
                  <option value="1.5">1.5x ATR</option>
                  <option value="2">2x ATR</option>
                  <option value="3">3x ATR</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 p-4 bg-white/5 rounded-lg">
              <div className="text-center">
                <div className="text-sm text-gray-400">Stop Loss Distance</div>
                <div className="text-xl font-bold text-red-400">$1,850</div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-400">Position Size</div>
                <div className="text-xl font-bold text-green-400">0.108 BTC</div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-400">Position Value</div>
                <div className="text-xl font-bold text-white">$10,305</div>
              </div>
            </div>
          </div>

          {/* Expected Move Calculator */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <Scale className="w-5 h-5 text-blue-400" />
              Expected Price Range
            </h3>
            <p className="text-sm text-gray-400 mb-4">
              Based on historical volatility, predict expected price ranges
            </p>
            <div className="space-y-4">
              {['BTC', 'ETH', 'SOL'].map(symbol => {
                const token = volatilityData.find(t => t.symbol === symbol)
                if (!token) return null
                const vol = token[volKey] / 100
                const upper = token.price * (1 + vol)
                const lower = token.price * (1 - vol)
                const upper2sd = token.price * (1 + vol * 2)
                const lower2sd = token.price * (1 - vol * 2)
                return (
                  <div key={symbol} className="p-4 bg-white/5 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-white font-semibold">{symbol}</span>
                      <span className="text-gray-400">${token.price.toLocaleString()}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <div className="text-gray-500 mb-1">1 SD Range (68%)</div>
                        <div className="flex justify-between">
                          <span className="text-red-400">${lower.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                          <span className="text-gray-500">to</span>
                          <span className="text-green-400">${upper.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500 mb-1">2 SD Range (95%)</div>
                        <div className="flex justify-between">
                          <span className="text-red-400">${lower2sd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                          <span className="text-gray-500">to</span>
                          <span className="text-green-400">${upper2sd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Volatility Comparison */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-400" />
              Historical Volatility Comparison
            </h3>
            <div className="space-y-3">
              {volatilityData.slice(0, 8).map(token => {
                const width24h = (token.vol24h / 10) * 100
                const width7d = (token.vol7d / 15) * 100
                const width30d = (token.vol30d / 30) * 100
                return (
                  <div key={token.symbol} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-white font-medium w-16">{token.symbol}</span>
                      <div className="flex gap-4 text-xs">
                        <span className="text-red-400">{token.vol24h.toFixed(1)}%</span>
                        <span className="text-yellow-400">{token.vol7d.toFixed(1)}%</span>
                        <span className="text-blue-400">{token.vol30d.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="flex gap-1 h-2">
                      <div className="bg-red-500/30 rounded-full overflow-hidden flex-1">
                        <div className="h-full bg-red-500 rounded-full" style={{ width: `${Math.min(width24h, 100)}%` }} />
                      </div>
                      <div className="bg-yellow-500/30 rounded-full overflow-hidden flex-1">
                        <div className="h-full bg-yellow-500 rounded-full" style={{ width: `${Math.min(width7d, 100)}%` }} />
                      </div>
                      <div className="bg-blue-500/30 rounded-full overflow-hidden flex-1">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(width30d, 100)}%` }} />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex justify-center gap-6 mt-4 text-xs">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500 rounded-full"></span> 24h</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-yellow-500 rounded-full"></span> 7d</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded-full"></span> 30d</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VolatilityAnalyzer
