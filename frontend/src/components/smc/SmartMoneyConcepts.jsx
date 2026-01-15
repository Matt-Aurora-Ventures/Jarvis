import React, { useState, useMemo, useEffect } from 'react'
import {
  Brain,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Target,
  Layers,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  DollarSign,
  Eye,
  Zap,
  Shield
} from 'lucide-react'

export function SmartMoneyConcepts() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('1h')
  const [viewMode, setViewMode] = useState('overview') // overview, orderblocks, fvg, liquidity
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['5m', '15m', '1h', '4h', '1d']

  // Generate mock SMC data
  const smcData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Market Structure
    const structureBias = Math.random() > 0.5 ? 'bullish' : 'bearish'
    const lastBOS = {
      type: structureBias === 'bullish' ? 'bullish' : 'bearish',
      price: currentPrice * (structureBias === 'bullish' ? 0.97 : 1.03),
      time: new Date(Date.now() - Math.random() * 6 * 60 * 60 * 1000)
    }

    const lastChoCH = Math.random() > 0.7 ? {
      type: structureBias === 'bullish' ? 'bullish' : 'bearish',
      price: currentPrice * (structureBias === 'bullish' ? 0.95 : 1.05),
      time: new Date(Date.now() - Math.random() * 12 * 60 * 60 * 1000)
    } : null

    // Order Blocks
    const orderBlocks = Array.from({ length: 8 }, (_, i) => {
      const isBullish = Math.random() > 0.5
      const high = currentPrice * (0.9 + Math.random() * 0.2)
      const low = high * (0.98 + Math.random() * 0.015)

      return {
        id: i + 1,
        type: isBullish ? 'bullish' : 'bearish',
        high,
        low,
        midpoint: (high + low) / 2,
        strength: Math.floor(Math.random() * 100),
        tested: Math.random() > 0.5,
        mitigated: Math.random() > 0.7,
        time: new Date(Date.now() - i * 4 * 60 * 60 * 1000),
        volume: Math.floor(Math.random() * 10000000) + 1000000
      }
    }).sort((a, b) => b.time - a.time)

    // Fair Value Gaps (FVG)
    const fvgs = Array.from({ length: 6 }, (_, i) => {
      const isBullish = Math.random() > 0.5
      const gapSize = currentPrice * (0.005 + Math.random() * 0.02)
      const top = currentPrice * (0.95 + Math.random() * 0.1)
      const bottom = top - gapSize

      return {
        id: i + 1,
        type: isBullish ? 'bullish' : 'bearish',
        top,
        bottom,
        size: gapSize,
        percentSize: (gapSize / currentPrice) * 100,
        filled: Math.random() > 0.6,
        fillPercent: Math.floor(Math.random() * 100),
        time: new Date(Date.now() - i * 3 * 60 * 60 * 1000)
      }
    }).sort((a, b) => b.time - a.time)

    // Liquidity Levels
    const liquidityLevels = {
      buyStops: Array.from({ length: 4 }, (_, i) => ({
        id: i + 1,
        price: currentPrice * (1.02 + i * 0.015),
        strength: Math.floor(Math.random() * 100),
        swept: Math.random() > 0.7
      })),
      sellStops: Array.from({ length: 4 }, (_, i) => ({
        id: i + 1,
        price: currentPrice * (0.98 - i * 0.015),
        strength: Math.floor(Math.random() * 100),
        swept: Math.random() > 0.7
      })),
      equalHighs: currentPrice * (1.05 + Math.random() * 0.03),
      equalLows: currentPrice * (0.95 - Math.random() * 0.03)
    }

    // Premium/Discount Zones
    const swingHigh = currentPrice * (1.08 + Math.random() * 0.05)
    const swingLow = currentPrice * (0.92 - Math.random() * 0.05)
    const equilibrium = (swingHigh + swingLow) / 2
    const premiumZone = { top: swingHigh, bottom: equilibrium }
    const discountZone = { top: equilibrium, bottom: swingLow }
    const inPremium = currentPrice > equilibrium
    const inDiscount = currentPrice < equilibrium

    // Inducement
    const inducements = Array.from({ length: 3 }, (_, i) => ({
      id: i + 1,
      type: Math.random() > 0.5 ? 'buy' : 'sell',
      price: currentPrice * (0.97 + Math.random() * 0.06),
      triggered: Math.random() > 0.5,
      time: new Date(Date.now() - i * 2 * 60 * 60 * 1000)
    }))

    // Breaker Blocks
    const breakerBlocks = orderBlocks
      .filter(ob => ob.mitigated)
      .map(ob => ({
        ...ob,
        isBreaker: true,
        reverseType: ob.type === 'bullish' ? 'bearish' : 'bullish'
      }))

    return {
      currentPrice,
      structureBias,
      lastBOS,
      lastChoCH,
      orderBlocks,
      fvgs,
      liquidityLevels,
      premiumZone,
      discountZone,
      equilibrium,
      inPremium,
      inDiscount,
      inducements,
      breakerBlocks,
      swingHigh,
      swingLow
    }
  }, [selectedToken, timeframe])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const formatTimeAgo = (date) => {
    const minutes = Math.floor((Date.now() - date.getTime()) / (1000 * 60))
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-indigo-400" />
          <h2 className="text-xl font-bold text-white">Smart Money Concepts</h2>
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

      {/* Market Structure Summary */}
      <div className={`rounded-lg p-4 mb-6 border ${
        smcData.structureBias === 'bullish' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Structure Bias</div>
            <div className={`text-xl font-bold capitalize flex items-center gap-2 ${
              smcData.structureBias === 'bullish' ? 'text-green-400' : 'text-red-400'
            }`}>
              {smcData.structureBias === 'bullish' ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
              {smcData.structureBias}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Last BOS</div>
            <div className={`text-lg font-medium ${smcData.lastBOS.type === 'bullish' ? 'text-green-400' : 'text-red-400'}`}>
              ${formatPrice(smcData.lastBOS.price)}
            </div>
            <div className="text-gray-500 text-xs">{formatTimeAgo(smcData.lastBOS.time)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Zone</div>
            <div className={`text-lg font-medium ${smcData.inDiscount ? 'text-green-400' : 'text-red-400'}`}>
              {smcData.inDiscount ? 'Discount' : 'Premium'}
            </div>
            <div className="text-gray-500 text-xs">
              EQ: ${formatPrice(smcData.equilibrium)}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Current Price</div>
            <div className="text-lg font-bold text-white">${formatPrice(smcData.currentPrice)}</div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'orderblocks', label: 'Order Blocks' },
          { id: 'fvg', label: 'Fair Value Gaps' },
          { id: 'liquidity', label: 'Liquidity' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {viewMode === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Premium/Discount */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              Premium/Discount Zones
            </h3>
            <div className="relative h-40 bg-gradient-to-b from-red-500/20 via-yellow-500/10 to-green-500/20 rounded-lg">
              {/* Premium Zone */}
              <div className="absolute top-0 left-0 right-0 h-1/2 border-b border-dashed border-yellow-500/50 flex items-start justify-between p-2">
                <span className="text-red-400 text-xs">Premium</span>
                <span className="text-gray-400 text-xs">${formatPrice(smcData.swingHigh)}</span>
              </div>
              {/* Discount Zone */}
              <div className="absolute bottom-0 left-0 right-0 h-1/2 flex items-end justify-between p-2">
                <span className="text-green-400 text-xs">Discount</span>
                <span className="text-gray-400 text-xs">${formatPrice(smcData.swingLow)}</span>
              </div>
              {/* Equilibrium Line */}
              <div className="absolute left-0 right-0 top-1/2 border-t-2 border-yellow-500">
                <span className="absolute right-2 -top-5 text-yellow-400 text-xs bg-[#0a0e14] px-1">
                  EQ: ${formatPrice(smcData.equilibrium)}
                </span>
              </div>
              {/* Current Price */}
              <div
                className="absolute left-0 right-0 h-1 bg-white/80"
                style={{
                  top: `${((smcData.swingHigh - smcData.currentPrice) / (smcData.swingHigh - smcData.swingLow)) * 100}%`
                }}
              >
                <span className="absolute left-2 -top-5 text-white text-xs bg-indigo-500 px-2 py-0.5 rounded">
                  ${formatPrice(smcData.currentPrice)}
                </span>
              </div>
            </div>
          </div>

          {/* Key Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-cyan-400" />
              Key SMC Levels
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between py-2 border-b border-white/5">
                <span className="text-gray-400">Swing High</span>
                <span className="text-red-400 font-medium">${formatPrice(smcData.swingHigh)}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-white/5">
                <span className="text-gray-400">Equal Highs (BSL)</span>
                <span className="text-red-400 font-medium">${formatPrice(smcData.liquidityLevels.equalHighs)}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-white/5">
                <span className="text-gray-400">Equilibrium</span>
                <span className="text-yellow-400 font-medium">${formatPrice(smcData.equilibrium)}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-white/5">
                <span className="text-gray-400">Equal Lows (SSL)</span>
                <span className="text-green-400 font-medium">${formatPrice(smcData.liquidityLevels.equalLows)}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-gray-400">Swing Low</span>
                <span className="text-green-400 font-medium">${formatPrice(smcData.swingLow)}</span>
              </div>
            </div>
          </div>

          {/* Active Order Blocks */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-orange-400" />
              Active Order Blocks
            </h3>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {smcData.orderBlocks.filter(ob => !ob.mitigated).slice(0, 4).map(ob => (
                <div key={ob.id} className={`p-2 rounded border ${
                  ob.type === 'bullish' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium capitalize ${
                      ob.type === 'bullish' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {ob.type} OB
                    </span>
                    <span className="text-gray-400 text-xs">{formatTimeAgo(ob.time)}</span>
                  </div>
                  <div className="text-white text-sm">
                    ${formatPrice(ob.low)} - ${formatPrice(ob.high)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Active FVGs */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              Unfilled FVGs
            </h3>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {smcData.fvgs.filter(fvg => !fvg.filled).slice(0, 4).map(fvg => (
                <div key={fvg.id} className={`p-2 rounded border ${
                  fvg.type === 'bullish' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium capitalize ${
                      fvg.type === 'bullish' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {fvg.type} FVG
                    </span>
                    <span className="text-gray-400 text-xs">{fvg.percentSize.toFixed(2)}%</span>
                  </div>
                  <div className="text-white text-sm">
                    ${formatPrice(fvg.bottom)} - ${formatPrice(fvg.top)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Order Blocks View */}
      {viewMode === 'orderblocks' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Bullish OBs */}
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
                <ChevronUp className="w-4 h-4" />
                Bullish Order Blocks (Demand)
              </h3>
              <div className="space-y-3">
                {smcData.orderBlocks.filter(ob => ob.type === 'bullish').map(ob => (
                  <div key={ob.id} className="bg-white/5 rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">
                        ${formatPrice(ob.low)} - ${formatPrice(ob.high)}
                      </span>
                      <div className="flex items-center gap-2">
                        {ob.tested && <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">Tested</span>}
                        {ob.mitigated && <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded">Mitigated</span>}
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-sm text-gray-400">
                      <span>Midpoint: ${formatPrice(ob.midpoint)}</span>
                      <span>Strength: {ob.strength}%</span>
                    </div>
                    <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500" style={{ width: `${ob.strength}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Bearish OBs */}
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
                <ChevronDown className="w-4 h-4" />
                Bearish Order Blocks (Supply)
              </h3>
              <div className="space-y-3">
                {smcData.orderBlocks.filter(ob => ob.type === 'bearish').map(ob => (
                  <div key={ob.id} className="bg-white/5 rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">
                        ${formatPrice(ob.low)} - ${formatPrice(ob.high)}
                      </span>
                      <div className="flex items-center gap-2">
                        {ob.tested && <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">Tested</span>}
                        {ob.mitigated && <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded">Mitigated</span>}
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-sm text-gray-400">
                      <span>Midpoint: ${formatPrice(ob.midpoint)}</span>
                      <span>Strength: {ob.strength}%</span>
                    </div>
                    <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full bg-red-500" style={{ width: `${ob.strength}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Breaker Blocks */}
          {smcData.breakerBlocks.length > 0 && (
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <h3 className="text-purple-400 font-medium mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Breaker Blocks (Mitigated OBs)
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {smcData.breakerBlocks.map(bb => (
                  <div key={bb.id} className="bg-white/5 rounded p-3">
                    <div className="flex items-center justify-between">
                      <span className={`font-medium capitalize ${
                        bb.reverseType === 'bullish' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        Now {bb.reverseType} Breaker
                      </span>
                      <span className="text-gray-400 text-sm">${formatPrice(bb.low)} - ${formatPrice(bb.high)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* FVG View */}
      {viewMode === 'fvg' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Bullish FVGs */}
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
                <ChevronUp className="w-4 h-4" />
                Bullish Fair Value Gaps
              </h3>
              <div className="space-y-3">
                {smcData.fvgs.filter(fvg => fvg.type === 'bullish').map(fvg => (
                  <div key={fvg.id} className="bg-white/5 rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">
                        ${formatPrice(fvg.bottom)} - ${formatPrice(fvg.top)}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        fvg.filled ? 'bg-gray-500/20 text-gray-400' : 'bg-green-500/20 text-green-400'
                      }`}>
                        {fvg.filled ? 'Filled' : 'Open'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm text-gray-400">
                      <span>Gap Size: {fvg.percentSize.toFixed(2)}%</span>
                      <span>{formatTimeAgo(fvg.time)}</span>
                    </div>
                    {!fvg.filled && (
                      <div className="mt-2">
                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                          <span>Fill Progress</span>
                          <span>{fvg.fillPercent}%</span>
                        </div>
                        <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-green-500" style={{ width: `${fvg.fillPercent}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Bearish FVGs */}
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
                <ChevronDown className="w-4 h-4" />
                Bearish Fair Value Gaps
              </h3>
              <div className="space-y-3">
                {smcData.fvgs.filter(fvg => fvg.type === 'bearish').map(fvg => (
                  <div key={fvg.id} className="bg-white/5 rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">
                        ${formatPrice(fvg.bottom)} - ${formatPrice(fvg.top)}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        fvg.filled ? 'bg-gray-500/20 text-gray-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {fvg.filled ? 'Filled' : 'Open'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm text-gray-400">
                      <span>Gap Size: {fvg.percentSize.toFixed(2)}%</span>
                      <span>{formatTimeAgo(fvg.time)}</span>
                    </div>
                    {!fvg.filled && (
                      <div className="mt-2">
                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                          <span>Fill Progress</span>
                          <span>{fvg.fillPercent}%</span>
                        </div>
                        <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-red-500" style={{ width: `${fvg.fillPercent}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Liquidity View */}
      {viewMode === 'liquidity' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Buy Side Liquidity */}
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Buy Side Liquidity (BSL)
              </h3>
              <div className="space-y-2">
                {smcData.liquidityLevels.buyStops.map(level => (
                  <div key={level.id} className="flex items-center justify-between p-2 bg-white/5 rounded">
                    <span className="text-white">${formatPrice(level.price)}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-red-500" style={{ width: `${level.strength}%` }} />
                      </div>
                      {level.swept && <span className="text-xs text-gray-500">Swept</span>}
                    </div>
                  </div>
                ))}
                <div className="mt-2 p-2 bg-red-500/20 rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-red-400 font-medium">Equal Highs</span>
                    <span className="text-white">${formatPrice(smcData.liquidityLevels.equalHighs)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Sell Side Liquidity */}
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Sell Side Liquidity (SSL)
              </h3>
              <div className="space-y-2">
                {smcData.liquidityLevels.sellStops.map(level => (
                  <div key={level.id} className="flex items-center justify-between p-2 bg-white/5 rounded">
                    <span className="text-white">${formatPrice(level.price)}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500" style={{ width: `${level.strength}%` }} />
                      </div>
                      {level.swept && <span className="text-xs text-gray-500">Swept</span>}
                    </div>
                  </div>
                ))}
                <div className="mt-2 p-2 bg-green-500/20 rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-green-400 font-medium">Equal Lows</span>
                    <span className="text-white">${formatPrice(smcData.liquidityLevels.equalLows)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Inducement */}
          <div className="bg-yellow-500/10 rounded-lg p-4 border border-yellow-500/20">
            <h3 className="text-yellow-400 font-medium mb-3 flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Inducement Levels
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {smcData.inducements.map(ind => (
                <div key={ind.id} className={`p-3 rounded border ${
                  ind.triggered ? 'bg-gray-500/10 border-gray-500/20' : 'bg-yellow-500/10 border-yellow-500/20'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`capitalize font-medium ${
                      ind.type === 'buy' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {ind.type} Inducement
                    </span>
                    {ind.triggered && <span className="text-xs text-gray-500">Triggered</span>}
                  </div>
                  <div className="text-white">${formatPrice(ind.price)}</div>
                  <div className="text-gray-500 text-xs">{formatTimeAgo(ind.time)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>BOS = Break of Structure</span>
          <span>ChoCH = Change of Character</span>
          <span>OB = Order Block</span>
          <span>FVG = Fair Value Gap</span>
          <span>BSL = Buy Side Liquidity</span>
          <span>SSL = Sell Side Liquidity</span>
        </div>
      </div>
    </div>
  )
}

export default SmartMoneyConcepts
