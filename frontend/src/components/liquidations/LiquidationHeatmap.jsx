import React, { useState, useMemo, useEffect } from 'react'
import {
  Flame,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertTriangle,
  DollarSign,
  Target,
  ChevronDown,
  ChevronUp,
  Activity,
  Clock,
  Zap,
  BarChart3
} from 'lucide-react'

export function LiquidationHeatmap() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('24h')
  const [viewMode, setViewMode] = useState('heatmap') // heatmap, levels, recent
  const [leverage, setLeverage] = useState('all')
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '24h', '7d']
  const leverages = ['all', '5x', '10x', '25x', '50x', '100x']

  // Get current price
  const currentPrice = useMemo(() => {
    const prices = {
      'SOL': 178.50, 'ETH': 3456.00, 'BTC': 67500.00, 'BONK': 0.000025,
      'WIF': 2.85, 'JUP': 1.25, 'RNDR': 8.50, 'PYTH': 0.45
    }
    return prices[selectedToken] || 100
  }, [selectedToken])

  // Generate liquidation levels
  const liquidationLevels = useMemo(() => {
    const levels = []

    // Generate long liquidation levels (below current price)
    for (let i = 1; i <= 20; i++) {
      const priceOffset = i * 0.01
      const price = currentPrice * (1 - priceOffset)
      const intensity = Math.max(0, 100 - i * 4 + Math.floor(Math.random() * 20))
      const volume = Math.floor(Math.random() * 10000000) + 500000
      const positions = Math.floor(Math.random() * 1000) + 50

      levels.push({
        type: 'long',
        price,
        intensity,
        volume,
        positions,
        leverage: [5, 10, 25, 50, 100][Math.floor(Math.random() * 5)],
        distance: (priceOffset * 100).toFixed(2)
      })
    }

    // Generate short liquidation levels (above current price)
    for (let i = 1; i <= 20; i++) {
      const priceOffset = i * 0.01
      const price = currentPrice * (1 + priceOffset)
      const intensity = Math.max(0, 100 - i * 4 + Math.floor(Math.random() * 20))
      const volume = Math.floor(Math.random() * 10000000) + 500000
      const positions = Math.floor(Math.random() * 1000) + 50

      levels.push({
        type: 'short',
        price,
        intensity,
        volume,
        positions,
        leverage: [5, 10, 25, 50, 100][Math.floor(Math.random() * 5)],
        distance: (priceOffset * 100).toFixed(2)
      })
    }

    return levels
  }, [currentPrice, selectedToken])

  // Filter by leverage
  const filteredLevels = useMemo(() => {
    if (leverage === 'all') return liquidationLevels
    const lev = parseInt(leverage)
    return liquidationLevels.filter(l => l.leverage === lev)
  }, [liquidationLevels, leverage])

  // Calculate totals
  const totals = useMemo(() => {
    const longLevels = filteredLevels.filter(l => l.type === 'long')
    const shortLevels = filteredLevels.filter(l => l.type === 'short')

    return {
      totalLongVolume: longLevels.reduce((sum, l) => sum + l.volume, 0),
      totalShortVolume: shortLevels.reduce((sum, l) => sum + l.volume, 0),
      totalLongPositions: longLevels.reduce((sum, l) => sum + l.positions, 0),
      totalShortPositions: shortLevels.reduce((sum, l) => sum + l.positions, 0),
      nearestLong: longLevels.sort((a, b) => b.price - a.price)[0],
      nearestShort: shortLevels.sort((a, b) => a.price - b.price)[0],
      highestIntensityLong: longLevels.sort((a, b) => b.intensity - a.intensity)[0],
      highestIntensityShort: shortLevels.sort((a, b) => b.intensity - a.intensity)[0]
    }
  }, [filteredLevels])

  // Recent liquidations
  const recentLiquidations = useMemo(() => {
    return Array.from({ length: 20 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'long' : 'short',
      price: currentPrice * (1 + (Math.random() - 0.5) * 0.1),
      size: Math.floor(Math.random() * 500000) + 10000,
      leverage: [5, 10, 25, 50, 100][Math.floor(Math.random() * 5)],
      exchange: ['Binance', 'Bybit', 'OKX', 'dYdX'][Math.floor(Math.random() * 4)],
      time: new Date(Date.now() - i * 60000 * Math.random() * 30)
    })).sort((a, b) => b.time - a.time)
  }, [currentPrice])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(2)
    if (price >= 1) return price.toFixed(4)
    return price.toFixed(6)
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(0)
  }

  const formatTime = (date) => {
    const diff = Date.now() - date.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    return `${hours}h ago`
  }

  const getIntensityColor = (intensity, type) => {
    if (type === 'long') {
      if (intensity > 70) return 'bg-green-500'
      if (intensity > 40) return 'bg-green-500/70'
      return 'bg-green-500/40'
    } else {
      if (intensity > 70) return 'bg-red-500'
      if (intensity > 40) return 'bg-red-500/70'
      return 'bg-red-500/40'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Flame className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold text-white">Liquidation Heatmap</h2>
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

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
          <div className="text-gray-400 text-sm mb-1">Long Liquidations</div>
          <div className="text-2xl font-bold text-green-400">${formatNumber(totals.totalLongVolume)}</div>
          <div className="text-xs text-gray-500">{totals.totalLongPositions} positions</div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
          <div className="text-gray-400 text-sm mb-1">Short Liquidations</div>
          <div className="text-2xl font-bold text-red-400">${formatNumber(totals.totalShortVolume)}</div>
          <div className="text-xs text-gray-500">{totals.totalShortPositions} positions</div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Nearest Long Liq</div>
          <div className="text-xl font-bold text-white">
            ${formatPrice(totals.nearestLong?.price || 0)}
          </div>
          <div className="text-xs text-gray-500">-{totals.nearestLong?.distance}%</div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Nearest Short Liq</div>
          <div className="text-xl font-bold text-white">
            ${formatPrice(totals.nearestShort?.price || 0)}
          </div>
          <div className="text-xs text-gray-500">+{totals.nearestShort?.distance}%</div>
        </div>
      </div>

      {/* Leverage Filter */}
      <div className="flex gap-2 mb-4">
        {leverages.map(lev => (
          <button
            key={lev}
            onClick={() => setLeverage(lev)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              leverage === lev
                ? 'bg-orange-500/20 text-orange-400'
                : 'bg-white/5 text-gray-400 hover:bg-white/10'
            }`}
          >
            {lev === 'all' ? 'All' : lev}
          </button>
        ))}
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'heatmap', label: 'Heatmap' },
          { id: 'levels', label: 'Price Levels' },
          { id: 'recent', label: 'Recent Liqs' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Heatmap Mode */}
      {viewMode === 'heatmap' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="relative h-96">
            {/* Short liquidations (above) */}
            <div className="absolute top-0 left-0 right-0 h-[45%] flex flex-col justify-end">
              {filteredLevels
                .filter(l => l.type === 'short')
                .sort((a, b) => a.price - b.price)
                .slice(0, 15)
                .map((level, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 py-0.5"
                    title={`$${formatNumber(level.volume)} at $${formatPrice(level.price)}`}
                  >
                    <div className="w-20 text-xs text-gray-500 text-right">+{level.distance}%</div>
                    <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                      <div
                        className={`h-full ${getIntensityColor(level.intensity, 'short')} rounded`}
                        style={{ width: `${level.intensity}%` }}
                      />
                    </div>
                    <div className="w-16 text-xs text-gray-500">${formatNumber(level.volume)}</div>
                  </div>
                ))}
            </div>

            {/* Current Price Line */}
            <div className="absolute top-[45%] left-0 right-0 h-[10%] flex items-center">
              <div className="flex-1 border-t-2 border-dashed border-white/50" />
              <div className="px-3 py-1 bg-white/20 rounded text-white text-sm font-medium">
                ${formatPrice(currentPrice)}
              </div>
              <div className="flex-1 border-t-2 border-dashed border-white/50" />
            </div>

            {/* Long liquidations (below) */}
            <div className="absolute bottom-0 left-0 right-0 h-[45%] flex flex-col justify-start">
              {filteredLevels
                .filter(l => l.type === 'long')
                .sort((a, b) => b.price - a.price)
                .slice(0, 15)
                .map((level, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 py-0.5"
                    title={`$${formatNumber(level.volume)} at $${formatPrice(level.price)}`}
                  >
                    <div className="w-20 text-xs text-gray-500 text-right">-{level.distance}%</div>
                    <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                      <div
                        className={`h-full ${getIntensityColor(level.intensity, 'long')} rounded`}
                        style={{ width: `${level.intensity}%` }}
                      />
                    </div>
                    <div className="w-16 text-xs text-gray-500">${formatNumber(level.volume)}</div>
                  </div>
                ))}
            </div>
          </div>

          {/* Legend */}
          <div className="flex justify-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-red-500 rounded" />
              <span className="text-gray-400">Short Liquidations (Price Up)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded" />
              <span className="text-gray-400">Long Liquidations (Price Down)</span>
            </div>
          </div>
        </div>
      )}

      {/* Levels Mode */}
      {viewMode === 'levels' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Long Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
              <TrendingDown className="w-4 h-4" />
              Long Liquidation Levels
            </h3>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {filteredLevels
                .filter(l => l.type === 'long')
                .sort((a, b) => b.price - a.price)
                .slice(0, 15)
                .map((level, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-green-500/10 rounded">
                    <div>
                      <span className="text-white">${formatPrice(level.price)}</span>
                      <span className="text-gray-500 text-xs ml-2">-{level.distance}%</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-400">{level.leverage}x</span>
                      <span className="text-green-400">${formatNumber(level.volume)}</span>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Short Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Short Liquidation Levels
            </h3>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {filteredLevels
                .filter(l => l.type === 'short')
                .sort((a, b) => a.price - b.price)
                .slice(0, 15)
                .map((level, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-red-500/10 rounded">
                    <div>
                      <span className="text-white">${formatPrice(level.price)}</span>
                      <span className="text-gray-500 text-xs ml-2">+{level.distance}%</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-400">{level.leverage}x</span>
                      <span className="text-red-400">${formatNumber(level.volume)}</span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Recent Mode */}
      {viewMode === 'recent' && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {recentLiquidations.map(liq => (
            <div
              key={liq.id}
              className={`p-3 rounded-lg border ${
                liq.type === 'long'
                  ? 'bg-green-500/10 border-green-500/20'
                  : 'bg-red-500/10 border-red-500/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {liq.type === 'long' ? (
                    <TrendingDown className="w-5 h-5 text-green-400" />
                  ) : (
                    <TrendingUp className="w-5 h-5 text-red-400" />
                  )}
                  <div>
                    <span className={`font-medium ${liq.type === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                      {liq.type.toUpperCase()}
                    </span>
                    <span className="text-white ml-2">{selectedToken}</span>
                    <span className="text-gray-500 text-sm ml-2">{liq.leverage}x @ ${formatPrice(liq.price)}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">${formatNumber(liq.size)}</div>
                  <div className="text-gray-500 text-xs">{liq.exchange} - {formatTime(liq.time)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default LiquidationHeatmap
