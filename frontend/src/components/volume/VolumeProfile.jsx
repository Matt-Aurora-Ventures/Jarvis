import React, { useState, useMemo, useEffect } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Target,
  Layers,
  Eye,
  Settings,
  ChevronUp,
  ChevronDown,
  AlertCircle
} from 'lucide-react'

export function VolumeProfile() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('1d')
  const [viewMode, setViewMode] = useState('profile') // profile, vwap, vpvr
  const [showPOC, setShowPOC] = useState(true)
  const [showVA, setShowVA] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w', '1M']

  // Generate mock volume profile data
  const profileData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    const priceRange = currentPrice * 0.15 // 15% range
    const highPrice = currentPrice + priceRange / 2
    const lowPrice = currentPrice - priceRange / 2
    const levels = 40

    // Generate volume at each price level
    const volumeLevels = Array.from({ length: levels }, (_, i) => {
      const price = lowPrice + (i / levels) * priceRange
      const distanceFromCenter = Math.abs(price - currentPrice) / priceRange
      // More volume near current price (normal distribution-like)
      const baseVolume = Math.exp(-distanceFromCenter * 4) * 1000000
      const randomFactor = 0.5 + Math.random()
      const volume = baseVolume * randomFactor

      // Determine if buy or sell dominant
      const buyRatio = 0.3 + Math.random() * 0.4
      const buyVolume = volume * buyRatio
      const sellVolume = volume * (1 - buyRatio)

      return {
        price,
        volume,
        buyVolume,
        sellVolume,
        isBuyDominant: buyVolume > sellVolume
      }
    })

    // Find POC (Point of Control) - highest volume level
    const poc = volumeLevels.reduce((max, level) =>
      level.volume > max.volume ? level : max, volumeLevels[0])

    // Calculate Value Area (70% of volume)
    const totalVolume = volumeLevels.reduce((sum, l) => sum + l.volume, 0)
    const sortedByVolume = [...volumeLevels].sort((a, b) => b.volume - a.volume)
    let vaVolume = 0
    let vaLevels = []
    for (const level of sortedByVolume) {
      if (vaVolume >= totalVolume * 0.7) break
      vaVolume += level.volume
      vaLevels.push(level)
    }
    const vaPrices = vaLevels.map(l => l.price)
    const vah = Math.max(...vaPrices)
    const val = Math.min(...vaPrices)

    // Generate VWAP data
    const vwapData = Array.from({ length: 24 }, (_, i) => {
      const time = new Date(Date.now() - (23 - i) * 60 * 60 * 1000)
      const price = currentPrice + (Math.random() - 0.5) * priceRange * 0.3
      const volume = Math.floor(Math.random() * 10000000) + 1000000
      return { time, price, volume }
    })

    // Calculate VWAP
    let cumPV = 0
    let cumV = 0
    const vwapLine = vwapData.map(d => {
      cumPV += d.price * d.volume
      cumV += d.volume
      return {
        time: d.time,
        vwap: cumPV / cumV,
        price: d.price,
        volume: d.volume
      }
    })

    const latestVWAP = vwapLine[vwapLine.length - 1]?.vwap || currentPrice

    // High volume nodes
    const hvn = volumeLevels
      .filter(l => l.volume > totalVolume / levels * 1.5)
      .sort((a, b) => b.volume - a.volume)
      .slice(0, 5)

    // Low volume nodes
    const lvn = volumeLevels
      .filter(l => l.volume < totalVolume / levels * 0.5)
      .sort((a, b) => a.volume - b.volume)
      .slice(0, 5)

    return {
      currentPrice,
      highPrice,
      lowPrice,
      volumeLevels,
      poc,
      vah,
      val,
      totalVolume,
      vwapLine,
      latestVWAP,
      hvn,
      lvn,
      priceVsPOC: ((currentPrice - poc.price) / poc.price) * 100,
      priceVsVWAP: ((currentPrice - latestVWAP) / latestVWAP) * 100,
      inValueArea: currentPrice >= val && currentPrice <= vah
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
    return num.toFixed(2)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const maxVolume = Math.max(...profileData.volumeLevels.map(l => l.volume))

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Volume Profile</h2>
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

      {/* Key Levels Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
          <div className="text-gray-400 text-sm mb-1">POC (Point of Control)</div>
          <div className="text-xl font-bold text-purple-400">${formatPrice(profileData.poc.price)}</div>
          <div className={`text-sm ${profileData.priceVsPOC >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {profileData.priceVsPOC >= 0 ? '+' : ''}{profileData.priceVsPOC.toFixed(2)}% from price
          </div>
        </div>
        <div className="bg-cyan-500/10 rounded-lg p-4 border border-cyan-500/20">
          <div className="text-gray-400 text-sm mb-1">VWAP</div>
          <div className="text-xl font-bold text-cyan-400">${formatPrice(profileData.latestVWAP)}</div>
          <div className={`text-sm ${profileData.priceVsVWAP >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {profileData.priceVsVWAP >= 0 ? '+' : ''}{profileData.priceVsVWAP.toFixed(2)}% from price
          </div>
        </div>
        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
          <div className="text-gray-400 text-sm mb-1">Value Area High</div>
          <div className="text-xl font-bold text-green-400">${formatPrice(profileData.vah)}</div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
          <div className="text-gray-400 text-sm mb-1">Value Area Low</div>
          <div className="text-xl font-bold text-red-400">${formatPrice(profileData.val)}</div>
        </div>
      </div>

      {/* Position Status */}
      <div className={`rounded-lg p-4 mb-6 flex items-center justify-between ${
        profileData.inValueArea ? 'bg-yellow-500/10 border border-yellow-500/20' : 'bg-blue-500/10 border border-blue-500/20'
      }`}>
        <div className="flex items-center gap-3">
          {profileData.inValueArea ? (
            <Layers className="w-5 h-5 text-yellow-400" />
          ) : (
            <AlertCircle className="w-5 h-5 text-blue-400" />
          )}
          <div>
            <div className={`font-medium ${profileData.inValueArea ? 'text-yellow-400' : 'text-blue-400'}`}>
              {profileData.inValueArea ? 'Price Inside Value Area' : 'Price Outside Value Area'}
            </div>
            <div className="text-gray-400 text-sm">
              Current: ${formatPrice(profileData.currentPrice)} | Range: ${formatPrice(profileData.val)} - ${formatPrice(profileData.vah)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={showPOC}
              onChange={(e) => setShowPOC(e.target.checked)}
              className="rounded"
            />
            POC
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={showVA}
              onChange={(e) => setShowVA(e.target.checked)}
              className="rounded"
            />
            VA
          </label>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'profile', label: 'Volume Profile' },
          { id: 'vwap', label: 'VWAP' },
          { id: 'vpvr', label: 'Visible Range' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Volume Profile View */}
      {viewMode === 'profile' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <div className="flex gap-4">
            {/* Price Scale */}
            <div className="w-20 flex flex-col justify-between text-right text-xs text-gray-500">
              <span>${formatPrice(profileData.highPrice)}</span>
              {showVA && <span className="text-green-400">${formatPrice(profileData.vah)}</span>}
              {showPOC && <span className="text-purple-400">${formatPrice(profileData.poc.price)}</span>}
              <span className="text-white">${formatPrice(profileData.currentPrice)}</span>
              {showVA && <span className="text-red-400">${formatPrice(profileData.val)}</span>}
              <span>${formatPrice(profileData.lowPrice)}</span>
            </div>

            {/* Volume Bars */}
            <div className="flex-1 relative">
              {/* Value Area Highlight */}
              {showVA && (
                <div
                  className="absolute left-0 right-0 bg-yellow-500/10 border-y border-yellow-500/30"
                  style={{
                    top: `${((profileData.highPrice - profileData.vah) / (profileData.highPrice - profileData.lowPrice)) * 100}%`,
                    bottom: `${((profileData.val - profileData.lowPrice) / (profileData.highPrice - profileData.lowPrice)) * 100}%`
                  }}
                />
              )}

              {/* Volume Bars */}
              <div className="flex flex-col gap-0.5 relative z-10">
                {[...profileData.volumeLevels].reverse().map((level, i) => {
                  const isPOC = showPOC && level.price === profileData.poc.price
                  const width = (level.volume / maxVolume) * 100
                  const buyWidth = (level.buyVolume / level.volume) * width
                  const sellWidth = (level.sellVolume / level.volume) * width

                  return (
                    <div key={i} className="h-3 flex items-center group relative">
                      <div className="flex" style={{ width: `${width}%` }}>
                        <div
                          className={`h-full ${isPOC ? 'bg-purple-500' : 'bg-green-500/70'}`}
                          style={{ width: `${(buyWidth / width) * 100}%` }}
                        />
                        <div
                          className={`h-full ${isPOC ? 'bg-purple-400' : 'bg-red-500/70'}`}
                          style={{ width: `${(sellWidth / width) * 100}%` }}
                        />
                      </div>
                      {isPOC && (
                        <span className="ml-2 text-xs text-purple-400 font-medium">POC</span>
                      )}
                      <div className="absolute left-full ml-2 hidden group-hover:block bg-black/90 p-2 rounded text-xs text-white whitespace-nowrap z-20">
                        <div>Price: ${formatPrice(level.price)}</div>
                        <div>Volume: ${formatNumber(level.volume)}</div>
                        <div className="text-green-400">Buy: ${formatNumber(level.buyVolume)}</div>
                        <div className="text-red-400">Sell: ${formatNumber(level.sellVolume)}</div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Current Price Line */}
              <div
                className="absolute left-0 right-0 h-0.5 bg-white z-20"
                style={{
                  top: `${((profileData.highPrice - profileData.currentPrice) / (profileData.highPrice - profileData.lowPrice)) * 100}%`
                }}
              />
            </div>
          </div>

          <div className="flex justify-center gap-6 mt-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-green-500/70 rounded" /> Buy Volume
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-red-500/70 rounded" /> Sell Volume
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-purple-500 rounded" /> POC
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-yellow-500/30 rounded" /> Value Area
            </span>
          </div>
        </div>
      )}

      {/* VWAP View */}
      {viewMode === 'vwap' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">VWAP (Volume Weighted Average Price)</h3>
          <div className="h-48 flex items-end gap-1 mb-4">
            {profileData.vwapLine.map((point, i) => {
              const priceHeight = ((point.price - profileData.lowPrice) / (profileData.highPrice - profileData.lowPrice)) * 100
              const vwapHeight = ((point.vwap - profileData.lowPrice) / (profileData.highPrice - profileData.lowPrice)) * 100

              return (
                <div key={i} className="flex-1 relative h-full group">
                  {/* Price Bar */}
                  <div
                    className="absolute bottom-0 w-full bg-white/20 rounded-t"
                    style={{ height: `${priceHeight}%` }}
                  />
                  {/* VWAP Line Point */}
                  <div
                    className="absolute w-2 h-2 bg-cyan-400 rounded-full -ml-0.5 left-1/2"
                    style={{ bottom: `${vwapHeight}%` }}
                  />
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black/90 p-2 rounded text-xs text-white whitespace-nowrap z-10 left-1/2 -translate-x-1/2">
                    <div>{formatTime(point.time)}</div>
                    <div>Price: ${formatPrice(point.price)}</div>
                    <div className="text-cyan-400">VWAP: ${formatPrice(point.vwap)}</div>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>{formatTime(profileData.vwapLine[0]?.time)}</span>
            <span>{formatTime(profileData.vwapLine[profileData.vwapLine.length - 1]?.time)}</span>
          </div>
          <div className="mt-4 p-3 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Current Price vs VWAP</span>
              <span className={profileData.currentPrice > profileData.latestVWAP ? 'text-green-400' : 'text-red-400'}>
                {profileData.currentPrice > profileData.latestVWAP ? 'Above' : 'Below'} VWAP by {Math.abs(profileData.priceVsVWAP).toFixed(2)}%
              </span>
            </div>
          </div>
        </div>
      )}

      {/* VPVR (Visible Range) View */}
      {viewMode === 'vpvr' && (
        <div className="space-y-4">
          {/* High Volume Nodes */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <ChevronUp className="w-4 h-4 text-green-400" />
              High Volume Nodes (HVN) - Support/Resistance
            </h3>
            <div className="space-y-2">
              {profileData.hvn.map((node, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-white">${formatPrice(node.price)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      node.price > profileData.currentPrice
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-green-500/20 text-green-400'
                    }`}>
                      {node.price > profileData.currentPrice ? 'Resistance' : 'Support'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500"
                        style={{ width: `${(node.volume / maxVolume) * 100}%` }}
                      />
                    </div>
                    <span className="text-gray-400 text-sm">${formatNumber(node.volume)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Low Volume Nodes */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <ChevronDown className="w-4 h-4 text-yellow-400" />
              Low Volume Nodes (LVN) - Fast Move Zones
            </h3>
            <div className="space-y-2">
              {profileData.lvn.map((node, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-white">${formatPrice(node.price)}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                      Low Liquidity
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-yellow-500"
                        style={{ width: `${(node.volume / maxVolume) * 100}%` }}
                      />
                    </div>
                    <span className="text-gray-400 text-sm">${formatNumber(node.volume)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Volume Stats */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3">Volume Statistics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-gray-400 text-sm">Total Volume</div>
                <div className="text-white font-medium">${formatNumber(profileData.totalVolume)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Value Area Volume</div>
                <div className="text-white font-medium">${formatNumber(profileData.totalVolume * 0.7)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">POC Volume</div>
                <div className="text-purple-400 font-medium">${formatNumber(profileData.poc.volume)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Avg Volume/Level</div>
                <div className="text-white font-medium">${formatNumber(profileData.totalVolume / 40)}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VolumeProfile
