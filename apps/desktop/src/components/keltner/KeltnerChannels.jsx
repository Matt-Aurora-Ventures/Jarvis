import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Layers,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Settings,
  Zap,
  AlertTriangle,
  ChevronRight,
  Filter,
  Bell,
  Eye,
  LineChart
} from 'lucide-react'

export function KeltnerChannels() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('channels') // channels, squeeze, signals
  const [emaPeriod, setEmaPeriod] = useState(20)
  const [atrPeriod, setAtrPeriod] = useState(10)
  const [atrMultiplier, setAtrMultiplier] = useState(2)

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']

  // Generate Keltner Channel data
  const keltnerData = useMemo(() => {
    return tokens.map(token => {
      const currentPrice = 50 + Math.random() * 150
      const ema = currentPrice * (0.97 + Math.random() * 0.06)
      const atr = currentPrice * 0.02 * (1 + Math.random() * 0.5)

      const upperChannel = ema + (atr * atrMultiplier)
      const lowerChannel = ema - (atr * atrMultiplier)

      // Calculate position
      let position = 'middle'
      let positionLabel = 'Within Channel'
      let channelWidth = ((upperChannel - lowerChannel) / ema * 100)

      if (currentPrice > upperChannel) {
        position = 'above'
        positionLabel = 'Breakout Above'
      } else if (currentPrice < lowerChannel) {
        position = 'below'
        positionLabel = 'Breakout Below'
      } else if (currentPrice > ema) {
        position = 'upper_half'
        positionLabel = 'Upper Half'
      } else {
        position = 'lower_half'
        positionLabel = 'Lower Half'
      }

      // Bollinger Bands for squeeze detection
      const bbUpper = ema + (currentPrice * 0.015 * 2) // 2 std dev approximation
      const bbLower = ema - (currentPrice * 0.015 * 2)

      // Squeeze: Bollinger inside Keltner
      const inSqueeze = bbUpper < upperChannel && bbLower > lowerChannel
      const squeezeFiring = !inSqueeze && Math.random() > 0.7

      // ATR value and volatility
      const volatility = channelWidth > 8 ? 'high' : channelWidth > 4 ? 'normal' : 'low'

      // Channel trend
      const channelTrend = ema > currentPrice * 0.98 ? 'up' : ema < currentPrice * 1.02 ? 'down' : 'flat'

      return {
        token,
        currentPrice,
        ema,
        atr,
        upperChannel,
        lowerChannel,
        position,
        positionLabel,
        channelWidth,
        inSqueeze,
        squeezeFiring,
        volatility,
        channelTrend,
        bbUpper,
        bbLower,
        distanceFromEma: ((currentPrice - ema) / ema * 100),
        volume24h: (Math.random() * 500).toFixed(1)
      }
    })
  }, [atrMultiplier])

  // Price history for chart
  const priceHistory = useMemo(() => {
    const tokenData = keltnerData.find(d => d.token === selectedToken)
    const basePrice = tokenData?.currentPrice || 100
    const data = []

    for (let i = 30; i >= 0; i--) {
      const price = basePrice * (0.9 + Math.random() * 0.2)
      const ema = basePrice * (0.95 + Math.random() * 0.1)
      const atr = basePrice * 0.02 * (0.8 + Math.random() * 0.4)

      data.push({
        time: i === 0 ? 'Now' : `-${i}`,
        price,
        ema,
        upper: ema + atr * atrMultiplier,
        lower: ema - atr * atrMultiplier
      })
    }
    return data
  }, [selectedToken, atrMultiplier, keltnerData])

  // Squeeze history
  const squeezeHistory = useMemo(() => {
    const data = []
    for (let i = 20; i >= 0; i--) {
      data.push({
        time: i === 0 ? 'Now' : `-${i}`,
        inSqueeze: Math.random() > 0.6,
        momentum: (Math.random() - 0.5) * 2
      })
    }
    return data
  }, [selectedToken])

  // Signals
  const signals = useMemo(() => {
    return [
      { token: 'SOL', type: 'breakout_up', price: 145.20, time: '5m ago', strength: 'strong' },
      { token: 'BTC', type: 'squeeze_fire', price: 68500, time: '12m ago', strength: 'medium' },
      { token: 'ETH', type: 'mean_reversion', price: 2380, time: '25m ago', strength: 'strong' },
      { token: 'BONK', type: 'breakout_down', price: 0.000025, time: '1h ago', strength: 'weak' },
      { token: 'JUP', type: 'channel_ride', price: 0.95, time: '2h ago', strength: 'medium' }
    ]
  }, [])

  // Stats
  const aboveChannel = keltnerData.filter(d => d.position === 'above').length
  const belowChannel = keltnerData.filter(d => d.position === 'below').length
  const inSqueezeCount = keltnerData.filter(d => d.inSqueeze).length
  const squeezeFiringCount = keltnerData.filter(d => d.squeezeFiring).length

  const getPositionColor = (position) => {
    switch (position) {
      case 'above': return 'text-green-400'
      case 'below': return 'text-red-400'
      case 'upper_half': return 'text-cyan-400'
      case 'lower_half': return 'text-orange-400'
      default: return 'text-white/60'
    }
  }

  const getPositionBg = (position) => {
    switch (position) {
      case 'above': return 'bg-green-500/10'
      case 'below': return 'bg-red-500/10'
      case 'upper_half': return 'bg-cyan-500/10'
      case 'lower_half': return 'bg-orange-500/10'
      default: return 'bg-white/5'
    }
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-orange-500/20 rounded-lg">
            <Layers className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Keltner Channels</h1>
            <p className="text-white/60 text-sm">ATR-based volatility bands with squeeze detection</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Settings */}
          <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
            <span className="text-white/60 text-sm">EMA:</span>
            <select
              value={emaPeriod}
              onChange={(e) => setEmaPeriod(Number(e.target.value))}
              className="bg-transparent text-white text-sm outline-none"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
            <span className="text-white/60 text-sm">ATR x</span>
            <select
              value={atrMultiplier}
              onChange={(e) => setAtrMultiplier(Number(e.target.value))}
              className="bg-transparent text-white text-sm outline-none"
            >
              <option value={1}>1</option>
              <option value={1.5}>1.5</option>
              <option value={2}>2</option>
              <option value={2.5}>2.5</option>
              <option value={3}>3</option>
            </select>
          </div>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['channels', 'squeeze', 'signals'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-orange-500 text-white' : 'text-white/60 hover:text-white'
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
            <span className="text-white/60 text-sm">Above Channel</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{aboveChannel}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <ArrowDown className="w-4 h-4 text-red-400" />
            <span className="text-white/60 text-sm">Below Channel</span>
          </div>
          <p className="text-2xl font-bold text-red-400">{belowChannel}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">In Squeeze</span>
          </div>
          <p className="text-2xl font-bold text-yellow-400">{inSqueezeCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Squeeze Firing</span>
          </div>
          <p className="text-2xl font-bold text-purple-400">{squeezeFiringCount}</p>
        </div>
      </div>

      {viewMode === 'channels' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Channel Scanner Table */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Price</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">EMA</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Position</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Channel Width</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Volatility</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Squeeze</th>
                </tr>
              </thead>
              <tbody>
                {keltnerData.map((item, idx) => (
                  <tr
                    key={item.token}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      selectedToken === item.token ? 'bg-orange-500/10' : idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.token}</span>
                        {item.squeezeFiring && (
                          <Zap className="w-3 h-3 text-purple-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right font-medium">
                      ${item.currentPrice.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right text-orange-400">
                      ${item.ema.toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getPositionBg(item.position)} ${getPositionColor(item.position)}`}>
                          {item.positionLabel}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right text-white/60">
                      {item.channelWidth.toFixed(2)}%
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`px-2 py-1 rounded text-xs ${
                        item.volatility === 'high' ? 'bg-red-500/10 text-red-400' :
                        item.volatility === 'low' ? 'bg-blue-500/10 text-blue-400' :
                        'bg-white/5 text-white/60'
                      }`}>
                        {item.volatility}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {item.inSqueeze ? (
                        <span className="px-2 py-1 rounded text-xs bg-yellow-500/10 text-yellow-400">
                          Active
                        </span>
                      ) : (
                        <span className="text-white/30">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Selected Token Details */}
          <div className="space-y-4">
            {(() => {
              const tokenData = keltnerData.find(d => d.token === selectedToken)
              return (
                <>
                  {/* Channel Levels */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-orange-400" />
                      {selectedToken} Keltner Channels
                    </h3>

                    <div className="space-y-2">
                      <div className="flex justify-between items-center p-2 bg-green-500/10 rounded">
                        <span className="text-green-400 text-sm">Upper Channel</span>
                        <span className="font-medium">${tokenData.upperChannel.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-orange-500/20 rounded border border-orange-500/30">
                        <span className="text-orange-400 text-sm font-medium">EMA ({emaPeriod})</span>
                        <span className="font-bold text-orange-400">${tokenData.ema.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center p-2 bg-red-500/10 rounded">
                        <span className="text-red-400 text-sm">Lower Channel</span>
                        <span className="font-medium">${tokenData.lowerChannel.toFixed(2)}</span>
                      </div>
                    </div>

                    {/* Current Price */}
                    <div className="mt-3 p-2 bg-white/5 rounded-lg">
                      <div className="flex justify-between items-center">
                        <span className="text-white/60 text-sm">Current Price</span>
                        <span className="font-bold">${tokenData.currentPrice.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center mt-1">
                        <span className="text-white/60 text-sm">From EMA</span>
                        <span className={tokenData.distanceFromEma >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {tokenData.distanceFromEma >= 0 ? '+' : ''}{tokenData.distanceFromEma.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* ATR Info */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-cyan-400" />
                      ATR Analysis
                    </h3>

                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-white/60">ATR Value</span>
                        <span className="font-medium">${tokenData.atr.toFixed(4)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">ATR %</span>
                        <span className="font-medium">
                          {(tokenData.atr / tokenData.currentPrice * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">Channel Width</span>
                        <span className="font-medium">{tokenData.channelWidth.toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">Volatility</span>
                        <span className={`font-medium ${
                          tokenData.volatility === 'high' ? 'text-red-400' :
                          tokenData.volatility === 'low' ? 'text-blue-400' : 'text-white'
                        }`}>
                          {tokenData.volatility.charAt(0).toUpperCase() + tokenData.volatility.slice(1)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Squeeze Status */}
                  <div className={`border rounded-xl p-4 ${
                    tokenData.inSqueeze
                      ? 'bg-yellow-500/10 border-yellow-500/30'
                      : tokenData.squeezeFiring
                        ? 'bg-purple-500/10 border-purple-500/30'
                        : 'bg-white/5 border-white/10'
                  }`}>
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Target className="w-4 h-4 text-yellow-400" />
                      Squeeze Status
                    </h3>

                    {tokenData.inSqueeze ? (
                      <div className="text-center">
                        <div className="w-12 h-12 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-2">
                          <Target className="w-6 h-6 text-yellow-400" />
                        </div>
                        <p className="text-yellow-400 font-medium">SQUEEZE ACTIVE</p>
                        <p className="text-white/60 text-sm mt-1">Bollinger inside Keltner</p>
                        <p className="text-white/40 text-xs mt-1">Waiting for breakout...</p>
                      </div>
                    ) : tokenData.squeezeFiring ? (
                      <div className="text-center">
                        <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-2">
                          <Zap className="w-6 h-6 text-purple-400" />
                        </div>
                        <p className="text-purple-400 font-medium">SQUEEZE FIRING</p>
                        <p className="text-white/60 text-sm mt-1">Momentum releasing</p>
                      </div>
                    ) : (
                      <div className="text-center">
                        <p className="text-white/40">No squeeze detected</p>
                        <p className="text-white/30 text-sm mt-1">Normal volatility conditions</p>
                      </div>
                    )}
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {viewMode === 'squeeze' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Squeeze Scanner */}
          <div className="col-span-2 space-y-4">
            {/* Active Squeezes */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-yellow-400" />
                Active Squeezes
              </h2>

              <div className="grid grid-cols-2 gap-3">
                {keltnerData.filter(d => d.inSqueeze).map(item => (
                  <div
                    key={item.token}
                    className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl cursor-pointer hover:bg-yellow-500/20"
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold">{item.token}</span>
                      <Target className="w-4 h-4 text-yellow-400 animate-pulse" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/60">Price</span>
                      <span>${item.currentPrice.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/60">Width</span>
                      <span>{item.channelWidth.toFixed(2)}%</span>
                    </div>
                  </div>
                ))}
                {keltnerData.filter(d => d.inSqueeze).length === 0 && (
                  <div className="col-span-2 text-center py-8 text-white/40">
                    No active squeezes detected
                  </div>
                )}
              </div>
            </div>

            {/* Squeeze Firing */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-400" />
                Squeeze Firing (Breakouts)
              </h2>

              <div className="grid grid-cols-2 gap-3">
                {keltnerData.filter(d => d.squeezeFiring).map(item => (
                  <div
                    key={item.token}
                    className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl cursor-pointer hover:bg-purple-500/20"
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold">{item.token}</span>
                      <div className="flex items-center gap-1">
                        <Zap className="w-4 h-4 text-purple-400" />
                        {item.position === 'above' ? (
                          <ArrowUp className="w-4 h-4 text-green-400" />
                        ) : item.position === 'below' ? (
                          <ArrowDown className="w-4 h-4 text-red-400" />
                        ) : null}
                      </div>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/60">Price</span>
                      <span>${item.currentPrice.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/60">Direction</span>
                      <span className={item.distanceFromEma >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {item.distanceFromEma >= 0 ? 'Bullish' : 'Bearish'}
                      </span>
                    </div>
                  </div>
                ))}
                {keltnerData.filter(d => d.squeezeFiring).length === 0 && (
                  <div className="col-span-2 text-center py-8 text-white/40">
                    No squeezes firing currently
                  </div>
                )}
              </div>
            </div>

            {/* Squeeze History Chart */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <LineChart className="w-5 h-5 text-cyan-400" />
                {selectedToken} Squeeze History
              </h2>

              <div className="h-32 flex items-end gap-1">
                {squeezeHistory.map((item, idx) => (
                  <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                    {/* Momentum Bar */}
                    <div className="w-full relative h-20">
                      <div
                        className={`absolute bottom-1/2 w-full ${
                          item.momentum >= 0 ? 'bg-green-500' : 'bg-red-500'
                        }`}
                        style={{
                          height: `${Math.abs(item.momentum) * 40}%`,
                          transform: item.momentum >= 0 ? 'translateY(0)' : 'translateY(100%)',
                          bottom: item.momentum >= 0 ? '50%' : 'auto',
                          top: item.momentum < 0 ? '50%' : 'auto'
                        }}
                      />
                    </div>
                    {/* Squeeze Indicator */}
                    <div className={`w-2 h-2 rounded-full ${
                      item.inSqueeze ? 'bg-red-500' : 'bg-green-500'
                    }`} />
                  </div>
                ))}
              </div>

              <div className="flex justify-center gap-6 mt-3 text-xs text-white/60">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-red-500" />
                  <span>Squeeze On</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Squeeze Off</span>
                </div>
              </div>
            </div>
          </div>

          {/* Squeeze Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                TTM Squeeze Guide
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                  <p className="text-yellow-400 font-medium">Squeeze On (Red Dots)</p>
                  <p className="text-white/60 text-xs mt-1">BB inside Keltner. Low volatility, consolidation. Prepare for breakout.</p>
                </div>

                <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                  <p className="text-green-400 font-medium">Squeeze Off (Green Dots)</p>
                  <p className="text-white/60 text-xs mt-1">BB outside Keltner. Volatility expanding, momentum moving.</p>
                </div>

                <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
                  <p className="text-purple-400 font-medium">Squeeze Firing</p>
                  <p className="text-white/60 text-xs mt-1">First green dot after red. Entry signal in momentum direction.</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-orange-400" />
                Momentum Reading
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Green bars above zero = bullish momentum</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>Red bars below zero = bearish momentum</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Fading bars = momentum weakening</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-purple-400 mt-0.5 flex-shrink-0" />
                  <span>Strongest signals: squeeze fire + momentum aligned</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'signals' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Recent Signals */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Bell className="w-5 h-5 text-yellow-400" />
              Recent Keltner Signals
            </h2>

            <div className="space-y-3">
              {signals.map((signal, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border ${
                    signal.type.includes('up') || signal.type === 'squeeze_fire' && signal.strength === 'strong'
                      ? 'bg-green-500/10 border-green-500/30'
                      : signal.type.includes('down')
                        ? 'bg-red-500/10 border-red-500/30'
                        : 'bg-white/5 border-white/10'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-lg">{signal.token}</span>
                      <span className={`px-2 py-1 rounded text-xs ${
                        signal.type === 'breakout_up' ? 'bg-green-500/20 text-green-400' :
                        signal.type === 'breakout_down' ? 'bg-red-500/20 text-red-400' :
                        signal.type === 'squeeze_fire' ? 'bg-purple-500/20 text-purple-400' :
                        signal.type === 'mean_reversion' ? 'bg-cyan-500/20 text-cyan-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {signal.type.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded ${
                        signal.strength === 'strong' ? 'bg-green-500/20 text-green-400' :
                        signal.strength === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {signal.strength}
                      </span>
                      <span className="text-white/40 text-sm">{signal.time}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-sm">
                    <div>
                      <span className="text-white/60">Price: </span>
                      <span className="font-medium">${signal.price}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Signal Types Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-purple-400" />
                Signal Types
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <p className="text-green-400 font-medium">Breakout Up</p>
                  <p className="text-white/60 text-xs">Price closes above upper channel</p>
                </div>
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <p className="text-red-400 font-medium">Breakout Down</p>
                  <p className="text-white/60 text-xs">Price closes below lower channel</p>
                </div>
                <div className="p-2 bg-purple-500/10 rounded-lg">
                  <p className="text-purple-400 font-medium">Squeeze Fire</p>
                  <p className="text-white/60 text-xs">First release after squeeze</p>
                </div>
                <div className="p-2 bg-cyan-500/10 rounded-lg">
                  <p className="text-cyan-400 font-medium">Mean Reversion</p>
                  <p className="text-white/60 text-xs">Return to EMA from channel edge</p>
                </div>
                <div className="p-2 bg-orange-500/10 rounded-lg">
                  <p className="text-orange-400 font-medium">Channel Ride</p>
                  <p className="text-white/60 text-xs">Trending along channel boundary</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3">Signal Stats (24h)</h3>

              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Total Signals</span>
                  <span className="font-bold">23</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Win Rate</span>
                  <span className="font-bold text-green-400">72%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Avg Profit</span>
                  <span className="font-bold text-green-400">+3.2%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Best Signal</span>
                  <span className="font-bold">SOL +8.5%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default KeltnerChannels
