import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Layers,
  Calendar,
  Clock,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Settings,
  Zap,
  Eye,
  ChevronRight
} from 'lucide-react'

export function VWAPBands() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('standard') // standard, anchored, sessions
  const [bandMultiplier, setBandMultiplier] = useState(2)
  const [showExtended, setShowExtended] = useState(true)

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']

  // Generate VWAP data for all tokens
  const vwapData = useMemo(() => {
    return tokens.map(token => {
      const currentPrice = 50 + Math.random() * 150
      const vwap = currentPrice * (0.95 + Math.random() * 0.1)
      const stdDev = currentPrice * 0.02 * (1 + Math.random())

      const upperBand1 = vwap + stdDev
      const upperBand2 = vwap + stdDev * 2
      const upperBand3 = vwap + stdDev * 3
      const lowerBand1 = vwap - stdDev
      const lowerBand2 = vwap - stdDev * 2
      const lowerBand3 = vwap - stdDev * 3

      // Determine position relative to VWAP
      let position = 'neutral'
      let positionLabel = 'At VWAP'
      let deviation = 0

      if (currentPrice > upperBand2) {
        position = 'extended_above'
        positionLabel = 'Extended Above +2σ'
        deviation = ((currentPrice - vwap) / stdDev)
      } else if (currentPrice > upperBand1) {
        position = 'above_1'
        positionLabel = 'Above +1σ'
        deviation = ((currentPrice - vwap) / stdDev)
      } else if (currentPrice > vwap) {
        position = 'above'
        positionLabel = 'Above VWAP'
        deviation = ((currentPrice - vwap) / stdDev)
      } else if (currentPrice < lowerBand2) {
        position = 'extended_below'
        positionLabel = 'Extended Below -2σ'
        deviation = ((currentPrice - vwap) / stdDev)
      } else if (currentPrice < lowerBand1) {
        position = 'below_1'
        positionLabel = 'Below -1σ'
        deviation = ((currentPrice - vwap) / stdDev)
      } else if (currentPrice < vwap) {
        position = 'below'
        positionLabel = 'Below VWAP'
        deviation = ((currentPrice - vwap) / stdDev)
      }

      // Session VWAPs
      const asianVwap = vwap * (0.98 + Math.random() * 0.04)
      const londonVwap = vwap * (0.98 + Math.random() * 0.04)
      const nyVwap = vwap * (0.98 + Math.random() * 0.04)

      return {
        token,
        currentPrice,
        vwap,
        stdDev,
        upperBand1,
        upperBand2,
        upperBand3,
        lowerBand1,
        lowerBand2,
        lowerBand3,
        position,
        positionLabel,
        deviation,
        volume24h: (Math.random() * 500).toFixed(1),
        trend: Math.random() > 0.5 ? 'bullish' : 'bearish',
        asianVwap,
        londonVwap,
        nyVwap,
        distanceToVwap: ((currentPrice - vwap) / vwap * 100),
        dailyHigh: currentPrice * (1 + Math.random() * 0.05),
        dailyLow: currentPrice * (1 - Math.random() * 0.05)
      }
    })
  }, [])

  // Anchored VWAP data
  const anchoredVwaps = useMemo(() => {
    const tokenData = vwapData.find(d => d.token === selectedToken)
    const base = tokenData?.vwap || 100

    return [
      { name: 'Monthly Open', date: 'Jan 1', vwap: base * 0.92, color: 'purple' },
      { name: 'Weekly Open', date: 'Jan 13', vwap: base * 0.97, color: 'blue' },
      { name: 'Daily Open', date: 'Today', vwap: base * 1.0, color: 'cyan' },
      { name: 'Swing Low', date: 'Dec 20', vwap: base * 0.88, color: 'green' },
      { name: 'Major High', date: 'Nov 15', vwap: base * 1.15, color: 'red' }
    ]
  }, [selectedToken, vwapData])

  // Price history for chart
  const priceHistory = useMemo(() => {
    const tokenData = vwapData.find(d => d.token === selectedToken)
    const basePrice = tokenData?.currentPrice || 100
    const data = []

    for (let i = 24; i >= 0; i--) {
      const price = basePrice * (0.9 + Math.random() * 0.2)
      const volume = 1000 + Math.random() * 5000

      data.push({
        time: i === 0 ? 'Now' : `-${i}h`,
        price,
        volume,
        vwap: basePrice * (0.95 + Math.random() * 0.1)
      })
    }
    return data
  }, [selectedToken, vwapData])

  const getPositionColor = (position) => {
    if (position.includes('extended_above')) return 'text-red-400'
    if (position.includes('above')) return 'text-green-400'
    if (position.includes('extended_below')) return 'text-green-400'
    if (position.includes('below')) return 'text-red-400'
    return 'text-white/60'
  }

  const getPositionBg = (position) => {
    if (position.includes('extended_above')) return 'bg-red-500/10'
    if (position.includes('above')) return 'bg-green-500/10'
    if (position.includes('extended_below')) return 'bg-green-500/10'
    if (position.includes('below')) return 'bg-red-500/10'
    return 'bg-white/5'
  }

  // Stats
  const aboveVwap = vwapData.filter(d => d.currentPrice > d.vwap).length
  const belowVwap = vwapData.filter(d => d.currentPrice < d.vwap).length
  const extended = vwapData.filter(d => Math.abs(d.deviation) > 2).length

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg">
            <Layers className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">VWAP Bands</h1>
            <p className="text-white/60 text-sm">Volume Weighted Average Price with Standard Deviation Bands</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Band Multiplier */}
          <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
            <span className="text-white/60 text-sm">Bands:</span>
            <select
              value={bandMultiplier}
              onChange={(e) => setBandMultiplier(Number(e.target.value))}
              className="bg-transparent text-white text-sm outline-none"
            >
              <option value={1}>1σ</option>
              <option value={2}>2σ</option>
              <option value={3}>3σ</option>
            </select>
          </div>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['standard', 'anchored', 'sessions'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-cyan-500 text-white' : 'text-white/60 hover:text-white'
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
            <ArrowUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">Above VWAP</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{aboveVwap}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <ArrowDown className="w-4 h-4 text-red-400" />
            <span className="text-white/60 text-sm">Below VWAP</span>
          </div>
          <p className="text-2xl font-bold text-red-400">{belowVwap}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">Extended (2σ+)</span>
          </div>
          <p className="text-2xl font-bold text-yellow-400">{extended}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-cyan-400" />
            <span className="text-white/60 text-sm">Avg Distance</span>
          </div>
          <p className="text-2xl font-bold">
            {(vwapData.reduce((acc, d) => acc + Math.abs(d.distanceToVwap), 0) / vwapData.length).toFixed(1)}%
          </p>
        </div>
      </div>

      {viewMode === 'standard' && (
        <div className="grid grid-cols-3 gap-6">
          {/* VWAP Scanner Table */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Price</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">VWAP</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Distance</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Position</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">σ Level</th>
                </tr>
              </thead>
              <tbody>
                {vwapData.map((item, idx) => (
                  <tr
                    key={item.token}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      selectedToken === item.token ? 'bg-cyan-500/10' : idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.token}</span>
                        {item.trend === 'bullish' ? (
                          <TrendingUp className="w-3 h-3 text-green-400" />
                        ) : (
                          <TrendingDown className="w-3 h-3 text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right font-medium">
                      ${item.currentPrice.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right text-cyan-400">
                      ${item.vwap.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.distanceToVwap >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {item.distanceToVwap >= 0 ? '+' : ''}{item.distanceToVwap.toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getPositionBg(item.position)} ${getPositionColor(item.position)}`}>
                          {item.positionLabel}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`font-medium ${
                        Math.abs(item.deviation) > 2 ? 'text-yellow-400' :
                        Math.abs(item.deviation) > 1 ? 'text-orange-400' : 'text-white/60'
                      }`}>
                        {item.deviation >= 0 ? '+' : ''}{item.deviation.toFixed(2)}σ
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Selected Token Details */}
          <div className="space-y-4">
            {(() => {
              const tokenData = vwapData.find(d => d.token === selectedToken)
              return (
                <>
                  {/* Band Levels */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-cyan-400" />
                      {selectedToken} VWAP Bands
                    </h3>

                    <div className="space-y-2">
                      {showExtended && (
                        <div className="flex justify-between items-center p-2 bg-red-500/10 rounded">
                          <span className="text-red-400 text-sm">+3σ</span>
                          <span className="font-medium">${tokenData.upperBand3.toFixed(2)}</span>
                        </div>
                      )}
                      <div className="flex justify-between items-center p-2 bg-orange-500/10 rounded">
                        <span className="text-orange-400 text-sm">+2σ</span>
                        <span className="font-medium">${tokenData.upperBand2.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-yellow-500/10 rounded">
                        <span className="text-yellow-400 text-sm">+1σ</span>
                        <span className="font-medium">${tokenData.upperBand1.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-cyan-500/20 rounded border border-cyan-500/30">
                        <span className="text-cyan-400 text-sm font-medium">VWAP</span>
                        <span className="font-bold text-cyan-400">${tokenData.vwap.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-yellow-500/10 rounded">
                        <span className="text-yellow-400 text-sm">-1σ</span>
                        <span className="font-medium">${tokenData.lowerBand1.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-orange-500/10 rounded">
                        <span className="text-orange-400 text-sm">-2σ</span>
                        <span className="font-medium">${tokenData.lowerBand2.toFixed(2)}</span>
                      </div>
                      {showExtended && (
                        <div className="flex justify-between items-center p-2 bg-green-500/10 rounded">
                          <span className="text-green-400 text-sm">-3σ</span>
                          <span className="font-medium">${tokenData.lowerBand3.toFixed(2)}</span>
                        </div>
                      )}
                    </div>

                    {/* Current Price Indicator */}
                    <div className="mt-3 p-2 bg-white/5 rounded-lg">
                      <div className="flex justify-between items-center">
                        <span className="text-white/60 text-sm">Current Price</span>
                        <span className="font-bold">${tokenData.currentPrice.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center mt-1">
                        <span className="text-white/60 text-sm">Position</span>
                        <span className={getPositionColor(tokenData.position)}>
                          {tokenData.positionLabel}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Trading Signals */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Target className="w-4 h-4 text-purple-400" />
                      Trading Signals
                    </h3>

                    <div className="space-y-2 text-sm">
                      <div className={`p-2 rounded-lg ${
                        tokenData.currentPrice < tokenData.lowerBand2
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-white/5 text-white/60'
                      }`}>
                        <p className="font-medium">Mean Reversion Long</p>
                        <p className="text-xs opacity-70">Below -2σ, expect bounce to VWAP</p>
                      </div>
                      <div className={`p-2 rounded-lg ${
                        tokenData.currentPrice > tokenData.upperBand2
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-white/5 text-white/60'
                      }`}>
                        <p className="font-medium">Mean Reversion Short</p>
                        <p className="text-xs opacity-70">Above +2σ, expect pullback to VWAP</p>
                      </div>
                      <div className={`p-2 rounded-lg ${
                        tokenData.currentPrice > tokenData.vwap && tokenData.deviation < 1
                          ? 'bg-cyan-500/20 text-cyan-400'
                          : 'bg-white/5 text-white/60'
                      }`}>
                        <p className="font-medium">Trend Continuation</p>
                        <p className="text-xs opacity-70">Above VWAP, holding support</p>
                      </div>
                    </div>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {viewMode === 'anchored' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Anchored VWAP List */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold flex items-center gap-2">
                <Calendar className="w-5 h-5 text-purple-400" />
                Anchored VWAPs - {selectedToken}
              </h2>
              <button className="px-3 py-1.5 text-sm bg-purple-500/20 text-purple-400 rounded-lg hover:bg-purple-500/30">
                + Add Anchor
              </button>
            </div>

            {/* Anchored VWAP Visualization */}
            <div className="relative h-64 border border-white/10 rounded-lg bg-white/[0.02] mb-4">
              {/* Current Price Line */}
              {(() => {
                const tokenData = vwapData.find(d => d.token === selectedToken)
                const minVwap = Math.min(...anchoredVwaps.map(a => a.vwap))
                const maxVwap = Math.max(...anchoredVwaps.map(a => a.vwap), tokenData.currentPrice)
                const range = maxVwap - minVwap

                const priceY = ((maxVwap - tokenData.currentPrice) / range) * 100

                return (
                  <>
                    {/* Current Price */}
                    <div
                      className="absolute left-0 right-0 border-t-2 border-white/60"
                      style={{ top: `${priceY}%` }}
                    >
                      <span className="absolute right-2 -top-3 text-xs bg-white/10 px-1 rounded">
                        ${tokenData.currentPrice.toFixed(2)}
                      </span>
                    </div>

                    {/* Anchored VWAP Lines */}
                    {anchoredVwaps.map((anchor, idx) => {
                      const y = ((maxVwap - anchor.vwap) / range) * 100
                      const colors = {
                        purple: 'border-purple-500',
                        blue: 'border-blue-500',
                        cyan: 'border-cyan-500',
                        green: 'border-green-500',
                        red: 'border-red-500'
                      }

                      return (
                        <div
                          key={idx}
                          className={`absolute left-0 right-0 border-t-2 border-dashed ${colors[anchor.color]}`}
                          style={{ top: `${y}%` }}
                        >
                          <span className={`absolute left-2 -top-3 text-xs ${colors[anchor.color].replace('border', 'text')}`}>
                            {anchor.name}
                          </span>
                          <span className="absolute right-2 -top-3 text-xs text-white/60">
                            ${anchor.vwap.toFixed(2)}
                          </span>
                        </div>
                      )
                    })}
                  </>
                )
              })()}
            </div>

            {/* Anchor Table */}
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-2 px-3 text-white/60 text-sm font-medium">Anchor Point</th>
                  <th className="text-left py-2 px-3 text-white/60 text-sm font-medium">Date</th>
                  <th className="text-right py-2 px-3 text-white/60 text-sm font-medium">VWAP</th>
                  <th className="text-right py-2 px-3 text-white/60 text-sm font-medium">Distance</th>
                  <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {anchoredVwaps.map((anchor, idx) => {
                  const tokenData = vwapData.find(d => d.token === selectedToken)
                  const distance = ((tokenData.currentPrice - anchor.vwap) / anchor.vwap * 100)
                  const isSupport = tokenData.currentPrice > anchor.vwap
                  const colors = {
                    purple: 'text-purple-400',
                    blue: 'text-blue-400',
                    cyan: 'text-cyan-400',
                    green: 'text-green-400',
                    red: 'text-red-400'
                  }

                  return (
                    <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                      <td className={`py-2 px-3 font-medium ${colors[anchor.color]}`}>
                        {anchor.name}
                      </td>
                      <td className="py-2 px-3 text-white/60">{anchor.date}</td>
                      <td className="py-2 px-3 text-right font-medium">${anchor.vwap.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right">
                        <span className={distance >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {distance >= 0 ? '+' : ''}{distance.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span className={`px-2 py-1 rounded text-xs ${
                          isSupport ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                        }`}>
                          {isSupport ? 'Support' : 'Resistance'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Anchor Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                Anchored VWAP Guide
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-2 bg-purple-500/10 rounded-lg">
                  <p className="text-purple-400 font-medium">Monthly Open</p>
                  <p className="text-white/60 text-xs">Key institutional reference level</p>
                </div>
                <div className="p-2 bg-blue-500/10 rounded-lg">
                  <p className="text-blue-400 font-medium">Weekly Open</p>
                  <p className="text-white/60 text-xs">Swing traders watch this level</p>
                </div>
                <div className="p-2 bg-cyan-500/10 rounded-lg">
                  <p className="text-cyan-400 font-medium">Daily Open</p>
                  <p className="text-white/60 text-xs">Day trading reference</p>
                </div>
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <p className="text-green-400 font-medium">Swing Points</p>
                  <p className="text-white/60 text-xs">Anchor from significant highs/lows</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Settings className="w-4 h-4 text-white/60" />
                Token Select
              </h3>

              <div className="grid grid-cols-2 gap-2">
                {tokens.map(token => (
                  <button
                    key={token}
                    onClick={() => setSelectedToken(token)}
                    className={`px-3 py-2 rounded-lg text-sm ${
                      selectedToken === token
                        ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                        : 'bg-white/5 text-white/60 hover:text-white'
                    }`}
                  >
                    {token}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'sessions' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Session VWAPs */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <Clock className="w-5 h-5 text-yellow-400" />
                Session VWAPs
              </h2>
            </div>

            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Current</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Asian VWAP</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">London VWAP</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">NY VWAP</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Active Session</th>
                </tr>
              </thead>
              <tbody>
                {vwapData.map((item, idx) => (
                  <tr
                    key={item.token}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <td className="py-3 px-4 font-medium">{item.token}</td>
                    <td className="py-3 px-4 text-right font-medium">${item.currentPrice.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.currentPrice > item.asianVwap ? 'text-green-400' : 'text-red-400'}>
                        ${item.asianVwap.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.currentPrice > item.londonVwap ? 'text-green-400' : 'text-red-400'}>
                        ${item.londonVwap.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.currentPrice > item.nyVwap ? 'text-green-400' : 'text-red-400'}>
                        ${item.nyVwap.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="px-2 py-1 rounded text-xs bg-blue-500/10 text-blue-400">
                        NY Session
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Session Info */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4 text-yellow-400" />
                Trading Sessions (UTC)
              </h3>

              <div className="space-y-3">
                <div className="p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-yellow-400 font-medium">Asian Session</span>
                    <span className="text-white/60 text-xs">00:00 - 09:00</span>
                  </div>
                  <p className="text-white/60 text-xs">Tokyo, Sydney, Singapore</p>
                </div>

                <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-green-400 font-medium">London Session</span>
                    <span className="text-white/60 text-xs">08:00 - 17:00</span>
                  </div>
                  <p className="text-white/60 text-xs">London, Frankfurt, Zurich</p>
                </div>

                <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/30">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-blue-400 font-medium">NY Session</span>
                    <span className="text-white/60 text-xs">13:00 - 22:00</span>
                  </div>
                  <p className="text-white/60 text-xs">New York, Chicago (ACTIVE)</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-purple-400" />
                Session Strategy
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Price above all session VWAPs = Strong bullish</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Price below all session VWAPs = Strong bearish</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Session VWAP acts as dynamic support/resistance</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Watch for VWAP bounces at session opens</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VWAPBands
