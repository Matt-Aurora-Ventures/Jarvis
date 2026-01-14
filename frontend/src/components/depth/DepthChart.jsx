import React, { useState, useMemo, useEffect } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Settings,
  ZoomIn,
  ZoomOut,
  Layers,
  AlertTriangle,
  DollarSign,
  Activity,
  Eye,
  ArrowUp,
  ArrowDown,
  Target
} from 'lucide-react'

export function DepthChart() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [zoomLevel, setZoomLevel] = useState(5) // percentage from mid
  const [showOrders, setShowOrders] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY']

  // Generate mock order book data
  const orderBookData = useMemo(() => {
    const midPrice = selectedToken === 'SOL' ? 178.50 :
                     selectedToken === 'ETH' ? 3456.00 :
                     selectedToken === 'BTC' ? 67500.00 :
                     Math.random() * 100 + 1

    const spread = midPrice * 0.0005
    const bidPrice = midPrice - spread / 2
    const askPrice = midPrice + spread / 2

    // Generate bids (buy orders) - decreasing prices
    const bids = Array.from({ length: 50 }, (_, i) => {
      const priceOffset = (i + 1) * (midPrice * 0.001)
      const price = bidPrice - priceOffset
      const size = Math.random() * 1000 + 50
      const total = size * price

      return {
        price,
        size,
        total,
        cumulative: 0 // Will calculate
      }
    })

    // Calculate cumulative for bids
    let cumBid = 0
    bids.forEach(bid => {
      cumBid += bid.size
      bid.cumulative = cumBid
    })

    // Generate asks (sell orders) - increasing prices
    const asks = Array.from({ length: 50 }, (_, i) => {
      const priceOffset = (i + 1) * (midPrice * 0.001)
      const price = askPrice + priceOffset
      const size = Math.random() * 1000 + 50
      const total = size * price

      return {
        price,
        size,
        total,
        cumulative: 0 // Will calculate
      }
    })

    // Calculate cumulative for asks
    let cumAsk = 0
    asks.forEach(ask => {
      cumAsk += ask.size
      ask.cumulative = cumAsk
    })

    // Find walls (large orders)
    const avgBidSize = bids.reduce((sum, b) => sum + b.size, 0) / bids.length
    const avgAskSize = asks.reduce((sum, a) => sum + a.size, 0) / asks.length

    const bidWalls = bids.filter(b => b.size > avgBidSize * 3).slice(0, 3)
    const askWalls = asks.filter(a => a.size > avgAskSize * 3).slice(0, 3)

    return {
      midPrice,
      bidPrice,
      askPrice,
      spread,
      spreadPercent: (spread / midPrice * 100).toFixed(4),
      bids,
      asks,
      bidWalls,
      askWalls,
      totalBidLiquidity: bids.reduce((sum, b) => sum + b.total, 0),
      totalAskLiquidity: asks.reduce((sum, a) => sum + a.total, 0),
      imbalance: ((bids.reduce((sum, b) => sum + b.size, 0) - asks.reduce((sum, a) => sum + a.size, 0)) /
                 (bids.reduce((sum, b) => sum + b.size, 0) + asks.reduce((sum, a) => sum + a.size, 0)) * 100)
    }
  }, [selectedToken])

  // Filter data based on zoom level
  const visibleData = useMemo(() => {
    const priceRange = orderBookData.midPrice * (zoomLevel / 100)
    const minPrice = orderBookData.midPrice - priceRange
    const maxPrice = orderBookData.midPrice + priceRange

    return {
      bids: orderBookData.bids.filter(b => b.price >= minPrice),
      asks: orderBookData.asks.filter(a => a.price <= maxPrice)
    }
  }, [orderBookData, zoomLevel])

  const maxCumulative = Math.max(
    visibleData.bids.length ? visibleData.bids[visibleData.bids.length - 1].cumulative : 0,
    visibleData.asks.length ? visibleData.asks[visibleData.asks.length - 1].cumulative : 0
  )

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 500)
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
    return num.toFixed(2)
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-cyan-400" />
          <h2 className="text-xl font-bold text-white">Depth Chart</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {tokens.map(token => (
              <option key={token} value={token}>{token}/USDC</option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Price Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <div className="text-gray-400 text-xs">Mid Price</div>
          <div className="text-lg font-bold text-white">${formatPrice(orderBookData.midPrice)}</div>
        </div>
        <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
          <div className="text-gray-400 text-xs">Best Bid</div>
          <div className="text-lg font-bold text-green-400">${formatPrice(orderBookData.bidPrice)}</div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
          <div className="text-gray-400 text-xs">Best Ask</div>
          <div className="text-lg font-bold text-red-400">${formatPrice(orderBookData.askPrice)}</div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <div className="text-gray-400 text-xs">Spread</div>
          <div className="text-lg font-bold text-white">{orderBookData.spreadPercent}%</div>
        </div>
        <div className={`rounded-lg p-3 border ${orderBookData.imbalance >= 0 ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
          <div className="text-gray-400 text-xs">Imbalance</div>
          <div className={`text-lg font-bold ${orderBookData.imbalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {orderBookData.imbalance >= 0 ? '+' : ''}{orderBookData.imbalance.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Zoom Controls */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoomLevel(Math.max(1, zoomLevel - 1))}
            className="p-2 bg-white/5 rounded-lg hover:bg-white/10"
          >
            <ZoomIn className="w-4 h-4 text-gray-400" />
          </button>
          <input
            type="range"
            min="1"
            max="20"
            value={zoomLevel}
            onChange={(e) => setZoomLevel(Number(e.target.value))}
            className="w-32"
          />
          <button
            onClick={() => setZoomLevel(Math.min(20, zoomLevel + 1))}
            className="p-2 bg-white/5 rounded-lg hover:bg-white/10"
          >
            <ZoomOut className="w-4 h-4 text-gray-400" />
          </button>
          <span className="text-gray-400 text-sm ml-2">{zoomLevel}%</span>
        </div>
        <button
          onClick={() => setShowOrders(!showOrders)}
          className={`p-2 rounded-lg ${showOrders ? 'bg-cyan-500/20 text-cyan-400' : 'bg-white/5 text-gray-400'}`}
        >
          <Eye className="w-4 h-4" />
        </button>
      </div>

      {/* Depth Chart Visualization */}
      <div className="bg-white/5 rounded-lg p-4 border border-white/10 mb-6">
        <div className="h-64 flex relative">
          {/* Bid Side (Left) */}
          <div className="flex-1 relative flex flex-col">
            <div className="flex-1 relative">
              {visibleData.bids.map((bid, i) => {
                const width = (bid.cumulative / maxCumulative) * 100
                return (
                  <div
                    key={i}
                    className="absolute right-0 bg-green-500/30 border-r border-green-500"
                    style={{
                      width: `${width}%`,
                      height: '4px',
                      bottom: `${(i / visibleData.bids.length) * 100}%`
                    }}
                  />
                )
              })}
            </div>
            <div className="text-center text-green-400 text-sm mt-2">
              Bids: ${formatNumber(orderBookData.totalBidLiquidity)}
            </div>
          </div>

          {/* Mid Line */}
          <div className="w-px bg-white/20 relative">
            <div className="absolute -left-8 -top-2 text-xs text-gray-400">
              ${formatPrice(orderBookData.midPrice * (1 + zoomLevel / 100))}
            </div>
            <div className="absolute -left-8 top-1/2 -translate-y-1/2 px-2 py-1 bg-white/10 rounded text-white text-sm">
              ${formatPrice(orderBookData.midPrice)}
            </div>
            <div className="absolute -left-8 -bottom-2 text-xs text-gray-400">
              ${formatPrice(orderBookData.midPrice * (1 - zoomLevel / 100))}
            </div>
          </div>

          {/* Ask Side (Right) */}
          <div className="flex-1 relative flex flex-col">
            <div className="flex-1 relative">
              {visibleData.asks.map((ask, i) => {
                const width = (ask.cumulative / maxCumulative) * 100
                return (
                  <div
                    key={i}
                    className="absolute left-0 bg-red-500/30 border-l border-red-500"
                    style={{
                      width: `${width}%`,
                      height: '4px',
                      bottom: `${(i / visibleData.asks.length) * 100}%`
                    }}
                  />
                )
              })}
            </div>
            <div className="text-center text-red-400 text-sm mt-2">
              Asks: ${formatNumber(orderBookData.totalAskLiquidity)}
            </div>
          </div>
        </div>
      </div>

      {/* Order Book & Walls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Order Book */}
        {showOrders && (
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Order Book
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {/* Bids */}
              <div>
                <div className="text-xs text-gray-500 mb-2 flex justify-between">
                  <span>Price</span>
                  <span>Size</span>
                </div>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {visibleData.bids.slice(0, 15).map((bid, i) => (
                    <div key={i} className="flex justify-between text-xs relative">
                      <div
                        className="absolute inset-0 bg-green-500/10 rounded"
                        style={{ width: `${(bid.size / (visibleData.bids[0]?.size || 1)) * 100}%` }}
                      />
                      <span className="relative text-green-400">${formatPrice(bid.price)}</span>
                      <span className="relative text-white">{formatNumber(bid.size)}</span>
                    </div>
                  ))}
                </div>
              </div>
              {/* Asks */}
              <div>
                <div className="text-xs text-gray-500 mb-2 flex justify-between">
                  <span>Price</span>
                  <span>Size</span>
                </div>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {visibleData.asks.slice(0, 15).map((ask, i) => (
                    <div key={i} className="flex justify-between text-xs relative">
                      <div
                        className="absolute inset-0 bg-red-500/10 rounded"
                        style={{ width: `${(ask.size / (visibleData.asks[0]?.size || 1)) * 100}%` }}
                      />
                      <span className="relative text-red-400">${formatPrice(ask.price)}</span>
                      <span className="relative text-white">{formatNumber(ask.size)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Liquidity Walls */}
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            Liquidity Walls
          </h3>

          {/* Bid Walls */}
          <div className="mb-4">
            <div className="text-xs text-green-400 mb-2 flex items-center gap-1">
              <ArrowUp className="w-3 h-3" />
              Support (Bid Walls)
            </div>
            <div className="space-y-2">
              {orderBookData.bidWalls.length > 0 ? orderBookData.bidWalls.map((wall, i) => (
                <div key={i} className="flex items-center justify-between p-2 bg-green-500/10 rounded">
                  <span className="text-green-400 text-sm">${formatPrice(wall.price)}</span>
                  <span className="text-white text-sm font-medium">{formatNumber(wall.size)} {selectedToken}</span>
                </div>
              )) : (
                <div className="text-gray-500 text-sm">No significant walls</div>
              )}
            </div>
          </div>

          {/* Ask Walls */}
          <div>
            <div className="text-xs text-red-400 mb-2 flex items-center gap-1">
              <ArrowDown className="w-3 h-3" />
              Resistance (Ask Walls)
            </div>
            <div className="space-y-2">
              {orderBookData.askWalls.length > 0 ? orderBookData.askWalls.map((wall, i) => (
                <div key={i} className="flex items-center justify-between p-2 bg-red-500/10 rounded">
                  <span className="text-red-400 text-sm">${formatPrice(wall.price)}</span>
                  <span className="text-white text-sm font-medium">{formatNumber(wall.size)} {selectedToken}</span>
                </div>
              )) : (
                <div className="text-gray-500 text-sm">No significant walls</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DepthChart
