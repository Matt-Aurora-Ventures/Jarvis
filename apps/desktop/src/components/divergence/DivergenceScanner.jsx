import React, { useState, useMemo, useEffect } from 'react'
import {
  GitBranch,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Filter,
  Bell,
  BellOff,
  AlertTriangle,
  CheckCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Activity,
  BarChart3,
  Target,
  Zap,
  Eye
} from 'lucide-react'

export function DivergenceScanner() {
  const [selectedIndicator, setSelectedIndicator] = useState('all')
  const [selectedTimeframe, setSelectedTimeframe] = useState('all')
  const [selectedType, setSelectedType] = useState('all')
  const [alertsEnabled, setAlertsEnabled] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [viewMode, setViewMode] = useState('scanner') // scanner, alerts, settings

  const indicators = [
    { id: 'all', name: 'All Indicators' },
    { id: 'rsi', name: 'RSI' },
    { id: 'macd', name: 'MACD' },
    { id: 'obv', name: 'OBV' },
    { id: 'mfi', name: 'MFI' },
    { id: 'cci', name: 'CCI' },
    { id: 'stoch', name: 'Stochastic' },
    { id: 'williams', name: 'Williams %R' }
  ]

  const timeframes = [
    { id: 'all', name: 'All Timeframes' },
    { id: '5m', name: '5 Minutes' },
    { id: '15m', name: '15 Minutes' },
    { id: '1h', name: '1 Hour' },
    { id: '4h', name: '4 Hours' },
    { id: '1d', name: 'Daily' }
  ]

  const divergenceTypes = [
    { id: 'all', name: 'All Types' },
    { id: 'bullish_regular', name: 'Bullish Regular', color: 'text-green-400', bg: 'bg-green-500/20' },
    { id: 'bearish_regular', name: 'Bearish Regular', color: 'text-red-400', bg: 'bg-red-500/20' },
    { id: 'bullish_hidden', name: 'Bullish Hidden', color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
    { id: 'bearish_hidden', name: 'Bearish Hidden', color: 'text-orange-400', bg: 'bg-orange-500/20' }
  ]

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY', 'AVAX', 'LINK', 'DOT', 'ATOM', 'NEAR']

  // Generate mock divergences
  const divergences = useMemo(() => {
    const types = ['bullish_regular', 'bearish_regular', 'bullish_hidden', 'bearish_hidden']
    const indicatorIds = ['rsi', 'macd', 'obv', 'mfi', 'cci', 'stoch', 'williams']
    const timeframeIds = ['5m', '15m', '1h', '4h', '1d']

    return Array.from({ length: 40 }, (_, i) => {
      const type = types[Math.floor(Math.random() * types.length)]
      const indicator = indicatorIds[Math.floor(Math.random() * indicatorIds.length)]
      const timeframe = timeframeIds[Math.floor(Math.random() * timeframeIds.length)]
      const token = tokens[Math.floor(Math.random() * tokens.length)]
      const strength = Math.floor(Math.random() * 100) + 1
      const priceChange = (Math.random() - 0.5) * 10
      const indicatorValue = Math.random() * 100
      const price = Math.random() * 200 + 10

      return {
        id: i + 1,
        token,
        type,
        indicator,
        timeframe,
        strength,
        price,
        priceChange,
        indicatorValue,
        timestamp: new Date(Date.now() - i * 60000 * Math.random() * 60),
        priceLow: price * 0.95,
        priceHigh: price * 1.05,
        indicatorLow: indicatorValue * 0.9,
        indicatorHigh: indicatorValue * 1.1,
        confirmed: Math.random() > 0.3,
        isNew: Math.random() > 0.7
      }
    }).sort((a, b) => b.timestamp - a.timestamp)
  }, [])

  // Filter divergences
  const filteredDivergences = useMemo(() => {
    return divergences.filter(div => {
      if (selectedIndicator !== 'all' && div.indicator !== selectedIndicator) return false
      if (selectedTimeframe !== 'all' && div.timeframe !== selectedTimeframe) return false
      if (selectedType !== 'all' && div.type !== selectedType) return false
      return true
    })
  }, [divergences, selectedIndicator, selectedTimeframe, selectedType])

  // Statistics
  const stats = useMemo(() => {
    const bullish = divergences.filter(d => d.type.includes('bullish')).length
    const bearish = divergences.filter(d => d.type.includes('bearish')).length
    const regular = divergences.filter(d => d.type.includes('regular')).length
    const hidden = divergences.filter(d => d.type.includes('hidden')).length
    const confirmed = divergences.filter(d => d.confirmed).length

    return {
      total: divergences.length,
      bullish,
      bearish,
      regular,
      hidden,
      confirmed,
      avgStrength: (divergences.reduce((sum, d) => sum + d.strength, 0) / divergences.length).toFixed(1)
    }
  }, [divergences])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatTime = (date) => {
    const diff = Date.now() - date.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  const getTypeConfig = (type) => {
    return divergenceTypes.find(t => t.id === type) || divergenceTypes[0]
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <GitBranch className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Divergence Scanner</h2>
          <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
            {filteredDivergences.length} found
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAlertsEnabled(!alertsEnabled)}
            className={`p-2 rounded-lg ${alertsEnabled ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5 text-gray-400'}`}
          >
            {alertsEnabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
          </button>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'scanner', label: 'Scanner' },
          { id: 'alerts', label: 'Active Alerts' },
          { id: 'settings', label: 'Settings' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Scanner Mode */}
      {viewMode === 'scanner' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <select
              value={selectedIndicator}
              onChange={(e) => setSelectedIndicator(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              {indicators.map(ind => (
                <option key={ind.id} value={ind.id}>{ind.name}</option>
              ))}
            </select>
            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              {timeframes.map(tf => (
                <option key={tf.id} value={tf.id}>{tf.name}</option>
              ))}
            </select>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              {divergenceTypes.map(type => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
              <div className="text-gray-400 text-xs">Bullish</div>
              <div className="text-xl font-bold text-green-400">{stats.bullish}</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
              <div className="text-gray-400 text-xs">Bearish</div>
              <div className="text-xl font-bold text-red-400">{stats.bearish}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Confirmed</div>
              <div className="text-xl font-bold text-white">{stats.confirmed}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Avg Strength</div>
              <div className="text-xl font-bold text-white">{stats.avgStrength}%</div>
            </div>
          </div>

          {/* Divergence List */}
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {filteredDivergences.map(div => {
              const typeConfig = getTypeConfig(div.type)
              return (
                <div
                  key={div.id}
                  className={`p-4 rounded-lg border transition-colors ${
                    div.isNew ? 'bg-purple-500/10 border-purple-500/30' : 'bg-white/5 border-white/10'
                  } hover:bg-white/10`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${typeConfig.bg}`}>
                        {div.type.includes('bullish') ? (
                          <TrendingUp className={`w-5 h-5 ${typeConfig.color}`} />
                        ) : (
                          <TrendingDown className={`w-5 h-5 ${typeConfig.color}`} />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{div.token}</span>
                          <span className={`px-2 py-0.5 rounded text-xs ${typeConfig.bg} ${typeConfig.color}`}>
                            {typeConfig.name.replace('Bullish ', '').replace('Bearish ', '')}
                          </span>
                          <span className="px-2 py-0.5 bg-white/10 rounded text-xs text-gray-300">
                            {div.indicator.toUpperCase()}
                          </span>
                          <span className="text-gray-500 text-xs">{div.timeframe}</span>
                          {div.isNew && (
                            <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded animate-pulse">
                              NEW
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-400 mt-1">
                          <span>Price: ${div.price.toFixed(2)}</span>
                          <span>{div.indicator.toUpperCase()}: {div.indicatorValue.toFixed(1)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-2 justify-end">
                        <span className="text-gray-400 text-sm">Strength:</span>
                        <div className="w-16 h-2 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              div.strength > 70 ? 'bg-green-500' :
                              div.strength > 40 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${div.strength}%` }}
                          />
                        </div>
                        <span className="text-white text-sm w-10">{div.strength}%</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-500 mt-1 justify-end">
                        {div.confirmed ? (
                          <span className="flex items-center gap-1 text-green-400">
                            <CheckCircle className="w-3 h-3" />
                            Confirmed
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-yellow-400">
                            <Clock className="w-3 h-3" />
                            Pending
                          </span>
                        )}
                        <span>{formatTime(div.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Alerts Mode */}
      {viewMode === 'alerts' && (
        <div className="space-y-4">
          <div className="text-gray-400 text-sm">
            {alertsEnabled ? 'Alerts are enabled. You will be notified of new divergences.' : 'Alerts are disabled.'}
          </div>
          <div className="space-y-2">
            {filteredDivergences.filter(d => d.isNew).map(div => {
              const typeConfig = getTypeConfig(div.type)
              return (
                <div key={div.id} className="p-4 bg-purple-500/10 rounded-lg border border-purple-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="w-5 h-5 text-purple-400" />
                    <div>
                      <span className="text-white font-medium">{div.token}</span>
                      <span className={`ml-2 ${typeConfig.color}`}>{typeConfig.name}</span>
                      <span className="text-gray-400 text-sm ml-2">on {div.indicator.toUpperCase()} ({div.timeframe})</span>
                    </div>
                  </div>
                  <span className="text-gray-500 text-sm">{formatTime(div.timestamp)}</span>
                </div>
              )
            })}
            {filteredDivergences.filter(d => d.isNew).length === 0 && (
              <div className="text-center py-8 text-gray-500">
                No new alerts
              </div>
            )}
          </div>
        </div>
      )}

      {/* Settings Mode */}
      {viewMode === 'settings' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Divergence Detection Settings</h3>
            <div className="space-y-4">
              <div>
                <label className="text-gray-400 text-sm block mb-2">Minimum Strength (%)</label>
                <input
                  type="range"
                  min="10"
                  max="90"
                  defaultValue="30"
                  className="w-full"
                />
              </div>
              <div>
                <label className="text-gray-400 text-sm block mb-2">Lookback Period (candles)</label>
                <input
                  type="number"
                  defaultValue="14"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-gray-400 text-sm">
                  <input type="checkbox" className="rounded bg-white/10" defaultChecked />
                  Show only confirmed divergences
                </label>
              </div>
              <div>
                <label className="flex items-center gap-2 text-gray-400 text-sm">
                  <input type="checkbox" className="rounded bg-white/10" defaultChecked />
                  Include hidden divergences
                </label>
              </div>
            </div>
          </div>

          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Alert Tokens</h3>
            <div className="flex flex-wrap gap-2">
              {tokens.map(token => (
                <label key={token} className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg cursor-pointer hover:bg-white/10">
                  <input type="checkbox" className="rounded bg-white/10" defaultChecked />
                  <span className="text-white text-sm">{token}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DivergenceScanner
