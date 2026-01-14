import React, { useState, useEffect, useMemo } from 'react'
import {
  Signal, TrendingUp, TrendingDown, AlertTriangle, Bell,
  Target, Activity, Clock, Filter, Search, RefreshCw,
  ArrowUpRight, ArrowDownRight, ChevronDown, ExternalLink,
  Zap, BarChart3, Eye, EyeOff, Star, CheckCircle
} from 'lucide-react'

// Signal types
const SIGNAL_TYPES = {
  BREAKOUT: { label: 'Breakout', color: '#22c55e', description: 'Price breaking key resistance' },
  BREAKDOWN: { label: 'Breakdown', color: '#ef4444', description: 'Price breaking key support' },
  GOLDEN_CROSS: { label: 'Golden Cross', color: '#22c55e', description: 'MA50 crossing above MA200' },
  DEATH_CROSS: { label: 'Death Cross', color: '#ef4444', description: 'MA50 crossing below MA200' },
  RSI_OVERSOLD: { label: 'RSI Oversold', color: '#22c55e', description: 'RSI below 30, potential reversal' },
  RSI_OVERBOUGHT: { label: 'RSI Overbought', color: '#ef4444', description: 'RSI above 70, potential reversal' },
  MACD_BULLISH: { label: 'MACD Bullish', color: '#22c55e', description: 'MACD line crossing above signal' },
  MACD_BEARISH: { label: 'MACD Bearish', color: '#ef4444', description: 'MACD line crossing below signal' },
  VOLUME_SPIKE: { label: 'Volume Spike', color: '#8b5cf6', description: 'Unusual volume detected' },
  WHALE_ACTIVITY: { label: 'Whale Alert', color: '#f59e0b', description: 'Large wallet activity detected' },
  SUPPORT_TEST: { label: 'Support Test', color: '#3b82f6', description: 'Price testing support level' },
  RESISTANCE_TEST: { label: 'Resistance Test', color: '#ec4899', description: 'Price testing resistance level' }
}

// Timeframes
const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w']

// Assets
const ASSETS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 95000 },
  { symbol: 'ETH', name: 'Ethereum', price: 3200 },
  { symbol: 'SOL', name: 'Solana', price: 180 },
  { symbol: 'ARB', name: 'Arbitrum', price: 1.2 },
  { symbol: 'OP', name: 'Optimism', price: 2.5 },
  { symbol: 'LINK', name: 'Chainlink', price: 18 },
  { symbol: 'AVAX', name: 'Avalanche', price: 35 },
  { symbol: 'MATIC', name: 'Polygon', price: 0.9 },
  { symbol: 'DOT', name: 'Polkadot', price: 7 },
  { symbol: 'ATOM', name: 'Cosmos', price: 9 },
  { symbol: 'UNI', name: 'Uniswap', price: 8 },
  { symbol: 'AAVE', name: 'Aave', price: 180 }
]

// Generate signals
const generateSignals = () => {
  const signalTypes = Object.keys(SIGNAL_TYPES)
  const signals = []

  for (let i = 0; i < 30; i++) {
    const type = signalTypes[Math.floor(Math.random() * signalTypes.length)]
    const asset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
    const timeframe = TIMEFRAMES[Math.floor(Math.random() * TIMEFRAMES.length)]
    const isBullish = ['BREAKOUT', 'GOLDEN_CROSS', 'RSI_OVERSOLD', 'MACD_BULLISH'].includes(type)
    const confidence = Math.floor(Math.random() * 40 + 60)
    const priceTarget = isBullish
      ? asset.price * (1 + Math.random() * 0.2)
      : asset.price * (1 - Math.random() * 0.15)
    const stopLoss = isBullish
      ? asset.price * (1 - Math.random() * 0.05)
      : asset.price * (1 + Math.random() * 0.05)

    signals.push({
      id: `signal-${i}`,
      type,
      typeData: SIGNAL_TYPES[type],
      asset,
      timeframe,
      isBullish,
      confidence,
      currentPrice: asset.price,
      priceTarget,
      stopLoss,
      riskReward: Math.abs(priceTarget - asset.price) / Math.abs(asset.price - stopLoss),
      timestamp: Date.now() - Math.random() * 86400000,
      status: Math.random() > 0.3 ? 'active' : Math.random() > 0.5 ? 'hit' : 'stopped',
      performance: Math.random() > 0.5 ? (Math.random() * 20 - 5) : null,
      isTracking: Math.random() > 0.7,
      indicators: generateIndicators()
    })
  }

  return signals.sort((a, b) => b.timestamp - a.timestamp)
}

const generateIndicators = () => ({
  rsi: Math.random() * 100,
  macd: (Math.random() - 0.5) * 10,
  volume24h: Math.random() * 1000000000,
  volumeChange: (Math.random() - 0.4) * 200,
  ma50: Math.random() * 100,
  ma200: Math.random() * 100,
  bb_upper: Math.random() * 100,
  bb_lower: Math.random() * 100
})

// Generate performance stats
const generatePerformance = () => ({
  totalSignals: Math.floor(Math.random() * 500 + 200),
  winRate: Math.random() * 30 + 55,
  avgGain: Math.random() * 10 + 5,
  avgLoss: Math.random() * 5 + 2,
  profitFactor: Math.random() * 1.5 + 1.2,
  sharpeRatio: Math.random() * 1.5 + 0.5,
  maxDrawdown: Math.random() * 15 + 5,
  bestSignal: { asset: 'SOL', gain: Math.random() * 50 + 30 },
  activeSignals: Math.floor(Math.random() * 20 + 5)
})

export function TradingSignals() {
  const [signals, setSignals] = useState([])
  const [performance, setPerformance] = useState(null)
  const [selectedTimeframe, setSelectedTimeframe] = useState('all')
  const [selectedType, setSelectedType] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('signals') // signals, performance, alerts
  const [sortBy, setSortBy] = useState('time') // time, confidence, rr
  const [showBullish, setShowBullish] = useState(true)
  const [showBearish, setShowBearish] = useState(true)
  const [alerts, setAlerts] = useState([])

  // Initialize data
  useEffect(() => {
    setSignals(generateSignals())
    setPerformance(generatePerformance())

    // Simulate new signals
    const interval = setInterval(() => {
      setSignals(prev => {
        const signalTypes = Object.keys(SIGNAL_TYPES)
        const type = signalTypes[Math.floor(Math.random() * signalTypes.length)]
        const asset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
        const timeframe = TIMEFRAMES[Math.floor(Math.random() * TIMEFRAMES.length)]
        const isBullish = ['BREAKOUT', 'GOLDEN_CROSS', 'RSI_OVERSOLD', 'MACD_BULLISH'].includes(type)
        const confidence = Math.floor(Math.random() * 40 + 60)

        const newSignal = {
          id: `signal-${Date.now()}`,
          type,
          typeData: SIGNAL_TYPES[type],
          asset,
          timeframe,
          isBullish,
          confidence,
          currentPrice: asset.price * (1 + (Math.random() - 0.5) * 0.02),
          priceTarget: isBullish
            ? asset.price * (1 + Math.random() * 0.15)
            : asset.price * (1 - Math.random() * 0.1),
          stopLoss: isBullish
            ? asset.price * (1 - Math.random() * 0.05)
            : asset.price * (1 + Math.random() * 0.05),
          riskReward: Math.random() * 3 + 1,
          timestamp: Date.now(),
          status: 'active',
          isNew: true,
          indicators: generateIndicators()
        }

        // Add to alerts
        if (confidence > 80) {
          setAlerts(a => [{
            id: Date.now(),
            message: `${newSignal.typeData.label} on ${asset.symbol} (${confidence}% confidence)`,
            type: isBullish ? 'bullish' : 'bearish',
            timestamp: Date.now()
          }, ...a.slice(0, 4)])
        }

        setTimeout(() => {
          setSignals(s => s.map(sig => sig.id === newSignal.id ? { ...sig, isNew: false } : sig))
        }, 5000)

        return [newSignal, ...prev.slice(0, 29)]
      })
    }, 10000)

    return () => clearInterval(interval)
  }, [])

  // Filter signals
  const filteredSignals = useMemo(() => {
    return signals.filter(s => {
      if (selectedTimeframe !== 'all' && s.timeframe !== selectedTimeframe) return false
      if (selectedType !== 'all' && s.type !== selectedType) return false
      if (!showBullish && s.isBullish) return false
      if (!showBearish && !s.isBullish) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return s.asset.symbol.toLowerCase().includes(query) ||
               s.asset.name.toLowerCase().includes(query) ||
               s.typeData.label.toLowerCase().includes(query)
      }
      return true
    }).sort((a, b) => {
      switch (sortBy) {
        case 'confidence': return b.confidence - a.confidence
        case 'rr': return b.riskReward - a.riskReward
        default: return b.timestamp - a.timestamp
      }
    })
  }, [signals, selectedTimeframe, selectedType, searchQuery, sortBy, showBullish, showBearish])

  // Stats
  const stats = useMemo(() => {
    const activeSignals = signals.filter(s => s.status === 'active')
    const bullishCount = activeSignals.filter(s => s.isBullish).length
    const bearishCount = activeSignals.filter(s => !s.isBullish).length
    const avgConfidence = activeSignals.reduce((sum, s) => sum + s.confidence, 0) / activeSignals.length || 0

    return { activeSignals: activeSignals.length, bullishCount, bearishCount, avgConfidence }
  }, [signals])

  const formatNumber = (num) => {
    if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
    return `$${num.toFixed(2)}`
  }

  const formatTime = (timestamp) => {
    const diff = Date.now() - timestamp
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const toggleTracking = (signalId) => {
    setSignals(prev => prev.map(s =>
      s.id === signalId ? { ...s, isTracking: !s.isTracking } : s
    ))
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Signal className="w-6 h-6 text-green-400" />
          <h2 className="text-xl font-bold text-white">Trading Signals</h2>
          <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full animate-pulse">
            LIVE
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['signals', 'performance', 'alerts'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-green-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alerts Banner */}
      {alerts.length > 0 && viewMode !== 'alerts' && (
        <div className="space-y-2">
          {alerts.slice(0, 2).map(alert => (
            <div
              key={alert.id}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg animate-pulse ${
                alert.type === 'bullish' ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'
              }`}
            >
              <Zap className={`w-4 h-4 ${alert.type === 'bullish' ? 'text-green-400' : 'text-red-400'}`} />
              <span className={`text-sm ${alert.type === 'bullish' ? 'text-green-200' : 'text-red-200'}`}>
                {alert.message}
              </span>
              <span className="text-white/40 text-xs ml-auto">{formatTime(alert.timestamp)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Activity className="w-4 h-4" />
            <span>Active Signals</span>
          </div>
          <div className="text-2xl font-bold text-white">{stats.activeSignals}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <TrendingUp className="w-4 h-4" />
            <span>Bullish</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{stats.bullishCount}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <TrendingDown className="w-4 h-4" />
            <span>Bearish</span>
          </div>
          <div className="text-2xl font-bold text-red-400">{stats.bearishCount}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Target className="w-4 h-4" />
            <span>Avg Confidence</span>
          </div>
          <div className="text-2xl font-bold text-cyan-400">{stats.avgConfidence.toFixed(0)}%</div>
        </div>
      </div>

      {/* Filters */}
      {viewMode === 'signals' && (
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search by asset or signal type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-green-500"
            />
          </div>

          {/* Timeframe filter */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setSelectedTimeframe('all')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                selectedTimeframe === 'all'
                  ? 'bg-green-500 text-white'
                  : 'bg-white/5 text-white/60 hover:text-white'
              }`}
            >
              All
            </button>
            {TIMEFRAMES.slice(0, 5).map(tf => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                  selectedTimeframe === tf
                    ? 'bg-white/20 text-white'
                    : 'bg-white/5 text-white/60 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Bullish/Bearish toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowBullish(!showBullish)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all flex items-center gap-1.5 ${
                showBullish ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-white/40'
              }`}
            >
              <TrendingUp className="w-3 h-3" />
              Bullish
            </button>
            <button
              onClick={() => setShowBearish(!showBearish)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all flex items-center gap-1.5 ${
                showBearish ? 'bg-red-500/20 text-red-400' : 'bg-white/5 text-white/40'
              }`}
            >
              <TrendingDown className="w-3 h-3" />
              Bearish
            </button>
          </div>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
          >
            <option value="time">Latest</option>
            <option value="confidence">Confidence</option>
            <option value="rr">Risk/Reward</option>
          </select>
        </div>
      )}

      {/* Signals View */}
      {viewMode === 'signals' && (
        <div className="space-y-2">
          {filteredSignals.map(signal => (
            <div
              key={signal.id}
              className={`bg-white/5 rounded-xl p-4 border transition-all ${
                signal.isNew
                  ? 'border-green-500 animate-pulse'
                  : signal.status === 'hit'
                    ? 'border-green-500/50'
                    : signal.status === 'stopped'
                      ? 'border-red-500/50'
                      : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Signal type badge */}
                  <div
                    className="px-3 py-2 rounded-lg text-xs font-medium"
                    style={{
                      backgroundColor: `${signal.typeData.color}20`,
                      color: signal.typeData.color
                    }}
                  >
                    {signal.isBullish ? (
                      <TrendingUp className="w-4 h-4 inline mr-1" />
                    ) : (
                      <TrendingDown className="w-4 h-4 inline mr-1" />
                    )}
                    {signal.typeData.label}
                  </div>

                  {/* Asset */}
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-xs font-bold text-white">
                      {signal.asset.symbol.substring(0, 2)}
                    </div>
                    <div>
                      <div className="text-white font-medium">{signal.asset.symbol}</div>
                      <div className="text-white/40 text-xs">{signal.timeframe}</div>
                    </div>
                  </div>

                  {/* Status badges */}
                  {signal.isNew && (
                    <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded animate-pulse">
                      NEW
                    </span>
                  )}
                  {signal.status === 'hit' && (
                    <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                      TARGET HIT
                    </span>
                  )}
                  {signal.status === 'stopped' && (
                    <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">
                      STOPPED
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-6">
                  {/* Confidence */}
                  <div className="text-center">
                    <div className={`text-lg font-bold ${
                      signal.confidence >= 80 ? 'text-green-400' :
                      signal.confidence >= 60 ? 'text-yellow-400' : 'text-white/60'
                    }`}>
                      {signal.confidence}%
                    </div>
                    <div className="text-white/40 text-xs">Confidence</div>
                  </div>

                  {/* Price levels */}
                  <div className="text-right w-24">
                    <div className="text-white">${signal.currentPrice.toFixed(2)}</div>
                    <div className="text-white/40 text-xs">Current</div>
                  </div>

                  <div className="text-right w-24">
                    <div className={signal.isBullish ? 'text-green-400' : 'text-red-400'}>
                      ${signal.priceTarget.toFixed(2)}
                    </div>
                    <div className="text-white/40 text-xs">Target</div>
                  </div>

                  <div className="text-right w-20">
                    <div className="text-white/60">${signal.stopLoss.toFixed(2)}</div>
                    <div className="text-white/40 text-xs">Stop</div>
                  </div>

                  {/* R:R */}
                  <div className="text-center w-16">
                    <div className="text-cyan-400 font-medium">{signal.riskReward.toFixed(1)}:1</div>
                    <div className="text-white/40 text-xs">R:R</div>
                  </div>

                  {/* Time */}
                  <div className="text-white/40 text-sm w-20 text-right">
                    {formatTime(signal.timestamp)}
                  </div>

                  {/* Track button */}
                  <button
                    onClick={() => toggleTracking(signal.id)}
                    className={`p-2 rounded-lg transition-all ${
                      signal.isTracking
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-white/5 text-white/40 hover:text-white'
                    }`}
                  >
                    {signal.isTracking ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Indicators bar */}
              <div className="mt-3 pt-3 border-t border-white/10 flex items-center gap-6 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-white/40">RSI:</span>
                  <span className={
                    signal.indicators.rsi > 70 ? 'text-red-400' :
                    signal.indicators.rsi < 30 ? 'text-green-400' : 'text-white/60'
                  }>
                    {signal.indicators.rsi.toFixed(1)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/40">MACD:</span>
                  <span className={signal.indicators.macd >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {signal.indicators.macd.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/40">Vol 24h:</span>
                  <span className="text-white/60">{formatNumber(signal.indicators.volume24h)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/40">Vol Change:</span>
                  <span className={signal.indicators.volumeChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {signal.indicators.volumeChange >= 0 ? '+' : ''}{signal.indicators.volumeChange.toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Performance View */}
      {viewMode === 'performance' && performance && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Signal Performance</h3>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-white/40 text-sm mb-1">Total Signals</div>
                <div className="text-2xl font-bold text-white">{performance.totalSignals}</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Win Rate</div>
                <div className="text-2xl font-bold text-green-400">{performance.winRate.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Avg Gain</div>
                <div className="text-xl font-bold text-green-400">+{performance.avgGain.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Avg Loss</div>
                <div className="text-xl font-bold text-red-400">-{performance.avgLoss.toFixed(1)}%</div>
              </div>
            </div>
          </div>

          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Risk Metrics</h3>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-white/40 text-sm mb-1">Profit Factor</div>
                <div className="text-2xl font-bold text-cyan-400">{performance.profitFactor.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Sharpe Ratio</div>
                <div className="text-2xl font-bold text-purple-400">{performance.sharpeRatio.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Max Drawdown</div>
                <div className="text-xl font-bold text-red-400">-{performance.maxDrawdown.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-white/40 text-sm mb-1">Active Signals</div>
                <div className="text-xl font-bold text-white">{performance.activeSignals}</div>
              </div>
            </div>
          </div>

          <div className="bg-white/5 rounded-xl p-6 border border-white/10 col-span-2">
            <h3 className="text-white font-medium mb-4">Signal Type Performance</h3>
            <div className="grid grid-cols-4 gap-4">
              {Object.entries(SIGNAL_TYPES).slice(0, 8).map(([key, value]) => {
                const winRate = Math.random() * 30 + 50
                const count = Math.floor(Math.random() * 50 + 10)
                return (
                  <div key={key} className="p-3 bg-white/5 rounded-lg">
                    <div
                      className="text-sm font-medium mb-2"
                      style={{ color: value.color }}
                    >
                      {value.label}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-white text-lg font-bold">{winRate.toFixed(0)}%</span>
                      <span className="text-white/40 text-xs">{count} signals</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Alerts View */}
      {viewMode === 'alerts' && (
        <div className="space-y-2">
          {signals.filter(s => s.confidence >= 75).slice(0, 15).map(signal => (
            <div
              key={signal.id}
              className={`bg-white/5 rounded-xl p-4 border transition-all ${
                signal.isBullish ? 'border-green-500/30' : 'border-red-500/30'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    signal.isBullish ? 'bg-green-500/20' : 'bg-red-500/20'
                  }`}>
                    {signal.isBullish ? (
                      <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                  </div>

                  <div>
                    <div className="text-white font-medium">
                      {signal.typeData.label} on {signal.asset.symbol}
                    </div>
                    <div className="text-white/40 text-sm">{signal.typeData.description}</div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className={`text-lg font-bold ${
                    signal.confidence >= 85 ? 'text-green-400' : 'text-yellow-400'
                  }`}>
                    {signal.confidence}%
                  </div>

                  <div className="text-white/40 text-sm">
                    {formatTime(signal.timestamp)}
                  </div>

                  <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-all">
                    <Bell className="w-4 h-4 text-white/40" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default TradingSignals
