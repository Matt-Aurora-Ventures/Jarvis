import React, { useState, useMemo, useEffect } from 'react'
import {
  GitMerge,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  Target,
  Activity,
  AlertTriangle,
  CheckCircle,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  Circle,
  Clock,
  Eye,
  BarChart3,
  Zap
} from 'lucide-react'

export function MarketStructure() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [viewMode, setViewMode] = useState('overview') // overview, swings, breaks, analysis
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY']
  const timeframes = ['15m', '1h', '4h', '1d', '1w']

  // Get current price
  const currentPrice = useMemo(() => {
    const prices = {
      'SOL': 178.50, 'ETH': 3456.00, 'BTC': 67500.00, 'BONK': 0.000025,
      'WIF': 2.85, 'JUP': 1.25, 'RNDR': 8.50, 'PYTH': 0.45, 'JTO': 3.20, 'RAY': 4.50
    }
    return prices[selectedToken] || 100
  }, [selectedToken])

  // Generate market structure data
  const structureData = useMemo(() => {
    const trends = ['bullish', 'bearish', 'ranging']
    const trend = trends[Math.floor(Math.random() * trends.length)]

    // Generate swing points
    const swingHighs = Array.from({ length: 5 }, (_, i) => ({
      id: `HH-${i}`,
      type: Math.random() > 0.5 ? 'HH' : 'LH', // Higher High or Lower High
      price: currentPrice * (1.02 + i * 0.015 + Math.random() * 0.01),
      time: new Date(Date.now() - (i + 1) * 24 * 60 * 60 * 1000),
      confirmed: Math.random() > 0.2,
      strength: Math.floor(Math.random() * 50) + 50
    }))

    const swingLows = Array.from({ length: 5 }, (_, i) => ({
      id: `HL-${i}`,
      type: Math.random() > 0.5 ? 'HL' : 'LL', // Higher Low or Lower Low
      price: currentPrice * (0.98 - i * 0.015 - Math.random() * 0.01),
      time: new Date(Date.now() - (i + 1) * 24 * 60 * 60 * 1000),
      confirmed: Math.random() > 0.2,
      strength: Math.floor(Math.random() * 50) + 50
    }))

    // Structure breaks
    const breaks = Array.from({ length: 8 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'BOS' : 'CHoCH', // Break of Structure or Change of Character
      direction: Math.random() > 0.5 ? 'bullish' : 'bearish',
      price: currentPrice * (1 + (Math.random() - 0.5) * 0.1),
      time: new Date(Date.now() - i * 6 * 60 * 60 * 1000),
      significance: ['minor', 'moderate', 'major'][Math.floor(Math.random() * 3)],
      confirmed: Math.random() > 0.3
    }))

    // Order blocks
    const orderBlocks = Array.from({ length: 4 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'bullish' : 'bearish',
      high: currentPrice * (1 + (Math.random() - 0.5) * 0.05),
      low: currentPrice * (1 + (Math.random() - 0.5) * 0.05 - 0.01),
      mitigated: Math.random() > 0.6,
      strength: Math.floor(Math.random() * 50) + 50,
      distance: ((Math.random() - 0.5) * 10).toFixed(2)
    }))

    // Fair value gaps
    const fvgs = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'bullish' : 'bearish',
      high: currentPrice * (1 + (Math.random() - 0.5) * 0.08),
      low: currentPrice * (1 + (Math.random() - 0.5) * 0.08 - 0.005),
      filled: Math.random() > 0.5,
      fillPercent: Math.floor(Math.random() * 100)
    }))

    return {
      trend,
      bias: trend === 'bullish' ? 'long' : trend === 'bearish' ? 'short' : 'neutral',
      swingHighs,
      swingLows,
      breaks,
      orderBlocks,
      fvgs,
      lastHH: swingHighs.find(s => s.type === 'HH'),
      lastHL: swingLows.find(s => s.type === 'HL'),
      lastLH: swingHighs.find(s => s.type === 'LH'),
      lastLL: swingLows.find(s => s.type === 'LL')
    }
  }, [currentPrice, selectedToken, timeframe])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(2)
    if (price >= 1) return price.toFixed(4)
    return price.toFixed(6)
  }

  const formatTime = (date) => {
    const diff = Date.now() - date.getTime()
    const hours = Math.floor(diff / (60 * 60 * 1000))
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  const getTrendIcon = (trend) => {
    switch(trend) {
      case 'bullish': return <TrendingUp className="w-5 h-5 text-green-400" />
      case 'bearish': return <TrendingDown className="w-5 h-5 text-red-400" />
      default: return <Minus className="w-5 h-5 text-yellow-400" />
    }
  }

  const getTrendColor = (trend) => {
    switch(trend) {
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
          <GitMerge className="w-6 h-6 text-indigo-400" />
          <h2 className="text-xl font-bold text-white">Market Structure</h2>
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

      {/* Trend Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className={`rounded-lg p-4 border ${
          structureData.trend === 'bullish' ? 'bg-green-500/10 border-green-500/20' :
          structureData.trend === 'bearish' ? 'bg-red-500/10 border-red-500/20' :
          'bg-yellow-500/10 border-yellow-500/20'
        }`}>
          <div className="text-gray-400 text-sm mb-1">Trend</div>
          <div className="flex items-center gap-2">
            {getTrendIcon(structureData.trend)}
            <span className={`text-xl font-bold capitalize ${getTrendColor(structureData.trend)}`}>
              {structureData.trend}
            </span>
          </div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Bias</div>
          <div className={`text-xl font-bold capitalize ${
            structureData.bias === 'long' ? 'text-green-400' :
            structureData.bias === 'short' ? 'text-red-400' : 'text-yellow-400'
          }`}>
            {structureData.bias}
          </div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Structure Breaks</div>
          <div className="text-xl font-bold text-white">{structureData.breaks.length}</div>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="text-gray-400 text-sm mb-1">Order Blocks</div>
          <div className="text-xl font-bold text-white">{structureData.orderBlocks.filter(ob => !ob.mitigated).length}</div>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'swings', label: 'Swing Points' },
          { id: 'breaks', label: 'BOS/CHoCH' },
          { id: 'analysis', label: 'OB & FVG' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Overview Mode */}
      {viewMode === 'overview' && (
        <div className="space-y-4">
          {/* Key Swing Points */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {structureData.lastHH && (
              <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                <div className="flex items-center gap-1 text-green-400 text-xs mb-1">
                  <ArrowUp className="w-3 h-3" />
                  Higher High
                </div>
                <div className="text-white font-medium">${formatPrice(structureData.lastHH.price)}</div>
              </div>
            )}
            {structureData.lastHL && (
              <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                <div className="flex items-center gap-1 text-green-400 text-xs mb-1">
                  <ArrowUp className="w-3 h-3" />
                  Higher Low
                </div>
                <div className="text-white font-medium">${formatPrice(structureData.lastHL.price)}</div>
              </div>
            )}
            {structureData.lastLH && (
              <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                <div className="flex items-center gap-1 text-red-400 text-xs mb-1">
                  <ArrowDown className="w-3 h-3" />
                  Lower High
                </div>
                <div className="text-white font-medium">${formatPrice(structureData.lastLH.price)}</div>
              </div>
            )}
            {structureData.lastLL && (
              <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                <div className="flex items-center gap-1 text-red-400 text-xs mb-1">
                  <ArrowDown className="w-3 h-3" />
                  Lower Low
                </div>
                <div className="text-white font-medium">${formatPrice(structureData.lastLL.price)}</div>
              </div>
            )}
          </div>

          {/* Structure Visual */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Market Structure Pattern</h3>
            <div className="h-32 flex items-center justify-center gap-4">
              {structureData.trend === 'bullish' && (
                <div className="flex items-end gap-8">
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-16 bg-green-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">HL</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-24 bg-green-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">HH</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-20 bg-green-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">HL</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-28 bg-green-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">HH</span>
                  </div>
                </div>
              )}
              {structureData.trend === 'bearish' && (
                <div className="flex items-end gap-8">
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-28 bg-red-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">LH</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-20 bg-red-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">LL</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-24 bg-red-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">LH</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-16 bg-red-500 rounded"></div>
                    <span className="text-xs text-gray-500 mt-1">LL</span>
                  </div>
                </div>
              )}
              {structureData.trend === 'ranging' && (
                <div className="flex items-center gap-8">
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-20 bg-yellow-500 rounded"></div>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-22 bg-yellow-500 rounded"></div>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-18 bg-yellow-500 rounded"></div>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-1 h-21 bg-yellow-500 rounded"></div>
                  </div>
                </div>
              )}
            </div>
            <div className={`text-center mt-4 ${getTrendColor(structureData.trend)}`}>
              {structureData.trend === 'bullish' && 'Higher Highs & Higher Lows - Uptrend Structure'}
              {structureData.trend === 'bearish' && 'Lower Highs & Lower Lows - Downtrend Structure'}
              {structureData.trend === 'ranging' && 'Equal Highs & Lows - Consolidation'}
            </div>
          </div>

          {/* Recent Breaks */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3">Recent Structure Breaks</h3>
            <div className="space-y-2">
              {structureData.breaks.slice(0, 4).map(brk => (
                <div key={brk.id} className="flex items-center justify-between p-2 bg-white/5 rounded">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      brk.type === 'BOS' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                    }`}>
                      {brk.type}
                    </span>
                    <span className={`${brk.direction === 'bullish' ? 'text-green-400' : 'text-red-400'}`}>
                      {brk.direction === 'bullish' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                    </span>
                    <span className="text-white">${formatPrice(brk.price)}</span>
                  </div>
                  <span className="text-gray-500 text-sm">{formatTime(brk.time)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Swings Mode */}
      {viewMode === 'swings' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Swing Highs */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
              <ChevronUp className="w-4 h-4" />
              Swing Highs
            </h3>
            <div className="space-y-2">
              {structureData.swingHighs.map(swing => (
                <div key={swing.id} className="flex items-center justify-between p-2 bg-red-500/10 rounded">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      swing.type === 'HH' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {swing.type}
                    </span>
                    <span className="text-white">${formatPrice(swing.price)}</span>
                    {swing.confirmed && <CheckCircle className="w-3 h-3 text-green-400" />}
                  </div>
                  <span className="text-gray-500 text-sm">{formatTime(swing.time)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Swing Lows */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
              <ChevronDown className="w-4 h-4" />
              Swing Lows
            </h3>
            <div className="space-y-2">
              {structureData.swingLows.map(swing => (
                <div key={swing.id} className="flex items-center justify-between p-2 bg-green-500/10 rounded">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      swing.type === 'HL' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {swing.type}
                    </span>
                    <span className="text-white">${formatPrice(swing.price)}</span>
                    {swing.confirmed && <CheckCircle className="w-3 h-3 text-green-400" />}
                  </div>
                  <span className="text-gray-500 text-sm">{formatTime(swing.time)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Breaks Mode */}
      {viewMode === 'breaks' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20 text-center">
              <div className="text-blue-400 text-2xl font-bold">
                {structureData.breaks.filter(b => b.type === 'BOS').length}
              </div>
              <div className="text-gray-400 text-sm">Break of Structure</div>
            </div>
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20 text-center">
              <div className="text-purple-400 text-2xl font-bold">
                {structureData.breaks.filter(b => b.type === 'CHoCH').length}
              </div>
              <div className="text-gray-400 text-sm">Change of Character</div>
            </div>
          </div>

          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3">All Structure Breaks</h3>
            <div className="space-y-2">
              {structureData.breaks.map(brk => (
                <div key={brk.id} className={`p-3 rounded-lg border ${
                  brk.type === 'BOS' ? 'bg-blue-500/10 border-blue-500/20' : 'bg-purple-500/10 border-purple-500/20'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        brk.type === 'BOS' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                      }`}>
                        {brk.type}
                      </span>
                      <span className={`flex items-center gap-1 ${
                        brk.direction === 'bullish' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {brk.direction === 'bullish' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                        {brk.direction}
                      </span>
                      <span className="text-white">${formatPrice(brk.price)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        brk.significance === 'major' ? 'bg-red-500/20 text-red-400' :
                        brk.significance === 'moderate' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {brk.significance}
                      </span>
                      <span className="text-gray-500 text-sm">{formatTime(brk.time)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Analysis Mode - Order Blocks & FVGs */}
      {viewMode === 'analysis' && (
        <div className="space-y-6">
          {/* Order Blocks */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Order Blocks</h3>
            <div className="space-y-3">
              {structureData.orderBlocks.map(ob => (
                <div key={ob.id} className={`p-3 rounded-lg ${
                  ob.type === 'bullish' ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'
                } ${ob.mitigated ? 'opacity-50' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        ob.type === 'bullish' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {ob.type.toUpperCase()} OB
                      </span>
                      <span className="text-white">
                        ${formatPrice(ob.low)} - ${formatPrice(ob.high)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400 text-sm">{ob.distance}% away</span>
                      {ob.mitigated ? (
                        <span className="text-gray-500 text-xs">Mitigated</span>
                      ) : (
                        <span className="text-yellow-400 text-xs">Active</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fair Value Gaps */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Fair Value Gaps (FVG)</h3>
            <div className="space-y-3">
              {structureData.fvgs.map(fvg => (
                <div key={fvg.id} className={`p-3 rounded-lg ${
                  fvg.type === 'bullish' ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        fvg.type === 'bullish' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {fvg.type.toUpperCase()} FVG
                      </span>
                      <span className="text-white">
                        ${formatPrice(fvg.low)} - ${formatPrice(fvg.high)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-white/10 rounded overflow-hidden">
                        <div
                          className={`h-full ${fvg.type === 'bullish' ? 'bg-green-500' : 'bg-red-500'}`}
                          style={{ width: `${fvg.fillPercent}%` }}
                        />
                      </div>
                      <span className="text-gray-400 text-sm">{fvg.fillPercent}% filled</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MarketStructure
