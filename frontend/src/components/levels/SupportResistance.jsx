import React, { useState, useMemo, useEffect } from 'react'
import {
  Layers,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Settings,
  Target,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Activity,
  Zap,
  Clock,
  Eye,
  EyeOff,
  BarChart3
} from 'lucide-react'

export function SupportResistance() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [showAllLevels, setShowAllLevels] = useState(false)
  const [viewMode, setViewMode] = useState('levels') // levels, zones, pivots
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY']
  const timeframes = ['15m', '1h', '4h', '1d', '1w']

  // Get current price for token
  const currentPrice = useMemo(() => {
    const prices = {
      'SOL': 178.50, 'ETH': 3456.00, 'BTC': 67500.00, 'BONK': 0.000025,
      'WIF': 2.85, 'JUP': 1.25, 'RNDR': 8.50, 'PYTH': 0.45, 'JTO': 3.20, 'RAY': 4.50
    }
    return prices[selectedToken] || 100
  }, [selectedToken])

  // Generate support and resistance levels
  const levels = useMemo(() => {
    const resistance = []
    const support = []

    // Generate resistance levels above current price
    for (let i = 1; i <= 8; i++) {
      const price = currentPrice * (1 + i * 0.02 + Math.random() * 0.01)
      const strength = Math.max(10, 100 - i * 10 + Math.floor(Math.random() * 20))
      const touches = Math.floor(Math.random() * 10) + 1
      const isKey = strength > 70

      resistance.push({
        type: 'resistance',
        price,
        strength,
        touches,
        isKey,
        distance: ((price - currentPrice) / currentPrice * 100).toFixed(2),
        source: ['Pivot', 'Swing High', 'Fib 0.618', 'Volume Profile', 'Previous High'][Math.floor(Math.random() * 5)],
        lastTest: `${Math.floor(Math.random() * 48) + 1}h ago`,
        rejected: Math.random() > 0.3
      })
    }

    // Generate support levels below current price
    for (let i = 1; i <= 8; i++) {
      const price = currentPrice * (1 - i * 0.02 - Math.random() * 0.01)
      const strength = Math.max(10, 100 - i * 10 + Math.floor(Math.random() * 20))
      const touches = Math.floor(Math.random() * 10) + 1
      const isKey = strength > 70

      support.push({
        type: 'support',
        price,
        strength,
        touches,
        isKey,
        distance: ((currentPrice - price) / currentPrice * 100).toFixed(2),
        source: ['Pivot', 'Swing Low', 'Fib 0.382', 'Volume Profile', 'Previous Low'][Math.floor(Math.random() * 5)],
        lastTest: `${Math.floor(Math.random() * 48) + 1}h ago`,
        held: Math.random() > 0.3
      })
    }

    return { resistance, support }
  }, [currentPrice, selectedToken, timeframe])

  // Generate zones (price ranges)
  const zones = useMemo(() => {
    return [
      {
        type: 'resistance_zone',
        high: currentPrice * 1.05,
        low: currentPrice * 1.03,
        strength: 85,
        label: 'Strong Supply Zone',
        color: 'red'
      },
      {
        type: 'resistance_zone',
        high: currentPrice * 1.10,
        low: currentPrice * 1.08,
        strength: 65,
        label: 'Weak Supply Zone',
        color: 'orange'
      },
      {
        type: 'support_zone',
        high: currentPrice * 0.97,
        low: currentPrice * 0.95,
        strength: 90,
        label: 'Strong Demand Zone',
        color: 'green'
      },
      {
        type: 'support_zone',
        high: currentPrice * 0.92,
        low: currentPrice * 0.90,
        strength: 55,
        label: 'Weak Demand Zone',
        color: 'emerald'
      }
    ]
  }, [currentPrice])

  // Generate pivot points
  const pivots = useMemo(() => {
    const high = currentPrice * 1.03
    const low = currentPrice * 0.97
    const close = currentPrice
    const pp = (high + low + close) / 3

    return {
      pp,
      r1: (2 * pp) - low,
      r2: pp + (high - low),
      r3: high + 2 * (pp - low),
      s1: (2 * pp) - high,
      s2: pp - (high - low),
      s3: low - 2 * (high - pp),
      camarilla: {
        r1: close + (high - low) * 1.1 / 12,
        r2: close + (high - low) * 1.1 / 6,
        r3: close + (high - low) * 1.1 / 4,
        r4: close + (high - low) * 1.1 / 2,
        s1: close - (high - low) * 1.1 / 12,
        s2: close - (high - low) * 1.1 / 6,
        s3: close - (high - low) * 1.1 / 4,
        s4: close - (high - low) * 1.1 / 2
      },
      fibonacci: {
        r1: pp + 0.382 * (high - low),
        r2: pp + 0.618 * (high - low),
        r3: pp + 1.000 * (high - low),
        s1: pp - 0.382 * (high - low),
        s2: pp - 0.618 * (high - low),
        s3: pp - 1.000 * (high - low)
      }
    }
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

  // Key levels (closest support and resistance)
  const keySupport = levels.support.filter(l => l.isKey)[0]
  const keyResistance = levels.resistance.filter(l => l.isKey)[0]

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Layers className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold text-white">Support & Resistance</h2>
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

      {/* Current Price */}
      <div className="bg-white/5 rounded-lg p-4 border border-white/10 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-gray-400 text-sm">Current Price</div>
            <div className="text-3xl font-bold text-white">${formatPrice(currentPrice)}</div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-4">
              {keySupport && (
                <div>
                  <div className="text-gray-400 text-xs">Nearest Support</div>
                  <div className="text-green-400 font-medium">${formatPrice(keySupport.price)}</div>
                  <div className="text-xs text-gray-500">{keySupport.distance}% away</div>
                </div>
              )}
              {keyResistance && (
                <div>
                  <div className="text-gray-400 text-xs">Nearest Resistance</div>
                  <div className="text-red-400 font-medium">${formatPrice(keyResistance.price)}</div>
                  <div className="text-xs text-gray-500">{keyResistance.distance}% away</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'levels', label: 'Price Levels' },
          { id: 'zones', label: 'Supply/Demand' },
          { id: 'pivots', label: 'Pivot Points' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Levels Mode */}
      {viewMode === 'levels' && (
        <div className="space-y-6">
          {/* Visual Chart */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="h-64 relative">
              {/* Current Price Line */}
              <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 border-t-2 border-dashed border-white/30 z-10">
                <span className="absolute -right-2 -top-3 px-2 py-0.5 bg-white/20 rounded text-xs text-white">
                  ${formatPrice(currentPrice)}
                </span>
              </div>

              {/* Resistance Levels */}
              {levels.resistance.slice(0, showAllLevels ? 8 : 4).map((level, i) => {
                const position = 50 - (i + 1) * 6
                return (
                  <div
                    key={`r-${i}`}
                    className="absolute left-0 right-0 border-t border-red-500/50"
                    style={{ top: `${position}%` }}
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-red-400">${formatPrice(level.price)}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-1 bg-red-500/50 rounded" style={{ width: `${level.strength}px` }} />
                        {level.isKey && <Target className="w-3 h-3 text-red-400" />}
                      </div>
                    </div>
                  </div>
                )
              })}

              {/* Support Levels */}
              {levels.support.slice(0, showAllLevels ? 8 : 4).map((level, i) => {
                const position = 50 + (i + 1) * 6
                return (
                  <div
                    key={`s-${i}`}
                    className="absolute left-0 right-0 border-t border-green-500/50"
                    style={{ top: `${position}%` }}
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-green-400">${formatPrice(level.price)}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-1 bg-green-500/50 rounded" style={{ width: `${level.strength}px` }} />
                        {level.isKey && <Target className="w-3 h-3 text-green-400" />}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex justify-center mt-2">
              <button
                onClick={() => setShowAllLevels(!showAllLevels)}
                className="text-gray-400 text-sm hover:text-white flex items-center gap-1"
              >
                {showAllLevels ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                {showAllLevels ? 'Show Less' : 'Show All Levels'}
              </button>
            </div>
          </div>

          {/* Levels Table */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Resistance */}
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Resistance Levels
              </h3>
              <div className="space-y-2">
                {levels.resistance.slice(0, 5).map((level, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-red-500/10 rounded">
                    <div>
                      <span className="text-white font-medium">${formatPrice(level.price)}</span>
                      <span className="text-gray-500 text-xs ml-2">+{level.distance}%</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-400">{level.source}</span>
                      <span className="text-gray-400">{level.touches} touches</span>
                      <div className="w-12 h-1.5 bg-white/10 rounded">
                        <div className="h-full bg-red-500 rounded" style={{ width: `${level.strength}%` }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Support */}
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
                <TrendingDown className="w-4 h-4" />
                Support Levels
              </h3>
              <div className="space-y-2">
                {levels.support.slice(0, 5).map((level, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-green-500/10 rounded">
                    <div>
                      <span className="text-white font-medium">${formatPrice(level.price)}</span>
                      <span className="text-gray-500 text-xs ml-2">-{level.distance}%</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-400">{level.source}</span>
                      <span className="text-gray-400">{level.touches} touches</span>
                      <div className="w-12 h-1.5 bg-white/10 rounded">
                        <div className="h-full bg-green-500 rounded" style={{ width: `${level.strength}%` }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Zones Mode */}
      {viewMode === 'zones' && (
        <div className="space-y-4">
          {zones.map((zone, i) => (
            <div
              key={i}
              className={`p-4 rounded-lg border ${
                zone.type.includes('resistance')
                  ? 'bg-red-500/10 border-red-500/20'
                  : 'bg-green-500/10 border-green-500/20'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className={`font-medium ${zone.type.includes('resistance') ? 'text-red-400' : 'text-green-400'}`}>
                  {zone.label}
                </span>
                <span className="text-white">Strength: {zone.strength}%</span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-gray-400">High: ${formatPrice(zone.high)}</span>
                <span className="text-gray-400">Low: ${formatPrice(zone.low)}</span>
                <span className="text-gray-500">
                  {((Math.abs(currentPrice - (zone.high + zone.low) / 2) / currentPrice) * 100).toFixed(1)}% from price
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pivots Mode */}
      {viewMode === 'pivots' && (
        <div className="space-y-6">
          {/* Standard Pivot Points */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Standard Pivot Points</h3>
            <div className="grid grid-cols-7 gap-2 text-center">
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R3</div>
                <div className="text-red-400">${formatPrice(pivots.r3)}</div>
              </div>
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R2</div>
                <div className="text-red-400">${formatPrice(pivots.r2)}</div>
              </div>
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R1</div>
                <div className="text-red-400">${formatPrice(pivots.r1)}</div>
              </div>
              <div className="p-2 bg-blue-500/10 rounded">
                <div className="text-xs text-gray-500">PP</div>
                <div className="text-blue-400">${formatPrice(pivots.pp)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S1</div>
                <div className="text-green-400">${formatPrice(pivots.s1)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S2</div>
                <div className="text-green-400">${formatPrice(pivots.s2)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S3</div>
                <div className="text-green-400">${formatPrice(pivots.s3)}</div>
              </div>
            </div>
          </div>

          {/* Fibonacci Pivot Points */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Fibonacci Pivot Points</h3>
            <div className="grid grid-cols-7 gap-2 text-center">
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R3</div>
                <div className="text-red-400">${formatPrice(pivots.fibonacci.r3)}</div>
              </div>
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R2</div>
                <div className="text-red-400">${formatPrice(pivots.fibonacci.r2)}</div>
              </div>
              <div className="p-2 bg-red-500/10 rounded">
                <div className="text-xs text-gray-500">R1</div>
                <div className="text-red-400">${formatPrice(pivots.fibonacci.r1)}</div>
              </div>
              <div className="p-2 bg-blue-500/10 rounded">
                <div className="text-xs text-gray-500">PP</div>
                <div className="text-blue-400">${formatPrice(pivots.pp)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S1</div>
                <div className="text-green-400">${formatPrice(pivots.fibonacci.s1)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S2</div>
                <div className="text-green-400">${formatPrice(pivots.fibonacci.s2)}</div>
              </div>
              <div className="p-2 bg-green-500/10 rounded">
                <div className="text-xs text-gray-500">S3</div>
                <div className="text-green-400">${formatPrice(pivots.fibonacci.s3)}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SupportResistance
