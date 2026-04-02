import React, { useState, useMemo, useEffect } from 'react'
import {
  Scale,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  Clock,
  Zap,
  BarChart3,
  Eye
} from 'lucide-react'

export function OrderImbalance() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('1h')
  const [viewMode, setViewMode] = useState('overview') // overview, history, alerts
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['5m', '15m', '1h', '4h', '1d']

  // Generate mock order imbalance data
  const imbalanceData = useMemo(() => {
    const bidVolume = Math.floor(Math.random() * 50000000) + 10000000
    const askVolume = Math.floor(Math.random() * 50000000) + 10000000
    const imbalance = ((bidVolume - askVolume) / (bidVolume + askVolume)) * 100
    const delta = bidVolume - askVolume

    // Generate imbalance by price level
    const priceData = Array.from({ length: 20 }, (_, i) => {
      const bidVol = Math.floor(Math.random() * 1000000) + 100000
      const askVol = Math.floor(Math.random() * 1000000) + 100000
      const levelImbalance = ((bidVol - askVol) / (bidVol + askVol)) * 100

      return {
        level: i + 1,
        bidVolume: bidVol,
        askVolume: askVol,
        imbalance: levelImbalance,
        significant: Math.abs(levelImbalance) > 50
      }
    })

    // Historical imbalance
    const history = Array.from({ length: 24 }, (_, i) => ({
      time: new Date(Date.now() - i * 60 * 60 * 1000),
      imbalance: (Math.random() - 0.5) * 80,
      volume: Math.floor(Math.random() * 10000000) + 1000000
    })).reverse()

    // Alerts
    const alerts = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'buy_pressure' : 'sell_pressure',
      magnitude: Math.floor(Math.random() * 50) + 50,
      time: new Date(Date.now() - i * 30 * 60 * 1000),
      price: 178.50 + (Math.random() - 0.5) * 10
    }))

    return {
      bidVolume,
      askVolume,
      totalVolume: bidVolume + askVolume,
      imbalance,
      delta,
      bias: imbalance > 10 ? 'bullish' : imbalance < -10 ? 'bearish' : 'neutral',
      priceData,
      history,
      alerts,
      buyPressure: imbalance > 0 ? Math.abs(imbalance) : 0,
      sellPressure: imbalance < 0 ? Math.abs(imbalance) : 0
    }
  }, [selectedToken, timeframe])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(0)
  }

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const getBiasColor = (bias) => {
    switch(bias) {
      case 'bullish': return 'text-green-400'
      case 'bearish': return 'text-red-400'
      default: return 'text-yellow-400'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Scale className="w-6 h-6 text-cyan-400" />
          <h2 className="text-xl font-bold text-white">Order Imbalance</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {tokens.map(token => (
              <option key={token} value={token}>{token}</option>
            ))}
          </select>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Main Imbalance Display */}
      <div className={`rounded-lg p-6 mb-6 border ${
        imbalanceData.bias === 'bullish' ? 'bg-green-500/10 border-green-500/20' :
        imbalanceData.bias === 'bearish' ? 'bg-red-500/10 border-red-500/20' :
        'bg-yellow-500/10 border-yellow-500/20'
      }`}>
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-2">Current Imbalance</div>
          <div className={`text-5xl font-bold ${getBiasColor(imbalanceData.bias)}`}>
            {imbalanceData.imbalance >= 0 ? '+' : ''}{imbalanceData.imbalance.toFixed(1)}%
          </div>
          <div className="text-gray-400 text-sm mt-2 capitalize">{imbalanceData.bias} Bias</div>
        </div>

        {/* Imbalance Bar */}
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-green-400 text-sm flex-1 text-left">
              Buy: ${formatNumber(imbalanceData.bidVolume)}
            </span>
            <span className="text-red-400 text-sm flex-1 text-right">
              Sell: ${formatNumber(imbalanceData.askVolume)}
            </span>
          </div>
          <div className="h-4 flex rounded-full overflow-hidden">
            <div
              className="bg-green-500 h-full"
              style={{ width: `${(imbalanceData.bidVolume / imbalanceData.totalVolume) * 100}%` }}
            />
            <div
              className="bg-red-500 h-full"
              style={{ width: `${(imbalanceData.askVolume / imbalanceData.totalVolume) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Total Volume</div>
          <div className="text-xl font-bold text-white">${formatNumber(imbalanceData.totalVolume)}</div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Net Delta</div>
          <div className={`text-xl font-bold ${imbalanceData.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${formatNumber(Math.abs(imbalanceData.delta))}
          </div>
        </div>
        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
          <div className="text-gray-400 text-sm mb-1">Buy Pressure</div>
          <div className="text-xl font-bold text-green-400">{imbalanceData.buyPressure.toFixed(1)}%</div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
          <div className="text-gray-400 text-sm mb-1">Sell Pressure</div>
          <div className="text-xl font-bold text-red-400">{imbalanceData.sellPressure.toFixed(1)}%</div>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'overview', label: 'By Price' },
          { id: 'history', label: 'History' },
          { id: 'alerts', label: 'Alerts' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Overview Mode - By Price Level */}
      {viewMode === 'overview' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">Imbalance by Price Level</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {imbalanceData.priceData.map((level, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-12 text-gray-500 text-sm">L{level.level}</div>
                <div className="flex-1 h-6 flex rounded overflow-hidden bg-white/5">
                  <div
                    className="bg-green-500/70 h-full"
                    style={{ width: `${(level.bidVolume / (level.bidVolume + level.askVolume)) * 100}%` }}
                  />
                  <div
                    className="bg-red-500/70 h-full"
                    style={{ width: `${(level.askVolume / (level.bidVolume + level.askVolume)) * 100}%` }}
                  />
                </div>
                <div className={`w-16 text-sm text-right font-medium ${
                  level.imbalance >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {level.imbalance >= 0 ? '+' : ''}{level.imbalance.toFixed(0)}%
                </div>
                {level.significant && (
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History Mode */}
      {viewMode === 'history' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">Imbalance History ({timeframe})</h3>
          <div className="h-48 flex items-end gap-1">
            {imbalanceData.history.map((point, i) => {
              const height = Math.abs(point.imbalance)
              const isPositive = point.imbalance >= 0

              return (
                <div key={i} className="flex-1 flex flex-col justify-end items-center group relative">
                  <div
                    className={`w-full rounded-t ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                    style={{ height: `${height}%` }}
                  />
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black/90 p-2 rounded text-xs text-white whitespace-nowrap z-10">
                    <div>{formatTime(point.time)}</div>
                    <div className={isPositive ? 'text-green-400' : 'text-red-400'}>
                      {point.imbalance.toFixed(1)}%
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <span>{formatTime(imbalanceData.history[0].time)}</span>
            <span>{formatTime(imbalanceData.history[imbalanceData.history.length - 1].time)}</span>
          </div>
        </div>
      )}

      {/* Alerts Mode */}
      {viewMode === 'alerts' && (
        <div className="space-y-3">
          {imbalanceData.alerts.map(alert => (
            <div
              key={alert.id}
              className={`p-4 rounded-lg border ${
                alert.type === 'buy_pressure'
                  ? 'bg-green-500/10 border-green-500/20'
                  : 'bg-red-500/10 border-red-500/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {alert.type === 'buy_pressure' ? (
                    <ChevronUp className="w-5 h-5 text-green-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-red-400" />
                  )}
                  <div>
                    <span className={`font-medium ${
                      alert.type === 'buy_pressure' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {alert.type === 'buy_pressure' ? 'Strong Buy Pressure' : 'Strong Sell Pressure'}
                    </span>
                    <span className="text-gray-400 text-sm ml-2">
                      at ${alert.price.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">{alert.magnitude}%</div>
                  <div className="text-gray-500 text-xs">
                    {formatTime(alert.time)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default OrderImbalance
