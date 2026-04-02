import React, { useState, useMemo, useEffect } from 'react'
import {
  Grid3X3,
  TrendingUp,
  TrendingDown,
  Zap,
  Activity,
  ChevronDown,
  RefreshCw,
  Eye,
  Settings,
  AlertTriangle,
  Layers
} from 'lucide-react'

export function OrderBookHeatmap() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('heatmap') // heatmap, history, analysis
  const [timeRange, setTimeRange] = useState('1h')
  const [depthLevels, setDepthLevels] = useState(25)
  const [refreshKey, setRefreshKey] = useState(0)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate heatmap data over time
  const heatmapData = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const priceStep = basePrice * 0.001
    const timeSlots = 30 // 30 time periods

    const data = []

    for (let t = 0; t < timeSlots; t++) {
      const timeSlot = {
        time: new Date(Date.now() - (timeSlots - t) * 2 * 60 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        levels: []
      }

      for (let p = 0; p < depthLevels; p++) {
        const price = basePrice + (p - depthLevels / 2) * priceStep
        const bidSize = Math.floor(Math.random() * 50000) + 1000
        const askSize = Math.floor(Math.random() * 50000) + 1000

        // Simulate order book changes - some levels get "pulled"
        const wasPulled = Math.random() < 0.1
        const wasAdded = Math.random() < 0.1

        timeSlot.levels.push({
          price,
          bidSize,
          askSize,
          totalSize: bidSize + askSize,
          wasPulled,
          wasAdded
        })
      }

      data.push(timeSlot)
    }

    return data
  }, [selectedToken, depthLevels, refreshKey])

  // Current order book snapshot
  const currentBook = useMemo(() => {
    if (heatmapData.length === 0) return null

    const latest = heatmapData[heatmapData.length - 1]
    const midIdx = Math.floor(latest.levels.length / 2)

    const bids = latest.levels.slice(0, midIdx).reverse()
    const asks = latest.levels.slice(midIdx)

    const totalBidSize = bids.reduce((sum, l) => sum + l.bidSize, 0)
    const totalAskSize = asks.reduce((sum, l) => sum + l.askSize, 0)

    // Find walls
    const maxBid = Math.max(...bids.map(b => b.bidSize))
    const maxAsk = Math.max(...asks.map(a => a.askSize))

    const bidWalls = bids.filter(b => b.bidSize > maxBid * 0.8).map(b => b.price)
    const askWalls = asks.filter(a => a.askSize > maxAsk * 0.8).map(a => a.price)

    return {
      bids,
      asks,
      totalBidSize,
      totalAskSize,
      imbalance: ((totalBidSize - totalAskSize) / (totalBidSize + totalAskSize)) * 100,
      bidWalls,
      askWalls,
      midPrice: latest.levels[midIdx].price
    }
  }, [heatmapData])

  // Spoofing detection
  const spoofingAlerts = useMemo(() => {
    if (heatmapData.length < 10) return []

    const alerts = []
    const recent = heatmapData.slice(-10)

    recent.forEach((slot, slotIdx) => {
      slot.levels.forEach((level, levelIdx) => {
        if (level.wasPulled) {
          alerts.push({
            time: slot.time,
            price: level.price,
            type: 'pulled',
            size: level.totalSize
          })
        }
      })
    })

    return alerts.slice(-5)
  }, [heatmapData])

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshKey(k => k + 1)
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const getHeatColor = (size, maxSize) => {
    const intensity = size / maxSize
    if (intensity > 0.8) return 'bg-purple-500'
    if (intensity > 0.6) return 'bg-purple-500/80'
    if (intensity > 0.4) return 'bg-purple-500/60'
    if (intensity > 0.2) return 'bg-purple-500/40'
    return 'bg-purple-500/20'
  }

  const formatSize = (size) => {
    if (size >= 1000000) return `${(size / 1000000).toFixed(1)}M`
    if (size >= 1000) return `${(size / 1000).toFixed(0)}K`
    return size.toString()
  }

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(0)
    return price.toFixed(2)
  }

  const maxSize = Math.max(...heatmapData.flatMap(slot => slot.levels.map(l => l.totalSize)))

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Grid3X3 className="w-5 h-5 text-fuchsia-400" />
            <h2 className="text-lg font-semibold text-white">Order Book Heatmap</h2>
            <div className="flex items-center gap-1 ml-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-gray-400">Live</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Token Selector */}
            <div className="relative">
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm appearance-none pr-8 cursor-pointer"
              >
                {tokens.map(token => (
                  <option key={token} value={token}>{token}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Time Range */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['15m', '1h', '4h'].map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    timeRange === range
                      ? 'bg-fuchsia-500/30 text-fuchsia-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            <button
              onClick={() => setRefreshKey(k => k + 1)}
              className="p-1.5 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'heatmap', label: 'Live Heatmap', icon: Grid3X3 },
            { id: 'history', label: 'Historical', icon: Activity },
            { id: 'analysis', label: 'Analysis', icon: Eye }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-fuchsia-500/30 text-fuchsia-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Bar */}
      {currentBook && (
        <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Total Bids</div>
              <div className="text-sm font-medium text-green-400">
                {formatSize(currentBook.totalBidSize)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Total Asks</div>
              <div className="text-sm font-medium text-red-400">
                {formatSize(currentBook.totalAskSize)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Imbalance</div>
              <div className={`text-sm font-medium ${currentBook.imbalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {currentBook.imbalance >= 0 ? '+' : ''}{currentBook.imbalance.toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Mid Price</div>
              <div className="text-sm font-medium text-white">
                ${formatPrice(currentBook.midPrice)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Bid Walls</div>
              <div className="text-sm font-medium text-green-400">
                {currentBook.bidWalls.length}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Ask Walls</div>
              <div className="text-sm font-medium text-red-400">
                {currentBook.askWalls.length}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'heatmap' && (
          <div className="space-y-4">
            {/* Heatmap Grid */}
            <div className="overflow-x-auto">
              <div className="min-w-max">
                {/* Time axis */}
                <div className="flex gap-0.5 mb-1 ml-16">
                  {heatmapData.filter((_, i) => i % 5 === 0).map((slot, idx) => (
                    <div key={idx} className="text-[10px] text-gray-500" style={{ width: '30px' }}>
                      {slot.time}
                    </div>
                  ))}
                </div>

                {/* Heatmap rows */}
                <div className="space-y-0.5">
                  {Array.from({ length: depthLevels }, (_, priceIdx) => {
                    const price = heatmapData[0]?.levels[priceIdx]?.price || 0
                    const isAsk = priceIdx >= depthLevels / 2

                    return (
                      <div key={priceIdx} className="flex items-center gap-1">
                        {/* Price label */}
                        <div className={`w-14 text-right text-[10px] font-mono ${
                          isAsk ? 'text-red-400/70' : 'text-green-400/70'
                        }`}>
                          ${formatPrice(price)}
                        </div>

                        {/* Heat cells */}
                        <div className="flex gap-0.5">
                          {heatmapData.map((slot, timeIdx) => {
                            const level = slot.levels[priceIdx]
                            const size = isAsk ? level.askSize : level.bidSize

                            return (
                              <div
                                key={timeIdx}
                                className={`w-3 h-3 rounded-sm ${getHeatColor(size, maxSize)} ${
                                  level.wasPulled ? 'ring-1 ring-yellow-400' : ''
                                }`}
                                title={`${slot.time}: ${formatSize(size)} @ $${formatPrice(level.price)}`}
                              />
                            )
                          })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Low</span>
                <div className="flex gap-0.5">
                  <div className="w-4 h-4 bg-purple-500/20 rounded"></div>
                  <div className="w-4 h-4 bg-purple-500/40 rounded"></div>
                  <div className="w-4 h-4 bg-purple-500/60 rounded"></div>
                  <div className="w-4 h-4 bg-purple-500/80 rounded"></div>
                  <div className="w-4 h-4 bg-purple-500 rounded"></div>
                </div>
                <span className="text-xs text-gray-400">High</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-purple-500/40 ring-1 ring-yellow-400 rounded-sm"></div>
                <span className="text-xs text-gray-400">Order Pulled</span>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'history' && (
          <div className="space-y-4">
            {/* Order Flow History */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Order Book Changes</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {spoofingAlerts.map((alert, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded bg-yellow-500/10 border border-yellow-500/20"
                  >
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      <div>
                        <div className="text-sm text-white">Order {alert.type}</div>
                        <div className="text-xs text-gray-400">{alert.time}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-yellow-400">
                        ${formatPrice(alert.price)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatSize(alert.size)}
                      </div>
                    </div>
                  </div>
                ))}
                {spoofingAlerts.length === 0 && (
                  <div className="text-center text-gray-500 py-4">
                    No significant order changes detected
                  </div>
                )}
              </div>
            </div>

            {/* Wall History */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-green-400 mb-3">Bid Wall Activity</h3>
                <div className="space-y-2">
                  {currentBook?.bidWalls.map((price, idx) => (
                    <div key={idx} className="flex justify-between text-xs">
                      <span className="text-gray-400">Wall {idx + 1}</span>
                      <span className="text-green-400">${formatPrice(price)}</span>
                    </div>
                  ))}
                  {(!currentBook?.bidWalls || currentBook.bidWalls.length === 0) && (
                    <div className="text-xs text-gray-500">No significant walls</div>
                  )}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-red-400 mb-3">Ask Wall Activity</h3>
                <div className="space-y-2">
                  {currentBook?.askWalls.map((price, idx) => (
                    <div key={idx} className="flex justify-between text-xs">
                      <span className="text-gray-400">Wall {idx + 1}</span>
                      <span className="text-red-400">${formatPrice(price)}</span>
                    </div>
                  ))}
                  {(!currentBook?.askWalls || currentBook.askWalls.length === 0) && (
                    <div className="text-xs text-gray-500">No significant walls</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'analysis' && (
          <div className="space-y-4">
            {/* Book Quality */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className={`text-2xl font-bold ${
                  Math.abs(currentBook?.imbalance || 0) < 10 ? 'text-green-400' :
                  Math.abs(currentBook?.imbalance || 0) < 25 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {Math.abs(currentBook?.imbalance || 0) < 10 ? 'Balanced' :
                   Math.abs(currentBook?.imbalance || 0) < 25 ? 'Moderate' : 'Imbalanced'}
                </div>
                <div className="text-xs text-gray-400 mt-1">Book Quality</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  {depthLevels}
                </div>
                <div className="text-xs text-gray-400 mt-1">Depth Levels</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-purple-400">
                  {spoofingAlerts.length}
                </div>
                <div className="text-xs text-gray-400 mt-1">Pulled Orders</div>
              </div>
            </div>

            {/* Depth Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Cumulative Depth</h3>
              <div className="h-32 flex items-end justify-center gap-px">
                {/* Bids */}
                <div className="flex items-end gap-px">
                  {currentBook?.bids.slice().reverse().map((bid, idx, arr) => {
                    const cumSize = arr.slice(0, idx + 1).reduce((sum, b) => sum + b.bidSize, 0)
                    const maxCum = arr.reduce((sum, b) => sum + b.bidSize, 0)
                    const height = (cumSize / maxCum) * 100

                    return (
                      <div
                        key={idx}
                        className="w-2 bg-green-500/60 rounded-t"
                        style={{ height: `${height}%` }}
                      />
                    )
                  })}
                </div>

                {/* Mid divider */}
                <div className="w-0.5 h-full bg-yellow-400 mx-1"></div>

                {/* Asks */}
                <div className="flex items-end gap-px">
                  {currentBook?.asks.map((ask, idx, arr) => {
                    const cumSize = arr.slice(0, idx + 1).reduce((sum, a) => sum + a.askSize, 0)
                    const maxCum = arr.reduce((sum, a) => sum + a.askSize, 0)
                    const height = (cumSize / maxCum) * 100

                    return (
                      <div
                        key={idx}
                        className="w-2 bg-red-500/60 rounded-t"
                        style={{ height: `${height}%` }}
                      />
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Trading Signal */}
            <div className={`rounded-lg p-4 border ${
              (currentBook?.imbalance || 0) > 20 ? 'bg-green-500/10 border-green-500/20' :
              (currentBook?.imbalance || 0) < -20 ? 'bg-red-500/10 border-red-500/20' :
              'bg-white/5 border-white/10'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className={`w-4 h-4 ${
                  (currentBook?.imbalance || 0) > 20 ? 'text-green-400' :
                  (currentBook?.imbalance || 0) < -20 ? 'text-red-400' :
                  'text-gray-400'
                }`} />
                <h3 className="text-sm font-medium text-white">Order Book Signal</h3>
              </div>
              <p className="text-sm text-gray-300">
                {(currentBook?.imbalance || 0) > 20
                  ? `Strong bid side (${(currentBook?.imbalance || 0).toFixed(1)}% imbalance) - potential support forming`
                  : (currentBook?.imbalance || 0) < -20
                  ? `Strong ask side (${(currentBook?.imbalance || 0).toFixed(1)}% imbalance) - potential resistance forming`
                  : `Balanced book (${(currentBook?.imbalance || 0).toFixed(1)}% imbalance) - no strong directional bias`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default OrderBookHeatmap
