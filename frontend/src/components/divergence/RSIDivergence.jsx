import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  AlertTriangle,
  Eye,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  BarChart3,
  Clock,
  Bell,
  ChevronDown,
  ChevronUp,
  Layers,
  Search
} from 'lucide-react'

export function RSIDivergence() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [rsiPeriod, setRsiPeriod] = useState(14)
  const [viewMode, setViewMode] = useState('scanner') // scanner, chart, alerts
  const [divergenceFilter, setDivergenceFilter] = useState('all') // all, bullish, bearish, regular, hidden

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']
  const timeframes = ['15m', '1h', '4h', '1d']

  // Generate RSI divergence data
  const divergenceData = useMemo(() => {
    return tokens.map(token => {
      const currentRsi = 30 + Math.random() * 40
      const previousRsi = 30 + Math.random() * 40
      const currentPrice = 50 + Math.random() * 150
      const previousPrice = 50 + Math.random() * 150

      // Determine divergence type
      let divergenceType = null
      let divergenceStrength = 0

      // Regular Bullish: Price makes lower low, RSI makes higher low
      if (currentPrice < previousPrice && currentRsi > previousRsi) {
        divergenceType = 'regular_bullish'
        divergenceStrength = Math.abs(currentRsi - previousRsi) / 10
      }
      // Regular Bearish: Price makes higher high, RSI makes lower high
      else if (currentPrice > previousPrice && currentRsi < previousRsi) {
        divergenceType = 'regular_bearish'
        divergenceStrength = Math.abs(currentRsi - previousRsi) / 10
      }
      // Hidden Bullish: Price makes higher low, RSI makes lower low (trend continuation)
      else if (currentPrice > previousPrice && currentRsi < previousRsi && currentRsi < 40) {
        divergenceType = 'hidden_bullish'
        divergenceStrength = Math.abs(currentRsi - previousRsi) / 12
      }
      // Hidden Bearish: Price makes lower high, RSI makes higher high (trend continuation)
      else if (currentPrice < previousPrice && currentRsi > previousRsi && currentRsi > 60) {
        divergenceType = 'hidden_bearish'
        divergenceStrength = Math.abs(currentRsi - previousRsi) / 12
      }

      // Multi-timeframe confirmation
      const mtfConfirmation = {
        '15m': Math.random() > 0.5,
        '1h': Math.random() > 0.4,
        '4h': Math.random() > 0.3,
        '1d': Math.random() > 0.6
      }

      const confirmedTimeframes = Object.values(mtfConfirmation).filter(Boolean).length

      return {
        token,
        currentPrice,
        previousPrice,
        priceChange: ((currentPrice - previousPrice) / previousPrice * 100),
        currentRsi,
        previousRsi,
        rsiChange: currentRsi - previousRsi,
        divergenceType,
        divergenceStrength: Math.min(divergenceStrength, 1),
        mtfConfirmation,
        confirmedTimeframes,
        candlesAgo: Math.floor(Math.random() * 20) + 3,
        volume24h: (Math.random() * 500).toFixed(1),
        alerts: Math.random() > 0.7
      }
    })
  }, [])

  // Filter divergences
  const filteredDivergences = useMemo(() => {
    return divergenceData.filter(d => {
      if (!d.divergenceType) return divergenceFilter === 'all'

      if (divergenceFilter === 'bullish') {
        return d.divergenceType.includes('bullish')
      }
      if (divergenceFilter === 'bearish') {
        return d.divergenceType.includes('bearish')
      }
      if (divergenceFilter === 'regular') {
        return d.divergenceType.startsWith('regular')
      }
      if (divergenceFilter === 'hidden') {
        return d.divergenceType.startsWith('hidden')
      }
      return true
    })
  }, [divergenceData, divergenceFilter])

  // Active divergences count
  const activeDivergences = divergenceData.filter(d => d.divergenceType).length
  const bullishCount = divergenceData.filter(d => d.divergenceType?.includes('bullish')).length
  const bearishCount = divergenceData.filter(d => d.divergenceType?.includes('bearish')).length

  // RSI chart data for selected token
  const rsiHistory = useMemo(() => {
    const data = []
    let rsi = 50
    let price = 100

    for (let i = 30; i >= 0; i--) {
      rsi = Math.max(10, Math.min(90, rsi + (Math.random() - 0.5) * 15))
      price = Math.max(50, price + (Math.random() - 0.5) * 10)

      data.push({
        time: i === 0 ? 'Now' : `-${i}`,
        rsi,
        price,
        overbought: rsi > 70,
        oversold: rsi < 30
      })
    }
    return data
  }, [selectedToken])

  // Pending alerts
  const pendingAlerts = useMemo(() => {
    return [
      { token: 'SOL', type: 'regular_bullish', timeframe: '4h', rsi: 28.5, triggered: '5m ago', strength: 0.85 },
      { token: 'ETH', type: 'hidden_bearish', timeframe: '1h', rsi: 72.3, triggered: '12m ago', strength: 0.72 },
      { token: 'BTC', type: 'regular_bullish', timeframe: '1d', rsi: 31.2, triggered: '1h ago', strength: 0.91 },
      { token: 'JUP', type: 'regular_bearish', timeframe: '4h', rsi: 68.9, triggered: '3h ago', strength: 0.78 },
      { token: 'BONK', type: 'hidden_bullish', timeframe: '15m', rsi: 35.6, triggered: '8m ago', strength: 0.65 }
    ]
  }, [])

  const getDivergenceLabel = (type) => {
    switch (type) {
      case 'regular_bullish': return 'Regular Bullish'
      case 'regular_bearish': return 'Regular Bearish'
      case 'hidden_bullish': return 'Hidden Bullish'
      case 'hidden_bearish': return 'Hidden Bearish'
      default: return 'None'
    }
  }

  const getDivergenceColor = (type) => {
    if (!type) return 'text-white/40'
    return type.includes('bullish') ? 'text-green-400' : 'text-red-400'
  }

  const getDivergenceBg = (type) => {
    if (!type) return 'bg-white/5'
    return type.includes('bullish') ? 'bg-green-500/10' : 'bg-red-500/10'
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Activity className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">RSI Divergence Scanner</h1>
            <p className="text-white/60 text-sm">Detect regular and hidden divergences</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* RSI Period */}
          <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
            <span className="text-white/60 text-sm">RSI:</span>
            <select
              value={rsiPeriod}
              onChange={(e) => setRsiPeriod(Number(e.target.value))}
              className="bg-transparent text-white text-sm outline-none"
            >
              <option value={7}>7</option>
              <option value={14}>14</option>
              <option value={21}>21</option>
            </select>
          </div>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['scanner', 'chart', 'alerts'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-purple-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Active Divergences</span>
          </div>
          <p className="text-2xl font-bold">{activeDivergences}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">Bullish Signals</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{bullishCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <span className="text-white/60 text-sm">Bearish Signals</span>
          </div>
          <p className="text-2xl font-bold text-red-400">{bearishCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bell className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">Pending Alerts</span>
          </div>
          <p className="text-2xl font-bold text-yellow-400">{pendingAlerts.length}</p>
        </div>
      </div>

      {viewMode === 'scanner' && (
        <>
          {/* Filters */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-white/40" />
              <span className="text-white/60 text-sm">Filter:</span>
            </div>
            {['all', 'bullish', 'bearish', 'regular', 'hidden'].map(filter => (
              <button
                key={filter}
                onClick={() => setDivergenceFilter(filter)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-all ${
                  divergenceFilter === filter
                    ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    : 'bg-white/5 text-white/60 hover:text-white'
                }`}
              >
                {filter.charAt(0).toUpperCase() + filter.slice(1)}
              </button>
            ))}
          </div>

          {/* Scanner Table */}
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Price</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">RSI</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Divergence</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Strength</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">MTF Confirm</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Candles Ago</th>
                </tr>
              </thead>
              <tbody>
                {filteredDivergences.map((item, idx) => (
                  <tr
                    key={item.token}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.token}</span>
                        {item.alerts && (
                          <Bell className="w-3 h-3 text-yellow-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div>
                        <p className="font-medium">${item.currentPrice.toFixed(2)}</p>
                        <p className={`text-xs ${item.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {item.priceChange >= 0 ? '+' : ''}{item.priceChange.toFixed(2)}%
                        </p>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className={`font-medium ${
                          item.currentRsi > 70 ? 'text-red-400' :
                          item.currentRsi < 30 ? 'text-green-400' : 'text-white'
                        }`}>
                          {item.currentRsi.toFixed(1)}
                        </span>
                        {item.rsiChange !== 0 && (
                          item.rsiChange > 0
                            ? <ChevronUp className="w-4 h-4 text-green-400" />
                            : <ChevronDown className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getDivergenceBg(item.divergenceType)} ${getDivergenceColor(item.divergenceType)}`}>
                          {getDivergenceLabel(item.divergenceType)}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center">
                        {item.divergenceType && (
                          <div className="w-20">
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  item.divergenceType.includes('bullish') ? 'bg-green-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${item.divergenceStrength * 100}%` }}
                              />
                            </div>
                            <p className="text-xs text-center mt-1 text-white/60">
                              {(item.divergenceStrength * 100).toFixed(0)}%
                            </p>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center gap-1">
                        {Object.entries(item.mtfConfirmation).map(([tf, confirmed]) => (
                          <div
                            key={tf}
                            className={`w-6 h-6 rounded text-xs flex items-center justify-center ${
                              confirmed ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-white/30'
                            }`}
                            title={tf}
                          >
                            {tf.replace('m', '').replace('h', '').replace('d', '')}
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right text-white/60">
                      {item.divergenceType ? item.candlesAgo : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {viewMode === 'chart' && (
        <div className="grid grid-cols-3 gap-6">
          {/* RSI Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold">{selectedToken} RSI Chart</h2>
              </div>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="bg-white/5 border border-white/10 rounded px-3 py-1 text-sm"
              >
                {timeframes.map(tf => (
                  <option key={tf} value={tf}>{tf}</option>
                ))}
              </select>
            </div>

            {/* RSI Zone Visualization */}
            <div className="relative h-64 border border-white/10 rounded-lg overflow-hidden">
              {/* Overbought zone */}
              <div className="absolute top-0 left-0 right-0 h-[30%] bg-red-500/10 border-b border-red-500/30">
                <span className="absolute right-2 top-1 text-xs text-red-400">Overbought 70</span>
              </div>

              {/* Oversold zone */}
              <div className="absolute bottom-0 left-0 right-0 h-[30%] bg-green-500/10 border-t border-green-500/30">
                <span className="absolute right-2 bottom-1 text-xs text-green-400">Oversold 30</span>
              </div>

              {/* RSI Line */}
              <svg className="w-full h-full">
                <polyline
                  fill="none"
                  stroke="#a855f7"
                  strokeWidth="2"
                  points={rsiHistory.map((d, i) => {
                    const x = (i / (rsiHistory.length - 1)) * 100
                    const y = 100 - d.rsi
                    return `${x}%,${y}%`
                  }).join(' ')}
                />
                {/* Divergence markers */}
                {rsiHistory.map((d, i) => {
                  if (i > 0 && i < rsiHistory.length - 1) {
                    const prev = rsiHistory[i - 1]
                    const next = rsiHistory[i + 1]
                    if (d.rsi < prev.rsi && d.rsi < next.rsi && d.rsi < 35) {
                      // Potential bullish divergence point
                      const x = (i / (rsiHistory.length - 1)) * 100
                      const y = 100 - d.rsi
                      return (
                        <circle
                          key={i}
                          cx={`${x}%`}
                          cy={`${y}%`}
                          r="4"
                          fill="#22c55e"
                          opacity="0.8"
                        />
                      )
                    }
                  }
                  return null
                })}
              </svg>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full" />
                <span className="text-white/60">RSI ({rsiPeriod})</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full" />
                <span className="text-white/60">Bullish Divergence</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full" />
                <span className="text-white/60">Bearish Divergence</span>
              </div>
            </div>
          </div>

          {/* Divergence Details */}
          <div className="space-y-4">
            {/* Current Token Stats */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Search className="w-4 h-4 text-purple-400" />
                {selectedToken} Analysis
              </h3>

              {(() => {
                const tokenData = divergenceData.find(d => d.token === selectedToken)
                return (
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-white/60">Current RSI</span>
                      <span className={`font-medium ${
                        tokenData.currentRsi > 70 ? 'text-red-400' :
                        tokenData.currentRsi < 30 ? 'text-green-400' : 'text-white'
                      }`}>
                        {tokenData.currentRsi.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Previous RSI</span>
                      <span className="font-medium">{tokenData.previousRsi.toFixed(1)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Divergence</span>
                      <span className={getDivergenceColor(tokenData.divergenceType)}>
                        {getDivergenceLabel(tokenData.divergenceType)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Signal Strength</span>
                      <span className="font-medium">
                        {(tokenData.divergenceStrength * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">MTF Confirmed</span>
                      <span className="font-medium">
                        {tokenData.confirmedTimeframes}/4 TFs
                      </span>
                    </div>
                  </div>
                )
              })()}
            </div>

            {/* Divergence Types Guide */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-400" />
                Divergence Types
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <p className="text-green-400 font-medium">Regular Bullish</p>
                  <p className="text-white/60 text-xs">Price: Lower Low / RSI: Higher Low</p>
                </div>
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <p className="text-red-400 font-medium">Regular Bearish</p>
                  <p className="text-white/60 text-xs">Price: Higher High / RSI: Lower High</p>
                </div>
                <div className="p-2 bg-emerald-500/10 rounded-lg">
                  <p className="text-emerald-400 font-medium">Hidden Bullish</p>
                  <p className="text-white/60 text-xs">Price: Higher Low / RSI: Lower Low</p>
                </div>
                <div className="p-2 bg-orange-500/10 rounded-lg">
                  <p className="text-orange-400 font-medium">Hidden Bearish</p>
                  <p className="text-white/60 text-xs">Price: Lower High / RSI: Higher High</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'alerts' && (
        <div className="space-y-4">
          {/* Alert Settings */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Bell className="w-5 h-5 text-yellow-400" />
              Alert Configuration
            </h2>

            <div className="grid grid-cols-4 gap-4">
              <div className="p-3 bg-white/5 rounded-lg">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded" />
                  <span className="text-sm">Regular Bullish</span>
                </label>
              </div>
              <div className="p-3 bg-white/5 rounded-lg">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded" />
                  <span className="text-sm">Regular Bearish</span>
                </label>
              </div>
              <div className="p-3 bg-white/5 rounded-lg">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded" />
                  <span className="text-sm">Hidden Bullish</span>
                </label>
              </div>
              <div className="p-3 bg-white/5 rounded-lg">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded" />
                  <span className="text-sm">Hidden Bearish</span>
                </label>
              </div>
            </div>
          </div>

          {/* Recent Alerts */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              Recent Divergence Alerts
            </h2>

            <div className="space-y-3">
              {pendingAlerts.map((alert, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border ${
                    alert.type.includes('bullish')
                      ? 'bg-green-500/10 border-green-500/30'
                      : 'bg-red-500/10 border-red-500/30'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      {alert.type.includes('bullish') ? (
                        <ArrowUpRight className="w-5 h-5 text-green-400" />
                      ) : (
                        <ArrowDownRight className="w-5 h-5 text-red-400" />
                      )}
                      <span className="font-bold">{alert.token}</span>
                      <span className={`px-2 py-1 rounded text-xs ${getDivergenceBg(alert.type)} ${getDivergenceColor(alert.type)}`}>
                        {getDivergenceLabel(alert.type)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-white/60 text-sm">
                      <Clock className="w-4 h-4" />
                      {alert.triggered}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-sm">
                    <div>
                      <span className="text-white/60">Timeframe: </span>
                      <span className="font-medium">{alert.timeframe}</span>
                    </div>
                    <div>
                      <span className="text-white/60">RSI: </span>
                      <span className="font-medium">{alert.rsi}</span>
                    </div>
                    <div>
                      <span className="text-white/60">Strength: </span>
                      <span className="font-medium">{(alert.strength * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Alert Summary */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-green-400">{pendingAlerts.filter(a => a.type.includes('bullish')).length}</p>
              <p className="text-white/60 text-sm mt-1">Bullish Alerts Today</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-red-400">{pendingAlerts.filter(a => a.type.includes('bearish')).length}</p>
              <p className="text-white/60 text-sm mt-1">Bearish Alerts Today</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-purple-400">78%</p>
              <p className="text-white/60 text-sm mt-1">Avg Accuracy (30d)</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RSIDivergence
